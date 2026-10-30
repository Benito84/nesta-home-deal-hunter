"""
Harmonogram zadań w tle (APScheduler).
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (Sekcja 1.1 i 4.1).
"""

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session
from app.core.database import engine
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
from app.engine.freshness_checker import verify_active_listings_batch

scheduler = BackgroundScheduler(daemon=True)

def scheduled_scraping_job():
    """Cykliczne zadanie w tle: pobieranie ogłoszeń ze zweryfikowanych źródeł Szczecina"""
    print("[Scheduler] Rozpoczynam cykliczne skanowanie źródeł Szczecina...")
    with Session(engine) as session:
        connectors = [
            InfoludekConnector(),
            PortalsConnector(),
            OtodomConnector(),
            GratkaConnector(),
            SprzedajemyConnector(),
            KomornikConnector(),
            SpoldzielnieConnector(),
            LentoConnector(),
            KurierConnector()
        ]
        items = []
        for conn in connectors:
            try:
                fetched = conn.fetch_listings()
                print(f"[Scheduler] {conn.name}: pobrano {len(fetched)} ofert.")
                items.extend(fetched)
            except Exception as e:
                print(f"[Scheduler Error in {conn.name}]: {e}")

        for item in items:
            try:
                process_raw_listing(item, session)
            except Exception as e:
                print(f"[Scheduler Error for item]: {e}")
    print("[Scheduler] Zakończono cykliczne skanowanie.")

def scheduled_freshness_job():
    """Cykliczne sprawdzanie czy aktywne oferty na portalach nie wygasły lub nie zostały skasowane"""
    print("[Scheduler] Uruchamiam cykliczne sprawdzanie aktualności ofert (Freshness Checker)...")
    try:
        with Session(engine) as session:
            res = verify_active_listings_batch(session, limit=30)
            print(f"[Scheduler Freshness] Sprawdzono: {res.get('checked')}, zarchiwizowano wygasłych: {res.get('archived')}, nadal aktywnych: {res.get('still_active')}")
    except Exception as e:
        print(f"[Scheduler Freshness Error]: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(scheduled_scraping_job, "interval", minutes=30, id="portal_scraper")
        scheduler.add_job(scheduled_freshness_job, "interval", hours=4, id="freshness_verifier")
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
