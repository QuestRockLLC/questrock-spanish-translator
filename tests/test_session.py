import asyncio

import pytest

from audio.types import AudioFrame, LoopbackDevice
from backend.sessions.call_session import CallSession
from backend.sessions.manager import SessionManager, production_dependencies
from ai.vad.segmenter import Utterance, VadPushResult
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
        vad=FakeVad(emit_on_nth=3, pcm=b"\x00\x10" * 20000),
        whisper=FakeWhisper(text="Hola mundo", confidence=0.9),
        translator=FakeTranslator(text="Hello world"),
        emit=events.append,
    )

    await session.run()

    assert "transcribing" in [event.state for event in events if isinstance(event, Status)]
    assert "translating" in [event.state for event in events if isinstance(event, Status)]
    transcripts = [event for event in events if isinstance(event, Transcript)]
    assert len(transcripts) == 1
    assert transcripts[0].original_text == "Hola mundo"
    assert transcripts[0].translated_text == "Hello world"
    assert transcripts[0].is_final is True
    assert transcripts[0].call_session_id == "abc"
    assert transcripts[0].confidence == 0.9
    assert transcripts[0].t0_ms == 0
    assert transcripts[0].t1_ms == 1250
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
        vad=FakeVad(emit_on_nth=1, pcm=b"\x00\x10" * 20000),
        whisper=FakeWhisper(text="Hola mundo", confidence=0.8),
        translator=FakeTranslator(text=None),
        emit=events.append,
    )

    await session.run()

    transcript = next(event for event in events if isinstance(event, Transcript))
    assert transcript.original_text == "Hola mundo"
    assert transcript.translated_text == "Hola mundo"


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
        vad=FakeVad(emit_on_nth=1, pcm=b"\x00\x10" * 20000),
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


@pytest.mark.asyncio
async def test_capture_keeps_reading_while_transcription_runs() -> None:
    import time

    from ai.whisper.transcriber import TranscriptText

    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()] * 12,
    )

    class StallDetector:
        def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText:
            del pcm_s16le, partial
            deadline = time.time() + 2
            while capture.frames_yielded < 10:
                if time.time() > deadline:
                    raise TimeoutError("capture stalled during transcribe")
                time.sleep(0.01)
            return TranscriptText(text="Hola mundo", confidence=0.9)

    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=FakeVad(emit_on_nth=3, pcm=b"\x00\x10" * 20000),
        whisper=StallDetector(),  # type: ignore[arg-type]
        translator=FakeTranslator(text="Hello world"),
        emit=events.append,
    )

    await session.run()

    assert capture.frames_yielded == 12
    assert any(isinstance(event, Transcript) for event in events)


class _MultiVad:
    def __init__(self, *, emit_on: set[int], pcm: bytes) -> None:
        self._emit_on = emit_on
        self._pcm = pcm
        self._pushes = 0

    def push(self, frame: AudioFrame) -> VadPushResult:
        self._pushes += 1
        if self._pushes not in self._emit_on:
            return VadPushResult()
        duration_ms = (len(self._pcm) // 2) * 1000 // frame.sample_rate
        return VadPushResult(
            final=Utterance(
                pcm_s16le=self._pcm,
                t0_ms=self._pushes * 20,
                t1_ms=self._pushes * 20 + duration_ms,
            ),
        )

    def flush(self) -> Utterance | None:
        return None


@pytest.mark.asyncio
async def test_queued_utterances_all_get_transcribed() -> None:
    from ai.whisper.transcriber import TranscriptText

    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()] * 10,
    )
    calls: list[int] = []

    class CountingWhisper:
        def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText:
            del pcm_s16le, partial
            calls.append(len(calls) + 1)
            return TranscriptText(text=f"Hola numero {len(calls)}", confidence=0.9)

    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=_MultiVad(emit_on={2, 5, 8}, pcm=b"\x00\x10" * 20000),
        whisper=CountingWhisper(),  # type: ignore[arg-type]
        translator=FakeTranslator(text="Hello"),
        emit=events.append,
    )

    await session.run()

    transcripts = [event for event in events if isinstance(event, Transcript)]
    assert calls == [1, 2, 3]
    assert [t.original_text for t in transcripts] == [
        "Hola numero 1",
        "Hola numero 2",
        "Hola numero 3",
    ]


