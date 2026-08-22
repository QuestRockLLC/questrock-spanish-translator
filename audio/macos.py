from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import BinaryIO, Protocol

from audio.resample import TARGET_SAMPLE_RATE, to_16k_mono_s16le
from audio.types import AudioFrame, LoopbackDevice

FRAME_DURATION_MS = 20
HELPER_PATH = Path(__file__).resolve().parent.parent / "native" / "macos" / "AudioTap"


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
        self._build_helper = proc_factory is None
        self._proc: Proc | None = None
        self._sample_rate = 0
        self._channels = 0

    def list_devices(self) -> list[LoopbackDevice]:
        return [LoopbackDevice("system-audio", "System Audio", "loopback")]

    def start(self, device_id: str) -> None:
        if device_id != "system-audio":
            raise KeyError(device_id)
        if self._build_helper and sys.platform == "darwin" and not HELPER_PATH.exists():
            subprocess.run([str(HELPER_PATH.with_name("build.sh"))], check=True)

        self._proc = self._proc_factory([str(HELPER_PATH)])
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
        self._proc = None

    def _raise_for_permission_error(self) -> None:
        if self._proc is not None and b"capture_permission" in self._proc.stderr.read():
            raise CapturePermissionError("macOS screen and system audio capture permission is required")
