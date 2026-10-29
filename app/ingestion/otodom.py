"""
Konektor: Otodom.pl (Bezpośredni scraper ofert mieszkań w Szczecinie)
Wykorzystuje impersonację TLS Chrome 124 (curl_cffi) oraz bezpośrednią ekstrakcję
danych strukturalnych z obiektu hydratacji __NEXT_DATA__ bez konieczności logowania.
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from app.ingestion.base import BaseConnector
from app.ingestion.komornik import match_szczecin_district

ROOMS_MAP = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
    "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10
}

FLOOR_MAP = {
    "GROUND": 0, "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
    "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10
}

class OtodomConnector(BaseConnector):
    """Konektor dla portalu Otodom.pl z bezpośrednią ekstrakcją danych JSON"""

    @property
    def name(self) -> str:
        return "otodom"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        url = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/zachodniopomorskie/szczecin/szczecin/szczecin?limit=36&ownerTypeSingleSelect=ALL&by=LATEST&direction=DESC"
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        try:
            resp = cffi_requests.get(
                url,
                headers=headers,
                impersonate="chrome124",
                timeout=15
            )

            if resp.status_code != 200:
                print(f"[Otodom Scraper Warning]: HTTP status {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            next_data_tag = soup.find("script", id="__NEXT_DATA__")
            if not next_data_tag or not next_data_tag.string:
                print("[Otodom Scraper Warning]: Brak znacznika __NEXT_DATA__ w kodzie strony")
                return results

            data = json.loads(next_data_tag.string)
            props = data.get("props", {}).get("pageProps", {})
            search_ads = props.get("data", {}).get("searchAds", {})
            items = search_ads.get("items", [])

            if not isinstance(items, list):
                return results

            for it in items:
                try:
                    offer_id = it.get("id")
                    title = it.get("title") or "Mieszkanie na sprzedaż Szczecin"
                    slug = it.get("slug") or ""
                    if not slug:
                        continue

                    full_url = f"https://www.otodom.pl/pl/oferta/{slug}"
                    area = float(it.get("areaInSquareMeters") or 0.0)

                    price_obj = it.get("totalPrice") or {}
                    price = float(price_obj.get("value") or 0.0) if price_obj else 0.0

                    rooms_str = str(it.get("roomsNumber", "")).upper()
                    rooms = ROOMS_MAP.get(rooms_str)

                    floor_str = str(it.get("floorNumber", "")).upper()
                    floor = FLOOR_MAP.get(floor_str)

                    # Rozpoznanie lokalizacji i dzielnicy z reverseGeocoding
                    loc = it.get("location") or {}
                    rev = loc.get("reverseGeocoding", {}).get("locations", [])
                    district = None
                    district_names = [l.get("name", "") for l in rev]
                    loc_full = " ".join(district_names)

                    for d in ["Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno", "Gumieńce", "Pomorzany", "Warszewo", "Dąbie", "Słoneczne", "Bukowe", "Majowe", "Żelechowa", "Podjuchy", "Krzekowo"]:
                        if any(d.lower() in dn.lower() for dn in district_names):
                            district = d
                            break

                    if not district:
                        district = match_szczecin_district(f"{title} {loc_full}")

                    # Ulica jeśli dostępna
                    addr = loc.get("address") or {}
                    street = addr.get("street") or None

                    # Tagi i cechy lokalu
                    tags = [t.get("value", "") for t in it.get("tags") or []]
                    has_balcony = any("BALCONY" in t or "TERRACE" in t or "LOGGIA" in t for t in tags) or "balkon" in title.lower()

                    # Czynsz administracyjny
                    rent_obj = it.get("rentPrice") or {}
                    admin_rent = float(rent_obj.get("value") or 0.0) if rent_obj else 0.0

                    # Typ budynku
                    title_lower = title.lower()
                    building_type = "Kamienica" if ("kamienic" in title_lower or "oficyn" in title_lower) else ("Wielka płyta" if "płyt" in title_lower else "Niski blok")

                    # Prywatne vs biuro
                    is_private = bool(it.get("isPrivateOwner"))

                    # Data publikacji na Otodom
                    published_at = None
                    raw_date = it.get("dateCreated") or it.get("createdAt") or it.get("dateCreatedFirst")
                    if raw_date:
                        try:
                            published_at = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                        except Exception:
                            pass

                    desc = f"{title}. Szczecin, {district}. {loc_full}. Tagi: {', '.join(tags)}."

                    if area > 0 and price > 0:
                        results.append({
                            "source": "otodom",
                            "external_id": str(offer_id),
                            "url": full_url,
                            "title": title,
                            "description": desc,
                            "district": district,
                            "street": street,
                            "area_m2": area,
                            "price_pln": price,
                            "rooms": rooms,
                            "floor": floor,
                            "total_floors": None,
                            "building_type": building_type,
                            "heating_source": None,
                            "has_balcony": has_balcony,
                            "has_agency_fee": not is_private,
                            "admin_rent": admin_rent,
                            "published_at": published_at
                        })

                except Exception as ie:
                    continue

        except Exception as e:
            print(f"[Otodom Scraper Global Error]: {e}")

        return results
