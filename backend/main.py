import uvicorn
from fastapi import FastAPI

from backend.api.health import router as health_router
from backend.logging import configure_logging
from backend.settings import Settings


def create_app(
    capture: object | None = None,
    session_factory: object | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    return app


def run() -> None:
    configure_logging()
    settings = Settings()
    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=settings.port,
        log_config=None,
    )
