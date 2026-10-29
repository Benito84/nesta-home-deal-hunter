"""
Router Domenowy: Zarządzanie Źródłami, Diagnostyka Scraperów (Healthcheck) i Kolejka Backlogu.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker v4.16.
"""

import re
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.config import settings
from app.core.templates import templates
from app.models.source import ScraperSource
from app.engine.health_check import test_source_health, test_all_active_sources
from app.ingestion.pipeline import process_raw_listing
from app.ingestion.infoludek import InfoludekConnector
from app.ingestion.portals import PortalsConnector
from app.ingestion.gratka import GratkaConnector
from app.ingestion.sprzedajemy import SprzedajemyConnector
from app.ingestion.komornik import KomornikConnector
from app.ingestion.zbilk import ZbilkConnector
from app.ingestion.otodom import OtodomConnector
from app.ingestion.spoldzielnie import SpoldzielnieConnector
from app.ingestion.lento import LentoConnector
from app.ingestion.kurier import KurierConnector

router = APIRouter(tags=["Sources"])

@router.get("/sources", response_class=HTMLResponse)
def sources_view(request: Request, session: Session = Depends(get_session)):
    active_sources = session.exec(select(ScraperSource).where(ScraperSource.is_active == True).order_by(ScraperSource.id)).all()
    queued_sources = session.exec(select(ScraperSource).where(ScraperSource.is_active == False).order_by(ScraperSource.id)).all()

    return templates.TemplateResponse(
        request=request,
        name="sources.html",
        context={
            "active_sources": active_sources,
            "queued_sources": queued_sources,
            "tracker_url": settings.tracker_active_url,
            "imap_configured": bool(settings.IMAP_HOST and settings.IMAP_USER)
        }
    )

@router.post("/api/v1/sources/{source_id}/test")
def test_source_endpoint(source_id: int, session: Session = Depends(get_session)):
    """Testuje pojedyncze źródło i zwraca wynik diagnostyczny"""
    source = session.get(ScraperSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Źródło nie istnieje")
    
    result = test_source_health(source, session)
    return result

@router.post("/api/v1/sources/test-all")
def test_all_sources_endpoint(session: Session = Depends(get_session)):
    """Testuje wszystkie aktywne źródła jednocześnie"""
    results = test_all_active_sources(session)
    return {"status": "success", "results": results}

@router.post("/api/v1/sources/add")
def add_source_to_queue(
    name: str = Form(...),
    url: str = Form(...),
    notes: Optional[str] = Form(None),
    tier: str = Form("Kolejka: Do analizy"),
    session: Session = Depends(get_session)
):
    """Dodaje nową stronę do kolejki do analizy i zakodowania w aplikacji"""
    slug = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())[:30].strip('_')
    code = f"custom_{slug}"

    # Sprawdzenie czy kod już istnieje
    existing = session.exec(select(ScraperSource).where(ScraperSource.code == code)).first()
    if existing:
        code = f"{code}_{int(session.exec(select(ScraperSource)).all().__len__())}"

    new_source = ScraperSource(
        code=code,
        name=name.strip(),
        url=url.strip(),
        tier=tier,
        is_active=False,
        status="QUEUED",
        last_message="Zgłoszono do analizy i oprogramowania parsera.",
        notes=notes.strip() if notes else None
    )
    session.add(new_source)
    session.commit()

    return RedirectResponse(url="/sources", status_code=303)

@router.post("/api/v1/sources/{source_id}/delete")
def delete_source_from_queue(source_id: int, session: Session = Depends(get_session)):
    """Usuwa źródło z kolejki backlogu"""
    source = session.get(ScraperSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Źródło nie istnieje")
    if source.is_active:
        raise HTTPException(status_code=400, detail="Nie można usunąć aktywnego wbudowanego scrapera")
    
    session.delete(source)
    session.commit()
    return RedirectResponse(url="/sources", status_code=303)

@router.post("/api/v1/trigger-scrape")
def trigger_scrape_endpoint(session: Session = Depends(get_session)):
    """Ręczne wyzwolenie pobierania ze wszystkich aktywnych źródeł"""
    connectors = [
        InfoludekConnector(),
        PortalsConnector(),
        OtodomConnector(),
        GratkaConnector(),
        SprzedajemyConnector(),
        KomornikConnector(),
        ZbilkConnector(),
        SpoldzielnieConnector(),
        LentoConnector(),
        KurierConnector()
    ]

    raw_items = []
    for conn in connectors:
        try:
            raw_items.extend(conn.fetch_listings())
        except Exception as e:
            print(f"[Manual Scrape Error in {conn.name}]: {e}")

    processed_count = 0
    qualified_count = 0

    for item in raw_items:
        l, msg = process_raw_listing(item, session)
        if l:
            processed_count += 1
            if l.gate_1_decision in ["DO POCZEKALNI", "DZWONIMY"]:
                qualified_count += 1

    return {
        "status": "success",
        "fetched_total": len(raw_items),
        "saved": processed_count,
        "qualified_hot_deals": qualified_count
    }
