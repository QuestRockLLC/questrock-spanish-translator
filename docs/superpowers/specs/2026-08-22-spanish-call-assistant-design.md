# QuestRock Spanish Call Assistant - Phase 1 Design

Date: 2026-08-22
Status: Phase 1 Mac live loop works (capture, Whisper, glossary translation).
Local unsigned Mac DMG packaging works.
App version `0.1.1` (tags `v0.1.0`, `v0.1.1`).
Release CI builds both OS artifacts then creates a single GitHub Release per tag.
Windows live loop is not proven on this machine.
Signing is not done.
Product: QuestRock AI Assistant (QuestRock LLC)

This spec is the locked design for Phase 1 of the Spanish Call Assistant.
Later phases (Zoom-specific capture, Modal workers, login, mortgage intent) must plug into the seams defined here.
They are out of scope for the first implementation.
This product never stores transcripts.
Zoom Phone already stores the call.

## 1. Problem

A Spanish-speaking loan officer at QuestRock takes Zoom Phone calls with Spanish-speaking borrowers.
She can speak Spanish, but she is not native-level.
She needs a live comprehension layer: hear the borrower, see accurate English on screen within about 2-3 seconds, and keep talking in Spanish herself.

This is not voice-to-voice translation.
The assistant does not speak.

Success for Phase 1: pick a loopback device, start a session, play Spanish audio through speakers, and see Spanish plus glossary-aware English on a click-through overlay within about 2-3 seconds, on both macOS and Windows.

## 2. Locked decisions

- Both macOS and Windows are production platforms.
- Capture is a first-class `AudioCapture` interface with a native backend per OS.
- Phase 1 uses real system-audio loopback on both OSes (play audio through speakers; the app captures that output).
- Two windows: a control window plus a click-through overlay that never steals Zoom focus.
- Overlay layout: compact captions (English primary, Spanish as a verifier line, default bottom-right).
- Electron is UI only.
- A local Python FastAPI sidecar owns loopback capture, VAD, Whisper, and translation.
- The UI WebSocket is JSON only.
- Electron never sends or receives PCM.
- Whisper and OpenAI run on completed utterances (VAD), not on every audio packet.
- Audio streams continuously in ~20 ms PCM frames.
- Phase 1 has no auth, no cloud, and no intent engine.
- Transcripts are never persisted in this product (any phase). Zoom Phone is the system of record.
- Inference stack is faster-whisper `small` plus OpenAI `gpt-4.1-mini`.
- Mortgage glossary lives in external JSON.
- No audio is written to disk.

## 3. Non-goals (Phase 1)

- Zoom Phone process-specific tap (Phase 2).
- Modal GPU workers (Phase 3).
- Login / LO identity (Phase 4). No user database is required for captions.
- Intent detection and suggested follow-up questions (Phase 5).
- Durable transcript, call-session, or audio storage in any phase. Zoom Phone already stores the call.
- TTS / spoken translation.
- Chromium `getDisplayMedia` / `desktopCapturer` audio.
- A second ASR engine (whisper.cpp, Deepgram, AssemblyAI).
- Always-on GPU.

Rejected alternatives, recorded so they are not revived without a new design:

- Electron native capture addons: lower capture latency, much worse Electron ABI maintenance.
- Chromium display-media capture: permission prompts, weak Zoom Phone path.
- Managed streaming ASR: better ops for 150 minutes/month, but the product wants an owned Whisper pipeline and Modal later.

## 4. System architecture

Two local processes, one UI protocol, one internal inference seam.

```text
Loan officer
    |
    v
Electron (UI shell)
  Control window     Overlay window (click-through)
  Main process: spawn sidecar, open WebSocket, never touches PCM
    |
    |  WebSocket JSON  ws://127.0.0.1:<port>/v1/calls
    v
Python sidecar (FastAPI; `uv` in dev, PyInstaller in the installer)
  SessionManager -> CallSession (isolated per call_session_id)
    AudioCapture (WASAPI | Core Audio system tap)
    VadSegmenter (Silero)
    WhisperTranscriber (faster-whisper small, warm for the call)
    MortgageTranslator (OpenAI + glossary)
```

