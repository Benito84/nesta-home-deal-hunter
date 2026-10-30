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
    category: str = "general"  # heating, area, floor, location, legal, general
    weight: float = 1.0
    source: Optional[str] = "manual"  # manual, feedback_promotion, ai_synthesis
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class UserFeedbackHistory(SQLModel, table=True):
    """Historia decyzji użytkownika w UI (Active Learning / Feedback Loop)"""
    __tablename__ = "user_feedback_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(index=True)
    decision: str  # INTERESTED ("Jedziemy na oględziny"), REJECTED ("Odrzuć")
    reason_category: Optional[str] = None  # REKLAMA_USLUGA, WADA_PRAWNA, WADA_TECHNICZNA, CENA_ZAWYZONA, LOKALIZACJA_ZLA, UKLAD_ZLY, INNE
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class SystemPromptSetting(SQLModel, table=True):
    """Globalne wytyczne inwestycyjne i rozszerzony prompt dla AI"""
    __tablename__ = "system_prompt_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(default="global_directives", unique=True, index=True)
    custom_directives: str = Field(
        default="""- Odrzucaj wszelkie ogłoszenia, które są reklamami skupu nieruchomości, pomocy prawnej, pożyczek lub zapytaniami 'kupię'.
- Zwracaj szczególną uwagę na oficyny i kondygnacje parterowe w kamienicach (ryzyko zawilgocenia, ciemnych podwórek i braku nasłonecznienia).
- W przypadku ogrzewania piecami kaflowymi, traktuj to jako dźwignię do twardych negocjacji cenowych, o ile w budynku jest pion gazowy lub sieć SEC.
- Nie akceptujemy ofert, w których przedmiotem transakcji jest tylko ułamek/udział (np. 1/2 lub 1/4 lokalu bez czystej KW).
- Mieszkania na 4. piętrze w kamienicy lub bloku bez windy wymagają dyskonta cenowego min. 8% z uwagi na dłuższą odsprzedaż."""
    )
    updated_at: datetime = Field(default_factory=utc_now)
