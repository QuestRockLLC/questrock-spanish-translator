from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from ai.translation.translator import TranslationResult
from ai.whisper.types import TranscriptText


@dataclass(frozen=True)
class CaptionResult:
    text: str
    translated_text: str | None
    confidence: float


@dataclass(frozen=True)
class ModalInferenceConfig:
    base_url: str
    token: str = ""
    timeout_s: float = 25.0
    warmup_timeout_s: float = 90.0
    sync_transport: httpx.BaseTransport | None = None
    async_transport: httpx.BaseTransport | None = None


def _headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


class ModalInferenceClient:
    def __init__(self, config: ModalInferenceConfig) -> None:
        self._config = config
        self._base_url = _normalize_base_url(config.base_url)

    @classmethod
    def from_settings(cls, *, base_url: str, token: str) -> ModalInferenceClient:
        return cls(
            ModalInferenceConfig(
                base_url=base_url,
                token=token,
            )
        )

    def _sync_client(self, timeout_s: float) -> httpx.Client:
        client_kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(timeout_s, connect=10.0),
        }
        if self._config.sync_transport is not None:
            client_kwargs["transport"] = self._config.sync_transport
        return httpx.Client(**client_kwargs)

    def warmup(self) -> None:
        with self._sync_client(self._config.warmup_timeout_s) as client:
            try:
                response = client.get(
                    f"{self._base_url}/health",
                    headers=_headers(self._config.token),
                )
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    f"Modal warmup timed out after {self._config.warmup_timeout_s:.0f}s"
                ) from exc

    def caption(self, pcm_s16le: bytes) -> CaptionResult | None:
        payload = {"pcm_b64": base64.b64encode(pcm_s16le).decode("ascii")}
        with self._sync_client(self._config.timeout_s) as client:
            try:
                response = client.post(
                    f"{self._base_url}/v1/caption",
                    json=payload,
                    headers=_headers(self._config.token),
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    f"Modal caption timed out after {self._config.timeout_s:.0f}s"
                ) from exc
            if response.status_code == 204:
                return None
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Modal caption failed ({exc.response.status_code}): "
                    f"{exc.response.text[:300]}"
                ) from exc
            if not response.content:
                return None
            data = response.json()
            if not data or not isinstance(data, dict):
                return None
            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                return None
            translated = data.get("translated_text")
            return CaptionResult(
                text=text.strip(),
                translated_text=translated.strip() if isinstance(translated, str) else None,
                confidence=float(data.get("confidence") or 0.0),
            )

    def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText | None:
        payload = {
            "pcm_b64": base64.b64encode(pcm_s16le).decode("ascii"),
            "partial": partial,
        }
        with self._sync_client(self._config.timeout_s) as client:
            try:
                response = client.post(
                    f"{self._base_url}/v1/transcribe",
                    json=payload,
                    headers=_headers(self._config.token),
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    f"Modal transcribe timed out after {self._config.timeout_s:.0f}s"
                ) from exc
            if response.status_code == 204:
                return None
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Modal transcribe failed ({exc.response.status_code}): "
                    f"{exc.response.text[:300]}"
                ) from exc
            if not response.content:
                return None
            data = response.json()
            if not data or not isinstance(data, dict):
                return None
            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                return None
            return TranscriptText(
                text=text.strip(),
                confidence=float(data.get("confidence") or 0.0),
            )

    async def translate(
        self,
        spanish: str,
        *,
        retries: int = 1,
        max_tokens: int | None = None,
    ) -> TranslationResult:
        payload: dict[str, Any] = {
            "spanish": spanish,
            "retries": retries,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        client_kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(self._config.timeout_s, connect=10.0),
        }
        if self._config.async_transport is not None:
            client_kwargs["transport"] = self._config.async_transport
        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/v1/translate",
                    json=payload,
                    headers=_headers(self._config.token),
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    f"Modal translate timed out after {self._config.timeout_s:.0f}s"
                ) from exc
            response.raise_for_status()
            data = response.json()
            return TranslationResult(
                original_text=str(data["original_text"]),
                translated_text=data.get("translated_text"),
            )


class RemoteWhisperTranscriber:
    def __init__(self, client: ModalInferenceClient, model_name: str) -> None:
        self._client = client
        self._model_name = model_name

    @classmethod
    def load(
        cls,
        model_name: str,
        *,
        base_url: str,
        token: str,
    ) -> RemoteWhisperTranscriber:
        return cls(
            ModalInferenceClient.from_settings(base_url=base_url, token=token),
            model_name,
        )

    def warmup(self) -> None:
        self._client.warmup()

    def caption(self, pcm_s16le: bytes) -> CaptionResult | None:
        return self._client.caption(pcm_s16le)

    def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText | None:
        del self._model_name
        return self._client.transcribe(pcm_s16le, partial=partial)


class RemoteMortgageTranslator:
    def __init__(self, client: ModalInferenceClient) -> None:
        self._client = client

    @classmethod
    def load(cls, *, base_url: str, token: str) -> RemoteMortgageTranslator:
        return cls(ModalInferenceClient.from_settings(base_url=base_url, token=token))

    async def translate(
        self,
        spanish: str,
        *,
        retries: int = 1,
        max_tokens: int | None = None,
    ) -> TranslationResult:
        return await self._client.translate(
            spanish,
            retries=retries,
            max_tokens=max_tokens,
        )
