"""
Moduł Fingerprintingu i Ochrony Przed Marnowaniem Tokenów AI.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (v4.15, Sekcja 4.2).
"""

import hashlib
from typing import Optional

def compute_listing_fingerprint(
    city: str = "Szczecin",
    district: Optional[str] = None,
    street: Optional[str] = None,
    price_pln: float = 0.0,
    area_m2: float = 0.0
) -> str:
    """
    Wylicza unikalny hash ogłoszenia.
    Umożliwia wykrycie, czy ogłoszenie o tych parametrach było już poddane analizie AI.
    """
    c = (city or "szczecin").strip().lower()
    d = (district or "centrum").strip().lower()
    s = (street or "").strip().lower()
    p = f"{round(float(price_pln), 2)}"
    a = f"{round(float(area_m2), 2)}"
    
    raw_key = f"{c}_{d}_{s}_{p}_{a}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
