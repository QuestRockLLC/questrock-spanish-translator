from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ai.translation.glossary import load_glossary
from ai.translation.prompt import build_system_prompt
from ai.translation.translator import MortgageTranslator
from ai.vad.segmenter import VadSegmenter
from ai.whisper.transcriber import WhisperTranscriber
from audio.factory import AudioCapture
from backend.settings import Settings
from backend.sessions.call_session import CallSession
from backend.websocket.protocol import ServerMessage


@dataclass(frozen=True)
class SessionDependencies:
    load_whisper: Callable[[], WhisperTranscriber]
    load_translator: Callable[[], MortgageTranslator]
    load_vad: Callable[[], VadSegmenter]


def production_dependencies(
    settings: Settings | None = None,
) -> SessionDependencies:
    settings = settings or Settings()

    def load_whisper() -> WhisperTranscriber:
        return WhisperTranscriber.load(settings.whisper_model)

    def load_translator() -> MortgageTranslator:
        from openai import AsyncOpenAI

        glossary = load_glossary(Path("config/mortgage_glossary.json"))
        client = (
            AsyncOpenAI(api_key=settings.openai_api_key)
            if settings.openai_api_key
            else None
        )
        return MortgageTranslator(
            client=client,
            model=settings.openai_translation_model,
            system_prompt=build_system_prompt(glossary),
        )

    def load_vad() -> VadSegmenter:
        return VadSegmenter.with_silero(
            silence_ms=settings.vad_silence_ms,
            max_utterance_ms=settings.vad_max_utterance_ms,
        )

    return SessionDependencies(
        load_whisper=load_whisper,
        load_translator=load_translator,
        load_vad=load_vad,
    )


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, CallSession] = {}

    def create(
        self,
        *,
        call_session_id: str,
        device_id: str,
        capture: AudioCapture,
        vad: VadSegmenter,
        whisper: WhisperTranscriber,
        translator: MortgageTranslator,
        emit: Callable[[ServerMessage], None],
    ) -> CallSession:
        session = CallSession(
            call_session_id=call_session_id,
            device_id=device_id,
            capture=capture,
            vad=vad,
            whisper=whisper,
            translator=translator,
            emit=emit,
        )
        self._sessions[call_session_id] = session
        return session

    def get(self, call_session_id: str) -> CallSession | None:
        return self._sessions.get(call_session_id)

    def discard(self, call_session_id: str) -> None:
        self._sessions.pop(call_session_id, None)


def production_session_factory() -> Callable[..., CallSession]:
    dependencies = production_dependencies()
    manager = SessionManager()

    def create_session(
        *,
        call_session_id: str,
        device_id: str,
        capture: AudioCapture,
        emit: Callable[[ServerMessage], None],
    ) -> CallSession:
        return manager.create(
            call_session_id=call_session_id,
            device_id=device_id,
            capture=capture,
            vad=dependencies.load_vad(),
            whisper=dependencies.load_whisper(),
            translator=dependencies.load_translator(),
            emit=emit,
        )

    return create_session
