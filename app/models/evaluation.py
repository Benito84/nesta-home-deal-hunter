from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class RecommendationEnum(str, Enum):
    HOT_DEAL = "HOT_DEAL"
    WORTH_CHECKING = "WORTH_CHECKING"
    MONITOR_PRICE_DROP = "MONITOR_PRICE_DROP"
    REJECT = "REJECT"

class RenovationScopeEnum(str, Enum):
    COSMETIC = "COSMETIC"
    MEDIUM = "MEDIUM"
    FULL_GENERAL = "FULL_GENERAL"

class AIEvaluationResult(BaseModel):
    """Ustrukturyzowany format wyjściowy oceny AI z Google Gemini dla Nesta Home"""
    deal_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Ocena atrakcyjności inwestycyjnej lokalu od 0 do 100 punktów wg kryteriów Nesta Home."
    )
    recommendation: RecommendationEnum = Field(
        ...,
        description="Rekomendacja decyzyjna (HOT_DEAL, WORTH_CHECKING, MONITOR_PRICE_DROP, REJECT)."
    )
    estimated_renovation_scope: RenovationScopeEnum = Field(
        ...,
        description="Szacowany zakres prac remontowych: COSMETIC, MEDIUM lub FULL_GENERAL."
    )
    estimated_renovation_cost_pln: int = Field(
        ...,
        description="Szacunkowy budżet remontu w PLN (dla kamienicy min. 1900 zł/m2, blok 1700 zł/m2, nowe 1500 zł/m2)."
    )
    estimated_arv_pln: int = Field(
        ...,
        description="Szacowana cena sprzedaży lokalu po wykończeniu w standardzie Nesta Home w danej dzielnicy Szczecina."
    )
    estimated_gross_margin_pln: int = Field(
        ...,
        description="Szacowany zysk brutto przed kosztami holdingowymi i prowizją koordynatora."
    )
    room_layout_potential: str = Field(
        ...,
        description="Potencjał układu funkcjonalnego (np. możliwość wydzielenia 3. pokoju, przeniesienie aneksu kuchennego)."
    )
    pros: List[str] = Field(
        default_factory=list,
        description="Mocne atuty oferty (np. niska cena m2, balkon, gaz/SEC w klatce, piece kaflowe jako dźwignia negocjacyjna)."
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="Ryzyka i wady do natychmiastowej weryfikacji telefonicznej (np. ciemna oficyna, stan stropów, zaległości w czynszu)."
    )
    negotiation_arguments: List[str] = Field(
        default_factory=list,
        description="Konkretne argumenty dla koordynatora do zbicia ceny zakupu podczas rozmowy ze sprzedającym."
    )
