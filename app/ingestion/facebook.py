"""
Konektor: Facebook Groups Scraper (Szczecin Nieruchomości)
Integracja z platformą Apify (Actor: apify/facebook-groups-scraper)
Zapewnia bezpieczne pobieranie ofert z grup Facebooka bez ryzyka bana dla konta firmowego.
Wspiera ciasteczka sesyjne dla grup prywatnych oraz automatyczną ekstrakcję encji AI (Gemini).
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx

from app.ingestion.base import BaseConnector
from app.core.config import settings
from app.engine.smart_extractor import smart_extract_listing

logger = logging.getLogger("facebook_ingestion")

DEFAULT_SZCZECIN_GROUPS = [
    "https://www.facebook.com/groups/mieszkaniaszczecin/",
    "https://www.facebook.com/groups/nieruchomosci.szczecin/",
    "https://www.facebook.com/groups/szczecin.mieszkania/",
    "https://www.facebook.com/groups/157256194451000/"  # Mieszkania Szczecin bezpośrednio
]

class FacebookConnector(BaseConnector):
    def __init__(self, token: Optional[str] = None):
        self.api_token = token or settings.APIFY_API_TOKEN

    @property
    def name(self) -> str:
        return "facebook"

    def get_configured_group_urls(self) -> List[str]:
        """Pobiera listę URL grup ze zmiennej środowiskowej, pliku konfiguracyjnego lub domyślnych"""
        urls = []
        if settings.FB_GROUPS_URLS:
            for u in settings.FB_GROUPS_URLS.replace(";", ",").split(","):
                u_clean = u.strip()
                if u_clean:
                    urls.append(u_clean)

        groups_file = Path(settings.BASE_DIR) / "data" / "fb_groups.txt"
        if groups_file.exists():
            try:
                for line in groups_file.read_text(encoding="utf-8").splitlines():
                    line_clean = line.strip()
                    if line_clean and not line_clean.startswith("#"):
                        if line_clean not in urls:
                            urls.append(line_clean)
            except Exception as e:
                logger.warning(f"Błąd odczytu pliku {groups_file}: {e}")

        if not urls:
            urls = DEFAULT_SZCZECIN_GROUPS
        return urls

    def load_cookies(self) -> Optional[List[Dict[str, Any]]]:
        """Wczytuje ciasteczka sesyjne z pliku JSON (wyeksportowane np. przez Cookie-Editor)"""
        cookies_file = Path(settings.FB_COOKIES_PATH)
        if not cookies_file.exists():
            # Sprawdź też domyślne data/fb_cookies.json
            cookies_file = Path(settings.BASE_DIR) / "data" / "fb_cookies.json"

        if cookies_file.exists():
            try:
                data = json.loads(cookies_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception as e:
                logger.warning(f"Błąd odczytu ciasteczek z {cookies_file}: {e}")
        return None

    def fetch_listings(self) -> List[Dict[str, Any]]:
        """
        Uruchamia aktora Apify facebook-groups-scraper i przetwarza posty przez silnik AI.
        """
        if not self.api_token:
            logger.info("Brak skonfigurowanego APIFY_API_TOKEN - pomijam pobieranie z grup Facebooka.")
            return []

        group_urls = self.get_configured_group_urls()
        if not group_urls:
            return []

        cookies = self.load_cookies()

        run_input = {
            "startUrls": [{"url": u} for u in group_urls],
            "resultsLimit": 15,
            "viewOption": "CHRONOLOGICAL",
            "onlyPostsNewerThan": "3 days"
        }
        if cookies:
            run_input["cookies"] = cookies

        logger.info(f"Uruchamiam Apify Facebook Groups Scraper dla {len(group_urls)} grup...")

        actor_url = f"https://api.apify.com/v2/acts/apify~facebook-groups-scraper/run-sync-get-dataset-items"
        headers = {
            "Content-Type": "application/json"
        }
        params = {
            "token": self.api_token,
            "timeout": 120
        }

        raw_items = []
        try:
            with httpx.Client(timeout=140.0) as client:
                resp = client.post(actor_url, json=run_input, headers=headers, params=params)
                if resp.status_code in (200, 201):
                    raw_items = resp.json()
                    logger.info(f"Apify zwrócił {len(raw_items)} postów z Facebooka.")
                else:
                    logger.error(f"Błąd Apify API ({resp.status_code}): {resp.text[:300]}")
                    return []
        except httpx.TimeoutException:
            logger.warning("Limit czasu (timeout 120s) podczas scrapowania grup Facebooka przez Apify.")
            return []
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd wywołania Apify: {e}")
            return []

        results = []
        for item in raw_items:
            try:
                # Pola z aktora Apify facebook-groups-scraper
                post_text = item.get("text") or item.get("postText") or item.get("message") or ""
                post_text = post_text.strip()
                if len(post_text) < 25:
                    continue

                # Odrzucamy posty typu "szukam", "kupię", "poszukuję", "wynajmę"
                lower_text = post_text.lower()
                if any(w in lower_text for w in ["szukam mieszkania", "poszukuję mieszkania", "kupię mieszkanie", "wynajmę", "do wynajęcia"]):
                    continue

                post_url = item.get("url") or item.get("postUrl")
                if not post_url and item.get("id"):
                    post_url = f"https://www.facebook.com/groups/post/{item.get('id')}"

                # Ekstrakcja parametrów oferty za pomocą Smart Extractor (AI / Heurystyki)
                extracted, _ = smart_extract_listing(raw_text=post_text)

                price_pln = extracted.get("price_pln")
                area_m2 = extracted.get("area_m2")

                # Post musi zawierać przynajmniej cenę lub metraż, by kwalifikować się do kalkulatora
                if not price_pln or price_pln <= 0:
                    continue

                title = extracted.get("title") or post_text[:75].strip()
                if not title.startswith("[FB]"):
                    title = f"[FB Grupy] {title}"

                # Czas dodania
                time_str = item.get("time") or item.get("timestamp")
                published_dt = None
                if time_str:
                    try:
                        published_dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                listing = {
                    "source": "facebook",
                    "title": title,
                    "description": post_text,
                    "price_pln": float(price_pln),
                    "area_m2": float(area_m2) if area_m2 else 45.0,  # domyślny metraż jeśli podano samą cenę
                    "district": extracted.get("district") or "Centrum",
                    "street": extracted.get("street"),
                    "rooms": extracted.get("rooms"),
                    "floor": extracted.get("floor"),
                    "total_floors": extracted.get("total_floors"),
                    "building_type": extracted.get("building_type") or "Kamienica",
                    "heating_source": extracted.get("heating_source") or "Do weryfikacji",
                    "has_balcony": extracted.get("has_balcony", False),
                    "has_agency_fee": False,
                    "url": post_url or f"https://www.facebook.com/groups/post/{item.get('id', 'unknown')}",
                    "published_at": published_dt or datetime.now(timezone.utc)
                }
                results.append(listing)
            except Exception as e:
                logger.warning(f"Błąd przetwarzania pojedynczego posta z FB: {e}")

        logger.info(f"Pomyślnie wyekstrahowano {len(results)} ofert sprzedaży z grup Facebooka.")
        return results
