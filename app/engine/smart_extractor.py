"""
Smart Extractor dla Nesta Deal Hunter Szczecin.
Automatyczne wyodrębnianie parametrów nieruchomości ze zrzutów ekranu (print screenów),
surowego tekstu ogłoszenia lub bezpośrednich linków URL.
Zgodnie ze Standardem Nesta Home v4.16 - zero dodatkowych pól dla użytkownika.
"""

import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger("smart_extractor")

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from curl_cffi import requests as curl_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False
    import httpx

DISTRICT_PATTERNS = [
    (r'\bturzyn(?:ie|em|a)?\b', "Turzyn"),
    (r'\bpogodn(?:o|a|ie|em)?\b', "Pogodno"),
    (r'\bniebuszew(?:o|a|ie|em|-bolinko)?\b|\bbolink(?:o|a|u)?\b', "Niebuszewo"),
    (r'\b(?:śródmieści|srodmiesci)(?:e|u|a|em)?\b', "Śródmieście"),
    (r'\bcentrum\b', "Centrum"),
    (r'\bgumieńc(?:e|ach|ami)?\b|\bgumienc(?:e|ach|ami)?\b', "Gumieńce"),
    (r'\bpomorzan(?:y|ach|ami)?\b', "Pomorzany"),
    (r'\bwarszew(?:o|a|ie|em)?\b', "Warszewo"),
    (r'\b(?:drzetow|grabow)(?:o|a|ie|em)?\b', "Drzetowo-Grabowo"),
    (r'\b(?:stare\s+miasto|starym\s+mieście|starówk[aięe])\b', "Śródmieście"),
    (r'\b(?:nowe\s+miasto|nowym\s+mieście)\b', "Centrum"),
    (r'\bbukow(?:e|ym|ego)?\b', "Bukowe"),
    (r'\bsłoneczn(?:e|ym|ego)?\b|\bsloneczn(?:e|ym|ego)?\b', "Słoneczne"),
    (r'\bmajow(?:e|ym|ego)?\b', "Majowe"),
    (r'\bdąbi(?:e|u|em)?\b|\bdabi(?:e|u|em)?\b', "Dąbie"),
    (r'\bprawobrzeż(?:e|u|a|em)?\b|\bprawobrzez(?:e|u|a|em)?\b', "Prawobrzeże"),
    (r'\bzdroj(?:e|ach|ami)?\b', "Zdroje"),
    (r'\bpodjuch(?:y|ach|ami)?\b', "Podjuchy"),
    (r'\bkrzekow(?:o|a|ie)?\b|\bbezrzecz(?:e|u)?\b', "Krzekowo-Bezrzecze"),
    (r'\bosow(?:o|a|ie)?\b|\bosów\b', "Osów"),
    (r'\bgłębok(?:ie|im)?\b|\bglebok(?:ie|im)?\b', "Głębokie"),
    (r'\bżelechow(?:a|y|ie)?\b|\bzelechow(?:a|y|ie)?\b', "Żelechowa"),
    (r'\bgolęcin(?:o|a|ie)?\b|\bgolecin(?:o|a|ie)?\b', "Golęcino"),
    (r'\bstołczyn(?:ie|em|a)?\b|\bstolczyn(?:ie|em|a)?\b', "Stołczyn"),
    (r'\bskolwin(?:ie|em|a)?\b', "Skolwin")
]

POPULAR_STREETS = [
    "Śląska", "Slaska", "Mickiewicza", "Wojska Polskiego", "Piłsudskiego", "Pilsudskiego",
    "Jagiellońska", "Jagiellonska", "Krzywoustego", "Bohaterów Warszawy", "Bohaterow Warszawy",
    "Piastów", "Piastow", "Wyzwolenia", "Niepodległości", "Niepodleglosci", "Wielkopolska",
    "Monte Cassino", "Rayskiego", "Mazurska", "Narutowicza", "Kopernika", "Kaszubska",
    "Bogusława", "Boguslawa", "5 Lipca", "Wojciecha", "Edmunda Bałuki", "Baluki",
    "Grodzka", "Tkacka", "Koński Kierat", "Konski Kierat", "Staromłyńska", "Staromlynska",
    "Królowej Korony Polskiej", "Krolowej Korony Polskiej", "Wawrzyniaka", "Traugutta",
    "Krasickiego", "Wyszyńskiego", "Wyszynskiego", "Kolejowa", "Chmielewskiego", "Smolańska", "Smolanska"
]


