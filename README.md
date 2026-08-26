# QuestRock AI Assistant

Local live captions for Spanish mortgage calls.

The loan officer hears Spanish.
The overlay shows Spanish and English after each short pause (~450 ms silence).
Use `WHISPER_MODEL=small` for production quality.
`tiny` is too inaccurate for live Spanish fragments.

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

Out of Phase 1: Zoom Phone process tap, login, mortgage intent.
This app does not store transcripts. Zoom Phone already does.

## Development

1. Copy `.env.example` to `.env` at the repo root and set `OPENAI_API_KEY`.
2. `uv sync --extra dev`
3. On macOS: `bash native/macos/build.sh`, then enable Screen Recording when prompted (Electron and AudioTap if listed).
4. `cd electron && npm install`
5. From `electron/`: `npm run dev`

Select **System Audio** (Mac) or the WASAPI loopback that matches the speakers/headset.
Press **Start Spanish mode**.
Play Spanish through that output.
Captions appear after each pause (~450 ms silence) or at the 8 s utterance cap.

First Start downloads Whisper `small` from Hugging Face only when Modal is not configured.
Set `QUESTROCK_MODAL_URL` in the repo-root `.env` for local GPU inference (see [docs/MODAL.md](docs/MODAL.md)).
Packaged installers already point at Modal.

## Packaged installers

The `.dmg` / `.exe` already contains Electron, the UI, a PyInstaller sidecar, and a baked `sidecar-config.json` (Modal URL + token).
The loan officer does not install Python, Node, or pip.
The loan officer does not create a `.env` file.

OpenAI keys stay on Modal (`questrock-inference` secret).
They never ship in the installer as a readable `.env`.

Local `npm run dist:mac` / `dist:win` copies `QUESTROCK_MODAL_URL` and `QUESTROCK_MODAL_TOKEN` from your repo-root `.env` into the app bundle at build time.
GitHub Release builds use repository secrets with the same names.

Dev still uses `uv run questrock-sidecar` plus the repo-root `.env`.
Packaged Electron spawns `Contents/Resources/sidecar/questrock-sidecar` (or `.exe` on Windows).

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

Installer: `electron/release/QuestRock AI Assistant-0.2.0-arm64.dmg`

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

Installer: `electron/release/QuestRock-AI-Assistant-Setup-0.2.0.exe`

## Public downloads and updates

This is a desktop app, not a Vercel site.

Installers go to GitHub Releases.
GitHub Pages (`docs/`) at https://abbassaeedza.github.io/questrock-spanish-whispy/ links the latest `.dmg` / `.exe`.
The picker ignores `.blockmap` files so the Download button is a real installer.

Current app version is `0.2.0` (`electron/package.json`, tag `v0.2.0`).

Installed copies check Releases on launch and show **Update now** in the control window.

### Ship a new version

1. Set `version` in `electron/package.json` (must match the tag you will push).
2. Commit.
3. `git tag v0.2.1` (example).
4. `git push origin main v0.2.1`

GitHub Actions builds Mac and Windows with `--publish never`, uploads artifacts, then a **publish** job creates **one** GitHub Release for that tag.
Add GitHub Actions secrets `QUESTROCK_MODAL_URL` and `QUESTROCK_MODAL_TOKEN` so the installer can talk to Modal.
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
