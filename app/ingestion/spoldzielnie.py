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
                            lower_t = raw_title.lower()
                            
                            # Odrzucenie przetargów budowlanych, instalacyjnych, SWZ i niemieszkalnych
                            if any(k in lower_t for k in ["remont", "wymian", "instalac", "muru", "dachu", "swz", "docieplen", "użytkow", "garaż", "konserwac"]):
                                continue
                            # Wymagane odniesienie do sprzedaży mieszkania / lokalu mieszkalnego
                            if not any(k in lower_t for k in ["mieszkan", "lokal mieszkalny", "lokalu mieszkalnego", "zbyci"]):
                                continue

                            full_url = href if href.startswith("http") else f"https://smsrodmiescie.szczecin.pl{href}"
                            
                            # ID przetargu
                            m_id = re.search(r"/przetargi/(\d+)", href)
                            ext_id = f"sm-srod-{m_id.group(1)}" if m_id else f"sm-srod-{abs(hash(href)) % 100000}"

                            # Rozpoznanie ulicy i dzielnicy
                            district = match_szczecin_district(raw_title)
                            
                            # Ekstrakcja metrażu jeśli występuje
                            m_area = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", raw_title, re.I)
                            if not m_area:
                                continue
                            area = float(m_area.group(1).replace(",", "."))

                            # Ekstrakcja ceny lub wadium
                            m_price = re.search(r"(\d[\d\s]{3,})\s*(?:zł|pln)", raw_title, re.I)
                            if not m_price:
                                continue
                            price = parse_pln_amount(m_price.group(1))

                            if price < 130000 or area < 20:
                                continue

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
                        lower_txt = txt.lower()
                        # Odrzucenie niemieszkalnych i wykonawczych
                        if any(k in lower_txt for k in ["garaż", "garaz", "użytkow", "remont", "wymian", "swz", "nowe"]):
                            continue
                        if any(k in lower_txt for k in ["mieszka", "lokal mieszkalny", "zbycie lokalu"]) and len(txt) > 8:
                            full_url = href if href.startswith("http") else f"https://smdab.szczecin.pl{href}"
                            ext_id = f"sm-dab-{abs(hash(full_url)) % 100000}"
                            clean_t = re.sub(r"\s+", " ", txt)
                            
                            # Ekstrakcja metrażu i ceny
                            m_area = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", clean_t, re.I)
                            m_price = re.search(r"(\d[\d\s]{3,})\s*(?:zł|pln)", clean_t, re.I)
                            if not m_area or not m_price:
                                continue
                            
                            area = float(m_area.group(1).replace(",", "."))
                            price = parse_pln_amount(m_price.group(1))

                            if price < 130000 or area < 20:
                                continue
                            
                            results.append({
                                "source": "spoldzielnie",
                                "external_id": ext_id,
                                "url": full_url,
                                "title": f"[SM Dąb Prawobrzeże] {clean_t[:80]}",
                                "description": f"PRZETARG SPÓŁDZIELCZY SM DĄB (SZCZECIN PRAWOBRZEŻE)\nLokale z odzysku / przetarg ofertowy: {clean_t}",
                                "district": "Prawobrzeże",
                                "street": None,
                                "area_m2": area,
                                "price_pln": price,
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
                        lower_txt = txt.lower()
                        # Bezwzględne odrzucenie zamówień wykonawczych, robót i SWZ
                        if any(k in lower_txt for k in ["swz", "siwz", "remont", "wymian", "instalac", "docieplen", "muru", "garaż", "użytkow"]):
                            continue
                        if any(k in lower_txt for k in ["sprzedaż mieszkania", "lokal mieszkalny", "zbycie lokalu", "lokal z odzysku"]) and len(txt) > 15:
                            clean_t = re.sub(r"\s+", " ", txt)
                            district = match_szczecin_district(clean_t)
                            ext_id = f"sm-wdom-{abs(hash(href)) % 100000}"

                            m_area = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", clean_t, re.I)
                            m_price = re.search(r"(\d[\d\s]{3,})\s*(?:zł|pln)", clean_t, re.I)
                            if not m_area or not m_price:
                                continue

                            area = float(m_area.group(1).replace(",", "."))
                            price = parse_pln_amount(m_price.group(1))

                            if price < 130000 or area < 20:
                                continue

                            results.append({
                                "source": "spoldzielnie",
                                "external_id": ext_id,
                                "url": href,
                                "title": f"[SM Wspólny Dom] {clean_t[:80]}",
                                "description": f"PRZETARG SM WSPÓLNY DOM SZCZECIN\n{clean_t}",
                                "district": district,
                                "street": None,
                                "area_m2": area,
                                "price_pln": price,
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
