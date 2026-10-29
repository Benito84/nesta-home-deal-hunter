"""
Klient integracyjny z Nesta Home Master Tracker.
Wysyła zweryfikowane okazje bezpośrednio do Poczekalni Ofert (POST /api/staging).
Obsługuje środowisko PROD (:20120) oraz DEV (:30120) zgodnie ze specyfikacją API v4.04.
"""

from typing import Dict, Any, Tuple
import httpx
from app.core.config import settings
from app.models.listing import Listing

def push_to_nesta_tracker(listing: Listing, force: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Wysyła ofertę do Poczekalni Ofert Nesta Master Tracker.
    Zwraca (sukces: bool, komunikat: str, odpowiedź_json: dict)
    """
    target_url = settings.tracker_active_url

    # Mapowanie danych z modelu Listing na specyfikację API /api/staging
    payload = {
        "title": listing.title or f"{listing.district}, {listing.area_m2} m2",
        "district": listing.district,
        "street": listing.street,
        "area_m2": float(listing.area_m2),
        "price_pln": float(listing.price_pln),
        "rooms": listing.rooms,
        "floor": listing.floor,
        "total_floors": listing.total_floors,
        "building_type": listing.building_type,
        "building_year": listing.building_year,
        "has_elevator": bool(listing.has_elevator),
        "has_balcony": bool(listing.has_balcony),
        "balcony_type": listing.balcony_type or "Balkon",
        "heating_source": listing.heating_source,
        "ownership_type": listing.ownership_type or "PELNA_WLASNOSC",
        "admin_rent": float(listing.admin_rent or 0.0),
        "has_agency_fee": bool(listing.has_agency_fee),
        "agency_fee_pct": float(listing.agency_fee_pct or 0.03),
        "seller_name": listing.seller_name,
        "seller_phone": listing.seller_phone,
        "description": listing.description,
        "force": force
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(target_url, json=payload)
            data = response.json()

            if response.status_code == 200:
                status = data.get("status")
                if status == "success":
                    staging_id = data.get("staging_id")
                    return True, f"Oferta pomyślnie dodana do Poczekalni Trackera (ID #{staging_id})", data
                elif status == "duplicate":
                    existing_id = data.get("existing_id")
                    return False, f"Wykryto duplikat w Trackerze (Istniejące ID #{existing_id}). Użyj 'Wymuś wysyłkę' aby nadpisać.", data
                else:
                    return False, f"Odpowiedź Trackera: {data.get('message', 'Nieznany status')}", data
            else:
                return False, f"Błąd HTTP {response.status_code}: {response.text}", {}

    except httpx.RequestError as e:
        return False, f"Błąd połączenia z serwerem Trackera ({target_url}): {str(e)}", {}
    except Exception as e:
        return False, f"Wystąpił nieoczekiwany błąd: {str(e)}", {}
