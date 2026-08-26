from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.paths import resource_root


def _env_file() -> str | None:
    frozen = resource_root() / ".env"
    if frozen.is_file():
        return str(frozen)
    repo_env = Path(__file__).resolve().parent.parent / ".env"
    if repo_env.is_file():
        return str(repo_env)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file(), extra="ignore")

    openai_api_key: str = ""
    openai_translation_model: str = "gpt-4.1-mini"
    whisper_model: str = "small"
    vad_silence_ms: int = 650
    vad_max_utterance_ms: int = 8000
    vad_partial_interval_ms: int = 700
    vad_partial_window_ms: int = 2000
    questrock_modal_url: str = ""
    questrock_modal_token: str = ""
    host: str = "127.0.0.1"
    port: int = 8765
