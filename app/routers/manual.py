"""
Router Domenowy: Instrukcja Obsługi i Baza Wiedzy Nesta Deal Hunter.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker v4.16.
Zawiera kompletny opis zasad działania aplikacji oraz szczegółowe dossier wszystkich źródeł sourcingu.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.core.templates import templates

router = APIRouter(tags=["Manual"])

@router.get("/manual", response_class=HTMLResponse)
def manual_view(request: Request):
    """Widok kompendium wiedzy, instrukcji obsługi i charakterystyki źródeł"""
    return templates.TemplateResponse(
        request=request,
        name="manual.html",
        context={}
    )
