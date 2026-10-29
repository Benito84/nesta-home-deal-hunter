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

    # Szybka wklejka użytkownika ma zawsze pełną analizę finansową
    if source == "manual":
        return True, "Weryfikacja manualna użytkownika (Szybka wklejka)"

    # Specjalne traktowanie źródeł pozarynkowych / instytucjonalnych (ZBiLK, licytacje komornicze, spółdzielnie)
    is_institutional = source in ["zbilk", "elicytacje", "spoldzielnie", "kurier"]

    # Odrzucenie ogłoszeń o wynajem lub błędów cenowych (mieszkanie na sprzedaż w Szczecinie >= 90k)
    if not is_institutional and price_pln < 90000.0:
        return False, f"Podejrzenie ogłoszenia o wynajem lub błędu ceny ({price_pln:,.0f} zł < 90 000 zł)"

    text_content = f"{title or ''} {description or ''}".lower()
    if not is_institutional:
        rental_keywords = ["do wynajęcia", "wynajmę", "odstąpię najem", "kaucja", "najem okazjonalny", "czynsz najmu"]
        if any(k in text_content for k in rental_keywords):
            return False, "Ogłoszenie dotyczy wynajmu, a nie sprzedaży nieruchomości"

    price_m2 = price_pln / area_m2
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
