from fastapi import APIRouter

from backend.settings import Settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    settings = Settings()
    modal = bool(settings.questrock_modal_url.strip())
    return {
        "ok": True,
        "inference": "modal" if modal else "local",
        "modal_url": settings.questrock_modal_url.strip() or None,
    }
