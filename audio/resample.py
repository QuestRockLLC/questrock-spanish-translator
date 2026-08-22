import numpy as np
import soxr

TARGET_SAMPLE_RATE = 16_000


def to_16k_mono_s16le(pcm: bytes, sample_rate: int, channels: int) -> bytes:
    if sample_rate == TARGET_SAMPLE_RATE and channels == 1:
        return pcm

    samples = np.frombuffer(pcm, dtype=np.int16)
    if channels > 1:
        frames = samples.reshape(-1, channels).astype(np.float32)
        mono = frames.mean(axis=1)
    else:
        mono = samples.astype(np.float32)

    mono /= np.iinfo(np.int16).max
    resampled = soxr.resample(mono, sample_rate, TARGET_SAMPLE_RATE)
    clipped = np.clip(resampled * np.iinfo(np.int16).max, np.iinfo(np.int16).min, np.iinfo(np.int16).max)
    return clipped.astype(np.int16).tobytes()
