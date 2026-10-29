"""
Moduł Weryfikacji Aktualności Ofert (Freshness Checker & Garbage Collector).
Zgodnie ze Standardem Architektury Nesta Home Master Tracker v4.16.
Sprawdza czy ogłoszenia na portalach są nadal aktywne i automatycznie archiwizuje wygasłe.
"""

import logging
from typing import Tuple, Dict, Any, List
from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models.listing import Listing

logger = logging.getLogger("freshness_checker")

try:
    from curl_cffi import requests as curl_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False
    import httpx

EXPIRED_SIGNATURES = [
    "to ogłoszenie jest nieaktualne",
    "to ogloszenie jest nieaktualne",
    "ta oferta jest już nieaktualna",
    "ta oferta jest juz nieaktualna",
    "ogłoszenie zakończone",
    "ogloszenie zakonczone",
    "ogłoszenie wygasło",
    "ogloszenie wygaslo",
    "oferta została wycofana",
    "oferta zostala wycofana",
    "ogłoszenie nie jest już dostępne",
    "ogloszenie nie jest juz dostepne",
    "przepraszamy, nie znaleziono",
    "nie znaleźliśmy tego ogłoszenia",
    "strona nie istnieje",
    "404 - nie znaleziono",
    "oferta archiwalna",
    "ogłoszenie zostało usunięte",
    "ogloszenie zostalo usuniete"
]


def check_single_url_alive(url: str) -> Tuple[bool, str]:
    """
    Bada czy pojedynczy link do oferty jest nadal aktywny na portalu.
    Zwraca (is_alive: bool, reason: str).
    """
    if not url or not url.startswith("http"):
        return True, "Brak weryfikowalnego adresu URL"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        response_text = ""
        status_code = 200
        final_url = url

        if CURL_AVAILABLE:
            try:
                r = curl_requests.get(url, impersonate="chrome", timeout=10, headers=headers, allow_redirects=True)
                status_code = r.status_code
                response_text = r.text
                final_url = r.url
            except Exception as ce:
                logger.warning(f"curl_cffi błąd zapytania {url}: {ce}")

        if not response_text:
            import httpx
            with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
                r = client.get(url)
                status_code = r.status_code
                response_text = r.text
                final_url = str(r.url)

        # 1. Kody błędów HTTP
        if status_code in [404, 410]:
            return False, f"Strona zwróciła kod HTTP {status_code} (Usunięto z portalu)"

        # 2. Przekierowanie na stronę główną lub ogólną listę (częsta praktyka Otodom / OLX przy usunięciu)
        clean_final = final_url.rstrip("/")
        clean_orig = url.rstrip("/")
        if clean_final != clean_orig:
            # Jeśli przekierowano na listing lub stronę główną portalu
            if clean_final in [
                "https://www.otodom.pl", "https://otodom.pl",
                "https://www.olx.pl", "https://olx.pl",
                "https://gratka.pl", "https://sprzedajemy.pl",
                "https://ogloszenia.infoludek.pl"
            ] or "/szukaj" in clean_final or "/kategoria" in clean_final:
                return False, "Portal przekierował ofertę na stronę główną (ogłoszenie skasowane)"

        # 3. Analiza sygnatur wygaśnięcia w treści HTML
        lower_body = response_text.lower()
        for sig in EXPIRED_SIGNATURES:
            if sig in lower_body:
                return False, f"Wykryto sygnaturę zakończenia: '{sig}'"

        return True, "Oferta aktywna"

    except Exception as e:
        logger.warning(f"Błąd podczas sprawdzania aktualności {url}: {e}")
        # W razie błędu sieciowego nie usuwamy pochopnie
        return True, f"Błąd weryfikacji sieciowej: {e}"


def verify_active_listings_batch(session: Session, limit: int = 40) -> Dict[str, int]:
    """
    Weryfikuje partię najstarszych aktywnych ofert posiadających URL.
    Automatycznie deaktywuje (`is_active = False`, `status = 'ARCHIVED'`) wygasłe oferty.
    """
    query = select(Listing).where(Listing.is_active == True).where(Listing.url != None).order_by(Listing.updated_at.asc()).limit(limit)
    listings = session.exec(query).all()

    checked = 0
    archived = 0

    for l in listings:
        if not l.url:
            continue

        checked += 1
        is_alive, reason = check_single_url_alive(l.url)
        
        if not is_alive:
            print(f"[Freshness Checker] Archiwizuję wygasłą ofertę #{l.id} ({l.title}): {reason}")
            l.is_active = False
            l.status = "ARCHIVED"
            l.updated_at = datetime.now(timezone.utc)
            session.add(l)
            archived += 1
        else:
            # Aktualizujemy updated_at żeby trafiło na koniec kolejki sprawdzania
            l.updated_at = datetime.now(timezone.utc)
            session.add(l)

    session.commit()

    return {
        "checked": checked,
        "archived": archived,
        "still_active": checked - archived
    }
