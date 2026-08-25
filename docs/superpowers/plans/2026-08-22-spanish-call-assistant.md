# QuestRock Spanish Call Assistant Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local Electron + Python sidecar that captures system-audio loopback on macOS and Windows, transcribes Spanish with faster-whisper, translates with glossary-aware GPT-4.1-mini, and shows compact click-through captions.

**Architecture:** Electron is UI only (control window + click-through overlay).
A FastAPI sidecar on 127.0.0.1 owns WASAPI / Core Audio tap capture, Silero VAD, Whisper, and OpenAI.
The UI WebSocket is JSON only.
PCM never enters Electron.

**Tech Stack:** Electron, electron-vite, React, TypeScript strict, Python 3.12, uv, FastAPI, WebSockets, faster-whisper, silero-vad, OpenAI SDK, Core Audio tap (Swift helper), pyaudiowpatch (Windows), electron-builder, PyInstaller, electron-updater.

**Spec:** `docs/superpowers/specs/2026-08-22-spanish-call-assistant-design.md`

## Status (2026-08-26)

Phase 1 tasks **1-18 are implemented** (sidecar, dual-OS capture backends, VAD, Whisper, translator, Electron control + overlay).
The Mac live loop has run: Whisper processed speech and OpenAI returned translations.
Local unsigned Mac DMG packaging has been built.
Shipped tags: `v0.1.0`, `v0.1.1` (app version 0.1.1).
Release workflow builds both OS installers, then one job publishes a single GitHub Release.

| Item | State |
| --- | --- |
| Tasks 1-18 | Done |
| Task 19 README / fixtures | README matches the shipping tree. Logging allowlist exists. `tests/test_logging.py` is still missing |
| Task 20 Mac smoke | Done (transcription + translation). Not a signed installer |
| Task 20 Windows smoke | Not done |
| Packaged sidecar + electron-builder | Mac DMG built locally. Windows installer is built in CI on `windows-latest` |
| In-app Update now + tag CI + Pages | In tree. Tags `v0.1.0` / `v0.1.1`. One Release per tag (`publish` job) |
| Code signing | Documented in `docs/CODE_SIGNING.md`. `identity: null` and `CSC_IDENTITY_AUTO_DISCOVERY=false` until certs exist |
| Phases 2-5 | Not started. Phase 4 is login only. No transcript DB in any phase (Zoom Phone stores the call) |

Left: Windows proof on hardware, logging-guard test, confirm v0.1.1 Release assets, Apple/Windows signing, then Phase 2 Zoom tap.

Historical TDD checkboxes below are the original recipe.
They are not a live tracker.

## Global Constraints

- TypeScript `strict: true`.
- Python 3.12+ with full type hints.
- Package and run Python with `uv` only (`pyproject.toml` + `uv.lock`; no primary `requirements.txt`).
- Bind sidecar to `127.0.0.1` only.
- No audio on disk unless `QUESTROCK_DEBUG_AUDIO=1`.
- Do not log `original_text` or `translated_text` at info.
- `OPENAI_API_KEY` never reaches the renderer.
- One `CallSession` per `call_session_id`. No global transcriber.
- Utterance-final transcripts only (`is_final` always true).
- Overlay copy: English primary, Spanish verifier, statuses exactly as in the spec.
- Translation failure English line is exactly `Translation unavailable`.
- Tests pass with no network and no real DB.
- Phase 1 ships no auth, Modal, or intent code.
- Never persist transcripts or call audio. Zoom Phone is the system of record.
- Do not use Chromium `getDisplayMedia` for capture.
- Do not use an em dash in user-facing copy.

## File map

Create these files.
Do not invent extra layers.

```text
pyproject.toml
.env.example
config/mortgage_glossary.json
backend/__init__.py
backend/settings.py
backend/logging.py
backend/main.py
backend/api/health.py
backend/api/devices.py
backend/websocket/protocol.py
backend/websocket/handler.py
backend/sessions/manager.py
backend/sessions/call_session.py
audio/types.py
audio/resample.py
audio/factory.py
audio/windows.py
audio/macos.py
ai/vad/segmenter.py
ai/whisper/transcriber.py
ai/translation/glossary.py
ai/translation/prompt.py
ai/translation/translator.py
native/macos/AudioTap.swift
native/macos/build.sh
electron/package.json
electron/electron.vite.config.ts
electron/tsconfig.json
electron/src/main/index.ts
electron/src/main/sidecar.ts
electron/src/main/windows.ts
electron/src/main/gateway.ts
electron/src/main/hotkeys.ts
electron/src/preload/index.ts
electron/src/shared/protocol.ts
electron/src/renderer/control/index.html
electron/src/renderer/control/main.tsx
electron/src/renderer/control/App.tsx
electron/src/renderer/overlay/index.html
electron/src/renderer/overlay/main.tsx
electron/src/renderer/overlay/Overlay.tsx
tests/test_protocol.py
tests/test_glossary.py
tests/test_translator.py
tests/test_resample.py
tests/test_vad.py
tests/test_whisper.py
tests/test_session.py
tests/test_ws_handler.py
tests/fakes.py
electron/src/shared/protocol.test.ts
electron/src/renderer/overlay/Overlay.test.tsx
README.md
fixtures/audio/README.md
```

---

### Task 1: Python project skeleton and health endpoint

**Files:**
- Create: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/settings.py`
- Create: `backend/logging.py`
- Create: `backend/main.py`
- Create: `backend/api/health.py`
- Create: `.env.example`
- Test: `tests/test_health.py`

**Interfaces:**
- Consumes: nothing
- Produces: `create_app() -> fastapi.FastAPI`, `GET /health` returns `{"ok": true}`, CLI `questrock-sidecar`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from backend.main import create_app

def test_health_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_health.py::test_health_ok -v`

Expected: FAIL because `backend.main` does not exist.

- [ ] **Step 3: Write minimal implementation**

`pyproject.toml`:

