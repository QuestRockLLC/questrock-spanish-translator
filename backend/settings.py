from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.paths import resource_root


def _env_file() -> str | None:
    candidate = resource_root() / ".env"
    if candidate.is_file():
        return str(candidate)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file(), extra="ignore")

    openai_api_key: str = ""
    openai_translation_model: str = "gpt-4.1-mini"
    whisper_model: str = "small"
    vad_silence_ms: int = 800
    vad_max_utterance_ms: int = 8000
    host: str = "127.0.0.1"
    port: int = 8765
