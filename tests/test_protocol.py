import pytest
from backend.websocket.protocol import (
    Hello,
    StartCall,
    StopCall,
    SessionStarted,
    Status,
    Transcript,
    ErrorMessage,
    ProtocolError,
    parse_client_message,
    encode_server_message,
)


def test_parse_hello():
    msg = parse_client_message({"type": "hello", "protocol_version": 1})
    assert msg == Hello(protocol_version=1)


def test_hello_rejects_non_v1_protocol_version():
    with pytest.raises(ProtocolError) as exc:
        parse_client_message({"type": "hello", "protocol_version": 2})
    assert exc.value.code == "protocol"


def test_parse_start_call():
    msg = parse_client_message(
        {"type": "start_call", "device_id": "system-audio", "language": "spanish"}
    )
    assert msg == StartCall(device_id="system-audio", language="spanish")


def test_parse_stop_call():
    assert parse_client_message({"type": "stop_call"}) == StopCall()


def test_unknown_type_is_protocol_error():
    with pytest.raises(ProtocolError) as exc:
        parse_client_message({"type": "nope"})
    assert exc.value.code == "protocol"


def test_start_call_rejects_non_spanish_language():
    with pytest.raises(ProtocolError) as exc:
        parse_client_message(
            {"type": "start_call", "device_id": "system-audio", "language": "english"}
        )
    assert exc.value.code == "protocol"


def test_encode_session_started():
    payload = encode_server_message(
        SessionStarted(call_session_id="uuid", device_id="system-audio")
    )
    assert payload == {
        "type": "session_started",
        "call_session_id": "uuid",
        "device_id": "system-audio",
    }


def test_encode_status():
    payload = encode_server_message(
        Status(call_session_id="uuid", state="listening", detail="optional safe string")
    )
    assert payload == {
        "type": "status",
        "call_session_id": "uuid",
        "state": "listening",
        "detail": "optional safe string",
    }


def test_encode_error_message():
    payload = encode_server_message(
        ErrorMessage(code="protocol", message="safe operator message")
    )
    assert payload == {
        "type": "error",
        "code": "protocol",
        "message": "safe operator message",
    }


def test_encode_transcript_is_final_true():
    payload = encode_server_message(
        Transcript(
            call_session_id="s1",
            id="t1",
            is_final=True,
            original_language="es",
            original_text="hola",
            translated_text="hello",
            confidence=0.9,
            t0_ms=0,
            t1_ms=800,
        )
    )
    assert payload["type"] == "transcript"
    assert payload["is_final"] is True
    assert payload["original_text"] == "hola"


def test_encode_transcript_translated_text_null():
    payload = encode_server_message(
        Transcript(
            call_session_id="s1",
            id="t1",
            is_final=True,
            original_language="es",
            original_text="hola",
            translated_text=None,
            confidence=0.9,
            t0_ms=0,
            t1_ms=800,
        )
    )
    assert payload["translated_text"] is None
