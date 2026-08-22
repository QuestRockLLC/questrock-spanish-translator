import struct

from audio.resample import to_16k_mono_s16le


def test_stereo_48k_silence_becomes_16k_mono():
    frames_48k_stereo = 4800  # 100 ms
    pcm = struct.pack("<" + "h" * (frames_48k_stereo * 2), *([0] * frames_48k_stereo * 2))
    out = to_16k_mono_s16le(pcm, sample_rate=48000, channels=2)
    assert len(out) == 1600 * 2  # 100 ms at 16 kHz mono s16le


def test_already_16k_mono_is_identity():
    pcm = b"\x00\x01" * 320
    assert to_16k_mono_s16le(pcm, 16000, 1) == pcm
