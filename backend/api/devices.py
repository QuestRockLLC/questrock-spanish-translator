from collections.abc import Callable

from fastapi import APIRouter

from audio.factory import AudioCapture


def create_devices_router(
    capture_provider: Callable[[], AudioCapture],
) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/devices")
    def list_devices() -> dict[str, list[dict[str, str]]]:
        devices = capture_provider().list_devices()
        return {
            "devices": [
                {"id": device.id, "name": device.name, "kind": device.kind}
                for device in devices
            ]
        }

    return router