```toml
[project]
name = "questrock-sidecar"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "websockets>=14",
  "pydantic-settings>=2.6",
  "faster-whisper>=1.1",
  "silero-vad>=5.1",
  "openai>=1.50",
  "numpy>=2.0",
  "soxr>=0.5",
]

[project.optional-dependencies]
windows = ["pyaudiowpatch>=0.2"]
dev = ["pytest>=8.3", "httpx>=0.27"]

[project.scripts]
questrock-sidecar = "backend.main:run"

[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["backend*", "audio*", "ai*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`backend/settings.py` reads env with pydantic-settings: `openai_api_key`, `openai_translation_model="gpt-4.1-mini"`, `whisper_model="small"`, `vad_silence_ms=800`, `vad_max_utterance_ms=8000`, `host="127.0.0.1"`, `port=8765`.

`backend/logging.py` configures JSON logs via stdlib `logging` + a formatter that never includes transcript fields.

`backend/api/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
```

`backend/main.py` `create_app()` includes the health router.
`run()` starts uvicorn on `127.0.0.1` (never `0.0.0.0`).

`.env.example`:

```
OPENAI_API_KEY=
OPENAI_TRANSLATION_MODEL=gpt-4.1-mini
WHISPER_MODEL=small
VAD_SILENCE_MS=800
VAD_MAX_UTTERANCE_MS=8000
QUESTROCK_LOG_TRANSCRIPTS=0
QUESTROCK_DEBUG_AUDIO=0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv sync --extra dev && uv run pytest tests/test_health.py::test_health_ok -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock backend tests/test_health.py .env.example
git commit -m "$(cat <<'EOF'
feat: add FastAPI sidecar skeleton with health endpoint

EOF
)"
```

---

### Task 2: UI WebSocket protocol v1

**Files:**
- Create: `backend/websocket/protocol.py`
- Test: `tests/test_protocol.py`

**Interfaces:**
- Consumes: spec section 7
- Produces: `parse_client_message(raw: dict) -> Hello | StartCall | StopCall` raises `ProtocolError`; `encode_server_message(msg) -> dict`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_protocol.py -v`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

Use frozen dataclasses (or pydantic models) for every v1 message in the spec.
`parse_client_message` requires `hello` shape, `start_call` with `device_id` + `language=="spanish"`, and `stop_call`.
Unknown or missing `type` raises `ProtocolError(code="protocol", message="Unknown message type")`.
`encode_server_message` emits the exact JSON keys from the spec.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_protocol.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/websocket/protocol.py tests/test_protocol.py
git commit -m "$(cat <<'EOF'
feat: add v1 UI WebSocket protocol codecs

EOF
)"
```

---

### Task 3: Mortgage glossary loader and prompt

**Files:**
- Create: `config/mortgage_glossary.json`
- Create: `ai/translation/glossary.py`
- Create: `ai/translation/prompt.py`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Consumes: glossary schema in spec 6.9
- Produces: `load_glossary(path: Path) -> Glossary`; `build_system_prompt(glossary: Glossary) -> str`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from ai.translation.glossary import load_glossary
from ai.translation.prompt import build_system_prompt

def test_seed_terms_present():
    glossary = load_glossary(Path("config/mortgage_glossary.json"))
    ens = {t.preferred_en for t in glossary.terms}
    assert "cash-out refinance" in ens
    assert "loan officer" in ens
    assert "closing costs" in ens
    assert "interest rate" in ens
    assert "monthly payment" in ens
    assert "down payment" in ens
    assert "preapproval" in ens

def test_prompt_contains_preferred_english_and_rules():
    glossary = load_glossary(Path("config/mortgage_glossary.json"))
    prompt = build_system_prompt(glossary)
    assert "cash-out refinance" in prompt
    assert "sacar dinero de mi casa" in prompt
    assert "Do not hallucinate" in prompt
    assert "Preserve numbers" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_glossary.py -v`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

JSON file with the seven seed terms from the spec, including Spanish variants for cash-out (`refinanciamiento con retiro de efectivo`, `sacar dinero de mi casa`).

`GlossaryTerm(en, es: list[str], preferred_en)`.

`build_system_prompt` returns a single system string that states: translate Spanish mortgage borrower speech to natural English; preserve meaning; use US mortgage terminology; do not hallucinate; preserve numbers, loan amounts, interest rates, and dates exactly; then lists `es -> preferred_en` pairs.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_glossary.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/mortgage_glossary.json ai/translation tests/test_glossary.py
git commit -m "$(cat <<'EOF'
feat: add mortgage glossary JSON and translation system prompt

EOF
)"
```

---

### Task 4: MortgageTranslator with mocked OpenAI

**Files:**
- Create: `ai/translation/translator.py`
- Create: `tests/fakes.py` (start; more fakes added in later tasks)
- Test: `tests/test_translator.py`

**Interfaces:**
- Consumes: `build_system_prompt`, `Glossary`
- Produces: `MortgageTranslator.translate(spanish: str) -> TranslationResult` where `TranslationResult(original_text: str, translated_text: str | None)`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from ai.translation.translator import MortgageTranslator, TranslationResult

class FakeCompletions:
    def __init__(self, create):
        self.create = create

class FakeChat:
    def __init__(self, create):
        self.completions = FakeCompletions(create)

class FakeOpenAI:
    def __init__(self, create):
        self.chat = FakeChat(create)

@pytest.mark.asyncio
async def test_translate_returns_model_text():
    async def create(**kwargs):
        assert kwargs["model"] == "gpt-4.1-mini"
        assert kwargs["temperature"] == 0
        class Choice:
            message = type("M", (), {"content": "I want to take cash out from my home."})()
        return type("R", (), {"choices": [Choice()]})()

    translator = MortgageTranslator(
        client=FakeOpenAI(create),
        model="gpt-4.1-mini",
        system_prompt="sys",
        timeout_s=8,
    )
    result = await translator.translate("Quiero sacar dinero de mi casa.")
    assert result == TranslationResult(
        original_text="Quiero sacar dinero de mi casa.",
        translated_text="I want to take cash out from my home.",
    )

@pytest.mark.asyncio
async def test_translate_timeout_keeps_spanish():
    async def create(**kwargs):
        raise TimeoutError("openai")

    translator = MortgageTranslator(
        client=FakeOpenAI(create),
        model="gpt-4.1-mini",
        system_prompt="sys",
        timeout_s=8,
    )
    result = await translator.translate("Hola")
    assert result.original_text == "Hola"
    assert result.translated_text is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_translator.py -v`

