from __future__ import annotations

import asyncio
from collections.abc import Callable

from fastapi.testclient import TestClient

from audio.factory import AudioCapture
from audio.types import LoopbackDevice
from backend.main import create_app
from backend.websocket.protocol import ServerMessage, Status
from tests.fakes import FakeCapture


class FakeSession:
    def __init__(
        self,
        *,
        call_session_id: str,
        emit: Callable[[ServerMessage], None],
    ) -> None:
        self.call_session_id = call_session_id
        self._emit = emit
        self.started = asyncio.Event()
        self.stopped = False

    async def run(self) -> None:
        self.started.set()
        self._emit(Status(call_session_id=self.call_session_id, state="listening"))
        while not self.stopped:
            await asyncio.sleep(0)

    def stop(self) -> None:
        self.stopped = True


class RecordingSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(
        self,
        *,
        call_session_id: str,
        device_id: str,
        capture: AudioCapture,
        emit: Callable[[ServerMessage], None],
    ) -> FakeSession:
        session = FakeSession(call_session_id=call_session_id, emit=emit)
        self.sessions.append(session)
        return session


def make_capture() -> FakeCapture:
    return FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[],
    )


def test_list_devices() -> None:
    client = TestClient(create_app(capture=make_capture()))

    response = client.get("/v1/devices")

    assert response.status_code == 200
    assert response.json() == {
        "devices": [{"id": "d1", "name": "Speakers", "kind": "loopback"}]
    }


def test_start_call_before_hello_returns_safe_protocol_error() -> None:
    borrower_speech = "mi número de seguro social"
    client = TestClient(create_app(capture=make_capture()))

    with client.websocket_connect("/v1/calls") as websocket:
        websocket.send_json(
            {
                "type": "start_call",
                "device_id": "d1",
                "language": "spanish",
                "borrower_text": borrower_speech,
            }
        )
        message = websocket.receive_json()

    assert message["type"] == "error"
    assert message["code"] == "protocol"
    assert borrower_speech not in message["message"]


def test_hello_start_stop_happy_path() -> None:
    factory = RecordingSessionFactory()
    client = TestClient(
        create_app(capture=make_capture(), session_factory=factory)
    )

    with client.websocket_connect("/v1/calls") as websocket:
        websocket.send_json({"type": "hello", "protocol_version": 1})
        websocket.send_json(
            {"type": "start_call", "device_id": "d1", "language": "spanish"}
        )
        started = websocket.receive_json()
        status = websocket.receive_json()
        websocket.send_json({"type": "stop_call"})

    assert started["type"] == "session_started"
    assert started["device_id"] == "d1"
    assert status == {
        "type": "status",
        "call_session_id": started["call_session_id"],
        "state": "listening",
    }
    assert factory.sessions[0].stopped is True


def test_second_start_stops_previous_session() -> None:
    factory = RecordingSessionFactory()
    client = TestClient(
        create_app(capture=make_capture(), session_factory=factory)
    )

    with client.websocket_connect("/v1/calls") as websocket:
        websocket.send_json({"type": "hello", "protocol_version": 1})
        websocket.send_json(
            {"type": "start_call", "device_id": "d1", "language": "spanish"}
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {"type": "start_call", "device_id": "d1", "language": "spanish"}
        )
        websocket.receive_json()
        websocket.receive_json()

        assert factory.sessions[0].stopped is True


def test_socket_close_stops_active_session() -> None:
    factory = RecordingSessionFactory()
    client = TestClient(
        create_app(capture=make_capture(), session_factory=factory)
    )

    with client.websocket_connect("/v1/calls") as websocket:
        websocket.send_json({"type": "hello", "protocol_version": 1})
        websocket.send_json(
            {"type": "start_call", "device_id": "d1", "language": "spanish"}
        )
        websocket.receive_json()
        websocket.receive_json()

    assert factory.sessions[0].stopped is True


class BoomSession:
    def __init__(self, *, emit: Callable[[ServerMessage], None]) -> None:
        self._emit = emit
        self.stopped = False

    async def run(self) -> None:
        raise RuntimeError("AudioTap exited before sending its format header")

    def stop(self) -> None:
        self.stopped = True


def test_session_run_failure_is_sent_to_client() -> None:
    def factory(
        *,
        call_session_id: str,
        device_id: str,
        capture: AudioCapture,
        emit: Callable[[ServerMessage], None],
    ) -> BoomSession:
        del call_session_id, device_id, capture
        return BoomSession(emit=emit)

    client = TestClient(create_app(capture=make_capture(), session_factory=factory))

    with client.websocket_connect("/v1/calls") as websocket:
        websocket.send_json({"type": "hello", "protocol_version": 1})
        websocket.send_json(
            {"type": "start_call", "device_id": "d1", "language": "spanish"}
        )
        started = websocket.receive_json()
        error = websocket.receive_json()

    assert started["type"] == "session_started"
    assert error["type"] == "error"
    assert "AudioTap" in error["message"]


def test_unknown_message_returns_safe_protocol_error() -> None:
    borrower_speech = "gano cinco mil dólares"
    client = TestClient(create_app(capture=make_capture()))

    with client.websocket_connect("/v1/calls") as websocket:
        websocket.send_json(
            {"type": "borrower_speech", "text": borrower_speech}
        )
        message = websocket.receive_json()

    assert message["type"] == "error"
    assert message["code"] == "protocol"
    assert borrower_speech not in message["message"]
