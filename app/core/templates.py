"""
Konfiguracja szablonów Jinja2 z globalnym SSOT wersji (Sekcja 3.3).
"""

from pathlib import Path
from fastapi.templating import Jinja2Templates
from app.core.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))

# Globalne zmienne szablonów (SSOT)
templates.env.globals["app_version"] = settings.APP_VERSION
templates.env.globals["tracker_env"] = settings.TRACKER_ENV
templates.env.globals["app_name"] = settings.APP_NAME
