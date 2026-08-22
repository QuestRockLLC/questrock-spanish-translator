from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import Protocol
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from audio.factory import AudioCapture
from backend.websocket.protocol import (
    ErrorMessage,
    Hello,
    ProtocolError,
    ServerMessage,
    SessionStarted,
    StartCall,
    StopCall,
    encode_server_message,
    parse_client_message,
)


class Session(Protocol):
    async def run(self) -> None: ...

    def stop(self) -> None: ...


class SessionFactory(Protocol):
    def __call__(
        self,
        *,
        call_session_id: str,
        device_id: str,
        capture: AudioCapture,
        emit: Callable[[ServerMessage], None],
    ) -> Session: ...


def create_calls_router(
    *,
    capture_provider: Callable[[], AudioCapture],
    session_factory: SessionFactory | None,
) -> APIRouter:
    router = APIRouter()

    @router.websocket("/v1/calls")
    async def calls(websocket: WebSocket) -> None:
        await websocket.accept()
        events: asyncio.Queue[ServerMessage] = asyncio.Queue()
        sender = asyncio.create_task(_send_events(websocket, events))
        hello_received = False
        active_session: Session | None = None
        active_task: asyncio.Task[None] | None = None

        async def stop_active_session() -> None:
            nonlocal active_session, active_task
            if active_session is not None:
                active_session.stop()
            if active_task is not None:
                active_task.cancel()
                with suppress(asyncio.CancelledError):
                    await active_task
            active_session = None
            active_task = None

        try:
            while True:
                raw = await websocket.receive_json()
                try:
                    if not isinstance(raw, dict):
                        raise TypeError
                    message = parse_client_message(raw)
                except (ProtocolError, TypeError):
                    events.put_nowait(
                        ErrorMessage(
                            code="protocol",
                            message="Invalid client message",
                        )
                    )
                    continue

                if isinstance(message, Hello):
                    hello_received = True
                    continue
                if isinstance(message, StopCall):
                    await stop_active_session()
                    continue
                if not hello_received:
                    events.put_nowait(
                        ErrorMessage(
                            code="protocol",
                            message="hello must precede start_call",
                        )
                    )
                    continue
                if isinstance(message, StartCall):
                    await stop_active_session()
                    if session_factory is None:
                        events.put_nowait(
                            ErrorMessage(
                                code="protocol",
                                message="Session service unavailable",
                            )
                        )
                        continue
                    call_session_id = str(uuid4())
                    active_session = session_factory(
                        call_session_id=call_session_id,
                        device_id=message.device_id,
                        capture=capture_provider(),
                        emit=events.put_nowait,
                    )
                    events.put_nowait(
                        SessionStarted(
                            call_session_id=call_session_id,
                            device_id=message.device_id,
                        )
                    )
                    active_task = asyncio.create_task(active_session.run())
        except WebSocketDisconnect:
            pass
        finally:
            await stop_active_session()
            sender.cancel()
            with suppress(asyncio.CancelledError):
                await sender

    return router


async def _send_events(
    websocket: WebSocket,
    events: asyncio.Queue[ServerMessage],
) -> None:
    while True:
        await websocket.send_json(encode_server_message(await events.get()))
