from dataclasses import dataclass
from typing import Protocol

from audio.types import AudioFrame

SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 512
CHUNK_BYTES = CHUNK_SAMPLES * 2
SPEECH_THRESHOLD = 0.5


class SpeechScorer(Protocol):
    def score(self, chunk: bytes) -> float: ...


@dataclass(frozen=True)
class Utterance:
    pcm_s16le: bytes
    t0_ms: int
    t1_ms: int


class VadSegmenter:
    def __init__(
        self,
        scorer: SpeechScorer,
        silence_ms: int,
        max_utterance_ms: int,
        min_utterance_ms: int = 250,
    ) -> None:
        self._scorer = scorer
        self._silence_ms = silence_ms
        self._max_utterance_ms = max_utterance_ms
        self._min_utterance_ms = min_utterance_ms
        self.reset()

    def push(self, frame: AudioFrame) -> Utterance | None:
        self._pending.extend(frame.pcm_s16le)

        while len(self._pending) >= CHUNK_BYTES:
            chunk = bytes(self._pending[:CHUNK_BYTES])
            del self._pending[:CHUNK_BYTES]
            utterance = self._process_chunk(chunk)
            if utterance is not None:
                return utterance

        return None

    def reset(self) -> None:
        self._pending = bytearray()
        self._utterance = bytearray()
        self._processed_samples = 0
        self._utterance_start_sample: int | None = None
        self._silence_samples = 0

    def _process_chunk(self, chunk: bytes) -> Utterance | None:
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
            return None

        duration_ms = self._samples_to_ms(
            self._processed_samples - self._utterance_start_sample
        )
        silence_ms = self._samples_to_ms(self._silence_samples)
        if duration_ms >= self._max_utterance_ms or silence_ms >= self._silence_ms:
            return self._finish_utterance(duration_ms)

        return None

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
        return utterance

    @staticmethod
    def _samples_to_ms(samples: int) -> int:
        return samples * 1000 // SAMPLE_RATE
