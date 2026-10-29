"""
Model Bazy Danych dla Źródeł i Scraperów.
Obsługuje diagnostykę stanu technicznego (Healthcheck) oraz Kolejkę Źródeł (Backlog).
Zgodnie ze Standardem Nesta Home Master Tracker v4.16.
"""

from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class ScraperSource(SQLModel, table=True):
    """Rejestr źródeł danych, stan techniczny scraperów i backlog wdrożeniowy"""
    __tablename__ = "scraper_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, description="Unikalny identyfikator techniczny np. gratka, infoludek")
    name: str = Field(description="Czytelna nazwa portalu lub źródła")
    url: str = Field(description="Adres URL lub ścieżka do źródła")
    tier: str = Field(default="Tier 2: Portale i IMAP", description="Kategoria / Poziom źródła")
    is_active: bool = Field(default=True, index=True, description="True dla wbudowanych scraperów, False dla kolejki")
    
    # Diagnostyka i Healthcheck
    status: str = Field(default="PENDING", index=True, description="HEALTHY, WARNING, ERROR, PENDING, QUEUED")
    last_latency_ms: Optional[int] = Field(default=None, description="Czas odpowiedzi serwera w milisekundach")
    last_items_found: Optional[int] = Field(default=None, description="Liczba ofert sparsowanych w ostatniej próbie")
    last_tested_at: Optional[datetime] = Field(default=None, description="Data i czas ostatniego testu")
    last_message: Optional[str] = Field(default=None, description="Komunikat diagnostyczny lub treść błędu")
    
    # Notatki operacyjne
    notes: Optional[str] = Field(default=None, description="Wytyczne biznesowe lub uwagi dla programisty AI")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
