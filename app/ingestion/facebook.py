"""
Konektor: Facebook Groups Scraper (Szczecin Nieruchomości)
Architektura: Direct Native Stealth Scraper (curl_cffi + Session Cookies)
100% BEZPŁATNY - Zero kosztów zewnętrznych platform (brak limitów Apify).
Wspiera profil B.ART SMART HOME (i_user) oraz grupy prywatne i zamknięte.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.ingestion.base import BaseConnector
from app.core.config import settings
from app.engine.smart_extractor import smart_extract_listing

logger = logging.getLogger("facebook_ingestion")

DEFAULT_SZCZECIN_GROUPS = [
    "https://www.facebook.com/groups/816374953729581/",  # NIERUCHOMOŚCI SZCZECIN OFF MARKET
    "https://www.facebook.com/groups/1654452844583344/", # kupno, sprzedaż, wynajem bez pośredników szczecin
    "https://www.facebook.com/groups/619830191803121/",  # Sprzedam mieszkanie - Szczecin, Police - bezpośrednio
    "https://www.facebook.com/groups/149639275885323/",  # Mieszkania Szczecin
    "https://www.facebook.com/groups/2217762418461254/", # Mieszkanie Szczecin
    "https://www.facebook.com/groups/265144983644555/",  # NIERUCHOMOŚCI SZCZECIN
    "https://www.facebook.com/groups/447848112082515/",  # Nieruchomości Szczecin
    "https://www.facebook.com/groups/1033159440779379/", # SZCZECIN NIERUCHOMOŚCI kupno/sprzedaż/wynajem
    "https://www.facebook.com/groups/1376346619326361/", # SZCZECIN NIERUCHOMOŚCI - sprzedaż & wynajem
    "https://www.facebook.com/groups/mieszkaniadomyszczecin/" # SZCZECIN NIERUCHOMOŚCI - sprzedaż, kupno i wynajem
]

class FacebookConnector(BaseConnector):
    def __init__(self):
        pass

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
                        # Weź sam URL (odetnij ewentualny komentarz # na końcu)
                        clean_url = line_clean.split("#")[0].strip()
                        if clean_url and clean_url not in urls:
                            urls.append(clean_url)
            except Exception as e:
                logger.warning(f"Błąd odczytu pliku {groups_file}: {e}")

        if not urls:
            urls = DEFAULT_SZCZECIN_GROUPS
        return urls

    def load_cookies_dict(self) -> Optional[Dict[str, str]]:
        """Wczytuje ciasteczka sesyjne z pliku JSON i ustawia kontekst B.ART SMART HOME"""
        cookies_file = Path(settings.FB_COOKIES_PATH)
        if not cookies_file.exists():
            cookies_file = Path(settings.BASE_DIR) / "data" / "fb_cookies.json"

        if cookies_file.exists():
            try:
                data = json.loads(cookies_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    c_dict = {c['name']: c['value'] for c in data if 'name' in c and 'value' in c}
                    # Ustawienie profilu B.ART SMART HOME (profil zarządzany)
                    if 'i_user' not in c_dict:
                        c_dict['i_user'] = '61577421089010'
                    return c_dict
            except Exception as e:
                logger.warning(f"Błąd odczytu ciasteczek z {cookies_file}: {e}")
        return None

    def fetch_listings(self) -> List[Dict[str, Any]]:
        """
        Natywne, bezpośrednie pobieranie ofert z grup Facebooka bez udziału zewnętrznych płatnych platform.
        Wykorzystuje curl_cffi z impersonacją Chrome TLS oraz ciasteczka sesyjne profilu B.ART.
        """
        cookies_dict = self.load_cookies_dict()
        if not cookies_dict:
            logger.warning("Brak ciasteczek sesyjnych Facebooka w data/fb_cookies.json - pomijam grupy FB.")
            return []

        group_urls = self.get_configured_group_urls()
        if not group_urls:
            return []

        # Aby nie obciążać Facebooka, w jednym cyklu odpytujemy do 10 grup
        groups_to_check = group_urls[:10]
        logger.info(f"[FB Connector] Rozpoczynam natywne skanowanie {len(groups_to_check)} grup Szczecina...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            logger.error("Brak biblioteki curl_cffi - nie można wykonać zapytania stealth do Facebooka.")
            return []

        results = []
        seen_urls = set()

        for group_url in groups_to_check:
            try:
                target_url = group_url.rstrip("/") + "/?sorting_setting=CHRONOLOGICAL"
                resp = curl_requests.get(target_url, cookies=cookies_dict, headers=headers, impersonate="chrome120", timeout=12)
                if resp.status_code != 200:
                    logger.warning(f"[FB] Grupa {group_url} zwróciła kod HTTP {resp.status_code}")
                    continue

                html = resp.text.replace('\\/', '/')
                # Wyszukiwanie postów w strumieniu Relay Facebooka
                raw_posts = re.findall(r'"text":"([^"]{25,2500})".*?"permalink_url":"([^"]+)"', html)

                for raw_text, purl in raw_posts:
                    if purl in seen_urls:
                        continue
                    seen_urls.add(purl)

                    clean_text = raw_text.encode('utf-8').decode('unicode-escape', errors='replace').replace('\\n', '\n').strip()
                    lower_text = clean_text.lower()

                    # 1. Odrzucenie oczywistego spamu
                    if any(w in lower_text for w in ["manicure", "pedicure", "paznokci", "korepetycje", "volvo", "nissan", "audi", "bmw", "opel"]):
                        continue

                    # 2. Odrzucenie zapytań poszukujących ("szukam", "kupię")
                    if any(lower_text.startswith(p) for p in ["poszukuj", "szukam", "kupi", "chętnie kupi", "chętnie poszukuj"]):
                        continue
                    if any(w in lower_text for w in ["szukam mieszkania", "poszukuję mieszkania", "kupię mieszkanie", "chętnie kupię"]):
                        if not ("sprzedam" in lower_text or "na sprzedaż" in lower_text):
                            continue

                    # 3. Odrzucenie ofert najmu
                    is_explicit_sale = any(w in lower_text for w in ["na sprzedaż", "sprzedam", "sprzedaży", "własnościowe", "do sprzedaży"])
                    is_rental = any(w in lower_text for w in ["do wynajęcia", "wynajmę", "odstąpię najem", "pokój do wynajęcia"])
                    if is_rental and not is_explicit_sale:
                        continue

                    # 4. Ekstrakcja parametrów oferty
                    extracted, _ = smart_extract_listing(raw_text=clean_text)
                    price_pln = extracted.get("price_pln")
                    if not price_pln or price_pln < 40000:
                        continue

                    area_m2 = extracted.get("area_m2") or 45.0
                    title = extracted.get("title") or clean_text[:75].strip()
                    if not title.startswith("[FB]"):
                        title = f"[FB Grupy] {title}"

                    listing = {
                        "source": "facebook",
                        "title": title,
                        "description": clean_text,
                        "price_pln": float(price_pln),
                        "area_m2": float(area_m2),
                        "district": extracted.get("district") or "Centrum",
                        "street": extracted.get("street"),
                        "rooms": extracted.get("rooms"),
                        "floor": extracted.get("floor"),
                        "total_floors": extracted.get("total_floors"),
                        "building_type": extracted.get("building_type") or "Kamienica",
                        "heating_source": extracted.get("heating_source") or "Do weryfikacji",
                        "has_balcony": extracted.get("has_balcony", False),
                        "has_agency_fee": False,
                        "url": purl,
                        "published_at": datetime.now(timezone.utc)
                    }
                    results.append(listing)
            except Exception as ge:
                logger.warning(f"[FB] Błąd przetwarzania grupy {group_url}: {ge}")

        logger.info(f"[FB Connector] Zakończono skanowanie. Wyekstrahowano {len(results)} ofert sprzedaży.")
        return results
