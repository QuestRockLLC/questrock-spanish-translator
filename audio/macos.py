from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from typing import BinaryIO, Protocol

from audio.resample import TARGET_SAMPLE_RATE, to_16k_mono_s16le
from audio.types import AudioFrame, LoopbackDevice
from backend.paths import macos_helper_path

FRAME_DURATION_MS = 20
PERMISSION_MESSAGE = (
    "macOS Screen Recording permission is required for system audio. "
    "Open System Settings > Privacy & Security > Screen Recording, "
    "enable it for Electron or Terminal, then click Start again."
)


class CapturePermissionError(RuntimeError):
    pass


class Proc(Protocol):
    stdout: BinaryIO
    stderr: BinaryIO

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


ProcFactory = Callable[[list[str]], Proc]


def _start_process(command: list[str]) -> Proc:
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class MacosScreenCaptureKitCapture:
    def __init__(self, proc_factory: ProcFactory | None = None) -> None:
        self._proc_factory = proc_factory or _start_process
        self._build_helper = proc_factory is None and not getattr(sys, "frozen", False)
        self._proc: Proc | None = None
        self._sample_rate = 0
        self._channels = 0
        self._stderr = b""
        self._stderr_thread: threading.Thread | None = None

    def list_devices(self) -> list[LoopbackDevice]:
        return [LoopbackDevice("system-audio", "System Audio", "loopback")]

    def start(self, device_id: str) -> None:
        if device_id != "system-audio":
            raise KeyError(device_id)
        helper = macos_helper_path()
        if self._build_helper and sys.platform == "darwin":
            source = helper.with_suffix(".swift")
            stale = (
                helper.is_file()
                and source.is_file()
                and source.stat().st_mtime > helper.stat().st_mtime
            )
            if not helper.is_file() or stale:
                subprocess.run([str(helper.with_name("build.sh"))], check=True)
            if not helper.is_file():
                raise RuntimeError("AudioTap helper is missing after build")

        self._stderr = b""
        self._proc = self._proc_factory([str(helper)])
        self._stderr_thread = threading.Thread(
            target=self._pump_stderr,
            args=(self._proc.stderr,),
            daemon=True,
        )
        self._stderr_thread.start()
        header_bytes = self._proc.stdout.readline()
        if not header_bytes:
            self._raise_for_permission_error()
            raise RuntimeError("AudioTap exited before sending its format header")

        header = json.loads(header_bytes)
        if header.get("format") != "s16le":
            raise RuntimeError("AudioTap returned an unsupported audio format")
        self._sample_rate = int(header["sample_rate"])
        self._channels = int(header["channels"])

    def frames(self) -> Iterator[AudioFrame]:
        if self._proc is None:
            raise RuntimeError("capture has not started")

        chunk_size = self._sample_rate * self._channels * 2 * FRAME_DURATION_MS // 1000
        while pcm := self._proc.stdout.read(chunk_size):
            if len(pcm) != chunk_size:
                break
            yield AudioFrame(
                pcm_s16le=to_16k_mono_s16le(pcm, self._sample_rate, self._channels),
                sample_rate=TARGET_SAMPLE_RATE,
                channels=1,
                duration_ms=FRAME_DURATION_MS,
            )
        self._raise_for_permission_error()

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        self._proc.wait(timeout=5)
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=1)
            self._stderr_thread = None
        self._proc = None

    def _pump_stderr(self, stream: BinaryIO) -> None:
        try:
            self._stderr = stream.read() or b""
        except OSError:
            self._stderr = b""

    def _raise_for_permission_error(self) -> None:
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=1)
        if b"capture_permission" in self._stderr:
            raise CapturePermissionError(PERMISSION_MESSAGE)
