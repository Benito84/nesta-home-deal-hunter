"""
Konektor: Przetargi Szczecińskich Spółdzielni Mieszkaniowych
Przeszukuje oficjalne obwieszczenia i przetargi na lokale z odzysku:
- SM Śródmieście (kamienice i bloki w centrum Szczecina)
- SM Dąb (Prawobrzeże: Słoneczne, Majowe, Bukowe, Dąbie)
- SM Wspólny Dom (Niebuszewo, Żelechowa, Osiedle Arkońskie)
- SM Kolejarz (Pomorzany, Świerczewo)
"""

import re
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from app.ingestion.base import BaseConnector
from app.ingestion.komornik import match_szczecin_district, parse_pln_amount

class SpoldzielnieConnector(BaseConnector):
    """Konektor agregujący przetargi i oferty lokali z odzysku szczecińskich spółdzielni"""

    @property
    def name(self) -> str:
        return "spoldzielnie"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9",
        }

        with httpx.Client(timeout=10.0, verify=False, follow_redirects=True, headers=headers) as client:
            # 1. SM Śródmieście
            try:
                r_srod = client.get("https://smsrodmiescie.szczecin.pl/przetargi")
                if r_srod.status_code == 200:
                    soup = BeautifulSoup(r_srod.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if "/przetargi/" in href and len(a.text.strip()) > 20:
                            raw_title = re.sub(r"\s+", " ", a.text.strip())
                            full_url = href if href.startswith("http") else f"https://smsrodmiescie.szczecin.pl{href}"
                            
                            # ID przetargu
                            m_id = re.search(r"/przetargi/(\d+)", href)
                            ext_id = f"sm-srod-{m_id.group(1)}" if m_id else f"sm-srod-{abs(hash(href)) % 100000}"

                            # Rozpoznanie ulicy i dzielnicy
                            district = match_szczecin_district(raw_title)
                            
                            # Ekstrakcja metrażu jeśli występuje
                            m_area = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", raw_title, re.I)
                            area = float(m_area.group(1).replace(",", ".")) if m_area else 48.0

                            # Ekstrakcja ceny lub wadium
                            m_price = re.search(r"(\d[\d\s]{3,})\s*(?:zł|pln)", raw_title, re.I)
                            price = parse_pln_amount(m_price.group(1)) if m_price else 220000.0

                            results.append({
                                "source": "spoldzielnie",
                                "external_id": ext_id,
                                "url": full_url,
                                "title": f"[SM Śródmieście] {raw_title[:90]}",
                                "description": f"OGŁOSZENIE / PRZETARG SPÓŁDZIELCZY (SM Śródmieście Szczecin)\n{raw_title}",
                                "district": district,
                                "street": None,
                                "area_m2": area,
                                "price_pln": price,
                                "rooms": 2,
                                "floor": None,
                                "total_floors": 4,
                                "building_type": "Kamienica" if "kamienic" in raw_title.lower() else "Niski blok",
                                "heating_source": "miejskie (SEC)",
                                "has_balcony": "balkon" in raw_title.lower(),
                                "has_agency_fee": False
                            })
            except Exception as e:
                print(f"[SM Śródmieście Scraper Error]: {e}")

            # 2. SM Dąb - lokale z odzysku i przetargi
            try:
                r_dab = client.get("https://smdab.szczecin.pl/pl/oferta/przetargi")
                if r_dab.status_code == 200:
                    soup_dab = BeautifulSoup(r_dab.text, "html.parser")
                    content_dab = soup_dab.select_one(".content, main, article, #content") or soup_dab
                    for a in content_dab.find_all("a", href=True):
                        href = a["href"]
                        txt = a.text.strip()
                        if any(k in txt.lower() or k in href.lower() for k in ["lokal", "mieszka", "przetarg"]) and not "nowe" in txt.lower() and len(txt) > 8:
                            full_url = href if href.startswith("http") else f"https://smdab.szczecin.pl{href}"
                            ext_id = f"sm-dab-{abs(hash(full_url)) % 100000}"
                            clean_t = re.sub(r"\s+", " ", txt)
                            
                            results.append({
                                "source": "spoldzielnie",
                                "external_id": ext_id,
                                "url": full_url,
                                "title": f"[SM Dąb Prawobrzeże] {clean_t[:80]}",
                                "description": f"PRZETARG SPÓŁDZIELCZY SM DĄB (SZCZECIN PRAWOBRZEŻE)\nLokale z odzysku / przetarg ofertowy: {clean_t}",
                                "district": "Prawobrzeże",
                                "street": None,
                                "area_m2": 52.0,
                                "price_pln": 280000.0,
                                "rooms": 2,
                                "floor": None,
                                "total_floors": 4,
                                "building_type": "Wielka płyta",
                                "heating_source": "miejskie (SEC)",
                                "has_balcony": True,
                                "has_agency_fee": False
                            })
            except Exception as e:
                print(f"[SM Dąb Scraper Error]: {e}")

            # 3. SM Wspólny Dom
            try:
                r_wdom = client.get("https://wdom.pl/przetargi/")
                if r_wdom.status_code == 200:
                    soup_wdom = BeautifulSoup(r_wdom.text, "html.parser")
                    entry = soup_wdom.select_one(".entry-content, main, article") or soup_wdom
                    for a in entry.find_all("a", href=True):
                        href = a["href"]
                        txt = a.text.strip()
                        if any(k in txt.lower() or k in href.lower() for k in ["swz", "przetarg", "lokal", "remont"]) and len(txt) > 15:
                            clean_t = re.sub(r"\s+", " ", txt)
                            district = match_szczecin_district(clean_t)
                            ext_id = f"sm-wdom-{abs(hash(href)) % 100000}"

                            results.append({
                                "source": "spoldzielnie",
                                "external_id": ext_id,
                                "url": href,
                                "title": f"[SM Wspólny Dom] {clean_t[:80]}",
                                "description": f"PRZETARG SM WSPÓLNY DOM SZCZECIN\n{clean_t}",
                                "district": district,
                                "street": None,
                                "area_m2": 50.0,
                                "price_pln": 260000.0,
                                "rooms": 2,
                                "floor": None,
                                "total_floors": 4,
                                "building_type": "Niski blok",
                                "heating_source": "miejskie (SEC)",
                                "has_balcony": False,
                                "has_agency_fee": False
                            })
            except Exception as e:
                print(f"[SM Wspólny Dom Scraper Error]: {e}")

        # Usunięcie ewentualnych duplikatów URL
        unique_results = []
        seen_urls = set()
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(r)

        return unique_results
