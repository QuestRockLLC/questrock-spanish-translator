# QuestRock AI Assistant

Phase 1 local live interpreter for Spanish mortgage calls.

Electron starts a Python sidecar on 127.0.0.1.
The sidecar captures system-audio loopback, transcribes Spanish with faster-whisper, and translates with GPT-4.1-mini using `config/mortgage_glossary.json`.
A click-through overlay shows English as the primary line and Spanish as a verifier.

## Setup (development)

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. `uv sync --extra dev`
3. On macOS: `bash native/macos/build.sh` then enable Screen Recording when prompted.
4. `cd electron && npm install`

## Run (development)

From `electron/`: `npm run dev`

Select the loopback device Zoom Phone (or your speakers) uses.
Press Start Spanish mode.
Play Spanish audio through that output.

Hotkeys: `Cmd/Ctrl+Shift+T` toggles overlay. `Cmd/Ctrl+Shift+L` makes it draggable for 3 seconds.

## Packaged installers

The `.dmg` / `.exe` is a full app, not a thin downloader.

It already contains Electron, the UI, and a PyInstaller sidecar (Python runtime, FastAPI, faster-whisper engine, Silero VAD, glossary, and on Mac the AudioTap helper).
The loan officer does not install Python, Node, or pip.

It does **not** ship the Whisper weight files.
The first **Start Spanish mode** downloads faster-whisper `small` from Hugging Face into the app-support folder (`hf/` under user data) and reuses it after that.
Translation calls OpenAI over the network using `OPENAI_API_KEY`.
That is an API call, not an installer step.

Put the OpenAI key in an `.env` file (same keys as `.env.example`) at:

- macOS: `~/Library/Application Support/QuestRock AI Assistant/.env`
- Windows: `%APPDATA%\\QuestRock AI Assistant\\.env`

Build the Mac installer on a Mac.
Build the Windows installer on a Windows PC.
Do not copy a Mac sidecar into a Windows installer.

### macOS

```bash
uv sync --extra packaging --extra dev
cd electron
npm install
npm run dist:mac
```

Installer: `electron/release/QuestRock AI Assistant-0.1.0-arm64.dmg`

Enable Screen Recording for QuestRock AI Assistant after first launch.

### Windows

On the Windows machine:

```bash
uv sync --extra packaging --extra windows --extra dev
cd electron
npm install
npm run dist:win
```

Installer: `electron/release/QuestRock-AI-Assistant-Setup-0.1.0.exe`

## Public downloads and updates

This is a desktop app. It is not hosted on Vercel.

GitHub stores the Mac `.dmg` and Windows `.exe`.
A GitHub Pages page at https://abbassaeedza.github.io/questrock-spanish-whispy/ detects the OS and links the right installer.
Installed copies check GitHub Releases on launch and show **Update now** in the control window.

### Ship a new version

1. Set `version` in `electron/package.json` (example `0.2.0`).
2. Commit.
3. `git tag v0.2.0`
4. `git push origin main v0.2.0`

GitHub Actions builds both OS installers and attaches them to that tag's Release.
Local `npm run dist:mac` / `dist:win` stay unpublished (`--publish never`).

Code signing is optional for now. See [docs/CODE_SIGNING.md](docs/CODE_SIGNING.md).

## License

MIT. Copyright (c) 2026 Abbas Saeed Zaidi. See [LICENSE](LICENSE).

## Tests

`uv run pytest -v`

`cd electron && npm test`