@pytest.mark.asyncio
async def test_transcribe_failure_does_not_drop_later_utterances() -> None:
    from ai.whisper.transcriber import TranscriptText

    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()] * 8,
    )

    class FailThenSucceed:
        def __init__(self) -> None:
            self.calls = 0

        def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText:
            del pcm_s16le, partial
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("Modal transcribe timed out")
            return TranscriptText(text="Hola mundo", confidence=0.9)

    whisper = FailThenSucceed()
    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=_MultiVad(emit_on={2, 5}, pcm=b"\x00\x10" * 20000),
        whisper=whisper,  # type: ignore[arg-type]
        translator=FakeTranslator(text="Hello world"),
        emit=events.append,
    )

    await session.run()

    errors = [event for event in events if isinstance(event, ErrorMessage)]
    transcripts = [event for event in events if isinstance(event, Transcript)]
    assert whisper.calls == 2
    assert len(errors) == 1
    assert "timed out" in errors[0].message
    assert len(transcripts) == 1
    assert transcripts[0].original_text == "Hola mundo"


@pytest.mark.asyncio
async def test_stale_utterances_are_dropped_while_transcribing() -> None:
    import threading

    from ai.whisper.transcriber import TranscriptText

    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()] * 12,
    )
    seen: list[int] = []
    entered = threading.Event()
    release = threading.Event()

    class GateWhisper:
        def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText:
            del pcm_s16le, partial
            seen.append(len(seen) + 1)
            if len(seen) == 1:
                entered.set()
                release.wait(timeout=2)
            return TranscriptText(text=f"Hola numero {len(seen)} extra", confidence=0.9)

    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=_MultiVad(emit_on={2, 5, 8}, pcm=b"\x00\x10" * 20000),
        whisper=GateWhisper(),  # type: ignore[arg-type]
        translator=FakeTranslator(text="Hello"),
        emit=events.append,
    )

    task = asyncio.create_task(session.run())
    assert await asyncio.to_thread(entered.wait, 2)
    await asyncio.sleep(0.15)
    release.set()
    await task

    transcripts = [event for event in events if isinstance(event, Transcript)]
    assert seen == [1, 2]
    assert [t.original_text for t in transcripts] == [
        "Hola numero 1 extra",
        "Hola numero 2 extra",
    ]


@pytest.mark.asyncio
async def test_short_utterance_is_not_sent_to_whisper() -> None:
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()] * 4,
    )
    calls = 0

    class CountingWhisper:
        def transcribe(self, pcm_s16le: bytes, *, partial: bool = False):
            del pcm_s16le, partial
            nonlocal calls
            calls += 1
            raise AssertionError("short utterance should not be transcribed")

    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=_MultiVad(emit_on={1}, pcm=b"\x00\x10" * 6400),
        whisper=CountingWhisper(),  # type: ignore[arg-type]
        translator=FakeTranslator(text="Hello"),
        emit=events.append,
    )

    await session.run()

    assert calls == 0
    assert not any(isinstance(event, Transcript) for event in events)


@pytest.mark.asyncio
async def test_remote_caption_is_one_round_trip() -> None:
    from ai.inference.modal_client import CaptionResult

    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[make_frame()] * 4,
    )

    class CaptionOnly:
        def caption(self, pcm_s16le: bytes) -> CaptionResult:
            del pcm_s16le
            return CaptionResult(
                text="Hola mundo",
                translated_text="Hello world",
                confidence=0.9,
            )

        def transcribe(self, pcm_s16le: bytes, *, partial: bool = False):
            del pcm_s16le, partial
            raise AssertionError("remote path should call caption, not transcribe")

    events: list[ServerMessage] = []
    session = CallSession(
        call_session_id="abc",
        device_id="d1",
        capture=capture,
        vad=FakeVad(emit_on_nth=1, pcm=b"\x00\x10" * 20000),
        whisper=CaptionOnly(),  # type: ignore[arg-type]
        translator=FakeTranslator(text="should not be used"),
        emit=events.append,
    )

    await session.run()

    transcripts = [event for event in events if isinstance(event, Transcript)]
    assert len(transcripts) == 1
    assert transcripts[0].original_text == "Hola mundo"
    assert transcripts[0].translated_text == "Hello world"
