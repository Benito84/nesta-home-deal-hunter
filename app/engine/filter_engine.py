"""
Pre-AI Filtering Engine dla Nesta Home Szczecin.
Twarde reguły biznesowe odsiewające szum i oszczędzające zapytania do LLM.
"""

from typing import Tuple, Dict, Any, Optional
from app.core.calculator import DEFAULT_DISTRICT_RATES

SZCZECIN_DISTRICTS = [
    "Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno",
    "Gumieńce", "Pomorzany", "Warszewo", "Prawobrzeże", "Dąbie",
    "Słoneczne", "Bukowe", "Majowe", "Drzetowo-Grabowo", "Inna"
]

def pre_filter_listing(
    area_m2: float,
    price_pln: float,
    district: str,
    title: Optional[str] = "",
    description: Optional[str] = "",
    building_type: Optional[str] = None,
    source: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Zwraca (passes_filter: bool, filter_reason: str).
    Jeżeli passes_filter == False, ogłoszenie zostaje odrzucone przed wywołaniem AI.
    """
    if not area_m2 or area_m2 <= 0 or not price_pln or price_pln <= 0:
        return False, "Nieprawidłowy metraż lub cena (<= 0)"

    text_content = f"{title or ''} {description or ''}".lower()

    # 0. Weryfikacja sygnatur nieaktualności, zakończenia lub rezerwacji
    expired_signatures = [
        "ogłoszenie nieaktualne", "ogloszenie nieaktualne", "oferta nieaktualna",
        "to ogłoszenie jest nieaktualne", "to ogloszenie jest nieaktualne",
        "ta oferta jest już nieaktualna", "ogłoszenie zakończone", "ogloszenie zakonczone",
        "ogłoszenie wygasło", "ogloszenie wygaslo", "oferta wycofana",
        "oferta archiwalna", "ogłoszenie archiwalne", "ogloszenie archiwalne",
        "ogłoszenie nie jest już dostępne", "ogloszenie nie jest juz dostepne",
        "ogłoszenie zostało usunięte", "ogloszenie zostalo usuniete",
        "sprzedane", "mieszkanie sprzedane", "lokal sprzedany",
        "rezerwacja", "zarezerwowane", "mieszkanie zarezerwowane", "oferta w rezerwacji"
    ]
    for sig in expired_signatures:
        if sig in text_content:
            return False, f"Wykryto sygnaturę ogłoszenia archiwalnego lub zakończonego: '{sig}'"

    # 0b. Odrzucenie reklam komercyjnych, skupu długów/spadków, usług i zapytań 'kupię'
    service_signatures = [
        "kupię spadek", "kupie spadek", "skup udziałów", "skup udzialow",
        "skup mieszkań", "skup mieszkan", "skup nieruchomości", "skup nieruchomosci",
        "problem ze spadkiem", "problem z udziałem", "problem z udzialem",
        "nie dogadujesz się ze współwłaścicielami", "nie dogadujesz sie",
        "czyszczenie zadłużeń", "czyszczenie zadluzen", "pożyczki pod zastaw",
        "pozyczki pod zastaw", "doradztwo prawne", "pomoc prawna", "kancelaria odszkodowawcza",
        "odkupię długi", "odkupie dlugi", "pomoc w oddłużaniu", "odkupię udział", "odkupie udzial",
        "kupię za gotówkę", "kupie za gotowke", "kupię każde", "kupie kazde"
    ]
    for sig in service_signatures:
        if sig in text_content:
            return False, f"Odrzucono: Wykryto ogłoszenie usługowe / reklamę skupu / pomoc prawną: '{sig}'"

    # 0c. Odrzucenie przetargów wykonawczych / budowlanych / instalacyjnych (np. spółdzielnie, BIP, SWZ)
    tender_signatures = [
        "swz", "siwz", "specyfikacja warunków", "specyfikacja istotnych warunków",
        "wymiana instalacji", "wymiany instalacji", "wymiana wlz", "instalacji elektrycznej",
        "instalacji sanitarnej", "pionów kanalizacyjnych", "remont instalacji", "remont dachu",
        "remont elewacji", "remont klatki", "remont muru", "docieplenie", "termomodernizac",
        "roboty budowlane", "konserwacja dźwigów", "przegląd kominiarski", "utrzymanie czystości",
        "przetarg na wykonanie", "wykonanie robót", "zamówienia publiczne", "zamówienie publiczne",
        "zapytanie ofertowe", "bip "
    ]
    for tsig in tender_signatures:
        if tsig in text_content:
            return False, f"Odrzucono: Przetarg wykonawczy / budowlany / zamówienie publiczne: '{tsig}'"

    # 0d. Odrzucenie nieruchomości niemieszkalnych (lokale użytkowe, garaże, grunty, hale)
    commercial_signatures = [
        "lokal użytkowy", "lokale użytkowe", "lokalu użytkowego", "lokali użytkowych",
        "lokale użytkowe i garaże", "lokal handlowy", "lokal usługowy", "obiekt magazynowy",
        "hala magazynowa", "obiekt komercyjny", "wieczystego gruntu", "grunty", "działka budowlana",
        "działka rolna", "działki rekreacyjne", "miejsce postojowe w hali", "boks garażowy"
    ]
    for csig in commercial_signatures:
        if csig in text_content and not any(k in text_content for k in ["adaptacja na mieszkanie", "przekształcenie na cele mieszkalne"]):
            return False, f"Odrzucono: Nieruchomość komercyjna / grunt / garaż: '{csig}'"

    title_lower = (title or "").lower()
    if title_lower.startswith("garaż") or title_lower.startswith("garaz") or "garaż na sprzedaż" in title_lower:
        return False, "Odrzucono: Samodzielny garaż (nie mieszkanie)"

    # 0e. Odrzucenie udziałów ułamkowych, ułamków i służebności osobistych (wady prawne / brak pełnej własności)
    share_signatures = [
        "udział w wysokości", "udział 1/", "udziału 1/", "1/2 części", "1/2 udziału",
        "1/3 części", "1/4 części", "1/6 części", "1/8 części", "licytacja udziału",
        "licytacja ułamka", "sprzedaż udziału", "ułamek nieruchomości", "współwłasność w częściach",
        "udział w lokalu", "udział w prawie", "udział w nieruchomości", "służebność osobista",
        "służebnością osobistą", "służebność mieszkania", "dożywocie", "umowa dożywocia"
    ]
    for ssig in share_signatures:
        if ssig in text_content:
            return False, f"Odrzucono: Wada prawna / udział ułamkowy / służebność: '{ssig}'"

    # 0f. Odrzucenie nieruchomości poza Szczecinem
    if "szczecinek" in text_content:
        return False, "Odrzucono: Miejscowość Szczecinek (poza zasięgiem Nesta Home Szczecin)"
    outside_towns = ["police", "stargard", "goleniów", "gryfino", "kołobrzeg", "koszalin", "świnoujście", "nowogard"]
    for town in outside_towns:
        if town in title_lower and "szczecin" not in title_lower:
            return False, f"Odrzucono: Miejscowość {town.capitalize()} (poza granicami Szczecina)"

    # 0g. Odrzucenie zasobu komunalnego ZBiLK ("Mieszkanie za remont" - brak prawa własności, umowa najmu dla osób fizycznych)
    if source == "zbilk" or "miejski zasób komunalny zbilk" in text_content or "program mieszkanie za remont" in text_content:
        return False, "Odrzucono: Lokal komunalny ZBiLK (program 'Mieszkanie za remont' - umowa najmu, brak możliwości flipa)"

    # Szybka wklejka użytkownika ma zawsze pełną analizę finansową (jeśli nie jest wygasła)
    if source == "manual":
        return True, "Weryfikacja manualna użytkownika (Szybka wklejka)"

    # Specjalne traktowanie źródeł pozarynkowych / licytacji
    is_auction = source in ["elicytacje"]

    # Odrzucenie ogłoszeń o wynajem lub skrajnych anomalii cenowych
    if not is_auction and price_pln < 130000.0:
        return False, f"Podejrzenie ogłoszenia o wynajem, udziału lub błędu ceny ({price_pln:,.0f} zł < 130 000 zł)"

    # Skrajnie niska cena za m2 na portalach otwartych (< 3500 zł/m2) to w 99% udział ułamkowy, błąd lub scam
    price_m2 = price_pln / area_m2
    if not is_auction and price_m2 < 3500.0:
        return False, f"Odrzucono: Podejrzenie sprzedaży udziału lub błędu danych ({price_m2:,.0f} zł/m2 < 3 500 zł/m2)"

    if not is_auction:
        rental_keywords = ["do wynajęcia", "wynajmę", "odstąpię najem", "kaucja", "najem okazjonalny", "czynsz najmu"]
        if any(k in text_content for k in rental_keywords):
            return False, "Ogłoszenie dotyczy wynajmu, a nie sprzedaży nieruchomości"
    dist_clean = district.strip() if district else "Centrum"
    rates = DEFAULT_DISTRICT_RATES.get(dist_clean, DEFAULT_DISTRICT_RATES["Centrum"])
    mkt_avg = rates["avg_renovation_m2"]
    ready_min = rates["ready_min_m2"]

    # 1. Sprawdzenie czy to nie jest już wyremontowany flip w cenie rynkowej (gotowiec)
    text_content = f"{title or ''} {description or ''}".lower()
    flip_keywords = ["po generalnym remoncie", "świeżo po remoncie", "standard pod klucz", "gotowe do wprowadzenia", "wysoki standard", "luksusowe wykończenie"]
    if price_m2 >= ready_min * 0.92 and any(k in text_content for k in flip_keywords):
        return False, f"Mieszkanie po flipie / w cenie rynkowej ({price_m2:,.0f} zł/m2 vs ARV min {ready_min:,.0f} zł/m2)"

    # 2. Skrajne metraże
    if area_m2 < 25.0:
        return False, f"Zbyt mały metraż ({area_m2} m2 < 25 m2)"

    # 3. Metraże powyżej 70 m2
    if area_m2 > 70.0:
        # Tylko wyjątkowe okazje w topowych punktach (Pogodno, Centrum, Śródmieście) z rabatem > 25%
        if dist_clean in ["Pogodno", "Centrum", "Śródmieście"] and price_m2 <= mkt_avg * 0.75:
            return True, f"Duży metraż ({area_m2} m2), ale dopuszczony ze względu na wybitną cenę ({price_m2:,.0f} zł/m2 w {dist_clean})"
        return False, f"Zbyt duży metraż dla profilu Nesta Home ({area_m2} m2 > 70 m2)"

    # 4. Segment 55.1 - 70 m2 (wymagany min. 18-20% dyskont do średniej dzielnicy)
    if area_m2 > 55.0 and area_m2 <= 70.0:
        if price_m2 > mkt_avg * 0.82:
            return False, f"Metraż 55-70 m2 bez wystarczającego dyskontu ({price_m2:,.0f} zł/m2 vs próg {mkt_avg*0.82:,.0f} zł/m2)"

    # 5. Segment Sweet Spot (38 - 55 m2) i Szybki Obrót (25 - 35 m2)
    # Sprawdzamy czy cena za m2 nie przekracza sufitu do remontu
    if price_m2 > mkt_avg * 1.05 and price_m2 > 8500:
        return False, f"Cena za m2 zbyt wysoka jak na stan przed remontem ({price_m2:,.0f} zł/m2)"

    return True, "Spełnia kryteria wstępne Nesta Home"
