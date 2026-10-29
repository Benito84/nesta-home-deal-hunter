"""
Główny pipeline przetwarzania ofert w Nesta Deal Hunter:
Pobieranie -> Filtr Wstępny -> Wycena Matematyczna -> Deduplikacja -> AI Evaluator -> Alert Telegram / Tracker
"""

from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models.listing import Listing
from app.models.benchmarks import DistrictBenchmark
from app.engine.filter_engine import pre_filter_listing
from app.engine.deduplicator import find_or_create_cluster, check_price_drop
from app.engine.fingerprint import compute_listing_fingerprint
from app.engine.ai_evaluator import evaluate_listing_ai
from app.core.calculator import calculate_offer
from app.alerts.telegram_bot import send_telegram_deal_alert
from app.engine.freshness_checker import check_single_url_alive

def process_raw_listing(raw: Dict[str, Any], session: Session) -> Tuple[Optional[Listing], str]:
    """
    Przetwarza surowy rekord ogłoszenia przez pełny lejek selekcji i wyceny Nesta Home.
    Zwraca (Listing lub None, status_komunikatu).
    """
    area_m2 = float(raw.get("area_m2") or 0.0)
    price_pln = float(raw.get("price_pln") or 0.0)
    district = raw.get("district") or "Centrum"
    title = raw.get("title") or "Ogłoszenie Szczecin"
    desc = raw.get("description") or ""

    # 1. Sprawdzenie fingerprintu (ochrona przed zbędną analizą LLM)
    fingerprint = compute_listing_fingerprint(
        city="Szczecin",
        district=district,
        street=raw.get("street"),
        price_pln=price_pln,
        area_m2=area_m2
    )

    url = raw.get("url")
    if url:
        existing = session.exec(select(Listing).where(Listing.url == url)).first()
        if existing:
            if not existing.is_active or existing.status == "ARCHIVED":
                return existing, "Oferta została wcześniej zarchiwizowana jako nieaktualna (pominięto)"
            drop = check_price_drop(session, existing, price_pln)
            if drop:
                return existing, f"Zaktualizowano cenę (obniżka o {drop.drop_pct*100:.1f}%)"
            return existing, "Oferta już istnieje w bazie (duplikat URL)"

    # Sprawdzenie czy istnieje identyczna oferta po hashu
    existing_by_hash = session.exec(select(Listing).where(Listing.content_hash == fingerprint)).first()
    if existing_by_hash:
        if not existing_by_hash.is_active or existing_by_hash.status == "ARCHIVED":
            return existing_by_hash, "Identyczna oferta została wcześniej zarchiwizowana jako nieaktualna (pominięto)"
        return existing_by_hash, "Identyczna oferta już została wcześniej poddana ewaluacji (fingerprint cache)"

    # Weryfikacja na żywo linku URL dla zgłoszeń manualnych / wklejanych
    if url and (raw.get("source") == "manual" or raw.get("verify_live")):
        is_alive, reason = check_single_url_alive(url)
        if not is_alive:
            return None, f"Odrzucono: ogłoszenie na portalu jest już nieaktualne ({reason})"

    # 2. Etap 1: Twardy filtr wstępny (oszczędność tokenów AI)
    passes, reason = pre_filter_listing(
        area_m2=area_m2,
        price_pln=price_pln,
        district=district,
        title=title,
        description=desc,
        building_type=raw.get("building_type"),
        source=raw.get("source")
    )
    if not passes:
        return None, f"Odrzucono na filtrze wstępnym: {reason}"

    # 3. Pobranie aktualnych stawek benchmarkowych z bazy
    benchmarks = session.exec(select(DistrictBenchmark)).all()
    custom_rates = {
        bm.district: {
            "avg_renovation_m2": bm.avg_renovation_m2,
            "ready_min_m2": bm.ready_min_m2,
            "ready_avg_m2": bm.ready_avg_m2,
            "ready_max_m2": bm.ready_max_m2
        } for bm in benchmarks
    }

    # 4. Wyliczenia Matematyczne Modelu Finansowego Nesta Home
    calc = calculate_offer(raw, custom_rates=custom_rates)
    if not calc:
        return None, "Błąd kalkulatora finansowego"

    # 5. Deduplikacja i klasteryzacja
    cluster, is_new_cluster = find_or_create_cluster(
        session=session,
        district=district,
        area_m2=area_m2,
        price_pln=price_pln,
        floor=raw.get("floor"),
        street=raw.get("street")
    )

    # 6. Analiza AI (Gemini Structured Outputs)
    ai_res = evaluate_listing_ai(raw, calc, session)

    # 7. Zapis do bazy danych
    listing = Listing(
        source=raw.get("source", "manual"),
        external_id=raw.get("external_id"),
        url=url,
        title=title,
        description=desc,
        district=district,
        street=raw.get("street"),
        area_m2=area_m2,
        price_pln=price_pln,
        price_per_m2=calc.get("price_per_m2"),
        rooms=raw.get("rooms"),
        floor=raw.get("floor"),
        total_floors=raw.get("total_floors"),
        building_type=raw.get("building_type", "Kamienica"),
        building_year=raw.get("building_year"),
        has_elevator=raw.get("has_elevator", False),
        has_balcony=raw.get("has_balcony", False),
        balcony_type=raw.get("balcony_type", "Balkon"),
        heating_source=raw.get("heating_source"),
        ownership_type=raw.get("ownership_type", "PELNA_WLASNOSC"),
        admin_rent=raw.get("admin_rent", 0.0),
        has_agency_fee=raw.get("has_agency_fee", True),
        agency_fee_pct=raw.get("agency_fee_pct", 0.03),
        seller_name=raw.get("seller_name"),
        seller_phone=raw.get("seller_phone"),
        cluster_id=cluster.id,
        content_hash=fingerprint,

        # Matematyka
        deal_score=ai_res.deal_score,
        gate_1_decision=calc.get("gate_1_decision", "STOP"),
        walk_away_price=calc.get("walk_away_price"),
        anchor_price=calc.get("anchor_price"),
        estimated_renovation=calc.get("estimated_renovation"),
        total_investment=calc.get("total_investment"),
        arv_target=calc.get("arv_target"),
        company_net_profit_pln=calc.get("company_net_profit_pln"),
        roi_target=calc.get("roi_target"),
        effective_ready_m2=calc.get("effective_ready_m2"),
        calculation_details=calc,

        # AI
        ai_recommendation=ai_res.recommendation.value,
        ai_renovation_scope=ai_res.estimated_renovation_scope.value,
        room_layout_potential=ai_res.room_layout_potential,
        pros=ai_res.pros,
        red_flags=ai_res.red_flags,
        negotiation_arguments=ai_res.negotiation_arguments,
        ai_analyzed_at=datetime.now(timezone.utc),
        status="QUALIFIED" if calc.get("gate_1_decision") in ["DO POCZEKALNI", "DZWONIMY"] else "NEW"
    )

    session.add(listing)
    session.commit()
    session.refresh(listing)

    # 8. Natychmiastowy Alert Telegram dla najlepszych okazji
    if listing.gate_1_decision in ["DO POCZEKALNI", "DZWONIMY"] or listing.deal_score >= 80:
        send_telegram_deal_alert(listing)

    return listing, "Pomyślnie przeanalizowano i dodano ofertę"
