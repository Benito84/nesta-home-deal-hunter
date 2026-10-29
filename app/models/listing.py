from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class PropertyCluster(SQLModel, table=True):
    """Klaster zrzeszający zduplikowane ogłoszenia tej samej fizycznej nieruchomości"""
    __tablename__ = "property_clusters"

    id: Optional[int] = Field(default=None, primary_key=True)
    district: str
    approximate_area_m2: float
    floor: Optional[int] = None
    street: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    listings: List["Listing"] = Relationship(back_populates="cluster")


class PriceDropEvent(SQLModel, table=True):
    """Zdarzenie obniżki ceny ogłoszenia w czasie"""
    __tablename__ = "price_drop_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listings.id")
    old_price_pln: float
    new_price_pln: float
    drop_pct: float
    detected_at: datetime = Field(default_factory=utc_now)

    listing: Optional["Listing"] = Relationship(back_populates="price_drops")


class Listing(SQLModel, table=True):
    """Główny model ogłoszenia nieruchomości w Szczecinie"""
    __tablename__ = "listings"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # olx, otodom, infoludek, komornik, bip_spoldzielnia, imap, manual
    external_id: Optional[str] = Field(default=None, index=True)
    url: Optional[str] = None
    title: str
    description: Optional[str] = None
    
    # Parametry fizyczne lokalu
    district: str = Field(default="Centrum", index=True)
    street: Optional[str] = None
    area_m2: float = Field(index=True)
    price_pln: float = Field(index=True)
    price_per_m2: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    building_type: Optional[str] = None  # Kamienica, Wielka płyta, Niski blok, Nowe budownictwo
    building_year: Optional[int] = None
    has_elevator: Optional[bool] = False
    has_balcony: Optional[bool] = False
    balcony_type: Optional[str] = "Balkon"
    heating_source: Optional[str] = None  # piece kaflowe, miejskie (SEC), gazowe (kocioł 2-f), elektryczne
    ownership_type: Optional[str] = "PELNA_WLASNOSC"
    admin_rent: Optional[float] = 0.0

    # Parametry transakcyjne
    has_agency_fee: Optional[bool] = True
    agency_fee_pct: Optional[float] = 0.03
    seller_name: Optional[str] = None
    seller_phone: Optional[str] = None
    is_auction: Optional[bool] = False

    # Klasteryzacja & Deduplikacja
    cluster_id: Optional[int] = Field(default=None, foreign_key="property_clusters.id")
    cluster: Optional[PropertyCluster] = Relationship(back_populates="listings")
    price_drops: List[PriceDropEvent] = Relationship(back_populates="listing")

    # Wyliczenia Matematyczne Modelu Finansowego Nesta Home
    deal_score: Optional[int] = Field(default=0, index=True)  # 0-100
    gate_1_decision: Optional[str] = Field(default="STOP", index=True)  # DZWONIMY, STOP, LICYTUJ
    walk_away_price: Optional[float] = None
    anchor_price: Optional[float] = None
    estimated_renovation: Optional[float] = None
    total_investment: Optional[float] = None
    arv_target: Optional[float] = None
    company_net_profit_pln: Optional[float] = None
    roi_target: Optional[float] = None
    effective_ready_m2: Optional[float] = None
    calculation_details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Analiza AI (Gemini Structured Output)
    ai_recommendation: Optional[str] = Field(default="REJECT", index=True)  # HOT_DEAL, WORTH_CHECKING, MONITOR_PRICE_DROP, REJECT
    ai_renovation_scope: Optional[str] = None  # COSMETIC, MEDIUM, FULL_GENERAL
    room_layout_potential: Optional[str] = None
    pros: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    red_flags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    negotiation_arguments: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    ai_analyzed_at: Optional[datetime] = None

    # Status przetwarzania i integracji
    status: str = Field(default="NEW", index=True)  # NEW, QUALIFIED, REJECTED, ARCHIVED
    tracker_synced: bool = Field(default=False, index=True)
    tracker_staging_id: Optional[int] = None
    tracker_synced_at: Optional[datetime] = None
    
    # Fingerprint i ochrona przed re-analizą LLM
    content_hash: Optional[str] = Field(default=None, index=True)

    # Metadane
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)
    is_active: bool = Field(default=True)
