"""
Ścisłe kontrakty danych Pydantic v2.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (Sekcja 1.1 i 4.3).
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ScrapedListing(BaseModel):
    """Ujednolicony schemat oferty z dowolnego parsera/konektora (Sekcja 4.3)"""
    source_portal: str = Field(..., description="Nazwa portalu: olx, infoludek, gratka, sprzedajemy itp.")
    external_id: Optional[str] = Field(None, description="Identyfikator ogłoszenia w portalu")
    url: Optional[str] = Field(None, description="Bezpośredni link do oferty")
    title: str = Field(..., description="Tytuł ogłoszenia")
    city: str = Field(default="Szczecin", description="Miasto nieruchomości")
    district: Optional[str] = Field(default="Centrum", description="Dzielnica Szczecina")
    street: Optional[str] = Field(None, description="Ulica lub rejon")
    price_pln: float = Field(..., gt=0, description="Cena ofertowa w PLN")
    area_m2: float = Field(..., gt=0, description="Metraż w m2")
    price_per_m2: Optional[float] = Field(None, description="Cena za m2")
    rooms: Optional[int] = Field(None, ge=1, le=10, description="Liczba pokoi")
    floor: Optional[int] = Field(None, ge=0, le=25, description="Piętro (0 = parter)")
    total_floors: Optional[int] = Field(None, ge=1, le=25, description="Liczba pięter w budynku")
    building_type: Optional[str] = Field(default="Kamienica", description="Kamienica, Wielka płyta, Niski blok, Nowe budownictwo")
    heating_source: Optional[str] = Field(None, description="Źródło ogrzewania")
    has_balcony: Optional[bool] = Field(False, description="Czy posiada balkon/taras/loggię")
    has_elevator: Optional[bool] = Field(False, description="Czy budynek posiada windę")
    is_private_seller: bool = Field(default=True, description="True jeśli bez prowizji/pośrednika")
    description_raw: str = Field(default="", description="Surowy opis oferty")

class QuickIngestRequest(BaseModel):
    """Model wejściowy szybkiej wklejki z Facebooka / telefonu / portali"""
    district: str = Field(..., description="Dzielnica Szczecina")
    street: Optional[str] = None
    area_m2: float = Field(..., gt=0)
    price_pln: float = Field(..., gt=0)
    title: Optional[str] = "Wprowadzona ręcznie"
    building_type: str = "Kamienica"
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    has_elevator: bool = False
    has_balcony: bool = False
    heating_source: str = "piece kaflowe"
    admin_rent: float = 380.0
    description: Optional[str] = ""
    url: Optional[str] = None

class RawIngestWebhookRequest(BaseModel):
    """Model wejściowy webhooka dla automatyzacji i zewnętrznych botów"""
    source: str = Field(default="webhook")
    external_id: Optional[str] = None
    url: Optional[str] = None
    title: str
    description: Optional[str] = ""
    district: str = "Centrum"
    street: Optional[str] = None
    area_m2: float = Field(..., gt=0)
    price_pln: float = Field(..., gt=0)
    rooms: Optional[int] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    building_type: str = "Kamienica"
    heating_source: Optional[str] = None
    has_balcony: bool = False
    has_elevator: bool = False
    admin_rent: float = 0.0
    has_agency_fee: bool = False

class DistrictRateUpdateRequest(BaseModel):
    """Aktualizacja stawek benchmarkowych dzielnicy"""
    district_id: int
    avg_renovation_m2: float
    ready_min_m2: float
    ready_avg_m2: float
    ready_max_m2: float

class GoldenRuleCreateRequest(BaseModel):
    """Tworzenie nowej złotej zasady Nesta Home"""
    rule_text: str = Field(..., min_length=5)
    category: str = "general"
    weight: float = 1.0

class FeedbackSubmitRequest(BaseModel):
    """Wprowadzenie decyzji użytkownika do pętli uczenia AI"""
    decision: str = Field(..., pattern="^(QUALIFIED|REJECTED)$")
    reason_category: Optional[str] = None
    comment: Optional[str] = None

class AppVersionResponse(BaseModel):
    """Pojedyncze Źródło Prawdy Wersji (SSOT, Sekcja 3.3)"""
    app_name: str
    version: str
    environment: str
    tracker_env: str
    api_standard: str = "v4.15"
