"""
Konektor Tier 1: infoludek.pl (Szczeciński Portal Ogłoszeniowy)
Ogłoszenia bezpośrednie od starszych właścicieli i lokalnych mieszkańców Szczecina.
"""

import re
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from app.ingestion.base import BaseConnector

class InfoludekConnector(BaseConnector):
    @property
    def name(self) -> str:
        return "infoludek"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        url = "https://ogloszenia.infoludek.pl/ogloszenia/kategorie/short/nieruchomosci-sprzedam-mieszkania.xhtml"
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
        }

        try:
            with httpx.Client(timeout=14.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return results

                soup = BeautifulSoup(resp.text, "html.parser")
                seen_urls = set()

                for a in soup.select('a[href*="/ogloszenia/info/"]'):
                    try:
                        href = a.get("href", "")
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        link = f"https://ogloszenia.infoludek.pl{href}" if href.startswith("/") else href
                        ext_id = href.split("/")[3] if len(href.split("/")) > 3 else None

                        text_full = a.get_text(" ", strip=True)
                        if len(text_full) < 15 and a.parent:
                            text_full = a.parent.get_text(" ", strip=True)

                        # Wyciąganie ceny
                        price_match = re.search(r"(\d[\d\s]{3,}(?:[.,]\d{2})?)\s*(?:zł|pln)", text_full, re.IGNORECASE)
                        price = float(price_match.group(1).replace(" ", "").replace(",", ".")) if price_match else 0.0

                        # Wyciąganie metrażu
                        area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m\s*(?:2|²)", text_full, re.IGNORECASE)
                        area = float(area_match.group(1).replace(",", ".")) if area_match else 0.0

                        # Tytuł
                        title_clean = text_full.split("PLN")[0] if "PLN" in text_full else text_full[:70]
                        title = re.sub(r'^\d+\s*', '', title_clean).strip()
                        if not title:
                            title = f"Mieszkanie Infoludek {area} m²"

                        # Dzielnica ze Szczecina
                        district = "Centrum"
                        for d in ["Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno", "Gumieńce", "Pomorzany", "Warszewo", "Dąbie", "Słoneczne", "Bukowe", "Majowe", "Podjuchy"]:
                            if d.lower() in text_full.lower():
                                district = d
                                break

                        # Ogrzewanie
                        heating = None
                        if "piec" in text_full.lower() or "kaflow" in text_full.lower():
                            heating = "piece kaflowe"
                        elif "sec" in text_full.lower() or "miejsk" in text_full.lower():
                            heating = "miejskie (SEC)"
                        elif "gaz" in text_full.lower():
                            heating = "gazowe (kocioł 2-f)"

                        building_type = "Kamienica" if ("kamienic" in text_full.lower() or "oficyn" in text_full.lower()) else "Wielka płyta"

                        if area > 0 and price > 0:
                            results.append({
                                "source": "infoludek",
                                "external_id": ext_id,
                                "url": link,
                                "title": title[:90],
                                "description": text_full,
                                "district": district,
                                "area_m2": area,
                                "price_pln": price,
                                "building_type": building_type,
                                "heating_source": heating,
                                "has_balcony": any(b in text_full.lower() for b in ["balkon", "loggia", "taras"]),
                                "has_agency_fee": False  # Infoludek to w 95% ogłoszenia bezpośrednie
                            })
                    except Exception:
                        continue

        except Exception as e:
            print(f"[Infoludek Scraper Error]: {e}")

        return results