Phase 1 runs gateway and worker in one process.
`CallSession` is the isolation boundary: capture, VAD state, Whisper, and translator belong to the session.
No global transcriber exists.

Phase 3 does not rewrite Electron.
It changes `GATEWAY_URL` and moves `WhisperTranscriber` + `MortgageTranslator` onto a Modal GPU container.
Capture stays on the loan officer machine.
The internal seam for that move is `AudioIngress`, an in-process PCM consumer in Phase 1 and a binary WebSocket to Modal in Phase 3.
VAD should remain local in Phase 3 so silence is not shipped to GPU.

## 5. Latency budget

Target: about 2-3 seconds from end of borrower speech to English on screen.

| Stage | Budget |
| --- | --- |
| Loopback capture + buffering | 100-300 ms |
| VAD endpoint (silence) | 700-900 ms |
| faster-whisper `small` on one utterance | 500-1000 ms |
| OpenAI translation | 300-1000 ms |
| UI update | <100 ms |

Do not chase sub-second latency if it cuts words or accuracy.
Utterance-final translation is the source of truth.
Phase 1 does not emit partial (non-final) transcripts.

Whisper model load happens at session start, not on the first utterance.
The first Start may take several seconds while the model loads.
The overlay status must show that (for example `Loading model`), then `Listening`.
After load, the model stays warm until `stop_call`.

## 6. Components

### 6.1 Electron main

- Spawn and supervise the Python sidecar with `uv run`.
- Allocate an ephemeral local port.
- Create the control `BrowserWindow` and the overlay `BrowserWindow`.
- Open the UI WebSocket and bridge events to both renderers via IPC.
- Restart the sidecar if it exits unexpectedly.
- On sidecar crash: mark the session dead and require the user to press Start again.

Overlay window properties:

- Always on top.
- Frameless, transparent background.
- Visible on all workspaces if the platform allows it.
- `setIgnoreMouseEvents(true, { forward: true })` so Zoom keeps focus.
- Default position: bottom-right of the primary display, compact width (~380-420 px).

Hotkeys (global while the app is running):

- `Cmd/Ctrl+Shift+T`: toggle overlay visibility.
- `Cmd/Ctrl+Shift+L`: make the overlay interactive for dragging; click-through resumes after drag end or after 3 seconds idle.

Control window owns position presets: bottom-right, bottom-center, top-right.

### 6.2 Control renderer

Interactive surface only.

- Loopback device picker, populated from `GET /v1/devices`.
- Start Spanish mode / Stop.
- Connection and session status.
- Rolling transcript history (Spanish + English + confidence).
- Overlay position presets.

No login screen in Phase 1.

### 6.3 Overlay renderer

Display-only compact captions:

- Brand: `QuestRock`
- Status pill: `Loading model` | `Listening` | `Transcribing` | `Translating` | `Reconnecting` | `Error`
- Spanish verifier line (smaller, secondary color)
- English live line (larger, primary)
- Do not show confidence on the overlay (it lives in the control history)
- Do not show AI insight / intent (Phase 5)

On a new final transcript, replace the current caption pair immediately.
The last pair stays visible until Stop or a newer transcript arrives.
Do not auto-clear captions.

### 6.4 FastAPI sidecar

HTTP:

- `GET /health` → `{ "ok": true }`
- `GET /v1/devices` → `{ "devices": [{ "id": string, "name": string, "kind": "loopback" }] }`

WebSocket:

- `WS /v1/calls`

One WebSocket equals at most one active `CallSession`.
A second `start_call` on the same socket stops the previous session first.

### 6.5 SessionManager and CallSession

`SessionManager.create(device_id, language) -> CallSession`

`CallSession` owns:

- `call_session_id` (UUID4)
- selected device
- capture task
- VAD state
- Whisper model handle (process-level cache allowed; see below)
- translation client
- outbound event queue to the WebSocket

Whisper weights may be cached at process level so a second call in the same sidecar life does not reload from disk.
Session isolation still requires per-session VAD state and a single active decoder at a time in Phase 1 (one LO, one call).
The public API must not expose a global "current transcript".
Everything is keyed by `call_session_id`.

### 6.6 AudioCapture

