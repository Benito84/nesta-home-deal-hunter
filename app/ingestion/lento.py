"""
Konektor: Lento.pl Szczecin (Ogłoszenia drobne mieszkań w Szczecinie)
Źródło ofert prywatnych, bezpośrednich oraz od spadkobierców i seniorów.
Wykorzystuje curl_cffi i selektory układu Lento.pl.
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from app.ingestion.base import BaseConnector
from app.ingestion.komornik import match_szczecin_district, parse_pln_amount

class LentoConnector(BaseConnector):
    """Konektor dla ogłoszeń drobnych mieszkań na Lento.pl Szczecin"""

    @property
    def name(self) -> str:
        return "lento"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        url = "https://szczecin.lento.pl/nieruchomosci/mieszkania/sprzedaz.html"
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
                print(f"[Lento Scraper Warning]: HTTP status {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            offer_links = soup.find_all("a", href=re.compile(r",\d+\.html$"))
            seen_urls = set()

            for a in offer_links:
                try:
                    href = a.get("href", "")
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)

                    title = a.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    full_url = href if href.startswith("http") else f"https://szczecin.lento.pl{href}"
                    
                    # ID ogłoszenia z URL
                    m_id = re.search(r",(\d+)\.html$", href)
                    ext_id = m_id.group(1) if m_id else str(abs(hash(href)) % 100000)

                    # Kontener wiersza
                    parent = a.find_parent("div", class_=re.compile("item|row|desc-list")) or a.find_parent("li")
                    full_text = parent.get_text(" ", strip=True) if parent else title

                    # Cena
                    price = 0.0
                    m_price = re.search(r"(\d[\d\s]{3,})\s*(?:zł|zl|pln)", full_text, re.I)
                    if m_price:
                        price = parse_pln_amount(m_price.group(1))

                    # Metraż
                    area = 0.0
                    m_area = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", full_text, re.I)
                    if m_area:
                        area = float(m_area.group(1).replace(",", "."))

                    # Liczba pokoi
                    rooms = None
                    m_rooms = re.search(r"(\d+)\s*pok", full_text, re.I)
                    if m_rooms:
                        rooms = int(m_rooms.group(1))

                    # Piętro
                    floor = None
                    lower_text = full_text.lower()
                    if "parter" in lower_text:
                        floor = 0
                    else:
                        m_f = re.search(r"(\d+)\.?\s*piętro", lower_text)
                        if m_f:
                            floor = int(m_f.group(1))

                    # Dzielnica
                    district = match_szczecin_district(full_text)

                    # Jeśli ogłoszenie wspomina o syndyku lub cena/m2 jest niska, pobieramy pełny opis aby zweryfikować udziały
                    if ("syndyk" in lower_text or (price > 0 and area > 0 and price / area < 3500)) and full_url:
                        try:
                            detail_r = cffi_requests.get(full_url, headers=headers, impersonate="chrome124", timeout=5)
                            if detail_r.status_code == 200:
                                d_soup = BeautifulSoup(detail_r.text, "html.parser")
                                d_block = d_soup.select_one(".block-description, .ad-desc, [itemprop='description']")
                                if d_block:
                                    full_text = f"{full_text}\n{d_block.get_text(' ', strip=True)}"
                                    lower_text = full_text.lower()
                        except Exception:
                            pass

                    # Typ budynku
                    building_type = "Kamienica" if "kamienic" in lower_text else ("Wielka płyta" if "płyt" in lower_text else "Niski blok")

                    # Ogrzewanie
                    heating = None
                    if "piec" in lower_text or "kaflow" in lower_text:
                        heating = "piece kaflowe"
                    elif "sec" in lower_text or "miejsk" in lower_text:
                        heating = "miejskie (SEC)"
                    elif "gaz" in lower_text:
                        heating = "gazowe (kocioł 2-f)"

                    # Pośrednik vs oferta prywatna
                    has_agency = "pośrednik" in lower_text or "biuro" in lower_text

                    if area > 0 and price > 0:
                        results.append({
                            "source": "lento",
                            "external_id": ext_id,
                            "url": full_url,
                            "title": title,
                            "description": full_text,
                            "district": district,
                            "street": None,
                            "area_m2": area,
                            "price_pln": price,
                            "rooms": rooms,
                            "floor": floor,
                            "total_floors": None,
                            "building_type": building_type,
                            "heating_source": heating,
                            "has_balcony": any(b in lower_text for b in ["balkon", "loggia", "taras"]),
                            "has_agency_fee": has_agency
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"[Lento Scraper Error]: {e}")

        return results
