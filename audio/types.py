from dataclasses import dataclass


@dataclass(frozen=True)
class AudioFrame:
    pcm_s16le: bytes
    sample_rate: int
    channels: int
    duration_ms: int
