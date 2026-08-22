from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol

from audio.resample import TARGET_SAMPLE_RATE, to_16k_mono_s16le
from audio.types import AudioFrame, LoopbackDevice

FRAME_DURATION_MS = 20
_PA_INT16 = 8


class PyAudioStream(Protocol):
    def read(self, num_frames: int, exception_on_overflow: bool = False) -> bytes: ...

    def stop_stream(self) -> None: ...

    def close(self) -> None: ...


class PyAudioLike(Protocol):
    def get_loopback_device_info_generator(self) -> Iterator[dict[str, Any]]: ...

    def open(self, **kwargs: Any) -> PyAudioStream: ...

    def terminate(self) -> None: ...


PaFactory = Callable[[], PyAudioLike]


def _default_pa_factory() -> PyAudioLike:
    import pyaudiowpatch as pyaudio

    return pyaudio.PyAudio()


class WindowsWasapiLoopbackCapture:
    def __init__(self, pa_factory: PaFactory | None = None) -> None:
        self._pa_factory = pa_factory or _default_pa_factory
        self._pa: PyAudioLike | None = None
        self._stream: PyAudioStream | None = None
        self._sample_rate = 0
        self._channels = 0

    def list_devices(self) -> list[LoopbackDevice]:
        pa = self._pa_factory()
        try:
            return [
                LoopbackDevice(
                    id=str(info["index"]),
                    name=str(info["name"]),
                    kind="loopback",
                )
                for info in pa.get_loopback_device_info_generator()
            ]
        finally:
            pa.terminate()

    def start(self, device_id: str) -> None:
        pa = self._pa_factory()
        device = _find_loopback_device(pa, device_id)
        if device is None:
            pa.terminate()
            raise KeyError(device_id)

        self._sample_rate = int(device["defaultSampleRate"])
        self._channels = int(device["maxInputChannels"])
        self._pa = pa
        self._stream = pa.open(
            format=_PA_INT16,
            channels=self._channels,
            rate=self._sample_rate,
            input=True,
            input_device_index=int(device["index"]),
        )

    def frames(self) -> Iterator[AudioFrame]:
        if self._stream is None:
            raise RuntimeError("capture has not started")

        frames_per_read = self._sample_rate * FRAME_DURATION_MS // 1000
        bytes_per_read = frames_per_read * self._channels * 2
        while pcm := self._stream.read(frames_per_read, exception_on_overflow=False):
            if len(pcm) < bytes_per_read:
                break
            yield AudioFrame(
                pcm_s16le=to_16k_mono_s16le(pcm, self._sample_rate, self._channels),
                sample_rate=TARGET_SAMPLE_RATE,
                channels=1,
                duration_ms=FRAME_DURATION_MS,
            )

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None


def _find_loopback_device(pa: PyAudioLike, device_id: str) -> dict[str, Any] | None:
    for info in pa.get_loopback_device_info_generator():
        if str(info["index"]) == device_id:
            return info
    return None