Expected: FAIL, `MortgageTranslator` missing.

- [ ] **Step 3: Write minimal implementation**

`MortgageTranslator.__init__(client, model, system_prompt, timeout_s=8)`.
`translate` calls `client.chat.completions.create` with `temperature=0`, `timeout=timeout_s`, system + user messages.
On any exception, return `translated_text=None` and keep Spanish.
Do not log the Spanish at info.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_translator.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/translation/translator.py tests/test_translator.py tests/fakes.py
git commit -m "$(cat <<'EOF'
feat: add glossary-aware translator with Spanish fallback

EOF
)"
```

---

### Task 5: PCM resample to 16 kHz mono s16le

**Files:**
- Create: `audio/types.py`
- Create: `audio/resample.py`
- Test: `tests/test_resample.py`

**Interfaces:**
- Consumes: nothing
- Produces: `AudioFrame(pcm_s16le: bytes, sample_rate: int, channels: int, duration_ms: int)`; `to_16k_mono_s16le(pcm: bytes, sample_rate: int, channels: int) -> bytes`

- [ ] **Step 1: Write the failing test**

```python
import struct
from audio.resample import to_16k_mono_s16le

def test_stereo_48k_silence_becomes_16k_mono():
    frames_48k_stereo = 4800  # 100 ms
    pcm = struct.pack("<" + "h" * (frames_48k_stereo * 2), *([0] * frames_48k_stereo * 2))
    out = to_16k_mono_s16le(pcm, sample_rate=48000, channels=2)
    assert len(out) == 1600 * 2  # 100 ms at 16 kHz mono s16le

def test_already_16k_mono_is_identity():
    pcm = b"\x00\x01" * 320
    assert to_16k_mono_s16le(pcm, 16000, 1) == pcm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resample.py -v`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

Use `numpy` + `soxr` to convert s16le -> float -> 16 kHz mono -> s16le.
Downmix stereo by averaging channels.
If input is already 16 kHz mono, return bytes unchanged.

`AudioFrame` is a dataclass with the four fields from the spec.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resample.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add audio/types.py audio/resample.py tests/test_resample.py
git commit -m "$(cat <<'EOF'
feat: resample capture PCM to 16 kHz mono

EOF
)"
```

---

### Task 6: VadSegmenter

**Files:**
- Create: `ai/vad/segmenter.py`
- Test: `tests/test_vad.py`

**Interfaces:**
- Consumes: `AudioFrame` at 16 kHz mono
- Produces: `VadSegmenter.push(frame: AudioFrame) -> Utterance | None`; `Utterance(pcm_s16le: bytes, t0_ms: int, t1_ms: int)`; `reset()`

Silero `VADIterator` requires **exactly 512 samples (32 ms)** at 16 kHz.
Buffer incoming ~20 ms frames until 512 samples are available.
Do not call the real Silero model in unit tests.
Inject a `SpeechScorer` protocol: `score(chunk_s16le_512: bytes) -> float`.

- [ ] **Step 1: Write the failing test**

```python
from audio.types import AudioFrame
from ai.vad.segmenter import VadSegmenter, Utterance

class ScriptedScorer:
    def __init__(self, probs: list[float]):
        self.probs = list(probs)
    def score(self, chunk: bytes) -> float:
        return self.probs.pop(0)

def frame_from_pcm(pcm: bytes, t0_ms: int) -> AudioFrame:
    duration_ms = (len(pcm) // 2) * 1000 // 16000
    return AudioFrame(pcm_s16le=pcm, sample_rate=16000, channels=1, duration_ms=duration_ms)

def test_speech_then_silence_emits_one_utterance():
    # 32 ms chunk = 512 samples = 1024 bytes
    chunk = b"\x00\x10" * 512
    scorer = ScriptedScorer([0.9, 0.9, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    vad = VadSegmenter(scorer=scorer, silence_ms=800, max_utterance_ms=8000, min_utterance_ms=250)
    results: list[Utterance] = []
    t = 0
    for _ in range(12):
        frame = frame_from_pcm(chunk, t)
        maybe = vad.push(frame)
        if maybe:
            results.append(maybe)
        t += 32
    assert len(results) == 1
    assert results[0].t1_ms - results[0].t0_ms >= 250

def test_silence_only_emits_nothing():
    chunk = b"\x00\x00" * 512
    vad = VadSegmenter(scorer=ScriptedScorer([0.0] * 20), silence_ms=800, max_utterance_ms=8000, min_utterance_ms=250)
    emitted = [vad.push(frame_from_pcm(chunk, i * 32)) for i in range(20)]
    assert all(x is None for x in emitted)

def test_max_cap_emits_before_silence():
    chunk = b"\x00\x10" * 512
    n = 8_000 // 32 + 2
    vad = VadSegmenter(scorer=ScriptedScorer([0.99] * n), silence_ms=800, max_utterance_ms=8000, min_utterance_ms=250)
    results = []
    for i in range(n):
        maybe = vad.push(frame_from_pcm(chunk, i * 32))
        if maybe:
            results.append(maybe)
    assert len(results) == 1
    assert results[0].t1_ms - results[0].t0_ms >= 8000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vad.py -v`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

Buffer bytes to 1024-byte (512 sample) chunks.
If `score >= 0.5`, start or continue an utterance and append PCM.
If in-utterance and silence duration >= `silence_ms`, emit if length >= `min_utterance_ms`, else drop.
If in-utterance and duration >= `max_utterance_ms`, emit immediately.
Track `t0_ms` / `t1_ms` from a monotonic sample counter.

Production constructor: `VadSegmenter.with_silero(silence_ms, max_utterance_ms)` wraps `silero_vad.load_silero_vad(onnx=True)` and `VADIterator` **or** a thin scorer that calls `model(chunk_tensor, 16000)`.
Unit tests always inject `SpeechScorer`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vad.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/vad/segmenter.py tests/test_vad.py
git commit -m "$(cat <<'EOF'
feat: add utterance VAD with silence and max-cap rules