def extract_from_url(url: str) -> Tuple[str, str, Dict[str, Any]]:
    """Pobiera zawartość strony i metadane z podanego linku"""
    from app.engine.freshness_checker import check_single_url_alive
    is_alive, reason = check_single_url_alive(url)
    if not is_alive:
        raise ValueError(f"Ogłoszenie na portalu źródłowym jest nieaktualne lub wygasło: {reason}")

    html = ""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    if CURL_AVAILABLE:
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=12, headers=headers)
            html = r.text
        except Exception as e:
            logger.warning(f"curl_cffi fetch error: {e}")
    
    if not html:
        import httpx
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            html = r.text

    soup = BeautifulSoup(html, "html.parser")
    
    title = ""
    og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    desc = ""
    og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    if og_desc and og_desc.get("content"):
        desc = og_desc["content"].strip()

    # Ekstrakcja danych z JSON-LD (Otodom, OLX, Gratka)
    meta_props = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0] if data else {}
            if isinstance(data, dict):
                # Price
                offers = data.get("offers", {})
                if isinstance(offers, dict) and offers.get("price"):
                    meta_props["price_pln"] = float(offers["price"])
                elif isinstance(offers, list) and offers and offers[0].get("price"):
                    meta_props["price_pln"] = float(offers[0]["price"])
                # Floor size
                if data.get("floorSize", {}).get("value"):
                    meta_props["area_m2"] = float(data["floorSize"]["value"])
                # Rooms
                if data.get("numberOfRooms"):
                    meta_props["rooms"] = int(data["numberOfRooms"])
                # Address
                address = data.get("address", {})
                if isinstance(address, dict):
                    if address.get("streetAddress"):
                        meta_props["street"] = address["streetAddress"]
                    if address.get("addressLocality"):
                        meta_props["district"] = address["addressLocality"]
                # Date posted
                raw_date = data.get("datePosted") or data.get("dateCreated") or data.get("uploadDate")
                if raw_date:
                    try:
                        meta_props["published_at"] = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                    except Exception:
                        pass
        except Exception:
            pass

    # Treść tekstowa
    # Usuwamy skrypty i style
    for s in soup(["script", "style", "nav", "footer", "header"]):
        s.extract()
    body_text = soup.get_text(separator=" ", strip=True)
    full_text = f"{title}\n{desc}\n{body_text[:3500]}"
    
    return title, full_text, meta_props


def extract_with_gemini(text: str, image_bytes: Optional[bytes] = None, mime_type: str = "image/jpeg") -> Optional[Dict[str, Any]]:
    """Wykorzystuje Gemini 2.5 Flash do ekstrakcji strukturalnej JSON z tekstu lub obrazu"""
    if not (settings.GEMINI_API_KEY and GENAI_AVAILABLE):
        return None

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = """Jesteś analitykiem nieruchomości w firmie Nesta Home w Szczecinie.
Wyodrębnij z poniższego materiału (tekstu lub zrzutu ekranu ogłoszenia) dane mieszkania i zwróć WYŁĄCZNIE czysty JSON:
{
  "title": "Tytuł ogłoszenia lub zwięzły nagłówek (np. Śródmieście, 2 pokoje w kamienicy)",
  "district": "Dzielnica w Szczecinie (np. Śródmieście, Centrum, Pogodno, Turzyn, Pomorzany, Gumieńce, Niebuszewo, Warszewo, Prawobrzeże)",
  "street": "Nazwa ulicy jeśli podano, lub null",
  "price_pln": 285000,
  "area_m2": 48.5,
  "rooms": 2,
  "floor": 2,
  "total_floors": 4,
  "building_type": "Kamienica" (lub "Wielka płyta", "Niski blok", "Nowe budownictwo"),
  "heating_source": "piece kaflowe" (lub "miejskie", "gazowe", "elektryczne"),
  "has_balcony": false,
  "has_elevator": false,
  "is_private_seller": true,
  "description": "Krótkie streszczenie opisu i stanu lokalu"
}
Wymagania:
- price_pln i area_m2 muszą być liczbami (float/int).
- Jeśli cena jest podana w tysiącach (np. 340 tys.), zamień na 340000.
- Jeśli brak pewności co do dzielnicy, wybierz najbardziej pasującą dzielnicę Szczecina.
Zwróć wyłącznie poprawny obiekt JSON, bez znaczników markdown.
"""
        contents = []
        if image_bytes:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
            contents.append(prompt + (f"\nDodatkowy kontekst tekstowy: {text}" if text else ""))
        else:
            contents.append(f"{prompt}\n\nTREŚĆ OGŁOSZENIA:\n{text[:4000]}")

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        if response and response.text:
            cleaned = response.text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
    except Exception as e:
        logger.error(f"Błąd ekstrakcji Gemini: {e}")
    return None