```python
class LoopbackDevice:
    id: str
    name: str
    kind: Literal["loopback"]

class AudioFrame:
    pcm_s16le: bytes   # 16 kHz mono signed 16-bit little-endian
    sample_rate: int    # always 16000
    channels: int       # always 1
    duration_ms: int    # ~20

class AudioCapture(Protocol):
    def list_devices(self) -> list[LoopbackDevice]: ...
    def start(self, device_id: str) -> None: ...
    def frames(self) -> Iterator[AudioFrame]: ...
    def stop(self) -> None: ...
```

Windows backend: WASAPI loopback in-process (shared mode).
Enumerate render devices and expose each as a loopback source.
The user picks the same output device Zoom Phone is using (headset vs speakers).

macOS backend: Core Audio system tap helper (`CATapDescription` global stereo tap, macOS 14.2+).
A small native helper (`native/macos/AudioTap`) captures system audio and writes raw PCM16 to stdout.
Python supervises the process and resamples to 16 kHz mono if the helper emits another rate.
The helper still requests Screen Recording permission (TCC for system audio).
`list_devices` on macOS Phase 1 returns at least one device: `system-audio` / `System Audio`.

Capture backends resample to 16 kHz mono before emitting frames.
Do not make Whisper or VAD deal with 48 kHz stereo.

### 6.7 VadSegmenter

Silero VAD on 16 kHz mono.

Utterance start: speech probability crosses threshold.
Utterance end: ~800 ms of silence (configurable, default 800, range 700-900), or 8.0 s maximum duration, whichever first.

Emit `Utterance(pcm_s16le, t0_ms, t1_ms)` only.
Do not emit overlapping partial windows in Phase 1.

Drop utterances shorter than 250 ms.

### 6.8 WhisperTranscriber

- Library: faster-whisper
- Model: `small`
- `language="es"`
- `vad_filter=False` (VAD already ran)
- Beam size 1 (latency)
- Device: CUDA if present, else CPU
- Compute type: `float16` on CUDA, `int8` on CPU

Return `{ text, confidence }` where confidence is a 0-1 value derived from average log probability, clamped.
Empty or whitespace-only text is discarded (no translation call, no UI event).

Model id is configurable via `WHISPER_MODEL` (default `small`) so `medium` / `large-v3` are an env change, not a rewrite.

### 6.9 MortgageTranslator

Model: `gpt-4.1-mini`, overridable via `OPENAI_TRANSLATION_MODEL`.
Timeout: 8 seconds.
Temperature: 0.

System prompt requirements:

- Translate a Spanish mortgage borrower conversation into natural English.
- Preserve meaning.
- Use US mortgage terminology.
- Do not hallucinate content that was not said.
- Preserve numbers, loan amounts, interest rates, and dates exactly.

Glossary file: `config/mortgage_glossary.json`.
The translator loads it at process start and injects it into the system prompt.
Do not hardcode term pairs in Python or TypeScript.

Glossary schema:

```json
{
  "terms": [
    {
      "en": "cash-out refinance",
      "es": ["refinanciamiento con retiro de efectivo", "sacar dinero de mi casa"],
      "preferred_en": "cash-out refinance"
    }
  ]
}
```

Required seed terms:

- cash-out refinance / refinanciamiento con retiro de efectivo
- loan officer / oficial de préstamos
- closing costs / costos de cierre
- interest rate / tasa de interés
- monthly payment / pago mensual
- down payment / pago inicial
- preapproval / preaprobación

If OpenAI fails or times out, return the Spanish transcript with `translated_text=null` and let the UI show `Translation unavailable`.
Never drop the original.

## 7. UI WebSocket protocol (version 1)

All messages are JSON objects with a `type` field.
`protocol_version` is `1`.

Client → server:

```json
{ "type": "hello", "protocol_version": 1 }
{ "type": "start_call", "device_id": "system-audio", "language": "spanish" }
{ "type": "stop_call" }
```

Server → client:

