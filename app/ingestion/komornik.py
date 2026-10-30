"""
Konektor: E-Licytacje i Obwieszczenia Komornicze Szczecin (Krajowa Rada Komornicza)
Oficjalny portal licytacji komorniczych dla Sądów Rejonowych w Szczecinie.
Pozwala na zakup nieruchomości z dyskontem 25-34% (3/4 lub 2/3 sumy oszacowania).
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from app.ingestion.base import BaseConnector

def match_szczecin_district(text: str, street: Optional[str] = "") -> str:
    """Rozpoznaje dzielnicę Szczecina na podstawie ulicy i treści ogłoszenia"""
    combined = f"{street or ''} {text or ''}".lower()
    
    # Precyzyjne dopasowanie ulic
    street_map = {
        "Pogodno": ["mickiewicza", "wernyhory", "reymonta", "poniatowskiego", "traugutta", "krasickiego", "konopnickiej", "szeroka", "żołnierska", "somosierry"],
        "Turzyn": ["bohaterów warszawy", "pocztowa", "chodkiewicza", "żółkiewskiego", "bolesława śmiałego", "ściegiennego", "turzyńska"],
        "Śródmieście": ["5 lipca", "piastów", "krzywoustego", "jagiellońska", "rayskiego", "śląska", "wielkopolska", "monte cassino", "narutowicza", "bogusława", "kaszubska"],
        "Centrum": ["wyzwolenia", "niepodległości", "wojska polskiego", "plac rodła", "plac grunwaldzki", "plac kościuszki", "papieża jana pawła", "dworcowa", "3 maja"],
        "Niebuszewo": ["krasińskiego", "słowackiego", "asnyka", "orzeszkowej", "kołłątaja", "długosza", "niemcewicza", "warcisława"],
        "Pomorzany": ["powstańców wielkopolskich", "budziszyńska", "chmielewskiego", "dunikowskiego", "milczańska", "smolańska", "starkiewicza"],
        "Gumieńce": ["ku słońcu", "derdowskiego", "kwiatowa", "hrubieszowska", "okulickiego", "krakowska"],
        "Warszewo": ["duńska", "złotowska", "szczecińska", "rostocka", "poznańska"],
        "Prawobrzeże": ["rydla", "łubinowa", "kolorowych domów", "chłopska", "jasna", "struga", "gryfińska", "goleniowska", "emilii gierczak", "dąbie", "słoneczne", "bukowe", "majowe", "zdroje", "podjuchy"]
    }
    
    for dist, st_list in street_map.items():
        if any(st in combined for st in st_list):
            return dist
            
    # Dopasowanie po nazwach dzielnic
    for d in ["Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno", "Gumieńce", "Pomorzany", "Warszewo", "Prawobrzeże"]:
        if d.lower() in combined:
            return d
            
    return "Centrum"

def parse_pln_amount(s: str) -> float:
    """Czyści i parsuje kwoty w PLN z formatu polskiego (np. '377 250,00 zł')"""
    if not s:
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", s).replace(",", ".")
    try:
        return float(cleaned)
    except:
        return 0.0

class KomornikConnector(BaseConnector):
    """Konektor API do Portalu Obwieszczeń i Licytacji Komorniczych (licytacje.komornik.pl)"""

    @property
    def name(self) -> str:
        return "elicytacje"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        search_url = "https://licytacje.komornik.pl/services/item-back/rest/item/notice/published"
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://licytacje.komornik.pl",
            "Referer": "https://licytacje.komornik.pl/wyszukiwarka/obwieszczenia-o-licytacji"
        }

        payload = {
            "limit": 50,
            "pageNumber": 0,
            "sortBy": "publicationDate",
            "sortOrder": "DESC",
            "object": {
                "filters": [
                    {"field": "city", "operator": "LIKE", "value": "Szczecin"},
                    {"field": "category", "operator": "=", "value": "REAL_ESTATE"}
                ]
            }
        }

        try:
            resp = cffi_requests.post(
                search_url,
                json=payload,
                headers=headers,
                impersonate="chrome124",
                timeout=15
            )

            if resp.status_code != 200:
                print(f"[Komornik Scraper Warning]: HTTP status {resp.status_code}")
                return results

            data = resp.json()
            items = data.get("object", [])
            if not isinstance(items, list):
                return results

            for item in items:
                try:
                    notice_id = item.get("id")
                    if not notice_id:
                        continue

                    title = item.get("title") or "Licytacja komornicza lokalu w Szczecinie"
                    type_str = item.get("type") or "APARTMENTS"
                    start_date = item.get("startDate") or ""
                    
                    addr = item.get("address") or {}
                    city_raw = (addr.get("city") or "").strip().lower()
                    if city_raw and city_raw != "szczecin":
                        continue

                    street_name = (addr.get("street") or "").strip()
                    building_no = (addr.get("buildingNo") or "").strip()
                    flat_no = (addr.get("flatNo") or "").strip()
                    zip_code = (addr.get("zipCode") or "").strip()
                    
                    street_full = f"{street_name} {building_no}".strip()
                    if flat_no:
                        street_full = f"{street_full}/{flat_no}"

                    # Pobieranie szczegółów obwieszczenia
                    detail_url = f"https://licytacje.komornik.pl/services/item-back/rest/item/notice/{notice_id}"
                    price = 0.0
                    estimate = 0.0
                    rekojmia = 0.0
                    content_clean = ""
                    office_name = ""

                    try:
                        d_resp = cffi_requests.get(
                            detail_url,
                            headers=headers,
                            impersonate="chrome124",
                            timeout=6
                        )
                        if d_resp.status_code == 200:
                            d_obj = d_resp.json().get("object", {})
                            office_name = d_obj.get("officeName") or ""
                            content_html = d_obj.get("content") or ""
                            soup = BeautifulSoup(content_html, "html.parser")
                            content_clean = soup.get_text("\n", strip=True)

                            # Parsowanie ceny wywołania
                            m_price = re.search(r"Cena\s+wywo[łl]ania\s*\n*\s*([\d\s\xa0]+,\d{2})\s*z[łl]", content_clean, re.I)
                            if m_price:
                                price = parse_pln_amount(m_price.group(1))

                            # Parsowanie sumy oszacowania
                            m_est = re.search(r"Suma\s+oszacowania\s*\n*\s*([\d\s\xa0]+,\d{2})\s*z[łl]", content_clean, re.I)
                            if m_est:
                                estimate = parse_pln_amount(m_est.group(1))

                            # Parsowanie rękojmi
                            m_rek = re.search(r"Wysoko[sś][ćc]\s+r[eę]kojmi\s*\n*\s*([\d\s\xa0]+,\d{2})\s*z[łl]", content_clean, re.I)
                            if m_rek:
                                rekojmia = parse_pln_amount(m_rek.group(1))

                    except Exception as de:
                        print(f"[Komornik Detail Error {notice_id}]: {de}")

                    # Weryfikacja treści: bezwzględne odrzucenie udziałów, służebności, nieruchomości niemieszkalnych i obcych miast
                    check_text = f"{title} {content_clean} {office_name}".lower()
                    if "szczecinek" in check_text or "sąd rejonowy w szczecinku" in check_text:
                        continue
                    if any(k in check_text for k in ["służebność osobist", "służebnością osobist", "dożywoci", "umowa dożywocia"]):
                        continue
                    if any(k in check_text for k in ["udział w", "udziału w", "1/2 części", "1/2 udziału", "licytacja udziału", "ułamek nieruchomości", "współwłasność"]):
                        continue
                    if any(k in check_text for k in ["lokal użytkowy", "lokale użytkowe", "lokalu użytkowego", "grunty", "wieczystego gruntu", "działka", "obiekt"]):
                        continue

                    # Fallback dla ceny
                    if price <= 0.0 and estimate > 0.0:
                        price = round(estimate * 0.75, 2)  # 3/4 oszacowania

                    # Parsowanie metrażu (z tytułu lub z treści)
                    area = 0.0
                    m_area = re.search(r"(\d+(?:[.,]\d+)?)\s*m2", f"{title} {content_clean}", re.I)
                    if m_area:
                        area = float(m_area.group(1).replace(",", "."))

                    # Jeśli brak realnego metrażu lub cena zbyt niska, pomijamy
                    if area <= 0.0 or price < 50000.0:
                        continue

                    # Parsowanie pokoi
                    rooms = None
                    if "jeden pokój" in content_clean.lower() or "1 pok" in content_clean.lower() or "kawalerka" in content_clean.lower():
                        rooms = 1
                    elif "dwa pokoje" in content_clean.lower() or "2 pok" in content_clean.lower():
                        rooms = 2
                    elif "trzy pokoje" in content_clean.lower() or "3 pok" in content_clean.lower():
                        rooms = 3
                    elif "cztery pokoje" in content_clean.lower() or "4 pok" in content_clean.lower():
                        rooms = 4
                    else:
                        m_r = re.search(r"(\d+)\s*pok", f"{title} {content_clean}", re.I)
                        if m_r:
                            rooms = int(m_r.group(1))

                    # Parsowanie piętra
                    floor = None
                    total_floors = None
                    lower_text = content_clean.lower()
                    if "parter" in lower_text:
                        floor = 0
                    elif "iv piętrze" in lower_text or "4 piętrze" in lower_text or "iv p." in lower_text:
                        floor = 4
                    elif "iii piętrze" in lower_text or "3 piętrze" in lower_text or "iii p." in lower_text:
                        floor = 3
                    elif "ii piętrze" in lower_text or "2 piętrze" in lower_text or "ii p." in lower_text:
                        floor = 2
                    elif "i piętrze" in lower_text or "1 piętrze" in lower_text or "i p." in lower_text:
                        floor = 1

                    # Typ budynku
                    building_type = "Kamienica" if any(w in lower_text for w in ["kamienic", "oficyn", "starym budownictwie"]) else ("Wielka płyta" if "wielkiej płyty" in lower_text or "wieżowcu" in lower_text else "Niski blok")

                    # Ogrzewanie
                    heating = None
                    if "piec" in lower_text or "kaflow" in lower_text:
                        heating = "piece kaflowe"
                    elif "sieci miejskiej" in lower_text or "sec" in lower_text or "miejsk" in lower_text:
                        heating = "miejskie (SEC)"
                    elif "gaz" in lower_text:
                        heating = "gazowe (kocioł 2-f)"

                    # Dzielnica
                    district = match_szczecin_district(content_clean, street_full)

                    # Treść opisu z parametrami licytacyjnymi
                    discount_pct = ((estimate - price) / estimate * 100) if estimate > 0 else 25.0
                    header_desc = (
                        f"OBWIESZCZENIE O LICYTACJI KOMORNICZEJ (SZCZECIN)\n"
                        f"Termin licytacji: {start_date}\n"
                        f"Cena wywołania: {price:,.0f} zł | Suma oszacowania: {estimate:,.0f} zł (dyskonto: {discount_pct:.1f}%)\n"
                        f"Rękojmia (wadium): {rekojmia:,.0f} zł\n"
                        f"Organ: {office_name}\n"
                        f"Adres: {street_full}, Szczecin\n"
                        f"--------------------------------------------------\n"
                    )
                    full_desc = f"{header_desc}{content_clean[:1800]}"

                    if price > 0:
                        results.append({
                            "source": "elicytacje",
                            "external_id": str(notice_id),
                            "url": f"https://licytacje.komornik.pl/wyszukiwarka/obwieszczenia-o-licytacji/{notice_id}",
                            "title": title,
                            "description": full_desc,
                            "district": district,
                            "street": street_full if street_full else None,
                            "area_m2": area,
                            "price_pln": price,
                            "rooms": rooms,
                            "floor": floor,
                            "total_floors": total_floors,
                            "building_type": building_type,
                            "heating_source": heating,
                            "has_balcony": "balkon" in lower_text or "taras" in lower_text,
                            "has_agency_fee": False
                        })

                except Exception as ie:
                    print(f"[Komornik Item Error]: {ie}")
                    continue

        except Exception as e:
            print(f"[Komornik Scraper Global Error]: {e}")

        return results