def parse_heuristics(text: str) -> Dict[str, Any]:
    """
    Zaawansowany lokalny parser heurystyczno-regexowy dla rynku szczecińskiego.
    Działa w 100% offline, bez konieczności używania tokenów AI.
    """
    clean_text = text.replace("\xa0", " ")
    lower_text = clean_text.lower()
    data: Dict[str, Any] = {
        "title": "Wklejona oferta Szczecin",
        "district": "Śródmieście",
        "street": None,
        "price_pln": 0.0,
        "area_m2": 0.0,
        "rooms": 2,
        "floor": None,
        "total_floors": None,
        "building_type": "Kamienica",
        "heating_source": "piece kaflowe",
        "has_balcony": False,
        "has_elevator": False,
        "is_private_seller": False,
        "description": clean_text[:1200]
    }

    # 1. Ekstrakcja Ceny (PLN)
    # Szukamy wzorców: "345 000 zł", "345.000 zł", "345000 zł", "345 tys", "345 000"
    price_patterns = [
        r'(?:cena|kwota|odstępne)?[:\s]*(\d{1,3}(?:[\s.]\d{3})+)\s*(?:zł|pln)',
        r'(\d{2,4})\s*tys(?:\.?|\s*zł|\s*pln)',
        r'(?:cena|kwota)[:\s]*(\d{5,7})\s*(?:zł|pln)?',
        r'(\d{5,7})\s*(?:zł|pln)'
    ]
    for p in price_patterns:
        match = re.search(p, lower_text)
        if match:
            raw_val = match.group(1).replace(" ", "").replace(".", "").strip()
            if "tys" in match.group(0):
                data["price_pln"] = float(raw_val) * 1000.0
            else:
                data["price_pln"] = float(raw_val)
            break

    # 2. Ekstrakcja Metrażu (m²)
    # Wzorce: "48,5 m2", "48.5 m²", "48 mkw", "48 metrów", "powierzchnia: 48"
    area_patterns = [
        r'(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:m2|m²|mkw|m\s*kw|metrów|metrow)',
        r'(?:powierzchnia|metraż|pow\.)[:\s]*(\d{1,3}(?:[.,]\d{1,2})?)'
    ]
    for p in area_patterns:
        match = re.search(p, lower_text)
        if match:
            raw_val = match.group(1).replace(",", ".").strip()
            try:
                area_candidate = float(raw_val)
                if 12.0 <= area_candidate <= 300.0:
                    data["area_m2"] = area_candidate
                    break
            except ValueError:
                pass

    # 3. Wykrywanie Dzielnicy Szczecina
    for pat, official_name in DISTRICT_PATTERNS:
        if re.search(pat, lower_text):
            data["district"] = official_name
            break

    # 4. Wykrywanie Ulicy
    street_match = re.search(r'ul\.\s*([A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż\s\-]+?)(?:,|\.|\d|\n|$)', clean_text)
    if street_match:
        cand = street_match.group(1).strip()
        if len(cand) > 2 and len(cand) < 40 and not any(w in cand.lower() for w in ["szczecin", "kamienica", "blok"]):
            data["street"] = f"ul. {cand}"
    if not data["street"]:
        for street in POPULAR_STREETS:
            if re.search(r'\b' + re.escape(street.lower()) + r'\b', lower_text):
                data["street"] = f"ul. {street}"
                break

    # 5. Liczba Pokoi
    if "kawalerka" in lower_text or "1-pokoj" in lower_text or "1 pok" in lower_text:
        data["rooms"] = 1
    else:
        rooms_match = re.search(r'(\d)\s*(?:pokoj|pokoje|pokoi|pok\b)', lower_text)
        if rooms_match:
            data["rooms"] = int(rooms_match.group(1))

    # 6. Piętro
    if "parter" in lower_text or "parterze" in lower_text:
        data["floor"] = 0
    else:
        floor_match = re.search(r'(\d)\s*(?:piętro|pietrze|p\.)', lower_text)
        if floor_match:
            data["floor"] = int(floor_match.group(1))

    # 7. Typ Budynku
    if any(k in lower_text for k in ["kamienica", "kamienicy", "stara cegła"]):
        data["building_type"] = "Kamienica"
    elif any(k in lower_text for k in ["wielka płyta", "wieżowiec", "z płyty", "wiezowiec"]):
        data["building_type"] = "Wielka płyta"
    elif any(k in lower_text for k in ["nowe budownictwo", "apartamentowiec", "deweloper", "202"]):
        data["building_type"] = "Nowe budownictwo"
    elif "blok" in lower_text:
        data["building_type"] = "Niski blok"

    # 8. Ogrzewanie
    if any(k in lower_text for k in ["piec kaflowy", "piece kaflowe", "kaflak", "ogrzewanie piecowe", "piecowe"]):
        data["heating_source"] = "piece kaflowe"
    elif any(k in lower_text for k in ["miejskie", "sec", "z sieci"]):
        data["heating_source"] = "miejskie"
    elif any(k in lower_text for k in ["gazowe", "piec 2-f", "piec gazowy", "kocioł gazowy"]):
        data["heating_source"] = "gazowe"
    elif "elektryczne" in lower_text:
        data["heating_source"] = "elektryczne"

    # 9. Balkon, Winda, Bezpośrednio
    if any(k in lower_text for k in ["balkon", "balkonem", "loggia", "taras"]):
        data["has_balcony"] = True
    if any(k in lower_text for k in ["winda", "windą", "windzie"]):
        data["has_elevator"] = True
    if any(k in lower_text for k in ["bezpośrednio", "od właściciela", "bez prowizji", "bez pośredników", "prywatnie"]):
        data["is_private_seller"] = True

    # 10. Tytuł
    first_line = clean_text.strip().split("\n")[0]
    if len(first_line) > 10 and len(first_line) < 100:
        data["title"] = first_line
    else:
        street_str = f", {data['street']}" if data['street'] else ""
        data["title"] = f"{data['district']}{street_str} – {data['rooms']} pok., {data['area_m2']} m²"

    return data


