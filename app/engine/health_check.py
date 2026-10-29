"""
Serwis Diagnostyczny i Healthcheck Scraperów (Drift Detection).
Zgodnie ze Standardem Architektury Nesta Home Master Tracker v4.16.
"""

import time
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlmodel import Session, select
from app.models.source import ScraperSource
from app.ingestion.infoludek import InfoludekConnector
from app.ingestion.sprzedajemy import SprzedajemyConnector
from app.ingestion.gratka import GratkaConnector
from app.ingestion.portals import PortalsConnector
from app.ingestion.komornik import KomornikConnector
from app.ingestion.zbilk import ZbilkConnector
from app.ingestion.otodom import OtodomConnector
from app.ingestion.spoldzielnie import SpoldzielnieConnector
from app.ingestion.lento import LentoConnector
from app.ingestion.kurier import KurierConnector
from app.core.config import settings

def test_source_health(source: ScraperSource, session: Session) -> Dict[str, Any]:
    """
    Przeprowadza rzeczywisty test techniczny źródła:
    1. Czas odpowiedzi (latencja w ms)
    2. Kod HTTP i integralność sieciowa
    3. Weryfikacja parsera (czy wyciąga oferty)
    4. Zabezpieczenia anti-bot (Cloudflare, 403)
    """
    start_time = time.perf_counter()
    status = "HEALTHY"
    items_count = 0
    message = "Połączenie i parser działają bez zarzutu."
    latency_ms = 0

    try:
        if source.code == "infoludek":
            connector = InfoludekConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} ofert ze Szczecina."
            else:
                status = "WARNING"
                message = "Portal odpowiedział (200 OK), ale selektory zwróciły 0 ofert. Możliwa zmiana układu strony."

        elif source.code == "sprzedajemy":
            connector = SprzedajemyConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} ofert prywatnych ze Szczecina."
            else:
                status = "WARNING"
                message = "Brak ofert w feedzie lub zmiana struktury artykułów."

        elif source.code == "gratka":
            connector = GratkaConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} ogłoszeń z pełnymi danymi."
            else:
                status = "WARNING"
                message = "Odpowiedź poprawna, brak pasujących kart mieszkań."

        elif source.code == "olx":
            connector = PortalsConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Pobrano {items_count} ofert z publicznego feedu OLX."
            else:
                status = "WARNING"
                message = "Blokada botów (HTTP 403). Aktywuj bezbłędny odbiór ofert OLX/Otodom przez moduł IMAP (Zero-ban)."

        elif source.code == "otodom":
            connector = OtodomConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} ogłoszeń z serwisu Otodom.pl."
            else:
                status = "WARNING"
                message = "Połączenie nawiązane, ale parser nie zwrócił ofert z Otodom."

        elif source.code == "elicytacje":
            connector = KomornikConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} obwieszczeń komorniczych ze Szczecina (Krajowa Rada Komornicza)."
            else:
                status = "WARNING"
                message = "Brak aktywnych obwieszczeń komorniczych ze Szczecina w bieżącym okresie."

        elif source.code == "zbilk":
            connector = ZbilkConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} lokali komunalnych ZBiLK i pustostanów do remontu."
            else:
                status = "WARNING"
                message = "Połączenie ze ZBiLK nawiązane, ale brak aktywnych wykazów lokali."

        elif source.code in ["spoldzielnie", "sm_srodmiescie"]:
            connector = SpoldzielnieConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} przetargów szczecińskich spółdzielni (Śródmieście, Dąb, Wspólny Dom)."
            else:
                status = "WARNING"
                message = "Połączenie ze spółdzielniami nawiązane, brak aktywnych ogłoszeń przetargowych."

        elif source.code == "lento":
            connector = LentoConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} ogłoszeń drobnych ze Szczecina z portalu Lento.pl."
            else:
                status = "WARNING"
                message = "Brak ogłoszeń na Lento.pl lub zmiana selektorów listy."

        elif source.code == "kurier":
            connector = KurierConnector()
            items = connector.fetch_listings()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            items_count = len(items)
            if items_count > 0:
                message = f"Sprawny. Sparsowano {items_count} ogłoszeń prasowych z 24kurier.pl."
            else:
                status = "WARNING"
                message = "Brak ogłoszeń prasowych w bieżącym wydaniu 24kurier.pl."

        elif source.code == "email_imap":
            if not settings.IMAP_HOST or not settings.IMAP_USER:
                status = "WARNING"
                message = "Skrzynka IMAP nie jest jeszcze skonfigurowana w pliku .env (opcjonalna)."
                latency_ms = 0
            else:
                import imaplib
                try:
                    mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
                    mail.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
                    mail.select(settings.IMAP_FOLDER)
                    mail.logout()
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    message = "Pomyślnie zalogowano do skrzynki IMAP. Gotowy do nasłuchu alertów."
                except Exception as ie:
                    status = "ERROR"
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    message = f"Błąd logowania do skrzynki IMAP: {ie}"

        else:
            # Test źródła z kolejki / dowolnego adresu URL
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(source.url)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                if resp.status_code == 200:
                    status = "HEALTHY"
                    message = f"Strona dostępna (HTTP 200 OK, rozmiar {len(resp.text)//1024} KB). Gotowa do oprogramowania parsera."
                elif resp.status_code in (401, 403):
                    status = "WARNING"
                    message = f"Wymaga uwierzytelnienia lub ochrony przed botami (HTTP {resp.status_code}). Wskazany scraper z sesją/Playwright."
                else:
                    status = "ERROR"
                    message = f"Błąd odpowiedzi serwera: HTTP {resp.status_code}."

    except httpx.TimeoutException:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        status = "ERROR"
        message = "Przekroczono limit czasu połączenia (Timeout > 10s)."
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        status = "ERROR"
        message = f"Błąd wykonania: {str(e)}"

    # Zapis w bazie danych
    source.status = status
    source.last_latency_ms = latency_ms
    source.last_items_found = items_count
    source.last_message = message
    source.last_tested_at = datetime.now(timezone.utc)
    source.updated_at = datetime.now(timezone.utc)

    session.add(source)
    session.commit()
    session.refresh(source)

    return {
        "id": source.id,
        "code": source.code,
        "name": source.name,
        "status": source.status,
        "latency_ms": source.last_latency_ms,
        "items_found": source.last_items_found,
        "message": source.last_message,
        "tested_at": source.last_tested_at.strftime("%H:%M:%S") if source.last_tested_at else None
    }

def test_all_active_sources(session: Session) -> List[Dict[str, Any]]:
    """Testuje wszystkie aktywne scrapery po kolei"""
    sources = session.exec(select(ScraperSource).where(ScraperSource.is_active == True)).all()
    results = []
    for src in sources:
        res = test_source_health(src, session)
        results.append(res)
    return results
