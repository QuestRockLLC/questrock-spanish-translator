# QuestRock AI Assistant

Local live captions for Spanish mortgage calls.

The loan officer hears Spanish.
The overlay shows English (primary) and Spanish (verifier) a couple of seconds after the borrower stops talking.

There is no TTS, login, cloud capture, or Zoom-process tap in this phase.

## What is implemented

- Electron control window plus a click-through overlay (hotkeys `Cmd/Ctrl+Shift+T` and `Cmd/Ctrl+Shift+L`).
- Python FastAPI sidecar on `127.0.0.1` only.
- JSON WebSocket `ws://127.0.0.1:<port>/v1/calls`.
- Electron never handles PCM.
- macOS loopback: Core Audio system tap (`native/macos/AudioTap`, macOS 14.2+). Screen Recording permission is still required.
- Windows loopback: WASAPI via `pyaudiowpatch` (code is in-tree; live proof is still on you).
- Silero VAD, utterance-final faster-whisper `small` (`avg_logprob` confidence), glossary translation with `gpt-4.1-mini`.
- Listening status includes a **signal** percent so you can see capture is not silent.
- Packaged Mac `.dmg` / Windows `.exe` that embed a PyInstaller sidecar.
- Packaged apps check GitHub Releases and show **Update now** (`electron-updater`).
- GitHub Actions on `v*` tags (`.github/workflows/release.yml`).
- Download page under `docs/` for GitHub Pages.

Phase 1 live loop has been run on this Mac (system audio, Spanish video, captions, OpenAI translation).
Windows live loop and a Windows-built installer are not proven here.

Out of Phase 1: Zoom Phone process tap, Modal GPU, Supabase/auth, mortgage intent.

## Development

1. Copy `.env.example` to `.env` at the repo root and set `OPENAI_API_KEY`.
2. `uv sync --extra dev`
3. On macOS: `bash native/macos/build.sh`, then enable Screen Recording when prompted (Electron and AudioTap if listed).
4. `cd electron && npm install`
5. From `electron/`: `npm run dev`

Select **System Audio** (Mac) or the WASAPI loopback that matches the speakers/headset.
Press **Start Spanish mode**.
Play Spanish through that output.
Captions appear after a pause (~800 ms silence) or at the 8 s utterance cap, not while someone is still talking.

First Start downloads Whisper `small` from Hugging Face into the Hugging Face cache (dev) or the app-support `hf/` folder (packaged).

## Packaged installers

The `.dmg` / `.exe` already contains Electron, the UI, and a PyInstaller sidecar (Python, FastAPI, faster-whisper engine, Silero, glossary, and on Mac the AudioTap binary).
The loan officer does not install Python, Node, or pip.

It does not ship Whisper weight files.
The first Start downloads them.

Dev still uses `uv run questrock-sidecar`.
Packaged Electron spawns `Contents/Resources/sidecar/questrock-sidecar` (or `.exe` on Windows).

Build the Mac installer on a Mac.
Build the Windows installer on a Windows PC.
Do not copy a Mac sidecar into a Windows installer.

OpenAI key for packaged apps (same keys as `.env.example`):

- macOS: `~/Library/Application Support/QuestRock AI Assistant/.env`
- Windows: `%APPDATA%\QuestRock AI Assistant\.env`

### macOS

```bash
uv sync --extra packaging --extra dev
cd electron
npm install
npm run dist:mac
```

Installer: `electron/release/QuestRock AI Assistant-0.1.1-arm64.dmg`

The local Mac DMG is unsigned.
First launch: right-click Open.
Enable Screen Recording for QuestRock AI Assistant.

### Windows

On the Windows machine:

```bash
uv sync --extra packaging --extra windows --extra dev
cd electron
npm install
npm run dist:win
```

Installer: `electron/release/QuestRock-AI-Assistant-Setup-0.1.1.exe`

## Public downloads and updates

This is a desktop app, not a Vercel site.

Installers go to GitHub Releases.
GitHub Pages (`docs/`) at https://abbassaeedza.github.io/questrock-spanish-whispy/ links the latest `.dmg` / `.exe`.
The picker ignores `.blockmap` files so the Download button is a real installer.

Current app version is `0.1.1` (`electron/package.json`, tag `v0.1.1`).

Installed copies check Releases on launch and show **Update now** in the control window.

### Ship a new version

1. Set `version` in `electron/package.json` (must match the tag you will push).
2. Commit.
3. `git tag v0.1.2` (example).
4. `git push origin main v0.1.2`

GitHub Actions builds Mac and Windows with `--publish never`, uploads artifacts, then a **publish** job creates **one** GitHub Release for that tag.
Do not let each OS job call `electron-builder --publish always`.
That created two competing `v0.1.0` releases and 404s on installer URLs.

Local `npm run dist:mac` / `dist:win` also use `--publish never`.

Code signing is optional until you are ready to sell.
See [docs/CODE_SIGNING.md](docs/CODE_SIGNING.md).

## Tests

`uv run pytest -v`

`cd electron && npm test`

## License

MIT.
Copyright (c) 2026 Abbas Saeed Zaidi.
See [LICENSE](LICENSE).