def smart_extract_listing(
    url: Optional[str] = None,
    raw_text: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg"
) -> Tuple[Dict[str, Any], str]:
    """
    Główna funkcja orkiestrująca Smart Extractor.
    Obsługuje Link, Print screen lub Wklejony tekst bez żadnych innych danych od użytkownika.
    """
    extracted_data = None
    extraction_source_note = ""

    fetched_url_text = ""
    meta_from_url = {}

    # Krok 1: Jeśli podano link URL
    if url and url.strip():
        url_clean = url.strip()
        try:
            _, fetched_url_text, meta_from_url = extract_from_url(url_clean)
            extraction_source_note = f"Pobrano treść ze strony {url_clean}"
        except Exception as e:
            logger.warning(f"Błąd pobierania strony z URL {url_clean}: {e}")
            extraction_source_note = f"Nie udało się wczytać strony automatycznie ({e})"

    # Łączymy treść z URL i ewentualny wpisany tekst
    combined_text = "\n".join(filter(None, [raw_text, fetched_url_text]))

    # Krok 2: Próba ekstrakcji przez Gemini (z obrazu lub tekstu)
    if settings.GEMINI_API_KEY and GENAI_AVAILABLE:
        ai_res = extract_with_gemini(text=combined_text, image_bytes=image_bytes, mime_type=mime_type)
        if ai_res and ai_res.get("price_pln") and ai_res.get("area_m2"):
            extracted_data = ai_res
            extraction_source_note = "Przeanalizowano i wyodrębniono przez model AI (Gemini 2.5 Flash)"

    # Krok 3: Fallback heurystyczny jeśli AI nie jest skonfigurowane lub zawiodło
    if not extracted_data:
        extracted_data = parse_heuristics(combined_text)
        # Uzupełniamy ewentualne dane wyciągnięte z JSON-LD strony
        for k, v in meta_from_url.items():
            if v and (not extracted_data.get(k) or extracted_data.get(k) == 0):
                extracted_data[k] = v
        if image_bytes and not combined_text.strip():
            extraction_source_note = "Zrzut ekranu zapisany. Dodaj klucz GEMINI_API_KEY w .env, aby AI bezpośrednio odczytywało parametry z obrazu."
        else:
            extraction_source_note = "Wyodrębniono automatycznie przez silnik reguł Nesta Home"

    # Nadajemy metadane źródłowe
    extracted_data["source"] = "manual"
    if url:
        extracted_data["url"] = url.strip()

    return extracted_data, extraction_source_note