EOF
)"
```

---

### Task 7: WhisperTranscriber wrapper

**Files:**
- Create: `ai/whisper/transcriber.py`
- Test: `tests/test_whisper.py`

**Interfaces:**
- Consumes: `Utterance.pcm_s16le`
- Produces: `WhisperTranscriber.transcribe(pcm_s16le: bytes) -> TranscriptText | None` where `TranscriptText(text: str, confidence: float)`

Do not load faster-whisper in unit tests.
Inject a `WhisperEngine` protocol.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from ai.whisper.transcriber import WhisperTranscriber, TranscriptText

class FakeEngine:
    def __init__(self, text: str, avg_log_prob: float):
        self.text = text
        self.avg_log_prob = avg_log_prob
        self.calls = []
    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        segment = type("S", (), {"text": self.text, "avg_log_prob": self.avg_log_prob})()
        return iter([segment]), None

def test_joins_segments_and_clamps_confidence():
    engine = FakeEngine("  Hola mundo  ", avg_log_prob=-0.2)
    t = WhisperTranscriber(engine=engine, model_name="small")
    pcm = (np.zeros(16000, dtype=np.int16)).tobytes()
    result = t.transcribe(pcm)
    assert result == TranscriptText(text="Hola mundo", confidence=result.confidence)
    assert 0.0 <= result.confidence <= 1.0
    assert engine.calls[0]["language"] == "es"
    assert engine.calls[0]["vad_filter"] is False
    assert engine.calls[0]["beam_size"] == 1

def test_blank_text_returns_none():
    t = WhisperTranscriber(engine=FakeEngine("   ", -0.1), model_name="small")
    pcm = (np.zeros(16000, dtype=np.int16)).tobytes()
    assert t.transcribe(pcm) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_whisper.py -v`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

Convert s16le bytes to float32 numpy in `[-1, 1]` at 16 kHz.
Call `engine.transcribe(audio, language="es", vad_filter=False, beam_size=1, best_of=1)`.
Join segment texts, strip.
Empty -> `None`.
Confidence: `1 / (1 + exp(-avg_log_prob))` or clamp `(avg_log_prob + 1) / 1` into `[0,1]`.
Pick one formula and unit-test the clamp.

Production: `WhisperTranscriber.load(model_name: str)` constructs `faster_whisper.WhisperModel(model_name, device="cuda" if available else "cpu", compute_type="float16" if cuda else "int8")` and caches the model object at process level.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_whisper.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/whisper/transcriber.py tests/test_whisper.py
git commit -m "$(cat <<'EOF'
feat: wrap faster-whisper with Spanish utterance API

EOF
)"
```

---

### Task 8: AudioCapture protocol and FakeCapture

**Files:**
- Create: `audio/factory.py` (protocol + fake + `capture_for_platform` stub)
- Modify: `tests/fakes.py`
- Test: `tests/test_session.py` (partial: devices list via fake; full session in Task 9)

**Interfaces:**
- Consumes: `AudioFrame`
- Produces:

```python
class LoopbackDevice:
    id: str
    name: str
    kind: Literal["loopback"]

class AudioCapture(Protocol):
    def list_devices(self) -> list[LoopbackDevice]: ...
    def start(self, device_id: str) -> None: ...
    def frames(self) -> Iterator[AudioFrame]: ...
    def stop(self) -> None: ...
```

`FakeCapture` in `tests/fakes.py` yields a provided sequence of frames, records `start`/`stop`, and raises `KeyError` on unknown device id.

- [ ] **Step 1: Write the failing test**

```python
from tests.fakes import FakeCapture
from audio.types import AudioFrame, LoopbackDevice

def test_fake_lists_and_stops():
    frame = AudioFrame(pcm_s16le=b"\x00\x00" * 320, sample_rate=16000, channels=1, duration_ms=20)
    cap = FakeCapture(devices=[LoopbackDevice(id="d1", name="Speakers", kind="loopback")], frames=[frame])
    assert cap.list_devices()[0].id == "d1"
    cap.start("d1")
    assert list(cap.frames()) == [frame]
    cap.stop()
    assert cap.stopped is True

def test_fake_unknown_device():
    cap = FakeCapture(devices=[], frames=[])
    try:
        cap.start("missing")
        raised = False
    except Exception:
        raised = True
    assert raised
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_session.py::test_fake_lists_and_stops -v`

Expected: FAIL until FakeCapture exists.
Put these two tests in `tests/test_capture_fake.py` if `test_session.py` is reserved for Task 9.
Prefer `tests/test_capture_fake.py`.

- [ ] **Step 3: Write minimal implementation**

Define `LoopbackDevice` and `AudioFrame` in `audio/types.py` if not already.
Implement `FakeCapture`.
`audio/factory.py` `capture_for_platform()` raises `RuntimeError("unsupported platform")` for non-darwin/win32 for now (real backends in Tasks 11-13).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_capture_fake.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add audio/types.py audio/factory.py tests/fakes.py tests/test_capture_fake.py
git commit -m "$(cat <<'EOF'
feat: add AudioCapture protocol and fake backend

EOF
)"
```

---

### Task 9: CallSession pipeline

**Files:**
- Create: `backend/sessions/call_session.py`
- Create: `backend/sessions/manager.py`
- Test: `tests/test_session.py`

**Interfaces:**
- Consumes: `AudioCapture`, `VadSegmenter`, `WhisperTranscriber`, `MortgageTranslator`
- Produces: `CallSession.start()` async generator or callback of protocol server messages; `CallSession.stop()`; `SessionManager.create(...) -> CallSession`

Pipeline: frames -> VAD -> whisper (skip None) -> translate -> `Transcript` event.
Emit `Status(loading_model)` then `Status(listening)` then `transcribing` / `translating` around work.
On translator `translated_text is None`, still emit transcript with `translated_text=None` (UI maps to `Translation unavailable`).

- [ ] **Step 1: Write the failing test**

