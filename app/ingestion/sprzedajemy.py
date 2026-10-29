"""
Konektor: Sprzedajemy.pl (Ogłoszenia mieszkań Szczecin)
Jeden z największych portali ogłoszeń drobnych w Polsce z przeważającą liczbą ofert bezpośrednich od właścicieli.
"""

import re
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from app.ingestion.base import BaseConnector

class SprzedajemyConnector(BaseConnector):
    @property
    def name(self) -> str:
        return "sprzedajemy"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        url = "https://sprzedajemy.pl/szczecin/nieruchomosci/mieszkania"
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
                articles = soup.select("article.element")

                seen_urls = set()
                for art in articles:
                    try:
                        title_el = art.select_one("h2.title a, h2 a")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        href = title_el.get("href", "")
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        full_url = f"https://sprzedajemy.pl{href}" if href.startswith("/") else href
                        ext_id = href.split("-nr")[-1] if "-nr" in href else href.split("/")[-1]

                        price_el = art.select_one(".price")
                        price_text = price_el.get_text(" ", strip=True) if price_el else ""
                        price_match = re.search(r"(\d[\d\s]{3,})\s*(?:zł|pln)", price_text, re.IGNORECASE)
                        price = float(price_match.group(1).replace(" ", "").replace("\xa0", "")) if price_match else 0.0

                        card_text = art.get_text(" ", strip=True)
                        area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", card_text, re.IGNORECASE)
                        area = float(area_match.group(1).replace(",", ".")) if area_match else 0.0

                        # Dzielnica Szczecina
                        district = "Centrum"
                        for d in ["Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno", "Gumieńce", "Pomorzany", "Warszewo", "Dąbie", "Słoneczne", "Bukowe", "Świerczewo", "Żelechowa", "Podjuchy"]:
                            if d.lower() in card_text.lower():
                                district = d
                                break

                        # Ogrzewanie
                        heating = None
                        if "piec" in card_text.lower() or "kaflow" in card_text.lower():
                            heating = "piece kaflowe"
                        elif "sec" in card_text.lower() or "miejsk" in card_text.lower():
                            heating = "miejskie (SEC)"
                        elif "gaz" in card_text.lower():
                            heating = "gazowe (kocioł 2-f)"

                        # Typ budynku
                        building_type = "Kamienica" if ("kamienic" in card_text.lower() or "oficyn" in card_text.lower()) else ("Wielka płyta" if "płyt" in card_text.lower() else "Niski blok")

                        # Czy pośrednik czy bezpośrednie
                        is_company = bool(art.select_one(".verified-company, .company"))

                        if area > 0 and price > 0:
                            results.append({
                                "source": "sprzedajemy",
                                "external_id": ext_id,
                                "url": full_url,
                                "title": title,
                                "description": card_text,
                                "district": district,
                                "area_m2": area,
                                "price_pln": price,
                                "building_type": building_type,
                                "heating_source": heating,
                                "has_balcony": any(b in card_text.lower() for b in ["balkon", "loggia", "taras"]),
                                "has_agency_fee": is_company
                            })
                    except Exception:
                        continue

        except Exception as e:
            print(f"[Sprzedajemy Scraper Error]: {e}")

        return results
