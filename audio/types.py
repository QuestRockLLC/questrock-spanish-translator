from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LoopbackDevice:
    id: str
    name: str
    kind: Literal["loopback"]


@dataclass(frozen=True)
class AudioFrame:
    pcm_s16le: bytes
    sample_rate: int
    channels: int
    duration_ms: int