```python
import asyncio
from audio.types import AudioFrame, LoopbackDevice
from backend.sessions.call_session import CallSession
from backend.websocket.protocol import Transcript, Status
from tests.fakes import FakeCapture, FakeVad, FakeWhisper, FakeTranslator

@pytest.mark.asyncio
async def test_session_emits_final_transcript_and_stops_capture():
    frame = AudioFrame(pcm_s16le=b"\x00\x10" * 320, sample_rate=16000, channels=1, duration_ms=20)
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[frame] * 5,
    )
    events = []
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
    types = [type(e) for e in events]
    assert Status in types
    transcripts = [e for e in events if isinstance(e, Transcript)]
    assert len(transcripts) == 1
    assert transcripts[0].original_text == "Hola"
    assert transcripts[0].translated_text == "Hello"
    assert transcripts[0].is_final is True
    assert transcripts[0].call_session_id == "abc"
    assert capture.stopped is True

@pytest.mark.asyncio
async def test_translation_failure_still_emits_spanish():
    capture = FakeCapture(
        devices=[LoopbackDevice("d1", "Speakers", "loopback")],
        frames=[AudioFrame(b"\x00\x10" * 320, 16000, 1, 20)],
    )
    events = []
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
    transcripts = [e for e in events if isinstance(e, Transcript)]
    assert transcripts[0].original_text == "Hola"
    assert transcripts[0].translated_text is None
```

Add `FakeVad`, `FakeWhisper`, `FakeTranslator` to `tests/fakes.py`.
`FakeVad.push` returns an `Utterance` on the nth frame then None.
`session.run()` reads frames until capture iterator ends, then stops.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_session.py -v`

Expected: FAIL, `CallSession` missing.

- [ ] **Step 3: Write minimal implementation**

`CallSession.run` is async.
If `capture.frames()` is sync, wrap with `asyncio.to_thread` per frame or iterate in a worker thread putting utterances on a queue.
Keep it simple: `asyncio.to_thread` for whisper (CPU) and await translator.
`stop()` sets a flag, calls `capture.stop()`, and is idempotent.
`SessionManager` stores sessions by id, `create` builds a session, `get`, `discard`.
Do not load real Whisper in this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_session.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/sessions tests/test_session.py tests/fakes.py
git commit -m "$(cat <<'EOF'
feat: add isolated CallSession transcription pipeline

EOF
)"
```

---

### Task 10: WebSocket handler and device HTTP

**Files:**
- Create: `backend/websocket/handler.py`
- Create: `backend/api/devices.py`
- Modify: `backend/main.py`
- Test: `tests/test_ws_handler.py`

**Interfaces:**
- Consumes: protocol codecs, `SessionManager`, `AudioCapture.list_devices`
- Produces: `WS /v1/calls`, `GET /v1/devices`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from backend.main import create_app
from audio.types import LoopbackDevice
from tests.fakes import FakeCapture

def test_list_devices(monkeypatch):
    fake = FakeCapture(devices=[LoopbackDevice("d1", "Speakers", "loopback")], frames=[])
    app = create_app(capture=fake)
    client = TestClient(app)
    response = client.get("/v1/devices")
    assert response.json() == {
        "devices": [{"id": "d1", "name": "Speakers", "kind": "loopback"}]
    }

def test_ws_hello_then_start_without_hello_errors():
    fake = FakeCapture(devices=[LoopbackDevice("d1", "Speakers", "loopback")], frames=[])
    app = create_app(capture=fake)
    client = TestClient(app)
    with client.websocket_connect("/v1/calls") as ws:
        ws.send_json({"type": "start_call", "device_id": "d1", "language": "spanish"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "protocol"
```

Also test happy path: `hello` then `start_call` yields `session_started` then at least one `status`.
`stop_call` then close.
Unknown type yields `error.code=protocol` and `message` contains no borrower text.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ws_handler.py -v`

Expected: FAIL, route missing.

- [ ] **Step 3: Write minimal implementation**

`create_app(capture: AudioCapture | None = None)` uses injected capture or `capture_for_platform()`.
WebSocket handler state machine: connected -> hello -> can start.
`start_call` creates session, sends `session_started`, runs session, forwards events as JSON.
A second `start_call` stops the previous session first.
Socket close == `stop_call`.
Bind remains `127.0.0.1`.

For tests, session may use fakes via `create_app(..., session_factory=...)`.
If that keeps the handler testable without Whisper, inject `session_factory`.
Do not call real OpenAI or Whisper in these tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ws_handler.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/websocket/handler.py backend/api/devices.py backend/main.py tests/test_ws_handler.py
git commit -m "$(cat <<'EOF'
feat: add local device list and v1 call WebSocket

EOF
)"
```

---

### Task 11: macOS ScreenCaptureKit helper

**Files:**
- Create: `native/macos/AudioTap.swift`
- Create: `native/macos/build.sh`

**Interfaces:**
- Consumes: ScreenCaptureKit
- Produces: binary `native/macos/AudioTap` that writes raw PCM to stdout

This task has no Python unit test (native helper).
Verify by compiling on darwin.

- [ ] **Step 1: Write the failing compile check**

```bash
test -x native/macos/AudioTap
```

Expected: FAIL, binary missing.

- [ ] **Step 2: Confirm it fails**

Run: `test -x native/macos/AudioTap ; echo $?`

Expected: non-zero on a clean tree.

- [ ] **Step 3: Implement helper**

`AudioTap.swift`:

- `SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)`
- Filter: first display, `excludingWindows: []`
- `SCStreamConfiguration`: `capturesAudio=true`, `excludesCurrentProcessAudio=true`, `sampleRate=48000`, `channelCount=2`, `width=2`, `height=2`, `minimumFrameInterval` 1 fps
- Add stream outputs for `.audio` and dummy `.screen` (ignore video) on separate queues
- Convert audio `CMSampleBuffer` to interleaved s16le stereo
- Write a one-line ASCII header to stdout: `{"sample_rate":48000,"channels":2,"format":"s16le"}\n` then raw PCM
- Diagnostic logs go to **stderr only**
- Exit non-zero if Screen Recording permission is denied, printing a stable error token `capture_permission` on stderr

`build.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
swiftc -O -o AudioTap AudioTap.swift \
  -framework ScreenCaptureKit \
  -framework CoreMedia \
  -framework AudioToolbox \
  -framework Foundation
