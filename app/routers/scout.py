"""
Router Domenowy: Szybka Wklejka (Scout) i Smart Ingestion.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker v4.16.
Użytkownik podaje TYLKO link, print screen lub wklejony tekst - zero dodatkowych pól.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session
from app.core.database import get_session
from app.core.templates import templates
from app.ingestion.pipeline import process_raw_listing
from app.engine.smart_extractor import smart_extract_listing
from app.schemas.listing import RawIngestWebhookRequest

router = APIRouter(tags=["Scout"])

@router.get("/quick-ingest", response_class=HTMLResponse)
def quick_ingest_view(request: Request):
    """Formularz szybkiej wklejki: tylko Link, Print Screen lub Tekst"""
    return templates.TemplateResponse(
        request=request,
        name="quick_ingest.html",
        context={"error": None, "url": "", "raw_text": ""}
    )

@router.post("/quick-ingest")
async def quick_ingest_post(
    request: Request,
    url: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None),
    screenshot: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session)
):
    url_clean = (url or "").strip()
    text_clean = (raw_text or "").strip()

    image_bytes = None
    mime_type = "image/jpeg"
    if screenshot and screenshot.filename:
        image_bytes = await screenshot.read()
        mime_type = screenshot.content_type or "image/jpeg"

    if not url_clean and not text_clean and not image_bytes:
        return templates.TemplateResponse(
            request=request,
            name="quick_ingest.html",
            context={
                "error": "Podaj co najmniej jedno źródło: wklej link do oferty, wpisz treść lub załącz print screen.",
                "url": url_clean,
                "raw_text": text_clean
            },
            status_code=400
        )

    # Automatyczna ekstrakcja parametrów oferty
    try:
        extracted, source_note = smart_extract_listing(
            url=url_clean or None,
            raw_text=text_clean or None,
            image_bytes=image_bytes,
            mime_type=mime_type
        )
    except ValueError as ve:
        return templates.TemplateResponse(
            request=request,
            name="quick_ingest.html",
            context={
                "error": f"Błąd weryfikacji oferty: {ve}",
                "url": url_clean,
                "raw_text": text_clean
            },
            status_code=422
        )

    # Weryfikacja kluczowych parametrów cenowych
    if not extracted.get("price_pln") or extracted.get("price_pln", 0) <= 0:
        return templates.TemplateResponse(
            request=request,
            name="quick_ingest.html",
            context={
                "error": "Nie udało się automatycznie odczytać ceny nieruchomości. Upewnij się, że wklejony tekst lub strona zawiera kwotę zakupu (np. 280 000 zł lub 280 tys.).",
                "url": url_clean,
                "raw_text": text_clean
            },
            status_code=422
        )

    if not extracted.get("area_m2") or extracted.get("area_m2", 0) <= 0:
        return templates.TemplateResponse(
            request=request,
            name="quick_ingest.html",
            context={
                "error": "Nie udało się automatycznie odczytać metrażu mieszkania. Upewnij się, że wklejony tekst lub strona zawiera powierzchnię (np. 48.5 m² lub 48 mkw).",
                "url": url_clean,
                "raw_text": text_clean
            },
            status_code=422
        )

    listing, msg = process_raw_listing(extracted, session)
    if not listing:
        return templates.TemplateResponse(
            request=request,
            name="quick_ingest.html",
            context={
                "error": f"Odrzucono ofertę: {msg}",
                "url": url_clean,
                "raw_text": text_clean
            },
            status_code=422
        )

    return RedirectResponse(url=f"/?highlight={listing.id}", status_code=303)


@router.post("/api/v1/ingest/smart")
async def smart_ingest_api(
    url: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None),
    screenshot: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session)
):
    """Programistyczny endpoint Smart Ingestion dla botów Telegram/FB/rozszerzeń przeglądarki"""
    image_bytes = None
    mime_type = "image/jpeg"
    if screenshot and screenshot.filename:
        image_bytes = await screenshot.read()
        mime_type = screenshot.content_type or "image/jpeg"

    try:
        extracted, note = smart_extract_listing(
            url=(url or "").strip() or None,
            raw_text=(raw_text or "").strip() or None,
            image_bytes=image_bytes,
            mime_type=mime_type
        )
    except ValueError as ve:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": str(ve)}
        )

    if not extracted.get("price_pln") or not extracted.get("area_m2"):
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "Nie wykryto ceny lub metrażu", "extracted": extracted}
        )

    listing, msg = process_raw_listing(extracted, session)
    if listing:
        return {
            "status": "success",
            "message": msg,
            "extraction_note": note,
            "listing_id": listing.id,
            "gate_1_decision": listing.gate_1_decision,
            "deal_score": listing.deal_score,
            "roi": listing.roi_target,
            "walk_away_price": listing.walk_away_price
        }
    return JSONResponse(status_code=422, content={"status": "rejected", "message": msg})


@router.post("/api/v1/ingest/raw")
def raw_ingest_webhook(
    payload: RawIngestWebhookRequest,
    session: Session = Depends(get_session)
):
    """Klasyczny webhook JSON dla precyzyjnych crawlerów"""
    listing, msg = process_raw_listing(payload.model_dump(), session)
    if listing:
        return {
            "status": "success",
            "message": msg,
            "listing_id": listing.id,
            "gate_1_decision": listing.gate_1_decision,
            "deal_score": listing.deal_score,
            "roi": listing.roi_target,
            "walk_away_price": listing.walk_away_price
        }
    return JSONResponse(status_code=422, content={"status": "rejected", "message": msg})