```json
{ "type": "session_started", "call_session_id": "uuid", "device_id": "system-audio" }
{ "type": "status", "call_session_id": "uuid", "state": "idle|loading_model|listening|transcribing|translating|error", "detail": "optional safe string" }
{ "type": "transcript", "call_session_id": "uuid", "id": "uuid", "is_final": true, "original_language": "es", "original_text": "...", "translated_text": "...", "confidence": 0.92, "t0_ms": 1200, "t1_ms": 4100 }
{ "type": "error", "code": "capture_permission|device_missing|whisper_failed|sidecar_dead|protocol", "message": "safe operator message" }
```

Rules:

- `is_final` is always `true` in Phase 1.
- `error.message` must never contain borrower speech.
- Unknown client `type` → `error` with code `protocol`.
- `hello` must precede `start_call`.
- Closing the socket is equivalent to `stop_call`.
- After stop, capture must end (no orphaned loopback).

## 8. Control and overlay copy

Control window title: `QuestRock AI Assistant`

Overlay brand: `QuestRock`

Status strings (exact):

- `Loading model`
- `Listening`
- `Transcribing`
- `Translating`
- `Reconnecting`
- `Error`

Translation failure English line: `Translation unavailable`

## 9. Security

Mortgage calls contain borrower PII.

Phase 1 controls:

- Sidecar binds `127.0.0.1` only.
- Transport is local WebSocket.
- `OPENAI_API_KEY` lives in `.env`, loaded only in the sidecar.
- Renderer processes never receive the API key.
- No audio files, no wav dumps, no debug recordings unless `QUESTROCK_DEBUG_AUDIO=1` (off by default; if ever enabled, files go to a temp dir and are deleted on session end).
- No durable transcript store. Overlay captions are ephemeral. Zoom Phone keeps the call recording/transcript.
- Structured JSON logs.
- Log fields at info: `call_session_id`, `state`, `latency_ms`, `error.code`.
- Do not log `original_text` or `translated_text` at info.
- Debug logging of transcript text is allowed only when `QUESTROCK_LOG_TRANSCRIPTS=1` and must be documented as unsafe for production.

Phase 3 will use `wss://` to Modal and Modal secrets.
That is not implemented now.

## 10. Error handling

| Failure | Behavior |
| --- | --- |
| No loopback devices | Control shows an error. Start is disabled. |
| macOS Screen Recording denied | `error.code=capture_permission` with instructions to enable Screen Recording for the helper. |
| Windows device in exclusive use / missing | `error.code=device_missing` |
| Whisper load or runtime failure | Session errors. Do not stay in Listening. |
| OpenAI timeout or HTTP error | Spanish still shown. English = `Translation unavailable`. |
| UI WebSocket drop | Overlay `Reconnecting`. Sidecar stops capture immediately. |
| Sidecar process crash | Electron respawns sidecar. Session is dead. User must Start again. |

Spanish transcript is never discarded because translation failed.

## 11. Testing

Tests must pass with no network and no real database.

Python (pytest, `uv run pytest`):

- Glossary loader: seed terms present, prompt contains preferred English.
- VAD: fixture PCM with speech then silence yields one utterance; silence-only yields none; 8 s cap splits.
- WS schema: encode/decode of every v1 message type; unknown type → protocol error.
- Translator: mocked OpenAI returns glossary-aware English; mocked timeout returns `translated_text=null` and keeps Spanish.
- Session: `start_call` then `stop_call` stops capture (mocked `AudioCapture`).

Electron:

- Protocol types compile under `strict`.
- Overlay renders English primary / Spanish secondary from a fixture event (unit or component test).

Manual acceptance (Phase 1 done):

1. Launch the app on macOS.
2. Play a Spanish mortgage sample through speakers (a WAV in `fixtures/audio/` is enough).
3. Select System Audio, press Start, wait until status is `Listening`.
4. Overlay shows Spanish + English within about 2-3 seconds after speech ends.
5. Repeat on Windows with WASAPI loopback of the playback device.

## 12. Repository layout

Implement at the workspace root (this repo), not a nested extra project folder.

```text
electron/                 # electron-vite, React, TypeScript strict
  main/
  renderer/
    control/
    overlay/
backend/                  # FastAPI sidecar
  api/
  websocket/
  sessions/
audio/                    # AudioCapture protocol + OS backends
ai/
  whisper/
  translation/
config/
  mortgage_glossary.json
native/macos/             # Core Audio tap PCM helper (AudioTap.swift)
packaging/                # PyInstaller spec and sidecar bundle script
.github/workflows/        # v* tag release builds
docs/                     # GitHub Pages download page + CODE_SIGNING.md
fixtures/audio/           # Spanish mortgage sample WAV(s) for manual tests
tests/
docs/superpowers/specs/
```