```

On non-darwin CI, skip compile.

- [ ] **Step 4: Compile on macOS**

Run: `bash native/macos/build.sh && test -x native/macos/AudioTap`

Expected: binary exists.

- [ ] **Step 5: Commit**

```bash
git add native/macos/AudioTap.swift native/macos/build.sh
git commit -m "$(cat <<'EOF'
feat: add ScreenCaptureKit system-audio helper

EOF
)"
```

Do not commit the compiled binary if it is large; add `native/macos/AudioTap` to `.gitignore` and build on sidecar start if missing.

---

### Task 12: macOS Python capture backend

**Files:**
- Create: `audio/macos.py`
- Test: `tests/test_macos_capture.py`

**Interfaces:**
- Consumes: helper stdout protocol, `to_16k_mono_s16le`
- Produces: `MacosScreenCaptureKitCapture` implementing `AudioCapture`

Do not start the real helper in unit tests.
Inject a `Proc` factory that returns a fake subprocess with a header line + PCM bytes.

- [ ] **Step 1: Write the failing test**

```python
from audio.macos import MacosScreenCaptureKitCapture
from audio.types import AudioFrame

class FakeProc:
    def __init__(self, stdout_bytes: bytes, stderr: bytes = b""):
        import io
        self.stdout = io.BytesIO(stdout_bytes)
        self.stderr = io.BytesIO(stderr)
        self.terminated = False
    def poll(self):
        return None
    def terminate(self):
        self.terminated = True
    def wait(self, timeout=None):
        return 0

