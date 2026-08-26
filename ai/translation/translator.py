from dataclasses import dataclass
from typing import Any

from ai.caption.quality import translation_too_expansive


@dataclass(frozen=True)
class TranslationResult:
    original_text: str
    translated_text: str | None


_REFUSAL_MARKERS = (
    "i'm sorry",
    "i am sorry",
    "i couldn't understand",
    "i could not understand",
    "could you please provide",
    "could you please clarify",
    "please provide more context",
    "please clarify",
    "i don't understand",
    "i do not understand",
    "appears incomplete or unclear",
    "provided text appears incomplete",
)


def looks_like_refusal(text: str) -> bool:
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return True
    return any(marker in normalized for marker in _REFUSAL_MARKERS)


class MortgageTranslator:
    def __init__(
        self,
        client: Any,
        model: str,
        system_prompt: str,
        timeout_s: float = 8,
    ) -> None:
        self._client = client
        self._model = model
        self._system_prompt = system_prompt
        self._timeout_s = timeout_s

    async def translate(
        self,
        spanish: str,
        *,
        retries: int = 1,
        max_tokens: int | None = None,
    ) -> TranslationResult:
        last_error: Exception | None = None
        attempts = max(1, retries + 1)
        for _ in range(attempts):
            try:
                request: dict[str, Any] = {
                    "model": self._model,
                    "temperature": 0,
                    "timeout": self._timeout_s,
                    "messages": [
                        {"role": "system", "content": self._system_prompt},
                        {"role": "user", "content": spanish},
                    ],
                }
                if max_tokens is not None:
                    request["max_tokens"] = max_tokens
                response = await self._client.chat.completions.create(**request)
                translated = response.choices[0].message.content
                if translated:
                    cleaned = translated.strip()
                    if (
                        cleaned
                        and not looks_like_refusal(cleaned)
                        and not translation_too_expansive(spanish, cleaned)
                    ):
                        return TranslationResult(
                            original_text=spanish,
                            translated_text=cleaned,
                        )
            except Exception as exc:
                last_error = exc
        del last_error
        return TranslationResult(
            original_text=spanish,
            translated_text=None,
        )