Python packaging: `uv` with `pyproject.toml`.
No `requirements.txt` as the primary lockfile.
Node: workspace under `electron/` with TypeScript `strict: true`.

## 13. Configuration

Environment variables (sidecar):

| Name | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | none, required to translate | OpenAI auth |
| `OPENAI_TRANSLATION_MODEL` | `gpt-4.1-mini` | Translation model |
| `WHISPER_MODEL` | `small` | faster-whisper model id |
| `VAD_SILENCE_MS` | `800` | Utterance end silence |
| `VAD_MAX_UTTERANCE_MS` | `8000` | Utterance cap |
| `QUESTROCK_LOG_TRANSCRIPTS` | `0` | Unsafe debug |
| `QUESTROCK_DEBUG_AUDIO` | `0` | Unsafe wav dump |

Electron:

| Name | Default | Purpose |
| --- | --- | --- |
| `GATEWAY_URL` | `ws://127.0.0.1:<spawned-port>/v1/calls` | UI gateway |
| `SIDECAR_COMMAND` | Dev: `uv run questrock-sidecar`. Packaged: extraResources `sidecar/questrock-sidecar` | How main spawns Python |

## 14. Risks

1. macOS system-audio capture requires Screen Recording permission and a native helper.
   Phase 1 uses a Core Audio global system tap, not ScreenCaptureKit.
   Phase 2 should switch to a per-process tap on the Zoom Phone process without changing `AudioCapture`.
2. Loopback captures whatever the selected output device plays.
   If the LO's headset is not the selected device, the overlay will be silent or will capture the wrong mix.
   The device picker is part of the product, not a developer tool.
3. Speaker loopback will also capture the LO if she is on speakerphone.
   That is acceptable for Phase 1.
   Phase 2 should prefer Zoom's incoming audio path when the OS allows it.
4. faster-whisper on Mac CPU is slower than CUDA.
   `small` + utterance segmentation is the mitigation.
   Do not switch engines.
5. OpenAI variability can blow the latency budget.
   Keep temperature 0, a short prompt, and the Spanish-fallback path.
6. Mixed Spanish/English borrower speech will be forced through `language="es"`.
   Accept mistranscription of English tokens in Phase 1 rather than auto language detect (auto-detect adds latency and flicker).

## 15. Phase 1 done when

- Control window lists loopback devices on macOS and Windows.
- Start creates an isolated `call_session_id` and loads Whisper once.
- Playing Spanish audio through the selected output produces a compact overlay caption: Spanish verifier + English primary, in about 2-3 seconds after the utterance ends.
- Translation uses the mortgage glossary (cash-out example translates as cash-out, not "take money from my house").
- Stop releases the capture device.
- No audio or transcripts are stored.
- No auth, Modal, or intent code ships.

## 16. Progress (2026-08-26)

Done on this Mac:

- Live loop: device list, Start/Stop, Core Audio tap capture, VAD, Whisper `small`, glossary translation, overlay captions.
- Listening status reports capture signal level.
- Local unsigned `npm run dist:mac` DMG (sidecar is PyInstaller onedir + AudioTap).
- GitHub Release auto-update (tag workflow, Pages download page, in-app Update now). Unsigned.
- Tags `v0.1.0` and `v0.1.1`.
- CI: Mac/Windows package with `--publish never`, then one `gh release create` job so installer URLs stay stable.

Still open for Phase 1:

- Windows live-loop proof (run `npm run dist:win` on a Windows PC and play Spanish through speakers).
- `tests/test_logging.py` (Task 19 logging guard).
- Confirm the `v0.1.1` Actions run attached both OS installers to one Release.
- Code signing / notarization (`docs/CODE_SIGNING.md`).

Later phases (not started): Zoom process tap (2), Modal GPU (3), login if needed (4), mortgage intent (5).
Never: a QuestRock transcript database. Zoom Phone already stores the call.
