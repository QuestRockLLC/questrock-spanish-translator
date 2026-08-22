from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from audio.factory import capture_for_platform
from audio.types import AudioFrame, LoopbackDevice
from audio.windows import WindowsWasapiLoopbackCapture


class FakeStream:
    def read(self, n: int, exception_on_overflow: bool = False) -> bytes:
        del exception_on_overflow
        return b"\x00\x00" * n * 2

    def stop_stream(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakePyAudio:
    def get_loopback_device_info_generator(self) -> Iterator[dict[str, Any]]:
        yield {
            "index": 7,
            "name": "Speakers (loopback)",
            "defaultSampleRate": 48000,
            "maxInputChannels": 2,
        }

    def open(self, **kwargs: Any) -> FakeStream:
        del kwargs
        return FakeStream()

    def terminate(self) -> None:
        pass


def test_lists_loopback_devices() -> None:
    cap = WindowsWasapiLoopbackCapture(pa_factory=lambda: FakePyAudio())
    devices = cap.list_devices()
    assert devices == [LoopbackDevice(id="7", name="Speakers (loopback)", kind="loopback")]


def test_start_unknown_device_raises_key_error() -> None:
    cap = WindowsWasapiLoopbackCapture(pa_factory=lambda: FakePyAudio())
    with pytest.raises(KeyError, match="missing"):
        cap.start("missing")


def test_emits_16k_mono_frames() -> None:
    cap = WindowsWasapiLoopbackCapture(pa_factory=lambda: FakePyAudio())
    cap.start("7")
    frame = next(cap.frames())
    assert frame == AudioFrame(
        pcm_s16le=b"\x00\x00" * 320,
        sample_rate=16_000,
        channels=1,
        duration_ms=20,
    )
    cap.stop()


def test_factory_returns_windows_capture_on_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("audio.factory.sys.platform", "win32")

    assert isinstance(capture_for_platform(), WindowsWasapiLoopbackCapture)
