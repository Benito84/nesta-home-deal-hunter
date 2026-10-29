"""
Router Systemowy: Wersja aplikacji (SSOT) i diagnostyka.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (Sekcja 3.3).
"""

from fastapi import APIRouter
from app.core.config import settings
from app.schemas.listing import AppVersionResponse

router = APIRouter(tags=["System"])

@router.get("/api/version", response_model=AppVersionResponse)
def get_version():
    """Pojedyncze Źródło Prawdy Wersji dla aplikacji i webhooków wdrożeniowych"""
    return AppVersionResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment="DEV" if settings.is_dev_env else "PROD",
        tracker_env=settings.TRACKER_ENV,
        api_standard="v4.15"
    )
