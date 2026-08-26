from __future__ import annotations

import re


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def should_emit_transcription(
    text: str,
    confidence: float,
    duration_ms: int,
    *,
    partial: bool,
) -> bool:
    stripped = text.strip()
    words = word_count(stripped)
    if not stripped:
        return False
    if len(stripped) < 5:
        return False
    if words < 2:
        return False
    if words < 3 and len(stripped) < 8:
        return False
    if partial and duration_ms < 450:
        return False
    if partial and words < 2:
        return False
    if confidence < 0.12 and words < 5:
        return False
    return True


def should_translate(
    text: str,
    confidence: float,
    *,
    partial: bool,
) -> bool:
    stripped = text.strip()
    words = word_count(stripped)
    if len(stripped) < 5 or words < 2:
        return False
    if words < 3 and len(stripped) < 8:
        return False
    if partial and words < 2:
        return False
    if partial and confidence < 0.12:
        return False
    return True


def translation_too_expansive(spanish: str, english: str) -> bool:
    spanish_words = word_count(spanish)
    english_words = word_count(english)
    if spanish_words == 0 or english_words == 0:
        return True
    if spanish_words <= 3 and english_words > spanish_words * 2:
        return True
    if spanish_words <= 6 and english_words > spanish_words * 2:
        return True
    if english_words > spanish_words * 3:
        return True
    return False
