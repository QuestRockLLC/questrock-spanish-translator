# QuestRock AI Assistant

Phase 1 local live interpreter for Spanish mortgage calls.

Electron starts a Python sidecar on 127.0.0.1.
The sidecar captures system-audio loopback, transcribes Spanish with faster-whisper, and translates with GPT-4.1-mini using `config/mortgage_glossary.json`.
A click-through overlay shows English as the primary line and Spanish as a verifier.

## Setup

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. `uv sync --extra dev`
3. On macOS: `bash native/macos/build.sh` then enable Screen Recording when prompted.
4. `cd electron && npm install`

## Run

From `electron/`: `npm run dev`

Select the loopback device Zoom Phone (or your speakers) uses.
Press Start Spanish mode.
Play Spanish audio through that output.

Hotkeys: `Cmd/Ctrl+Shift+T` toggles overlay. `Cmd/Ctrl+Shift+L` makes it draggable for 3 seconds.

## Tests

`uv run pytest -v`

`cd electron && npm test`
