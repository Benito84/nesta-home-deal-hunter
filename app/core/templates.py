"""
Konfiguracja szablonów Jinja2 z globalnym SSOT wersji (Sekcja 3.3).
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi.templating import Jinja2Templates
from app.core.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))

# Globalne zmienne szablonów (SSOT)
templates.env.globals["app_version"] = settings.APP_VERSION
templates.env.globals["tracker_env"] = settings.TRACKER_ENV
templates.env.globals["app_name"] = settings.APP_NAME


def format_datetime_filter(dt: Optional[datetime]) -> str:
    if not dt:
        return "Brak daty"
    return dt.strftime("%d.%m.%Y, %H:%M")


def time_ago_filter(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    total_sec = max(0, int(diff.total_seconds()))
    minutes = total_sec // 60
    hours = minutes // 60
    days = hours // 24

    if minutes < 2:
        return "przed chwilą"
    elif minutes < 60:
        return f"{minutes} min temu"
    elif hours == 1:
        return "1 godz. temu"
    elif hours in [2, 3, 4, 22, 23, 24]:
        return f"{hours} godz. temu"
    elif hours < 24:
        return f"{hours} godz. temu"
    elif days == 1:
        return "wczoraj"
    elif days < 7:
        return f"{days} dni temu"
    elif days < 30:
        return f"{days} dni na rynku"
    elif days < 60:
        return "1 mies. na rynku"
    else:
        months = days // 30
        return f"{months} mies. na rynku"


def freshness_badge_filter(dt: Optional[datetime]) -> Optional[Dict[str, Any]]:
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    hours = max(0.0, diff.total_seconds() / 3600.0)

    if hours <= 2.0:
        return {
            "label": "NOWOŚĆ",
            "class": "bg-emerald-600 text-white font-bold tracking-wide shadow-xs",
            "icon": "fa-bolt",
            "hint": "Świeża oferta - pojawiła się w ciągu ostatnich 2 godzin!"
        }
    elif hours <= 12.0:
        return {
            "label": "DZISIAJ",
            "class": "bg-emerald-50 text-emerald-800 border border-emerald-300 font-semibold",
            "icon": "fa-sparkles",
            "hint": "Oferta dodana dzisiaj"
        }
    elif hours >= 336.0:  # >= 14 dni
        days = int(hours // 24)
        return {
            "label": f"{days} DNI NA RYNKU",
            "class": "bg-amber-100 text-amber-900 border border-amber-300 font-bold",
            "icon": "fa-hourglass-half",
            "hint": "Oferta długo wisi na rynku - wysoki potencjał do agresywnych negocjacji cenowych!"
        }
    return None


def freshness_pill_class_filter(dt: Optional[datetime]) -> str:
    if not dt:
        return "bg-sand-100 text-stone-600 border border-sand-200"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    hours = diff.total_seconds() / 3600.0
    if hours <= 2.0:
        return "bg-emerald-100 text-emerald-900 border border-emerald-300"
    elif hours <= 24.0:
        return "bg-sand-200 text-stone-900 border border-sand-300"
    elif hours >= 336.0:
        return "bg-amber-100 text-amber-900 border border-amber-300"
    return "bg-sand-100 text-stone-700 border border-sand-200"


def is_aged_filter(dt: Optional[datetime]) -> bool:
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    return (diff.total_seconds() / 3600.0) >= 336.0


# Rejestracja filtrów Jinja
templates.env.filters["format_datetime"] = format_datetime_filter
templates.env.filters["time_ago"] = time_ago_filter
templates.env.filters["freshness_badge"] = freshness_badge_filter
templates.env.filters["freshness_pill_class"] = freshness_pill_class_filter
templates.env.filters["is_aged"] = is_aged_filter
