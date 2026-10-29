"""
Konektor: ZBiLK Szczecin (Zarząd Budynków i Lokali Komunalnych w Szczecinie)
Przeszukuje oficjalne wykazy lokali mieszkalnych do remontu, pustostanów
w kamienicach oraz miejskich przetargów komunalnych w Szczecinie.
"""

import re
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from app.ingestion.base import BaseConnector
from app.ingestion.komornik import match_szczecin_district, parse_pln_amount

def parse_area_m2(s: str) -> float:
    """Ekstrahuje metraż w m2 (np. '52,72 m2' -> 52.72)"""
    if not s:
        return 0.0
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    return float(m.group(1).replace(",", ".")) if m else 0.0

class ZbilkConnector(BaseConnector):
    """Konektor dla Zasobów Komunalnych ZBiLK Szczecin (wykazy mieszkań do remontu i przetargi)"""

    @property
    def name(self) -> str:
        return "zbilk"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9",
        }

        urls_to_scrape = [
            # Wykaz stały mieszkań do remontu przez przyszłego najemcę (pustostany w kamienicach)
            ("https://zbilk.szczecin.pl/?type=wykazy&action=view&id=32", "Wykaz stały do remontu"),
            # Wykaz lokali mieszkalnych TBS i komunalnych
            ("https://zbilk.szczecin.pl/?type=wykazy&action=view&id=69", "Wykaz TBS/Gmina 69"),
            ("https://zbilk.szczecin.pl/?type=wykazy&action=view&id=70", "Wykaz TBS/Gmina 70"),
            ("https://zbilk.szczecin.pl/?type=wykazy&action=view&id=72", "Wykaz TBS/Gmina 72"),
        ]

        seen_streets = set()

        try:
            with httpx.Client(timeout=14.0, verify=False, follow_redirects=True, headers=headers) as client:
                for base_url, category_name in urls_to_scrape:
                    try:
                        resp = client.get(base_url)
                        if resp.status_code != 200:
                            continue

                        soup = BeautifulSoup(resp.text, "html.parser")
                        table = soup.find("table")
                        if not table:
                            continue

                        rows = table.find_all("tr")
                        if len(rows) <= 1:
                            continue

                        # Odczyt nagłówków kolumn
                        headers_cols = [c.get_text(" ", strip=True).upper() for c in rows[0].find_all(["th", "td"])]

                        for row in rows[1:]:
                            cells = row.find_all(["td", "th"])
                            cols = [c.get_text(" ", strip=True) for c in cells]
                            if len(cols) < 4:
                                continue

                            street = cols[0].strip()
                            if not street or street.lower() in seen_streets:
                                continue
                            seen_streets.add(street.lower())

                            # Mapowanie kolumn
                            area_u = 0.0
                            area_m = 0.0
                            rooms = None
                            bath = "BRAK"
                            wc = "NA KLATCE"
                            floor = None
                            heating = "PIECE KAFLOWE"
                            cost_remont = 0.0
                            rent = 0.0

                            for idx, h_name in enumerate(headers_cols):
                                if idx >= len(cols):
                                    break
                                val = cols[idx]
                                if "POW. UŻYTKOWA" in h_name or "POW. U" in h_name:
                                    area_u = parse_area_m2(val)
                                elif "POW. MIESZKALNA" in h_name:
                                    area_m = parse_area_m2(val)
                                elif "ILOŚĆ POKOI" in h_name or "POKO" in h_name:
                                    rooms = int(val) if val.isdigit() else None
                                elif "ŁAZIENKA" in h_name:
                                    bath = val
                                elif "WC" in h_name:
                                    wc = val
                                elif "PIĘTRO" in h_name:
                                    if "parter" in val.lower():
                                        floor = 0
                                    elif val.isdigit():
                                        floor = int(val)
                                elif "OGRZEWANIE" in h_name:
                                    heating = val
                                elif "KOSZT REMONTU" in h_name:
                                    cost_remont = parse_pln_amount(val)
                                elif "CZYNSZ" in h_name:
                                    rent = parse_pln_amount(val)

                            # Domyślny koszt remontu i cena jeśli w wykazie nie ma podanej kwoty
                            if cost_remont <= 0.0:
                                # Standardowy koszt remontu ZBiLK: ~1400 zł/m2
                                cost_remont = round(area_u * 1400.0, 2) if area_u > 0 else 65000.0

                            # Link do karty lokalu / pobrania
                            link_el = row.find("a", href=True)
                            href = link_el["href"] if link_el else ""
                            full_url = f"https://zbilk.szczecin.pl/{href}" if href and not href.startswith("http") else (href if href else base_url)

                            # Identyfikator zewnętrzny
                            lokal_match = re.search(r"lokal=(\d+)", href)
                            ext_id = f"zbilk-lokal-{lokal_match.group(1)}" if lokal_match else f"zbilk-{abs(hash(street)) % 100000}"

                            # Standaryzacja ogrzewania pod reguły Nesta Home
                            norm_heating = "piece kaflowe"
                            h_lower = heating.lower()
                            if "sieci" in h_lower or "miejsk" in h_lower or "c.o." in h_lower:
                                norm_heating = "miejskie (SEC)"
                            elif "gaz" in h_lower:
                                norm_heating = "gazowe (kocioł 2-f)"
                            elif "elektr" in h_lower:
                                norm_heating = "elektryczne"

                            district = match_szczecin_district(category_name, street)

                            description = (
                                f"MIEJSKI ZASÓB KOMUNALNY ZBILK SZCZECIN ({category_name})\n"
                                f"Adres: {street}, Szczecin ({district})\n"
                                f"Metraż użytkowy: {area_u} m² | Powierzchnia mieszkalna: {area_m} m²\n"
                                f"Liczba pokoi: {rooms or 1} | Piętro: {floor if floor is not None else 'N/A'}\n"
                                f"Łazienka: {bath} | WC: {wc}\n"
                                f"Ogrzewanie: {heating}\n"
                                f"Oficjalny kosztorys remontu ZBiLK: {cost_remont:,.0f} zł\n"
                                f"Miesięczny czynsz najmu: {rent:,.2f} zł\n"
                                f"Program Mieszkanie za Remont - potencjał na flip po adaptacji/wykupie z bonifikatą miejską."
                            )

                            if area_u > 0:
                                results.append({
                                    "source": "zbilk",
                                    "external_id": ext_id,
                                    "url": full_url,
                                    "title": f"Lokal ZBiLK Szczecin: {street} ({area_u} m²)",
                                    "description": description,
                                    "district": district,
                                    "street": street,
                                    "area_m2": area_u,
                                    "price_pln": cost_remont,
                                    "rooms": rooms,
                                    "floor": floor,
                                    "total_floors": 4,
                                    "building_type": "Kamienica",
                                    "heating_source": norm_heating,
                                    "has_balcony": False,
                                    "has_agency_fee": False
                                })

                    except Exception as pe:
                        print(f"[ZBiLK Page Error {base_url}]: {pe}")
                        continue

        except Exception as e:
            print(f"[ZBiLK Scraper Global Error]: {e}")

        return results
