"""
Konektor Tier 2: Portale Otodom / OLX (Feedy ogłoszeń Szczecin).
Pobiera najświeższe ogłoszenia ze Szczecina z ominięciem TLS Fingerprinting (curl_cffi).
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from app.ingestion.base import BaseConnector

class PortalsConnector(BaseConnector):
    @property
    def name(self) -> str:
        return "olx"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        results = []
        url = "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/szczecin/?search%5Border%5D=created_at%3Adesc"

        try:
            # Używamy impersonacji TLS Chrome 124 (omijanie Cloudflare 403)
            try:
                from curl_cffi import requests as cffi_requests
                resp = cffi_requests.get(url, impersonate="chrome124", timeout=12)
                html_text = resp.text
                status_code = resp.status_code
            except ImportError:
                import httpx
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
                    r = client.get(url)
                    html_text = r.text
                    status_code = r.status_code

            if status_code != 200:
                return results

            soup = BeautifulSoup(html_text, "html.parser")
            cards = soup.select('[data-cy="l-card"]')

            for card in cards:
                try:
                    title_el = card.select_one("h6, h4, .css-16v5mdi")
                    link_el = card.select_one("a")
                    if not title_el or not link_el:
                        continue

                    title = title_el.get_text(strip=True)
                    href = link_el.get("href", "")
                    link = f"https://www.olx.pl{href}" if href.startswith("/") else href

                    text_card = card.get_text(" ", strip=True)

                    # Cena
                    price_match = re.search(r"(\d[\d\s]{3,})\s*zł", text_card)
                    price = float(price_match.group(1).replace(" ", "")) if price_match else 0.0

                    # Metraż
                    area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", text_card)
                    area = float(area_match.group(1).replace(",", ".")) if area_match else 0.0

                    # Dzielnica
                    district = "Centrum"
                    for d in ["Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno", "Gumieńce", "Pomorzany", "Warszewo", "Dąbie", "Słoneczne", "Bukowe", "Majowe", "Żelechowa"]:
                        if d.lower() in text_card.lower():
                            district = d
                            break

                    heating = None
                    if "piec" in text_card.lower() or "kaflow" in text_card.lower():
                        heating = "piece kaflowe"
                    elif "sec" in text_card.lower() or "miejsk" in text_card.lower():
                        heating = "miejskie (SEC)"
                    elif "gaz" in text_card.lower():
                        heating = "gazowe (kocioł 2-f)"

                    if area > 0 and price > 0:
                        results.append({
                            "source": "olx",
                            "external_id": link.split("-")[-1].replace(".html", "") if "-" in link else None,
                            "url": link,
                            "title": title,
                            "description": text_card,
                            "district": district,
                            "area_m2": area,
                            "price_pln": price,
                            "building_type": "Kamienica" if "kamienic" in text_card.lower() else "Wielka płyta",
                            "heating_source": heating,
                            "has_balcony": any(b in text_card.lower() for b in ["balkon", "loggia", "taras"]),
                            "has_agency_fee": "biuro" in text_card.lower() or "agencja" in text_card.lower()
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"[Portals Scraper Warning]: {e}")

        return results
