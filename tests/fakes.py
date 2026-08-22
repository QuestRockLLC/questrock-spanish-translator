"""Shared test fakes for later tasks."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from audio.types import AudioFrame, LoopbackDevice


class FakeCapture:
    def __init__(
        self,
        *,
        devices: Sequence[LoopbackDevice],
        frames: Sequence[AudioFrame],
    ) -> None:
        self._devices = list(devices)
        self._frames = list(frames)
        self._started_device_id: str | None = None
        self.stopped = False

    def list_devices(self) -> list[LoopbackDevice]:
        return list(self._devices)

    def start(self, device_id: str) -> None:
        if not any(device.id == device_id for device in self._devices):
            raise KeyError(device_id)
        self._started_device_id = device_id
        self.stopped = False

    def frames(self) -> Iterator[AudioFrame]:
        if self._started_device_id is None:
            return iter(())
        return iter(self._frames)

    def stop(self) -> None:
        self.stopped = True
        self._started_device_id = None
