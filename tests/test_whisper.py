import numpy as np

from ai.whisper.transcriber import TranscriptText, WhisperTranscriber


class FakeEngine:
    def __init__(self, text: str, avg_log_prob: float) -> None:
        self.text = text
        self.avg_log_prob = avg_log_prob
        self.calls: list[dict[str, object]] = []
        self.last_audio: np.ndarray | None = None

    def transcribe(self, audio: np.ndarray, **kwargs: object) -> tuple[object, None]:
        self.calls.append(dict(kwargs))
        self.last_audio = audio
        segment = type(
            "S", (), {"text": self.text, "avg_log_prob": self.avg_log_prob}
        )()
        return iter([segment]), None


class MultiSegmentEngine:
    def __init__(self, segments: list[tuple[str, float]]) -> None:
        self.segments = segments
        self.calls: list[dict[str, object]] = []

    def transcribe(self, audio: np.ndarray, **kwargs: object) -> tuple[object, None]:
        self.calls.append(dict(kwargs))
        items = [
            type("S", (), {"text": text, "avg_log_prob": prob})()
            for text, prob in self.segments
        ]
        return iter(items), None


def test_joins_segments_and_clamps_confidence() -> None:
    engine = FakeEngine("  Hola mundo  ", avg_log_prob=-0.2)
    t = WhisperTranscriber(engine=engine, model_name="small")
    pcm = np.zeros(16000, dtype=np.int16).tobytes()
    result = t.transcribe(pcm)
    assert result == TranscriptText(text="Hola mundo", confidence=result.confidence)
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence == 0.8
    assert engine.calls[0]["language"] == "es"
    assert engine.calls[0]["vad_filter"] is False
    assert engine.calls[0]["beam_size"] == 1
    assert engine.calls[0]["best_of"] == 1
    assert engine.last_audio is not None
    assert engine.last_audio.dtype == np.float32
    assert float(engine.last_audio.min()) >= -1.0
    assert float(engine.last_audio.max()) <= 1.0


def test_blank_text_returns_none() -> None:
    t = WhisperTranscriber(engine=FakeEngine("   ", -0.1), model_name="small")
    pcm = np.zeros(16000, dtype=np.int16).tobytes()
    assert t.transcribe(pcm) is None


def test_joins_multiple_segments() -> None:
    engine = MultiSegmentEngine([("Hola ", -0.2), ("mundo", -0.4)])
    t = WhisperTranscriber(engine=engine, model_name="small")
    pcm = np.zeros(16000, dtype=np.int16).tobytes()
    result = t.transcribe(pcm)
    assert result is not None
    assert result.text == "Hola mundo"
    assert result.confidence == 0.7


def test_reads_faster_whisper_avg_logprob_field() -> None:
    class Engine:
        def transcribe(self, audio: np.ndarray, **kwargs: object) -> tuple[object, None]:
            del audio, kwargs
            segment = type("S", (), {"text": "Hola", "avg_logprob": -0.2})()
            return iter([segment]), None

    t = WhisperTranscriber(engine=Engine(), model_name="small")
    pcm = np.zeros(16000, dtype=np.int16).tobytes()
    assert t.transcribe(pcm) == TranscriptText(text="Hola", confidence=0.8)


def test_confidence_clamped_at_bounds() -> None:
    low = WhisperTranscriber(
        engine=FakeEngine("hola", avg_log_prob=-5.0), model_name="small"
    )
    high = WhisperTranscriber(
        engine=FakeEngine("hola", avg_log_prob=2.0), model_name="small"
    )
    pcm = np.zeros(16000, dtype=np.int16).tobytes()
    assert low.transcribe(pcm) == TranscriptText(text="hola", confidence=0.0)
    assert high.transcribe(pcm) == TranscriptText(text="hola", confidence=1.0)
