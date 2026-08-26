# Real-time captions: current limits and next steps

## Why local Whisper feels slow

The current pipeline is:

1. Capture loopback audio locally
2. Every ~400 ms, run **local Whisper** on the last ~1.8 s of audio
3. Send the Spanish text to **OpenAI** for English translation
4. Push updates to the overlay

That design cannot match TV-style live captions on a Mac/PC CPU because:

- Whisper is a batch model, not a true streaming ASR engine
- Each partial pass re-decodes audio and costs hundreds of milliseconds to seconds on CPU
- OpenAI translation adds another network round trip
- `tiny` and `small` differ in accuracy, but both hit the same **architecture ceiling**

So if English still lags speech by 2-4 seconds after these UI fixes, that is expected on local CPU.

## What we ship in Phase 1 now

- Live overlay stack (max **5** lines, newest at bottom, older lines scroll off with animation)
- Spanish appears first on the active line; English replaces it when translation returns
- Partial translation runs in parallel again (does not block the next Whisper pass)
- Shorter silence window (**450 ms**) to commit a phrase faster

`WHISPER_MODEL=small` is still the recommended local default.

## Recommended path to true real-time

Ranked by impact vs effort for QuestRock:

### Option A - Modal GPU Whisper (best fit for current codebase)

Keep the same Python sidecar, move inference to a GPU worker on Modal.

- **Pros:** Minimal Electron change; 5-10× faster partial decode; reuses glossary + translator
- **Cons:** Needs network; small per-minute cost; build auth for audio upload

This matches the existing Phase 3 roadmap item.

### Option B - Streaming STT vendor (fastest product result)

Replace local Whisper partials with **Deepgram** or **AssemblyAI** Spanish streaming.

- Interim Spanish tokens in ~200-300 ms
- Translate interim text with `gpt-4.1-mini` (or vendor translation if good enough)
- Local sidecar becomes orchestration + capture only

- **Pros:** Real-time feel; production-grade latency
- **Cons:** Monthly cost; audio leaves the machine (check compliance with QuestRock)

### Option C - OpenAI audio / Realtime API

Send short PCM chunks to OpenAI for transcription + translation in one step.

- **Pros:** Simple mental model; good quality
- **Cons:** Cost; latency varies; less control over mortgage glossary unless prompt-engineered carefully

### Option D - Stay local, accept delay

Keep CPU Whisper for air-gapped / zero cloud capture requirements.

- Only viable if LO accepts 2-4 s caption delay
- Not compatible with "read along in real time" requirement

## Recommendation

1. **Short term (this week):** Use the new scrolling overlay + parallel partial pipeline on `small`.
   If delay is still unacceptable on your hardware, the bottleneck is confirmed as CPU Whisper.

2. **Next build (recommended):** **Modal GPU** for partial Whisper only.
   Finals can stay local or also move to GPU.

3. **If you need sub-second English while speaking:** Plan **Deepgram streaming** as Phase 2.5.
   That is the industry-standard approach for live bilingual captions.

## Decision checklist

| Requirement | Local CPU Whisper | Modal GPU | Deepgram streaming |
|-------------|-------------------|-----------|---------------------|
| Real-time English while speaking | Poor | Good | Best |
| Air-gapped / no cloud audio | Yes | No | No |
| Reuse current code | Yes | High | Medium |
| Mortgage glossary control | Yes | Yes | Yes (via translator) |
| Cost | Free | Low | Medium |

## What to tell loan officers today

Until GPU or streaming STT ships, captions are **assistive**, not simultaneous interpretation.
The overlay shows what was recently said, not word-for-word live dubbing.
