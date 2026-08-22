import pytest

from audio.types import AudioFrame, LoopbackDevice
from tests.fakes import FakeCapture


def test_fake_lists_and_stops():
    frame = AudioFrame(pcm_s16le=b"\x00\x00" * 320, sample_rate=16000, channels=1, duration_ms=20)
    cap = FakeCapture(
        devices=[LoopbackDevice(id="d1", name="Speakers", kind="loopback")],
        frames=[frame],
    )
    assert cap.list_devices()[0].id == "d1"
    cap.start("d1")
    assert list(cap.frames()) == [frame]
    cap.stop()
    assert cap.stopped is True


def test_fake_unknown_device():
    cap = FakeCapture(devices=[], frames=[])
    with pytest.raises(KeyError):
        cap.start("missing")
