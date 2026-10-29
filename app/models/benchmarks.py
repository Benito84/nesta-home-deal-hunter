from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class DistrictBenchmark(SQLModel, table=True):
    """Ceny rynkowe Szczecina wg dzielnic (przed i po remoncie ARV)"""
    __tablename__ = "district_benchmarks"

    id: Optional[int] = Field(default=None, primary_key=True)
    district: str = Field(unique=True, index=True)
    avg_renovation_m2: float = 9500.0   # Średnia cena za m2 w stanie do remontu
    ready_min_m2: float = 12000.0        # ARV konserwatywne (fast_flip)
    ready_avg_m2: float = 13000.0        # ARV zrównoważone (balanced)
    ready_max_m2: float = 14000.0        # ARV optymistyczne (premium)
    active: bool = True
    updated_at: datetime = Field(default_factory=utc_now)


class GoldenRule(SQLModel, table=True):
    """Złote Zasady Inwestycyjne Nesta Home wstrzykiwane do promptu AI (Few-Shot memory)"""
    __tablename__ = "golden_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    rule_text: str
    category: str = "general"  # heating, area, floor, location, legal
    weight: float = 1.0
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class UserFeedbackHistory(SQLModel, table=True):
    """Historia decyzji użytkownika w UI (Active Learning / Feedback Loop)"""
    __tablename__ = "user_feedback_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(index=True)
    decision: str  # INTERESTED ("Jedziemy na oględziny"), REJECTED ("Odrzuć")
    reason_category: Optional[str] = None  # czynsz, ulica, strop, uklad, marza
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
