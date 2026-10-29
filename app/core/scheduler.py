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

scheduler = BackgroundScheduler(daemon=True)

def scheduled_scraping_job():
    """Cykliczne zadanie w tle: pobieranie ogłoszeń z Infoludka, OLX, Otodom, Gratki, Sprzedajemy, Komornika, ZBiLK, Spółdzielni, Lento i Kuriera"""
    print("[Scheduler] Rozpoczynam cykliczne skanowanie źródeł Szczecina...")
    with Session(engine) as session:
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

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(scheduled_scraping_job, "interval", minutes=30, id="portal_scraper")
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
