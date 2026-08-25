from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Protocol

import numpy as np

SAMPLE_RATE = 16_000

_model_cache: dict[str, Any] = {}


class WhisperSegment(Protocol):
    text: str


class WhisperEngine(Protocol):
    def transcribe(
        self, audio: np.ndarray, **kwargs: Any
    ) -> tuple[Iterator[WhisperSegment], Any]: ...


@dataclass(frozen=True)
class TranscriptText:
    text: str
    confidence: float


def _segment_avg_logprob(segment: object) -> float:
    value = getattr(segment, "avg_logprob", None)
    if value is None:
        value = getattr(segment, "avg_log_prob", None)
    if value is None:
        return -1.0
    return float(value)


def _confidence_from_avg_log_prob(avg_log_prob: float) -> float:
    return max(0.0, min(1.0, avg_log_prob + 1.0))


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


class WhisperTranscriber:
    def __init__(self, engine: WhisperEngine, model_name: str) -> None:
        self._engine = engine
        self._model_name = model_name

    @classmethod
    def load(cls, model_name: str) -> WhisperTranscriber:
        if model_name not in _model_cache:
            from faster_whisper import WhisperModel

            cuda = _cuda_available()
            device = "cuda" if cuda else "cpu"
            compute_type = "float16" if cuda else "int8"
            _model_cache[model_name] = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )
        return cls(engine=_model_cache[model_name], model_name=model_name)

    def transcribe(self, pcm_s16le: bytes) -> TranscriptText | None:
        samples = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32)
        audio = samples / 32768.0

        segments, _info = self._engine.transcribe(
            audio,
            language="es",
            vad_filter=False,
            beam_size=1,
            best_of=1,
        )

        texts: list[str] = []
        log_probs: list[float] = []
        for segment in segments:
            texts.append(segment.text)
            log_probs.append(_segment_avg_logprob(segment))

        text = "".join(texts).strip()
        if not text:
            return None

        avg_log_prob = sum(log_probs) / len(log_probs)
        confidence = _confidence_from_avg_log_prob(avg_log_prob)
        return TranscriptText(text=text, confidence=confidence)
