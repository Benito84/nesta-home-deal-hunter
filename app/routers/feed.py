"""
Router Domenowy: Tablica Okazji (Feed) i Zaawansowane Filtrowanie Mieszkań.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker v4.16.
"""

from typing import Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select, or_
from app.core.database import get_session
from app.core.templates import templates
from app.models.listing import Listing
from app.engine.freshness_checker import check_single_url_alive

router = APIRouter(tags=["Feed"])

AVAILABLE_SOURCES = [
    {"code": "ALL", "name": "Wszystkie źródła"},
    {"code": "otodom", "name": "Otodom.pl"},
    {"code": "olx", "name": "OLX Szczecin"},
    {"code": "infoludek", "name": "infoludek.pl"},
    {"code": "sprzedajemy", "name": "Sprzedajemy.pl"},
    {"code": "gratka", "name": "Gratka.pl"},
    {"code": "elicytacje", "name": "E-Licytacje komornicze"},
    {"code": "zbilk", "name": "ZBiLK Szczecin (Miejskie)"},
    {"code": "spoldzielnie", "name": "Spółdzielnie mieszkaniowe"},
    {"code": "lento", "name": "Lento.pl Szczecin"},
    {"code": "kurier", "name": "24Kurier.pl (Drobne)"},
    {"code": "manual", "name": "Szybka wklejka"}
]

def parse_optional_float(val: Optional[Any]) -> Optional[float]:
    if val is None:
        return None
    val_str = str(val).strip().replace(" ", "").replace(",", ".")
    if not val_str:
        return None
    try:
        f = float(val_str)
        return f if f > 0 else None
    except ValueError:
        return None

def parse_optional_bool(val: Optional[Any]) -> bool:
    if val is None:
        return False
    val_str = str(val).strip().lower()
    return val_str in ("true", "1", "on", "yes")

