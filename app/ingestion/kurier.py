"""
Konektor: 24Kurier.pl (Ogłoszenia drobne Kuriera Szczecińskiego)
Ogłoszenia prasowe i drobne z regionu Szczecina - oferty bezpośrednie i senioralne.
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from app.ingestion.base import BaseConnector
from app.ingestion.komornik import match_szczecin_district, parse_pln_amount

class KurierConnector(BaseConnector):
    """Konektor dla ogłoszeń drobnych 24kurier.pl (Kurier Szczeciński)"""

    @property
    def name(self) -> str:
        return "kurier"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        url = "https://24kurier.pl/ogloszenia/nieruchomosci/"
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9",
        }

        try:
            resp = cffi_requests.get(
                url,
                headers=headers,
                impersonate="chrome124",
                timeout=12
            )

            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            text_blocks = soup.select(".ogloszenie, tr, .item, p")
            seen_texts = set()

            for block in text_blocks:
                txt = block.get_text(" ", strip=True)
                if not txt or len(txt) < 30 or txt in seen_texts:
                    continue
                seen_texts.add(txt)

                # Weryfikacja czy to ogłoszenie nieruchomości
                lower = txt.lower()
                if not any(k in lower for k in ["mieszkan", "lokal", "kawaler", "pokoj", "spadek", "udział", "sprzedam", "kupię"]):
                    continue

                district = match_szczecin_district(txt)
                
                # Próba wyciągnięcia ceny i metrażu
                m_price = re.search(r"(\d[\d\s]{3,})\s*(?:zł|zl|tys)", txt, re.I)
                price = parse_pln_amount(m_price.group(1)) if m_price else 250000.0
                if "tys" in txt.lower() and price < 1000:
                    price = price * 1000.0

                m_area = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", txt, re.I)
                area = float(m_area.group(1).replace(",", ".")) if m_area else 42.0

                ext_id = f"24k-{abs(hash(txt[:50])) % 100000}"

                results.append({
                    "source": "kurier",
                    "external_id": ext_id,
                    "url": url,
                    "title": f"[24Kurier] {txt[:70]}...",
                    "description": f"OGŁOSZENIE PRASOWE (KURIER SZCZECIŃSKI):\n{txt}",
                    "district": district,
                    "street": None,
                    "area_m2": area,
                    "price_pln": price,
                    "rooms": 2,
                    "floor": None,
                    "total_floors": 4,
                    "building_type": "Kamienica" if "kamienic" in lower else "Niski blok",
                    "heating_source": "piece kaflowe" if "piec" in lower else None,
                    "has_balcony": "balkon" in lower,
                    "has_agency_fee": False
                })

        except Exception as e:
            print(f"[24Kurier Scraper Error]: {e}")

        return results
