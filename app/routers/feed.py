"""
Router Domenowy: Tablica Okazji (Feed) i Zaawansowane Filtrowanie Mieszkań.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker v4.16.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select, or_
from app.core.database import get_session
from app.core.templates import templates
from app.models.listing import Listing

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

@router.get("/", response_class=HTMLResponse)
def index_view(
    request: Request,
    q: Optional[str] = None,
    source: Optional[str] = None,
    district: Optional[str] = None,
    gate: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    rooms: Optional[str] = None,
    building_type: Optional[str] = None,
    heating: Optional[str] = None,
    direct_only: Optional[bool] = False,
    has_balcony: Optional[bool] = False,
    min_roi: Optional[float] = None,
    sort: Optional[str] = "score",
    session: Session = Depends(get_session)
):
    query = select(Listing).where(Listing.is_active == True)
    active_filters_count = 0

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
    if price_min is not None and price_min > 0:
        query = query.where(Listing.price_pln >= price_min)
        active_filters_count += 1
    if price_max is not None and price_max > 0:
        query = query.where(Listing.price_pln <= price_max)
        active_filters_count += 1

    # 6. Przedział metrażu
    if area_min is not None and area_min > 0:
        query = query.where(Listing.area_m2 >= area_min)
        active_filters_count += 1
    if area_max is not None and area_max > 0:
        query = query.where(Listing.area_m2 <= area_max)
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
    if direct_only:
        query = query.where(Listing.has_agency_fee == False)
        active_filters_count += 1

    # 11. Balkon
    if has_balcony:
        query = query.where(Listing.has_balcony == True)
        active_filters_count += 1

    # 12. Minimalny ROI
    if min_roi is not None and min_roi > 0:
        roi_ratio = min_roi / 100.0 if min_roi > 1.0 else min_roi
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
            "price_min": price_min,
            "price_max": price_max,
            "area_min": area_min,
            "area_max": area_max,
            "rooms": rooms or "ALL",
            "building_type": building_type or "ALL",
            "heating": heating or "ALL",
            "direct_only": direct_only,
            "has_balcony": has_balcony,
            "min_roi": min_roi,
            "sort": sort or "score",
            "active_filters_count": active_filters_count
        }
    )
