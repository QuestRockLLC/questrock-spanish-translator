from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from audio.types import AudioFrame

if TYPE_CHECKING:
    from torch import Tensor

SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 512
CHUNK_BYTES = CHUNK_SAMPLES * 2
SPEECH_THRESHOLD = 0.5
SILENCE_PEAK = 0.02
SPEECH_PEAK = 0.08


class SpeechScorer(Protocol):
    def score(self, chunk: bytes) -> float: ...


class _SileroProbability(Protocol):
    def item(self) -> float: ...


class _SileroModel(Protocol):
    def __call__(
        self, audio: Tensor, sample_rate: int
    ) -> _SileroProbability: ...


class _SileroLoader(Protocol):
    def __call__(self, *, onnx: bool) -> _SileroModel: ...


class _SileroScorer:
    def __init__(self, model: _SileroModel) -> None:
        self._model = model

    def score(self, chunk: bytes) -> float:
        import numpy as np
        import torch

        samples = np.frombuffer(chunk, dtype="<i2").astype(np.float32)
        audio = torch.from_numpy(samples / 32768.0)
        return float(self._model(audio, SAMPLE_RATE).item())


@dataclass(frozen=True)
class Utterance:
    pcm_s16le: bytes
    t0_ms: int
    t1_ms: int


@dataclass(frozen=True)
class VadPushResult:
    partial: Utterance | None = None
    final: Utterance | None = None
    finals: tuple[Utterance, ...] = ()


class VadSegmenter:
    def __init__(
        self,
        scorer: SpeechScorer,
        silence_ms: int,
        max_utterance_ms: int,
        min_utterance_ms: int = 250,
        partial_interval_ms: int = 700,
        partial_window_ms: int = 2000,
    ) -> None:
        self._scorer = scorer
        self._silence_ms = silence_ms
        self._max_utterance_ms = max_utterance_ms
        self._min_utterance_ms = min_utterance_ms
        self._partial_interval_ms = partial_interval_ms
        self._partial_window_ms = partial_window_ms
        self.reset()

    @classmethod
    def with_silero(
        cls,
        silence_ms: int,
        max_utterance_ms: int,
        min_utterance_ms: int = 250,
        partial_interval_ms: int = 700,
        partial_window_ms: int = 2000,
        *,
        loader: _SileroLoader | None = None,
    ) -> VadSegmenter:
        if loader is None:
            from silero_vad import load_silero_vad

            loader = load_silero_vad

        return cls(
            scorer=_SileroScorer(loader(onnx=True)),
            silence_ms=silence_ms,
            max_utterance_ms=max_utterance_ms,
            min_utterance_ms=min_utterance_ms,
            partial_interval_ms=partial_interval_ms,
            partial_window_ms=partial_window_ms,
        )

    def push(self, frame: AudioFrame) -> VadPushResult:
        self._pending.extend(frame.pcm_s16le)

        partial: Utterance | None = None
        finals: list[Utterance] = []
        while len(self._pending) >= CHUNK_BYTES:
            chunk = bytes(self._pending[:CHUNK_BYTES])
            del self._pending[:CHUNK_BYTES]
            chunk_partial, chunk_final = self._process_chunk(chunk)
            if chunk_partial is not None:
                partial = chunk_partial
            if chunk_final is not None:
                finals.append(chunk_final)

        return VadPushResult(
            partial=partial,
            final=finals[-1] if finals else None,
            finals=tuple(finals),
        )

    def flush(self) -> Utterance | None:
        if self._utterance_start_sample is None:
            return None
        duration_ms = self._samples_to_ms(
            self._processed_samples - self._utterance_start_sample
        )
        return self._finish_utterance(duration_ms)

    def reset(self) -> None:
        self._pending = bytearray()
        self._utterance = bytearray()
        self._processed_samples = 0
        self._utterance_start_sample: int | None = None
        self._silence_samples = 0
        self._last_partial_emit_sample: int | None = None

    def _process_chunk(self, chunk: bytes) -> tuple[Utterance | None, Utterance | None]:
        peak = _chunk_peak(chunk)
        if peak < SILENCE_PEAK:
            is_speech = False
        elif peak >= SPEECH_PEAK:
            is_speech = True
        else:
            is_speech = self._scorer.score(chunk) >= SPEECH_THRESHOLD
        chunk_start_sample = self._processed_samples
        self._processed_samples += CHUNK_SAMPLES

        if is_speech:
            if self._utterance_start_sample is None:
                self._utterance_start_sample = chunk_start_sample
            self._utterance.extend(chunk)
            self._silence_samples = 0
        elif self._utterance_start_sample is not None:
            self._utterance.extend(chunk)
            self._silence_samples += CHUNK_SAMPLES

        if self._utterance_start_sample is None:
            return None, None

        duration_ms = self._samples_to_ms(
            self._processed_samples - self._utterance_start_sample
        )
        silence_ms = self._samples_to_ms(self._silence_samples)
        if duration_ms >= self._max_utterance_ms or silence_ms >= self._silence_ms:
            return None, self._finish_utterance(duration_ms)

        partial = None
        if is_speech:
            partial = self._maybe_partial_snapshot(duration_ms)
        return partial, None

    def _finish_utterance(self, duration_ms: int) -> Utterance | None:
        start_sample = self._utterance_start_sample
        assert start_sample is not None

        utterance = None
        if duration_ms >= self._min_utterance_ms:
            utterance = Utterance(
                pcm_s16le=bytes(self._utterance),
                t0_ms=self._samples_to_ms(start_sample),
                t1_ms=self._samples_to_ms(self._processed_samples),
            )

        self._utterance = bytearray()
        self._utterance_start_sample = None
        self._silence_samples = 0
        self._last_partial_emit_sample = None
        return utterance

    def _maybe_partial_snapshot(self, duration_ms: int) -> Utterance | None:
        if self._partial_interval_ms <= 0:
            return None
        if duration_ms < self._min_utterance_ms:
            return None
        start_sample = self._utterance_start_sample
        assert start_sample is not None
        anchor = self._last_partial_emit_sample or start_sample
        since_last_ms = self._samples_to_ms(self._processed_samples - anchor)
        if since_last_ms < self._partial_interval_ms:
            return None
        self._last_partial_emit_sample = self._processed_samples
        t1_ms = self._samples_to_ms(self._processed_samples)
        pcm = bytes(self._utterance)
        window_bytes = self._partial_window_ms * SAMPLE_RATE * 2 // 1000
        if len(pcm) > window_bytes:
            pcm = pcm[-window_bytes:]
            t0_ms = max(self._samples_to_ms(start_sample), t1_ms - self._partial_window_ms)
        else:
            t0_ms = self._samples_to_ms(start_sample)
        return Utterance(
            pcm_s16le=pcm,
            t0_ms=t0_ms,
            t1_ms=t1_ms,
        )

    @staticmethod
    def _samples_to_ms(samples: int) -> int:
        return samples * 1000 // SAMPLE_RATE


def _chunk_peak(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    import numpy as np

    samples = np.frombuffer(chunk, dtype="<i2").astype(np.float32)
    return float(np.max(np.abs(samples))) / 32768.0
