"""Shared test fakes for later tasks."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from ai.translation.translator import TranslationResult
from ai.vad.segmenter import Utterance, VadPushResult
from ai.whisper.transcriber import TranscriptText
from audio.types import AudioFrame, LoopbackDevice


class FakeCapture:
    def __init__(
        self,
        *,
        devices: Sequence[LoopbackDevice],
        frames: Sequence[AudioFrame],
    ) -> None:
        self._devices = list(devices)
        self._frames = list(frames)
        self._started_device_id: str | None = None
        self.stopped = False
        self.frames_yielded = 0

    def list_devices(self) -> list[LoopbackDevice]:
        return list(self._devices)

    def start(self, device_id: str) -> None:
        if not any(device.id == device_id for device in self._devices):
            raise KeyError(device_id)
        self._started_device_id = device_id
        self.stopped = False

    def frames(self) -> Iterator[AudioFrame]:
        if self._started_device_id is None:
            return iter(())
        def generate() -> Iterator[AudioFrame]:
            for frame in self._frames:
                self.frames_yielded += 1
                yield frame
        return generate()

    def stop(self) -> None:
        self.stopped = True
        self._started_device_id = None


class FakeVad:
    def __init__(self, *, emit_on_nth: int, pcm: bytes) -> None:
        self._emit_on_nth = emit_on_nth
        self._pcm = pcm
        self._pushes = 0

    def push(self, frame: AudioFrame) -> VadPushResult:
        self._pushes += 1
        if self._pushes != self._emit_on_nth:
            return VadPushResult()
        duration_ms = (len(self._pcm) // 2) * 1000 // frame.sample_rate
        return VadPushResult(
            final=Utterance(pcm_s16le=self._pcm, t0_ms=0, t1_ms=duration_ms),
        )

    def flush(self) -> Utterance | None:
        return None


class FakeWhisper:
    def __init__(self, *, text: str | None, confidence: float = 0.0) -> None:
        self._text = text
        self._confidence = confidence

    def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText | None:
        del partial
        if self._text is None:
            return None
        return TranscriptText(text=self._text, confidence=self._confidence)


class FakeTranslator:
    def __init__(self, *, text: str | None) -> None:
        self._text = text

    async def translate(
        self,
        spanish: str,
        *,
        retries: int = 1,
        max_tokens: int | None = None,
    ) -> TranslationResult:
        del retries, max_tokens
        return TranslationResult(
            original_text=spanish,
            translated_text=self._text,
        )
