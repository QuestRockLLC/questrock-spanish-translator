# Modal GPU inference for QuestRock

Move Whisper transcription and OpenAI translation off the loan officer laptop onto a Modal GPU worker.
Audio capture and VAD stay local.
Only PCM utterance chunks go to Modal.

The GPU container serves HTTP itself (`POST /v1/caption`).
Whisper and translation run in that same container.
There is no extra hop to a second Modal function.

## One-time setup

### 1. Install Modal CLI and log in

```bash
pip install modal
modal setup
```

Or with uv:

```bash
uv sync --extra modal
uv run modal setup
```

### 2. Create the Modal secret

Store OpenAI and QuestRock auth in Modal (not on the LO machine):

```bash
modal secret create questrock-inference \
  OPENAI_API_KEY=sk-... \
  OPENAI_TRANSLATION_MODEL=gpt-4.1-mini \
  WHISPER_MODEL=small \
  QUESTROCK_MODAL_TOKEN=your-long-random-token
```

Pick any long random string for `QUESTROCK_MODAL_TOKEN`.
The local sidecar sends it as `Authorization: Bearer ...`.

### 3. Deploy the worker

From the repo root:

```bash
uv run --extra modal modal deploy modal/worker.py
```

Modal prints a URL like:

```text
https://your-workspace--questrock-inference-web-app.modal.run
```

### 4. Point the sidecar at Modal

Add to repo-root `.env` (dev) or your cloud config JSON (packaged apps):

```env
QUESTROCK_MODAL_URL=https://your-workspace--questrock-inference-web-app.modal.run
QUESTROCK_MODAL_TOKEN=your-long-random-token
WHISPER_MODEL=small
```

When `QUESTROCK_MODAL_URL` is set:

- Local Whisper model download is skipped
- Local `OPENAI_API_KEY` is not required (OpenAI runs on Modal)
- Start warms the GPU container before the first pause
- Each pause sends one `POST /v1/caption` (transcribe + translate)

Restart the Electron app after changing `.env`.

## Verify

```bash
curl -sS https://YOUR-URL/health
# {"ok":true}
```

Start a call in the app.
The first Start after idle can take 10-20 s (GPU wake + Whisper load).
After that, a caption should return in a couple of seconds.

## Cost

Modal bills GPU time per second while the container is warm.
The worker uses a **T4** GPU and scales down after ~5 minutes idle.
Typical cost is a few cents per call minute.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| First Start is slow | GPU cold start. Wait for Listening, then speak. Later pauses should be fast. |
| Queued utterances, then silence | Restart the app so it uses `/v1/caption` on the GPU web worker. Redeploy if the URL 404s. |
| `401 Missing bearer token` | Set `QUESTROCK_MODAL_TOKEN` in `.env` to match the Modal secret |
| `403 Invalid bearer token` | Token mismatch between `.env` and Modal secret |
| Still downloading Whisper locally | `QUESTROCK_MODAL_URL` missing from sidecar env - restart app |

## Redeploy after code changes

```bash
uv run --extra modal modal deploy modal/worker.py
```

No Electron rebuild needed unless you changed the sidecar client.
