from __future__ import annotations

from typing import Any

from ai.whisper.decode import transcribe_pcm
from ai.whisper.types import TranscriptText, WhisperEngine

_model_cache: dict[str, Any] = {}


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


class WhisperTranscriber:
    def __init__(self, engine: WhisperEngine, model_name: str) -> None:
        self._engine = engine
        self._model_name = model_name

    @classmethod
    def load(cls, model_name: str) -> WhisperTranscriber:
        if model_name not in _model_cache:
            from faster_whisper import WhisperModel

            cuda = _cuda_available()
            device = "cuda" if cuda else "cpu"
            compute_type = "float16" if cuda else "int8"
            _model_cache[model_name] = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )
        return cls(engine=_model_cache[model_name], model_name=model_name)

    def transcribe(self, pcm_s16le: bytes, *, partial: bool = False) -> TranscriptText | None:
        del partial
        return transcribe_pcm(self._engine, pcm_s16le)
