from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TranslationResult:
    original_text: str
    translated_text: str | None


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

    async def translate(self, spanish: str) -> TranslationResult:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                timeout=self._timeout_s,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": spanish},
                ],
            )
            translated = response.choices[0].message.content
            return TranslationResult(
                original_text=spanish,
                translated_text=translated,
            )
        except Exception:
            return TranslationResult(
                original_text=spanish,
                translated_text=None,
            )
