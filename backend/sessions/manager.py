from collections.abc import Callable

from ai.translation.translator import MortgageTranslator
from ai.vad.segmenter import VadSegmenter
from ai.whisper.transcriber import WhisperTranscriber
from audio.factory import AudioCapture
from backend.sessions.call_session import CallSession
from backend.websocket.protocol import ServerMessage


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