@router.get("/", response_class=HTMLResponse)
def index_view(
    request: Request,
    q: Optional[str] = None,
    source: Optional[str] = None,
    district: Optional[str] = None,
    gate: Optional[str] = None,
    price_min: Optional[str] = None,
    price_max: Optional[str] = None,
    area_min: Optional[str] = None,
    area_max: Optional[str] = None,
    rooms: Optional[str] = None,
    building_type: Optional[str] = None,
    heating: Optional[str] = None,
    direct_only: Optional[str] = None,
    has_balcony: Optional[str] = None,
    min_roi: Optional[str] = None,
    sort: Optional[str] = "score",
    session: Session = Depends(get_session)
):
    query = select(Listing).where(Listing.is_active == True)
    active_filters_count = 0

    p_min = parse_optional_float(price_min)
    p_max = parse_optional_float(price_max)
    a_min = parse_optional_float(area_min)
    a_max = parse_optional_float(area_max)
    roi_min = parse_optional_float(min_roi)
    is_direct = parse_optional_bool(direct_only)
    is_balcony = parse_optional_bool(has_balcony)

    # 1. Wyszukiwanie pełnotekstowe (słowa kluczowe, ulica, tytuł)
    if q and q.strip():
        q_clean = q.strip()
        search_filter = or_(
            Listing.title.ilike(f"%{q_clean}%"),
            Listing.description.ilike(f"%{q_clean}%"),
            Listing.street.ilike(f"%{q_clean}%")
        )
        query = query.where(search_filter)
        active_filters_count += 1

    # 2. Filtr źródła
    if source and source != "ALL":
        query = query.where(Listing.source == source)
        active_filters_count += 1

    # 3. Filtr dzielnicy
    if district and district != "ALL":
        query = query.where(Listing.district == district)
        active_filters_count += 1

    # 4. Decyzja bramki
    if gate and gate != "ALL":
        if gate in ["DO POCZEKALNI", "DO_POCZEKALNI", "DZWONIMY"]:
            query = query.where(or_(Listing.gate_1_decision == "DO POCZEKALNI", Listing.gate_1_decision == "DZWONIMY"))
        else:
            query = query.where(Listing.gate_1_decision == gate)
        active_filters_count += 1

    # 5. Przedział cenowy
    if p_min is not None and p_min > 0:
        query = query.where(Listing.price_pln >= p_min)
        active_filters_count += 1
    if p_max is not None and p_max > 0:
        query = query.where(Listing.price_pln <= p_max)
        active_filters_count += 1

    # 6. Przedział metrażu
    if a_min is not None and a_min > 0:
        query = query.where(Listing.area_m2 >= a_min)
        active_filters_count += 1
    if a_max is not None and a_max > 0:
        query = query.where(Listing.area_m2 <= a_max)
        active_filters_count += 1

    # 7. Liczba pokoi
    if rooms and rooms != "ALL":
        active_filters_count += 1
        if rooms == "4+":
            query = query.where(Listing.rooms >= 4)
        elif rooms.isdigit():
            query = query.where(Listing.rooms == int(rooms))

    # 8. Typ budynku
    if building_type and building_type != "ALL":
        query = query.where(Listing.building_type == building_type)
        active_filters_count += 1

    # 9. Ogrzewanie
    if heating and heating != "ALL":
        query = query.where(Listing.heating_source.ilike(f"%{heating}%"))
        active_filters_count += 1

    # 10. Bezpośrednie vs biuro
    if is_direct:
        query = query.where(Listing.has_agency_fee == False)
        active_filters_count += 1

    # 11. Balkon
    if is_balcony:
        query = query.where(Listing.has_balcony == True)
        active_filters_count += 1

    # 12. Minimalny ROI
    if roi_min is not None and roi_min > 0:
        roi_ratio = roi_min / 100.0 if roi_min > 1.0 else roi_min
        query = query.where(Listing.roi_target >= roi_ratio)
        active_filters_count += 1

    # Sortowanie
    if sort == "roi":
        query = query.order_by(Listing.roi_target.desc())
    elif sort == "profit":
        query = query.order_by(Listing.company_net_profit_pln.desc())
    elif sort == "price_asc":
        query = query.order_by(Listing.price_pln.asc())
    elif sort == "price_desc":
        query = query.order_by(Listing.price_pln.desc())
    elif sort == "price_m2_asc":
        query = query.order_by(Listing.price_per_m2.asc())
    elif sort == "newest":
        query = query.order_by(Listing.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Listing.created_at.asc())
    else:  # default: score
        query = query.order_by(Listing.deal_score.desc())

    listings = session.exec(query).all()
    all_count = len(session.exec(select(Listing)).all())
    gate_call_count = len(session.exec(select(Listing).where(or_(Listing.gate_1_decision == "DO POCZEKALNI", Listing.gate_1_decision == "DZWONIMY"))).all())
    synced_count = len(session.exec(select(Listing).where(Listing.tracker_synced == True)).all())

    rois = [l.roi_target for l in listings if l.roi_target]
    avg_roi = (sum(rois) / len(rois) * 100) if rois else 0.0

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "listings": listings,
            "all_count": all_count,
            "gate_call_count": gate_call_count,
            "synced_count": synced_count,
            "avg_roi": avg_roi,
            "available_sources": AVAILABLE_SOURCES,
            "q": q or "",
            "source": source or "ALL",
            "district": district or "ALL",
            "gate": gate or "ALL",
            "price_min": int(p_min) if p_min and p_min.is_integer() else p_min,
            "price_max": int(p_max) if p_max and p_max.is_integer() else p_max,
            "area_min": int(a_min) if a_min and a_min.is_integer() else a_min,
            "area_max": int(a_max) if a_max and a_max.is_integer() else a_max,
            "rooms": rooms or "ALL",
            "building_type": building_type or "ALL",
            "heating": heating or "ALL",
            "direct_only": is_direct,
            "has_balcony": is_balcony,
            "min_roi": int(roi_min) if roi_min and roi_min.is_integer() else roi_min,
            "sort": sort or "score",
            "active_filters_count": active_filters_count
        }
    )

@router.post("/api/v1/listings/{listing_id}/archive")
def archive_listing_endpoint(listing_id: int, session: Session = Depends(get_session)):
    """Ręczna deaktywacja i archiwizacja oferty (usuwa z głównego widoku okazji)"""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Oferta nie istnieje")
    
    listing.is_active = False
    listing.status = "ARCHIVED"
    listing.updated_at = datetime.now(timezone.utc)
    session.add(listing)
    session.commit()
    return {"status": "success", "message": f"Oferta #{listing_id} została zarchiwizowana", "is_active": False}

@router.post("/api/v1/listings/{listing_id}/check-freshness")
def check_single_listing_freshness(listing_id: int, session: Session = Depends(get_session)):
    """Sprawdza na żywo czy ogłoszenie jest nadal aktywne na portalu źródłowym"""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Oferta nie istnieje")
    if not listing.url:
        return {"status": "skipped", "message": "Brak linku do weryfikacji", "is_alive": True}

    is_alive, reason = check_single_url_alive(listing.url)
    if not is_alive:
        listing.is_active = False
        listing.status = "ARCHIVED"
        listing.updated_at = datetime.now(timezone.utc)
        session.add(listing)
        session.commit()
        return {"status": "archived", "is_alive": False, "reason": reason}

    listing.updated_at = datetime.now(timezone.utc)
    session.add(listing)
    session.commit()
    return {"status": "active", "is_alive": True, "reason": reason}
