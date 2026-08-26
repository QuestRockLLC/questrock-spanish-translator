from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Protocol


@dataclass(frozen=True)
class TranscriptText:
    text: str
    confidence: float


class WhisperSegment(Protocol):
    text: str


class WhisperEngine(Protocol):
    def transcribe(
        self, audio: Any, **kwargs: Any
    ) -> tuple[Iterator[WhisperSegment], Any]: ...


def segment_avg_logprob(segment: object) -> float:
    value = getattr(segment, "avg_logprob", None)
    if value is None:
        value = getattr(segment, "avg_log_prob", None)
    if value is None:
        return -1.0
    return float(value)


def confidence_from_avg_log_prob(avg_log_prob: float) -> float:
    return max(0.0, min(1.0, avg_log_prob + 1.0))
