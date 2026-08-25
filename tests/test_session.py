import pytest

from audio.types import AudioFrame, LoopbackDevice
from backend.sessions.call_session import CallSession
from backend.sessions.manager import SessionManager, production_dependencies
from backend.websocket.protocol import ErrorMessage, ServerMessage, Status, Transcript
from tests.fakes import FakeCapture, FakeTranslator, FakeVad, FakeWhisper


def make_frame() -> AudioFrame:
    return AudioFrame(
        pcm_s16le=b"\x00\x10" * 320,
        sample_rate=16_000,
        channels=1,
        duration_ms=20,
    )


@pytest.mark.asyncio
async def test_session_emits_final_transcript_and_stops_capture() -> None:
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()] * 5,
    )
    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=FakeVad(emit_on_nth=3, pcm=b"\x00\x10" * 8000),
        whisper=FakeWhisper(text="Hola", confidence=0.9),
        translator=FakeTranslator(text="Hello"),
        emit=events.append,
    )

    await session.run()

    assert [event.state for event in events if isinstance(event, Status)] == [
        "loading_model",
        "listening",
        "listening",
        "transcribing",
        "translating",
        "idle",
    ]
    transcripts = [event for event in events if isinstance(event, Transcript)]
    assert len(transcripts) == 1
    assert transcripts[0].original_text == "Hola"
    assert transcripts[0].translated_text == "Hello"
    assert transcripts[0].is_final is True
    assert transcripts[0].call_session_id == "abc"
    assert transcripts[0].confidence == 0.9
    assert transcripts[0].t0_ms == 0
    assert transcripts[0].t1_ms == 500
    assert capture.stopped is True


@pytest.mark.asyncio
async def test_translation_failure_still_emits_spanish() -> None:
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()],
    )
    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=FakeVad(emit_on_nth=1, pcm=b"\x00\x10" * 8000),
        whisper=FakeWhisper(text="Hola", confidence=0.8),
        translator=FakeTranslator(text=None),
        emit=events.append,
    )

    await session.run()

    transcript = next(event for event in events if isinstance(event, Transcript))
    assert transcript.original_text == "Hola"
    assert transcript.translated_text is None


@pytest.mark.asyncio
async def test_blank_transcription_is_skipped() -> None:
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()],
    )
    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=FakeVad(emit_on_nth=1, pcm=b"\x00\x10" * 8000),
        whisper=FakeWhisper(text=None),
        translator=FakeTranslator(text="unused"),
        emit=events.append,
    )

    await session.run()

    assert not any(isinstance(event, Transcript) for event in events)
    assert capture.stopped is True


@pytest.mark.asyncio
async def test_capture_start_failure_emits_error() -> None:
    class BrokenCapture(FakeCapture):
        def start(self, device_id: str) -> None:
            raise RuntimeError("AudioTap exited before sending its format header")

    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=BrokenCapture(
            devices=[LoopbackDevice("d1", "Speakers", "loopback")],
            frames=[],
        ),
        vad=FakeVad(emit_on_nth=1, pcm=b""),
        whisper=FakeWhisper(text=None),
        translator=FakeTranslator(text=None),
        emit=events.append,
    )

    await session.run()

    errors = [event for event in events if isinstance(event, ErrorMessage)]
    assert len(errors) == 1
    assert "AudioTap" in errors[0].message


def test_stop_is_idempotent_and_stops_capture() -> None:
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[],
    )
    events: list[object] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=FakeVad(emit_on_nth=1, pcm=b""),
        whisper=FakeWhisper(text=None),
        translator=FakeTranslator(text=None),
        emit=events.append,
    )

    session.stop()
    session.stop()

    assert capture.stopped is True
    idle = [e for e in events if isinstance(e, Status) and e.state == "idle"]
    assert len(idle) == 1
    assert idle[0].call_session_id == "abc"


def test_session_manager_discards_stopped_session() -> None:
    manager = SessionManager()
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[],
    )

    session = manager.create(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=FakeVad(emit_on_nth=1, pcm=b""),
        whisper=FakeWhisper(text=None),
        translator=FakeTranslator(text=None),
        emit=lambda _event: None,
    )

    assert manager.get("abc") is session
    session.stop()
    assert manager.get("abc") is None


@pytest.mark.asyncio
async def test_session_manager_discards_finished_session() -> None:
    manager = SessionManager()
    session = manager.create(
        call_session_id="abc",
        device_id="d1",
        capture=FakeCapture(
            devices=[LoopbackDevice("d1", "Speakers", "loopback")],
            frames=[],
        ),
        vad=FakeVad(emit_on_nth=1, pcm=b""),
        whisper=FakeWhisper(text=None),
        translator=FakeTranslator(text=None),
        emit=lambda _event: None,
    )

    await session.run()

    assert manager.get("abc") is None


def test_production_dependencies_exposes_loader_hooks() -> None:
    deps = production_dependencies()

    assert hasattr(deps, "load_whisper")
    assert hasattr(deps, "load_translator")
    assert hasattr(deps, "load_vad")


def test_run_wires_production_session_factory(monkeypatch) -> None:
    import backend.main as main

    factory = object()
    captured_factories = []
    app = object()

    monkeypatch.setattr(
        main,
        "production_session_factory",
        lambda: factory,
        raising=False,
    )
    monkeypatch.setattr(
        main,
        "create_app",
        lambda capture=None, session_factory=None: (
            captured_factories.append(session_factory) or app
        ),
    )
    monkeypatch.setattr(main, "configure_logging", lambda: None)
    monkeypatch.setattr(main, "Settings", lambda: type("Settings", (), {"port": 8765})())
    monkeypatch.setattr(main.uvicorn, "run", lambda *_args, **_kwargs: None)

    main.run()

    assert captured_factories == [factory]
