from audio.types import AudioFrame
from ai.vad.segmenter import Utterance, VadSegmenter

SPEECH = b"\x00\x10" * 512
SILENCE = b"\x00\x00" * 512
MID = b"\x00\x04" * 512


class ScriptedScorer:
    def __init__(self, probs: list[float]) -> None:
        self.probs = list(probs)

    def score(self, chunk: bytes) -> float:
        del chunk
        return self.probs.pop(0)


class FakeProbability:
    def item(self) -> float:
        return 0.0


class FakeSileroModel:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[int, ...], int]] = []

    def __call__(self, audio: object, sample_rate: int) -> FakeProbability:
        shape = tuple(int(size) for size in audio.shape)  # type: ignore[attr-defined]
        self.calls.append((shape, sample_rate))
        return FakeProbability()


def frame_from_pcm(pcm: bytes, _t0_ms: int) -> AudioFrame:
    duration_ms = (len(pcm) // 2) * 1000 // 16000
    return AudioFrame(
        pcm_s16le=pcm,
        sample_rate=16000,
        channels=1,
        duration_ms=duration_ms,
    )


def _push_all(vad: VadSegmenter, frames: list[bytes]) -> list[Utterance]:
    finals: list[Utterance] = []
    for i, pcm in enumerate(frames):
        pushed = vad.push(frame_from_pcm(pcm, i * 32))
        finals.extend(pushed.finals)
        if pushed.final and not pushed.finals:
            finals.append(pushed.final)
    return finals


def test_speech_then_silence_emits_one_utterance() -> None:
    silence = 800 // 32
    frames = [SPEECH] * 10 + [SILENCE] * silence
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.9] * len(frames)),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
    )
    results = _push_all(vad, frames)
    assert len(results) == 1
    assert results[0].t1_ms - results[0].t0_ms >= 250


def test_silence_only_emits_nothing() -> None:
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.0] * 20),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
    )
    emitted = [vad.push(frame_from_pcm(SILENCE, i * 32)).final for i in range(20)]
    assert all(x is None for x in emitted)


def test_max_cap_emits_before_silence() -> None:
    n = 8_000 // 32 + 2
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.99] * n),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
    )
    results = _push_all(vad, [SPEECH] * n)
    assert len(results) >= 1
    assert results[0].t1_ms - results[0].t0_ms >= 8000


def test_continuous_speech_emits_partials_before_final() -> None:
    speech_chunks = 6_000 // 32
    silence_chunks = 800 // 32
    frames = [SPEECH] * speech_chunks + [SILENCE] * silence_chunks
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.99] * len(frames)),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
        partial_interval_ms=500,
    )
    partials: list[Utterance] = []
    finals: list[Utterance] = []
    for i, pcm in enumerate(frames):
        pushed = vad.push(frame_from_pcm(pcm, i * 32))
        if pushed.partial:
            partials.append(pushed.partial)
        if pushed.final:
            finals.append(pushed.final)
    assert len(partials) >= 2
    assert len(finals) == 1
    assert partials[-1].t1_ms <= finals[0].t1_ms


def test_second_utterance_emits_after_pause() -> None:
    silence = 800 // 32
    speech = 10
    frames = [SPEECH] * speech + [SILENCE] * silence + [SPEECH] * speech + [SILENCE] * silence
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.9] * len(frames)),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
        partial_interval_ms=0,
    )
    assert len(_push_all(vad, frames)) == 2


def test_flush_emits_open_utterance() -> None:
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.9] * 20),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
        partial_interval_ms=0,
    )
    for i in range(12):
        vad.push(frame_from_pcm(SPEECH, i * 32))
    flushed = vad.flush()
    assert flushed is not None
    assert flushed.t1_ms - flushed.t0_ms >= 250


def test_with_silero_uses_onnx_loader_and_scores_512_samples() -> None:
    model = FakeSileroModel()
    loader_calls: list[bool] = []

    def fake_loader(*, onnx: bool) -> FakeSileroModel:
        loader_calls.append(onnx)
        return model

    vad = VadSegmenter.with_silero(
        silence_ms=800,
        max_utterance_ms=8000,
        loader=fake_loader,
    )

    assert isinstance(vad, VadSegmenter)
    assert vad.push(frame_from_pcm(MID, 0)).final is None
    assert loader_calls == [True]
    assert model.calls == [((512,), 16000)]
