from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Hello:
    protocol_version: int


@dataclass(frozen=True)
class StartCall:
    device_id: str
    language: str


@dataclass(frozen=True)
class StopCall:
    pass


@dataclass(frozen=True)
class SessionStarted:
    call_session_id: str
    device_id: str


@dataclass(frozen=True)
class Status:
    call_session_id: str
    state: str
    detail: str | None = None


@dataclass(frozen=True)
class Transcript:
    call_session_id: str
    id: str
    is_final: bool
    original_language: str
    original_text: str
    translated_text: str | None
    confidence: float
    t0_ms: int
    t1_ms: int


@dataclass(frozen=True)
class ErrorMessage:
    code: str
    message: str


class ProtocolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


ClientMessage = Hello | StartCall | StopCall
ServerMessage = SessionStarted | Status | Transcript | ErrorMessage


def parse_client_message(raw: dict[str, Any]) -> ClientMessage:
    msg_type = raw.get("type")
    if msg_type == "hello":
        if raw.get("protocol_version") != 1:
            raise ProtocolError(code="protocol", message="Unknown message type")
        return Hello(protocol_version=raw["protocol_version"])
    if msg_type == "start_call":
        device_id = raw.get("device_id")
        language = raw.get("language")
        if not device_id or language != "spanish":
            raise ProtocolError(code="protocol", message="Unknown message type")
        return StartCall(device_id=device_id, language=language)
    if msg_type == "stop_call":
        return StopCall()
    raise ProtocolError(code="protocol", message="Unknown message type")


def encode_server_message(msg: ServerMessage) -> dict[str, Any]:
    if isinstance(msg, SessionStarted):
        return {
            "type": "session_started",
            "call_session_id": msg.call_session_id,
            "device_id": msg.device_id,
        }
    if isinstance(msg, Status):
        payload: dict[str, Any] = {
            "type": "status",
            "call_session_id": msg.call_session_id,
            "state": msg.state,
        }
        if msg.detail is not None:
            payload["detail"] = msg.detail
        return payload
    if isinstance(msg, Transcript):
        return {
            "type": "transcript",
            "call_session_id": msg.call_session_id,
            "id": msg.id,
            "is_final": msg.is_final,
            "original_language": msg.original_language,
            "original_text": msg.original_text,
            "translated_text": msg.translated_text,
            "confidence": msg.confidence,
            "t0_ms": msg.t0_ms,
            "t1_ms": msg.t1_ms,
        }
    if isinstance(msg, ErrorMessage):
        return {
            "type": "error",
            "code": msg.code,
            "message": msg.message,
        }
    raise TypeError(f"Unsupported server message: {type(msg)!r}")
