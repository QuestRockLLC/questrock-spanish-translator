import logging

import uvicorn
from fastapi import FastAPI

from audio.factory import AudioCapture, capture_for_platform
from backend.api.devices import create_devices_router
from backend.api.health import router as health_router
from backend.logging import configure_logging
from backend.sessions.manager import production_session_factory
from backend.settings import Settings
from backend.websocket.handler import SessionFactory, create_calls_router


def create_app(
    capture: AudioCapture | None = None,
    session_factory: SessionFactory | None = None,
) -> FastAPI:
    def capture_provider() -> AudioCapture:
        if capture is not None:
            return capture
        return capture_for_platform()

    app = FastAPI()
    app.include_router(health_router)
    app.include_router(create_devices_router(capture_provider))
    app.include_router(
        create_calls_router(
            capture_provider=capture_provider,
            session_factory=session_factory,
        )
    )
    return app


def run() -> None:
    import argparse

    configure_logging()
    settings = Settings()
    modal_url = getattr(settings, "questrock_modal_url", "") or ""
    if str(modal_url).strip():
        logging.getLogger("questrock").info(
            "inference backend=modal url=%s",
            str(modal_url).strip(),
        )
    else:
        logging.getLogger("questrock").info("inference backend=local")
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=settings.port)
    args, _unknown = parser.parse_known_args()
    uvicorn.run(
        create_app(session_factory=production_session_factory()),
        host="127.0.0.1",
        port=args.port,
        log_config=None,
    )
