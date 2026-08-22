from __future__ import annotations

import sys
from typing import Iterator, Protocol

from audio.types import AudioFrame, LoopbackDevice


class AudioCapture(Protocol):
    def list_devices(self) -> list[LoopbackDevice]: ...

    def start(self, device_id: str) -> None: ...

    def frames(self) -> Iterator[AudioFrame]: ...

    def stop(self) -> None: ...


def capture_for_platform() -> AudioCapture:
    platform = sys.platform
    if platform == "darwin":
        from audio.macos import MacosScreenCaptureKitCapture

        return MacosScreenCaptureKitCapture()
    if platform == "win32":
        from audio.windows import WindowsWasapiLoopbackCapture

        return WindowsWasapiLoopbackCapture()
    raise RuntimeError(f"unsupported platform: {platform}")
