"""
Konektor: Gratka.pl (Ogłoszenia mieszkań Szczecin)
Duży portal ogólnopolski z bogatą bazą kamienic i mieszkań z rynku wtórnego.
"""

import re
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from app.ingestion.base import BaseConnector

class GratkaConnector(BaseConnector):
    @property
    def name(self) -> str:
        return "gratka"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        url = "https://gratka.pl/nieruchomosci/mieszkania/szczecin/sprzedaz?sort=created_at:desc"
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        try:
            with httpx.Client(timeout=14.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return results

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("div.card, article.teaserItem, div.card__outer")

                seen_urls = set()
                for card in cards:
                    try:
                        link_el = card.select_one("a.property-card__link, a[href*='/ob/']")
                        if not link_el:
                            continue

                        href = link_el.get("href", "")
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        full_url = f"https://gratka.pl{href}" if href.startswith("/") else href
                        ext_id = href.split("/ob/")[-1] if "/ob/" in href else None

                        title_el = card.select_one(".property-card__title, h2, h3, a")
                        title = title_el.get_text(strip=True) if title_el else "Mieszkanie Szczecin"

                        loc_el = card.select_one(".property-card__location")
                        loc_text = loc_el.get_text(" ", strip=True) if loc_el else ""

                        price_el = card.select_one(".property-card__price--main, .property-card__price")
                        price_text = price_el.get_text(" ", strip=True) if price_el else ""
                        price_match = re.search(r"(\d[\d\s]{3,})\s*(?:zł|pln)", price_text, re.IGNORECASE)
                        price = float(price_match.group(1).replace(" ", "").replace("\xa0", "")) if price_match else 0.0

                        area = 0.0
                        rooms = None
                        floor = None
                        total_floors = None
                        for item in card.select("li.offer-info__item, .offer-info li"):
                            it_text = item.get_text(" ", strip=True)
                            if "m²" in it_text or "m2" in it_text:
                                am = re.search(r"(\d+(?:[.,]\d+)?)\s*m", it_text)
                                if am:
                                    area = float(am.group(1).replace(",", "."))
                            elif "pok" in it_text.lower():
                                rm = re.search(r"(\d+)\s*pok", it_text, re.IGNORECASE)
                                if rm:
                                    rooms = int(rm.group(1))
                            elif "piętro" in it_text.lower() or "parter" in it_text.lower():
                                if "parter" in it_text.lower():
                                    floor = 0
                                else:
                                    fm = re.search(r"piętro\s*(\d+)(?:/(\d+))?", it_text, re.IGNORECASE)
                                    if fm:
                                        floor = int(fm.group(1))
                                        if fm.group(2):
                                            total_floors = int(fm.group(2))

                        desc_el = card.select_one(".description__content, .property-card__property-description")
                        desc = desc_el.get_text(" ", strip=True) if desc_el else f"{title} {loc_text}"
                        full_content = f"{title} {loc_text} {desc}"

                        # Dzielnica
                        district = "Centrum"
                        for d in ["Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno", "Gumieńce", "Pomorzany", "Warszewo", "Dąbie", "Słoneczne", "Bukowe", "Świerczewo", "Żelechowa", "Podjuchy", "Krzekowo"]:
                            if d.lower() in full_content.lower():
                                district = d
                                break

                        # Ogrzewanie
                        heating = None
                        if "piec" in full_content.lower() or "kaflow" in full_content.lower():
                            heating = "piece kaflowe"
                        elif "sec" in full_content.lower() or "miejsk" in full_content.lower():
                            heating = "miejskie (SEC)"
                        elif "gaz" in full_content.lower():
                            heating = "gazowe (kocioł 2-f)"

                        # Typ budynku
                        building_type = "Kamienica" if ("kamienic" in full_content.lower() or "oficyn" in full_content.lower()) else ("Wielka płyta" if "płyt" in full_content.lower() else "Niski blok")

                        # Balkon
                        has_balcony = any(b in full_content.lower() for b in ["balkon", "loggia", "taras", "balkonem"])

                        # Prowizja
                        has_agency = not ("bezpośrednio" in full_content.lower() or "bez prowizji" in full_content.lower() or "od właściciela" in full_content.lower())

                        if area > 0 and price > 0:
                            results.append({
                                "source": "gratka",
                                "external_id": ext_id,
                                "url": full_url,
                                "title": title,
                                "description": full_content,
                                "district": district,
                                "street": loc_text.split(",")[0].strip() if "," in loc_text else None,
                                "area_m2": area,
                                "price_pln": price,
                                "rooms": rooms,
                                "floor": floor,
                                "total_floors": total_floors,
                                "building_type": building_type,
                                "heating_source": heating,
                                "has_balcony": has_balcony,
                                "has_agency_fee": has_agency
                            })
                    except Exception:
                        continue

        except Exception as e:
            print(f"[Gratka Scraper Error]: {e}")

        return results