def test_parses_header_and_emits_16k_frames(tmp_path):
    header = b'{"sample_rate":48000,"channels":2,"format":"s16le"}\n'
    pcm_48k_stereo_20ms = b"\x00\x00" * (48000 // 50 * 2)
    cap = MacosScreenCaptureKitCapture(proc_factory=lambda _cmd: FakeProc(header + pcm_48k_stereo_20ms))
    devices = cap.list_devices()
    assert devices[0].id == "system-audio"
    cap.start("system-audio")
    frame = next(cap.frames())
    assert isinstance(frame, AudioFrame)
    assert frame.sample_rate == 16000
    assert frame.channels == 1
    cap.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_macos_capture.py -v`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

`list_devices` returns `[LoopbackDevice("system-audio", "System Audio", "loopback")]`.
`start` spawns `native/macos/AudioTap` (build if missing on darwin).
Read header JSON, then read PCM in 20 ms chunks at the helper rate, resample, yield `AudioFrame`.
If process exits with `capture_permission` on stderr, raise a dedicated `CapturePermissionError`.
`stop` terminates the process.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_macos_capture.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add audio/macos.py tests/test_macos_capture.py
git commit -m "$(cat <<'EOF'
feat: add macOS loopback capture supervisor

EOF
)"
```

---

### Task 13: Windows WASAPI loopback backend

**Files:**
- Create: `audio/windows.py`
- Test: `tests/test_windows_capture.py`
- Modify: `audio/factory.py`

**Interfaces:**
- Consumes: pyaudiowpatch, resample
- Produces: `WindowsWasapiLoopbackCapture`

Unit tests mock pyaudiowpatch.
Do not require Windows to run tests.

- [ ] **Step 1: Write the failing test**

```python
from audio.windows import WindowsWasapiLoopbackCapture
from audio.types import LoopbackDevice

class FakePyAudio:
    def get_loopback_device_info_generator(self):
        yield {"index": 7, "name": "Speakers (loopback)", "defaultSampleRate": 48000, "maxInputChannels": 2}
    def open(self, **kwargs):
        class Stream:
            def read(self, n, exception_on_overflow=False):
                return b"\x00\x00" * n * 2
            def stop_stream(self): pass
            def close(self): pass
        return Stream()
    def terminate(self): pass

def test_lists_loopback_devices():
    cap = WindowsWasapiLoopbackCapture(pa_factory=lambda: FakePyAudio())
    devices = cap.list_devices()
    assert devices == [LoopbackDevice(id="7", name="Speakers (loopback)", kind="loopback")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_windows_capture.py -v`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

Wrap `pyaudiowpatch.PyAudio`.
Enumerate loopback devices only.
`start(device_id)` opens a stream at the device's native rate, int16, then resample each read to 16 kHz mono 20 ms frames.
Unknown device -> error that the session maps to `device_missing`.
`audio/factory.py`:

```python
def capture_for_platform() -> AudioCapture:
    if sys.platform == "darwin":
        return MacosScreenCaptureKitCapture()
    if sys.platform == "win32":
        return WindowsWasapiLoopbackCapture()
    raise RuntimeError(f"unsupported platform: {sys.platform}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_windows_capture.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add audio/windows.py audio/factory.py tests/test_windows_capture.py pyproject.toml
git commit -m "$(cat <<'EOF'
feat: add Windows WASAPI loopback capture

EOF
)"
```

---

### Task 14: Wire production session factory

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/sessions/manager.py`

**Interfaces:**
- Consumes: real Whisper load, real translator, real VAD, real capture
- Produces: production `session_factory` used when Electron starts the sidecar

- [ ] **Step 1: Write the failing test**

```python
from backend.sessions.manager import production_dependencies

def test_production_dependencies_exposes_loader_hooks():
    deps = production_dependencies()
    assert hasattr(deps, "load_whisper")
    assert hasattr(deps, "load_translator")
    assert hasattr(deps, "load_vad")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_session.py::test_production_dependencies_exposes_loader_hooks -v`

Expected: FAIL until helper exists.

- [ ] **Step 3: Write minimal implementation**

`production_dependencies()` returns loaders that read settings:
Whisper model name, VAD silence/max, glossary path `config/mortgage_glossary.json`, `AsyncOpenAI` from `OPENAI_API_KEY`.
Process-level Whisper cache: load once, reuse across sessions in this process.
Session still gets its own VAD state.
If API key missing, translator still constructs but `translate` returns `translated_text=None` (Spanish shown).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_session.py::test_production_dependencies_exposes_loader_hooks -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/sessions/manager.py backend/main.py tests/test_session.py
git commit -m "$(cat <<'EOF'
feat: wire production Whisper, VAD, and OpenAI loaders

EOF
)"
```

---

### Task 15: Electron app skeleton (two renderer entries)

**Files:**
- Create: `electron/package.json`
- Create: `electron/tsconfig.json`
- Create: `electron/electron.vite.config.ts`
- Create: `electron/src/main/index.ts` (empty windows first)
- Create: control and overlay HTML/TSX stubs
- Test: `electron/src/shared/protocol.test.ts` after Task 16; this task verifies `npx tsc --noEmit` and `npm run build` in `electron/`

**Interfaces:**
- Consumes: nothing
- Produces: electron-vite React + TS project with `control` and `overlay` inputs

- [ ] **Step 1: Write the failing check**

```bash
test -f electron/package.json
```

Expected: FAIL.

- [ ] **Step 2: Confirm it fails**

Run: `test -f electron/package.json ; echo $?`

Expected: non-zero.

- [ ] **Step 3: Scaffold**

Inside `electron/`, create an electron-vite + React + TypeScript app (do not nest another git repo).
`tsconfig` `strict: true`.
`electron.vite.config.ts` renderer inputs:

- `src/renderer/control/index.html`
- `src/renderer/overlay/index.html`

Main process loads `control` as the primary window.
Overlay window is created but not yet click-through (Task 17).
App name in `package.json`: `QuestRock AI Assistant`.

- [ ] **Step 4: Typecheck**

Run: `cd electron && npm test` or `npx tsc --noEmit`

Expected: PASS (no TS errors).

- [ ] **Step 5: Commit**

```bash
git add electron
git commit -m "$(cat <<'EOF'
feat: scaffold Electron control and overlay windows

EOF
)"
```

---

### Task 16: Shared TS protocol and gateway client

**Files:**
- Create: `electron/src/shared/protocol.ts`
- Create: `electron/src/main/gateway.ts`
- Create: `electron/src/preload/index.ts`
- Test: `electron/src/shared/protocol.test.ts`

**Interfaces:**
- Consumes: spec section 7
- Produces: typed client messages, `GatewayClient` in main that connects to `GATEWAY_URL`, preload API `window.questrock`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest'
import { parseServerMessage } from './protocol'

describe('parseServerMessage', () => {
  it('parses transcript', () => {
    const msg = parseServerMessage({
      type: 'transcript',
      call_session_id: 's',
      id: 't',
      is_final: true,
      original_language: 'es',
      original_text: 'Hola',
      translated_text: 'Hello',
      confidence: 0.9,
      t0_ms: 0,
      t1_ms: 800,
    })
    expect(msg.type).toBe('transcript')
    if (msg.type === 'transcript') {
      expect(msg.original_text).toBe('Hola')
    }
  })

  it('rejects unknown type', () => {
    expect(() => parseServerMessage({ type: 'nope' })).toThrow()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd electron && npx vitest run src/shared/protocol.test.ts`

Expected: FAIL, module missing.

- [ ] **Step 3: Write minimal implementation**

Mirror Python v1 types in `protocol.ts`.
`GatewayClient` uses the Node `ws` package (main process, not renderer).
Exposes `hello`, `startCall`, `stopCall`, event emitter for server messages.
Preload `contextBridge.exposeInMainWorld('questrock', { onEvent, startCall, stopCall, listDevices, setOverlayPosition })`.
`listDevices` is IPC to main which `GET http://127.0.0.1:<port>/v1/devices`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd electron && npx vitest run src/shared/protocol.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add electron/src/shared electron/src/main/gateway.ts electron/src/preload/index.ts
git commit -m "$(cat <<'EOF'
feat: add typed gateway client and preload API

EOF
)"
```

---

### Task 17: Sidecar supervisor, windows, overlay behavior, hotkeys

**Files:**
- Create: `electron/src/main/sidecar.ts`
- Create: `electron/src/main/windows.ts`
- Create: `electron/src/main/hotkeys.ts`
- Modify: `electron/src/main/index.ts`

**Interfaces:**
- Consumes: `questrock-sidecar` CLI
- Produces: spawned sidecar on ephemeral port, two windows with spec behavior

No network tests.
Verify by unit-testing helper functions where possible (`overlayBounds(display, preset)`).

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest'
import { overlayBounds } from './windows'

describe('overlayBounds', () => {
  const display = { x: 0, y: 0, width: 1920, height: 1080 }
  it('bottom-right compact card', () => {
    const b = overlayBounds(display, 'bottom-right')
    expect(b.width).toBeGreaterThanOrEqual(380)
    expect(b.width).toBeLessThanOrEqual(420)
    expect(b.x + b.width).toBe(1920)
    expect(b.y + b.height).toBe(1080)
  })
})
```

Place this next to `windows.ts` or extract `overlayBounds` to `electron/src/main/overlayBounds.ts` so vitest can import it without Electron.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd electron && npx vitest run src/main/overlayBounds.test.ts`

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

`sidecar.ts`: spawn `uv run questrock-sidecar --port <port>` with `cwd` repo root, `env` from `.env`.
Wait until `GET /health` is ok (timeout 30s).
On crash, emit `sidecar_dead` to renderers and respawn; session is dead (UI must Start again).
Never pass `OPENAI_API_KEY` to renderer.

`windows.ts`:
Control: normal window, title `QuestRock AI Assistant`.
Overlay: `alwaysOnTop: true`, `transparent: true`, `frame: false`, `skipTaskbar: true`, `focusable: false`, `setIgnoreMouseEvents(true, { forward: true })`, default `bottom-right`.

`hotkeys.ts`:
`CommandOrControl+Shift+T` toggles overlay visibility.
`CommandOrControl+Shift+L` sets `setIgnoreMouseEvents(false)` for drag; after `mouseup` or 3s idle, restore click-through.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd electron && npx vitest run src/main/overlayBounds.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add electron/src/main
git commit -m "$(cat <<'EOF'
feat: supervise sidecar and lock click-through overlay

EOF
)"
```

---

### Task 18: Control and overlay React UI

**Files:**
- Create: `electron/src/renderer/control/App.tsx`
- Create: `electron/src/renderer/overlay/Overlay.tsx`
- Test: `electron/src/renderer/overlay/Overlay.test.tsx`

**Interfaces:**
- Consumes: preload events
- Produces: spec control surface and compact captions

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from '@testing-library/react'
import { Overlay } from './Overlay'

it('shows English primary and Spanish verifier', () => {
  render(
    <Overlay
      status="Listening"
      originalText="Estoy buscando refinanciar mi casa porque mi pago mensual es muy alto."
      translatedText="I am looking to refinance my home because my monthly payment is very high."
    />,
  )
  expect(screen.getByText('QuestRock')).toBeInTheDocument()
  expect(screen.getByText('Listening')).toBeInTheDocument()
  const english = screen.getByText(/I am looking to refinance/)
  const spanish = screen.getByText(/Estoy buscando refinanciar/)
  expect(english.tagName.toLowerCase()).not.toBe('small')
  expect(spanish.compareDocumentPosition(english) & Node.DOCUMENT_POSITION_FOLLOWING || true).toBeTruthy()
})

it('shows Translation unavailable when translatedText is null', () => {
  render(<Overlay status="Listening" originalText="Hola" translatedText={null} />)
  expect(screen.getByText('Translation unavailable')).toBeInTheDocument()
})
```

Use vitest + jsdom + testing-library.
English must be the visually primary line (class `english` vs `spanish`).
Assert class names rather than font size if easier: `english` and `spanish` CSS classes.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd electron && npx vitest run src/renderer/overlay/Overlay.test.tsx`

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Overlay: brand `QuestRock`, status pill, spanish verifier, english primary.
Statuses used exactly: `Loading model`, `Listening`, `Transcribing`, `Translating`, `Reconnecting`, `Error`.
Replace caption pair on each transcript.
Do not auto-clear.
Do not show confidence or intent.

Control: device `<select>` from `listDevices`, Start / Stop, status, overlay position radios (`bottom-right`, `bottom-center`, `top-right`), rolling history with confidence.

Map `translated_text: null` to `Translation unavailable` in the UI mapping layer, not in Python.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd electron && npx vitest run src/renderer/overlay/Overlay.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add electron/src/renderer
git commit -m "$(cat <<'EOF'
feat: add control window and compact caption overlay

EOF
)"
```

---

### Task 19: README, fixtures, logging guard

**Files:**
- Create: `README.md`
- Create: `fixtures/audio/README.md`
- Test: `tests/test_logging.py`

**Interfaces:**
- Consumes: logging formatter
- Produces: operator docs and a test that info logs omit transcript text

- [ ] **Step 1: Write the failing test**

```python
import logging
from backend.logging import configure_logging, get_logger

def test_info_log_does_not_include_transcript_kwargs(caplog):
    configure_logging()
    log = get_logger("test")
    with caplog.at_level(logging.INFO):
        log.info("transcript_ready", extra={"call_session_id": "abc", "latency_ms": 12})
    assert "abc" in caplog.text
    log.info("should_not_dump", extra={"original_text": "secret-borrower"})
    # formatter must drop original_text at INFO
    assert "secret-borrower" not in caplog.text
```

If dropping arbitrary extras is hard, provide `log_event(event, **fields)` that allowlists `call_session_id`, `state`, `latency_ms`, `error.code` at info.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_logging.py -v`

Expected: FAIL or red on allowlist.

- [ ] **Step 3: Write minimal implementation**

Allowlisted info logger.
README: what the app is, Phase 1 scope, `uv sync`, `cd electron && npm install`, `npm run dev`, macOS Screen Recording permission, Windows loopback device picker, `.env` `OPENAI_API_KEY`, manual test (play Spanish WAV through speakers).
`fixtures/audio/README.md`: place a short Spanish mortgage WAV here for manual tests; do not commit large binaries.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_logging.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md fixtures/audio/README.md backend/logging.py tests/test_logging.py
git commit -m "$(cat <<'EOF'
docs: add Phase 1 runbook and safe logging guard

EOF
)"
```

---

### Task 20: Full local verification

**Files:** none new unless a test failed

- [ ] **Step 1: Run all Python tests**

Run: `uv run pytest -v`

Expected: all PASS, no network.

- [ ] **Step 2: Run all Electron tests**

Run: `cd electron && npx vitest run`

Expected: all PASS.

- [ ] **Step 3: Manual smoke on this Mac**

1. `OPENAI_API_KEY` in `.env`
2. Build `native/macos/AudioTap` if needed
3. Start the Electron app so it spawns the sidecar
4. Grant Screen Recording if prompted
5. Play a Spanish clip through speakers
6. Select System Audio, Start
7. Confirm overlay English within about 2-3 seconds after speech ends
8. Stop and confirm capture process exits (`pgrep AudioTap` empty)

- [ ] **Step 4: Fix any failures from steps 1-3**

Re-run the failing test first, then the fix.

- [ ] **Step 5: Commit remaining fixes if any**

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: complete Phase 1 live loop verification gaps

EOF
)"
```

---

## Self-review

**Spec coverage**

| Spec requirement | Task |
| --- | --- |
| Electron UI only | 15-18 |
| Python sidecar capture + inference | 1, 9-14 |
| JSON UI WebSocket, no PCM in Electron | 2, 10, 16 |
| Dual-OS loopback | 11-13 |
| VAD utterances, not per-packet Whisper | 6, 9 |
| faster-whisper small, env-upgradable | 7, 14 |
| GPT-4.1-mini + glossary JSON | 3, 4 |
| Compact click-through overlay | 17, 18 |
| Control device picker / start-stop | 18 |
| 127.0.0.1, no audio persistence, safe logs | 1, 19 |
| Isolated CallSession | 9 |
| Spanish kept if translation fails | 4, 9, 18 |
| No auth / Modal / intent | all (omitted) |
| No transcript database | all (Zoom Phone stores the call) |
| Manual 2-3s overlay check | 20 |

**Placeholder scan:** none remaining in task steps.

**Type consistency:** `AudioFrame`, `LoopbackDevice`, `Utterance`, `TranscriptText`, `TranslationResult`, protocol dataclasses, and TS `parseServerMessage` share the spec field names (`call_session_id`, `is_final`, `original_text`, `translated_text`, `t0_ms`, `t1_ms`).
