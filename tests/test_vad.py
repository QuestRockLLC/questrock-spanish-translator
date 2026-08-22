from audio.types import AudioFrame
from ai.vad.segmenter import Utterance, VadSegmenter


class ScriptedScorer:
    def __init__(self, probs: list[float]) -> None:
        self.probs = list(probs)

    def score(self, chunk: bytes) -> float:
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


def test_speech_then_silence_emits_one_utterance() -> None:
    chunk = b"\x00\x10" * 512
    scores = [0.9] * 3 + [0.0] * (800 // 32)
    scorer = ScriptedScorer(scores)
    vad = VadSegmenter(
        scorer=scorer,
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
    )
    results: list[Utterance] = []
    t = 0
    for _ in scores:
        frame = frame_from_pcm(chunk, t)
        maybe = vad.push(frame)
        if maybe:
            results.append(maybe)
        t += 32

    assert len(results) == 1
    assert results[0].t1_ms - results[0].t0_ms >= 250


def test_silence_only_emits_nothing() -> None:
    chunk = b"\x00\x00" * 512
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.0] * 20),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
    )

    emitted = [vad.push(frame_from_pcm(chunk, i * 32)) for i in range(20)]

    assert all(x is None for x in emitted)


def test_max_cap_emits_before_silence() -> None:
    chunk = b"\x00\x10" * 512
    n = 8_000 // 32 + 2
    vad = VadSegmenter(
        scorer=ScriptedScorer([0.99] * n),
        silence_ms=800,
        max_utterance_ms=8000,
        min_utterance_ms=250,
    )
    results: list[Utterance] = []
    for i in range(n):
        maybe = vad.push(frame_from_pcm(chunk, i * 32))
        if maybe:
            results.append(maybe)

    assert len(results) == 1
    assert results[0].t1_ms - results[0].t0_ms >= 8000


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
    assert vad.push(frame_from_pcm(b"\x00\x00" * 512, 0)) is None
    assert loader_calls == [True]
    assert model.calls == [((512,), 16000)]
