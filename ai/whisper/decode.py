from __future__ import annotations

import numpy as np

from ai.whisper.types import (
    TranscriptText,
    WhisperEngine,
    confidence_from_avg_log_prob,
    segment_avg_logprob,
)


def transcribe_pcm(engine: WhisperEngine, pcm_s16le: bytes) -> TranscriptText | None:
    samples = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32)
    audio = samples / 32768.0

    segments, info = engine.transcribe(
        audio,
        language="es",
        task="transcribe",
        vad_filter=False,
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
        without_timestamps=True,
        compression_ratio_threshold=2.2,
        log_prob_threshold=-0.9,
        no_speech_threshold=0.55,
    )

    no_speech_prob = float(getattr(info, "no_speech_prob", 0.0) or 0.0)
    if no_speech_prob > 0.55:
        return None

    texts: list[str] = []
    log_probs: list[float] = []
    for segment in segments:
        texts.append(segment.text)
        log_probs.append(segment_avg_logprob(segment))

    text = "".join(texts).strip()
    if not text:
        return None

    avg_log_prob = sum(log_probs) / len(log_probs)
    confidence = confidence_from_avg_log_prob(avg_log_prob)
    return TranscriptText(text=text, confidence=confidence)
