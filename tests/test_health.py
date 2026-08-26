import pytest
from fastapi.testclient import TestClient

from backend.main import create_app, run


def test_health_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["inference"] in {"modal", "local"}


def test_run_preserves_json_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, object]] = []

    def fake_configure_logging() -> None:
        events.append(("configure_logging", None))

    def fake_uvicorn_run(app: object, **kwargs: object) -> None:
        events.append(("uvicorn_run", kwargs))

    monkeypatch.setattr("backend.main.configure_logging", fake_configure_logging)
    monkeypatch.setattr("backend.main.uvicorn.run", fake_uvicorn_run)

    run()

    assert events == [
        ("configure_logging", None),
        (
            "uvicorn_run",
            {"host": "127.0.0.1", "port": 8765, "log_config": None},
        ),
    ]
