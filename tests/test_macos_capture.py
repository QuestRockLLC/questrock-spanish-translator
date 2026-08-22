from __future__ import annotations

import io

import pytest

from audio.factory import capture_for_platform
from audio.macos import CapturePermissionError, MacosScreenCaptureKitCapture
from audio.types import AudioFrame, LoopbackDevice


class FakeProc:
    def __init__(self, stdout_bytes: bytes, stderr: bytes = b"", returncode: int | None = None) -> None:
        self.stdout = io.BytesIO(stdout_bytes)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.terminated = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return 0


def test_parses_header_and_emits_16k_frames() -> None:
    header = b'{"sample_rate":48000,"channels":2,"format":"s16le"}\n'
    pcm_48k_stereo_20ms = b"\x00\x00" * (48_000 // 50 * 2)
    proc = FakeProc(header + pcm_48k_stereo_20ms)
    cap = MacosScreenCaptureKitCapture(proc_factory=lambda _cmd: proc)

    assert cap.list_devices() == [LoopbackDevice("system-audio", "System Audio", "loopback")]

    cap.start("system-audio")
    frame = next(cap.frames())

    assert frame == AudioFrame(
        pcm_s16le=b"\x00\x00" * 320,
        sample_rate=16_000,
        channels=1,
        duration_ms=20,
    )
    cap.stop()
    assert proc.terminated is True


def test_raises_capture_permission_error_from_helper_stderr() -> None:
    proc = FakeProc(b"", stderr=b"capture_permission\n", returncode=1)
    cap = MacosScreenCaptureKitCapture(proc_factory=lambda _cmd: proc)

    with pytest.raises(CapturePermissionError):
        cap.start("system-audio")


def test_factory_returns_macos_capture_on_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("audio.factory.sys.platform", "darwin")

    assert isinstance(capture_for_platform(), MacosScreenCaptureKitCapture)
