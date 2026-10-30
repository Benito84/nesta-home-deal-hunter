"""
AI Deal Evaluator dla Nesta Home Szczecin.
Używa Google Gemini API ze schematem Pydantic (Structured Outputs).
Dynamicznie wstrzykuje do promptu Złote Zasady oraz historię decyzji (Feedback Loop / Few-Shot).
Posiada inteligentny fallback matematyczny, gdy klucz API nie jest skonfigurowany.
"""

import json
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select
from app.core.config import settings
from app.models.evaluation import AIEvaluationResult, RecommendationEnum, RenovationScopeEnum
from app.models.benchmarks import GoldenRule, UserFeedbackHistory, SystemPromptSetting
from app.core.calculator import calculate_offer, DEFAULT_DISTRICT_RATES

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def build_system_prompt(session: Session) -> str:
    """Buduje kontekst systemowy z dynamicznym wstrzyknięciem Złotych Zasad, wytycznych zarządu oraz historii decyzji (Active Learning)"""
    golden_rules = session.exec(select(GoldenRule).where(GoldenRule.is_active == True)).all()
    feedback_history = session.exec(
        select(UserFeedbackHistory).order_by(UserFeedbackHistory.created_at.desc()).limit(10)
    ).all()

    setting = session.exec(select(SystemPromptSetting).where(SystemPromptSetting.key == "global_directives")).first()
    custom_directives = setting.custom_directives.strip() if setting and setting.custom_directives else ""

    rules_text = "\n".join([f"- [{r.category.upper()}] {r.rule_text} (waga: {r.weight}x)" for r in golden_rules])
    
    feedback_lines = []
    for f in feedback_history:
        status_label = "ODRZUCONO" if f.decision == "REJECTED" else "ZAAKCEPTOWANO NA OGLĘDZINY"
        cat = f" [Kategoria: {f.reason_category}]" if f.reason_category else ""
        note = f" -> Uwaga inwestora: \"{f.comment}\"" if f.comment else ""
        feedback_lines.append(f"- Oferta #{f.listing_id}: {status_label}{cat}{note}")
    feedback_text = "\n".join(feedback_lines)

    return f"""Jesteś Głównym Analitykiem Inwestycyjnym w spółce Nesta Home (nestahome.pl) w Szczecinie.
Firma zajmuje się profesjonalnym flippingiem mieszkań na rynku wtórnym, rewitalizacją lokali oraz kamienic w Szczecinie.

PROFIL INWESTYCYJNY NESTA HOME:
1. Sweet Spot: 38-55 m2 (2 do 3 pokoi) - najwyższa płynność po wykończeniu pod klucz w podwyższonym standardzie.
2. Segment uzupełniający: 25-35 m2 (szybki obrót kapitałem).
3. OGRZEWANIE - KLUCZOWA ZASADA: Piece kaflowe w kamienicach to nasz NAJWIĘKSZY ATUT! Zwykli klienci ich unikają, co pozwala drastycznie zbić cenę zakupu (np. do 4500-6000 zł/m2 w Śródmieściu). Nasz Kierownik Budowy Janek ma opanowaną instalację gazową z kotłem 2-f kondensacyjnym lub wpięcie do miejskiej sieci SEC. NIE ODRZUCAJ ofert z piecami kaflowymi - traktuj je jako pole do negocjacji!
4. Finanse: Minimalny ROI to 16%, a minimalny czysty zysk to 30 000 - 40 000 zł.
5. Standard remontu Nesta: Kamienica 1900 zł/m2, blok 1700 zł/m2, nowe 1500 zł/m2.
6. Nie robimy mikrokawalerek dla studentów - robimy piękne, funkcjonalne mieszkania dla rodzin/singli/inwestorów.

DODATKOWE WYTYCZNE INWESTYCYJNE ZARZĄDU (SYSTEM DIRECTIVES):
{custom_directives if custom_directives else "- Brak dodatkowych dyrektyw"}

AKTYWNE ZŁOTE ZASADY ZESPOŁU NESTA HOME:
{rules_text if rules_text else "- Standardowe wytyczne inwestycyjne Szczecin"}

PAMIĘĆ AKTYWNEGO UCZENIA (OSTATNIE DECYZJE I POWODY ODRZUCEŃ ZESPOŁU):
{feedback_text if feedback_text else "- Brak wcześniejszych odrzuceń."}

DYREKTYWA SAMOUCZENIA:
Powyższe decyzje zespołu to Twoje wzorce referencyjne. Jeśli oceniane ogłoszenie wykazuje te same wady lub cechy, które zespół odrzucił w przeszłości (np. reklama usługi, ułamek udziału, brak KW, wada techniczna, ciemna oficyna), musisz bezwzględnie obniżyć Deal Score lub zarekomendować REJECT i wpisać wykryte ryzyko w pole 'red_flags'.

Twoim zadaniem jest ocenić nadesłaną ofertę i zwrócić zwięzłą, rzetelną ocenę w formacie JSON zgodnym ze schematem."""


def evaluate_listing_ai(
    listing_dict: Dict[str, Any],
    calc_results: Dict[str, Any],
    session: Session
) -> AIEvaluationResult:
    """
    Dokonuje ewaluacji oferty za pomocą Gemini Structured Output lub fallbacku algorytmicznego.
    """
    if settings.GEMINI_API_KEY and GENAI_AVAILABLE:
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            system_prompt = build_system_prompt(session)

            user_content = f"""Przeanalizuj poniższe ogłoszenie mieszkania w Szczecinie:
Tytuł: {listing_dict.get('title')}
Dzielnica: {listing_dict.get('district')}
Ulica: {listing_dict.get('street') or 'Nie podano'}
Metraż: {listing_dict.get('area_m2')} m2
Cena ofertowa: {listing_dict.get('price_pln')} PLN ({calc_results.get('price_per_m2', 0):,.2f} PLN/m2)
Piętro: {listing_dict.get('floor')}/{listing_dict.get('total_floors') or '?'} (Winda: {listing_dict.get('has_elevator')})
Balkon: {listing_dict.get('has_balcony')} ({listing_dict.get('balcony_type')})
Budynek: {listing_dict.get('building_type') or 'Nie podano'}
Ogrzewanie: {listing_dict.get('heating_source') or 'Nie podano'}
Opis: {listing_dict.get('description', '')[:1500]}

WYNIKI KALKULATORA FINANSOWEGO NESTA HOME:
- Szacowany remont: {calc_results.get('estimated_renovation', 0):,.2f} PLN
- ARV (Sprzedaż po remoncie): {calc_results.get('arv_target', 0):,.2f} PLN ({calc_results.get('effective_ready_m2', 0):,.2f} PLN/m2)
- Czysty zysk spółki: {calc_results.get('company_net_profit_pln', 0):,.2f} PLN
- Zwrot ROI: {calc_results.get('roi_target', 0)*100:.2f}%
- Walk-Away Price (maks. cena za 16% ROI): {calc_results.get('walk_away_price', 0):,.2f} PLN
- Bramka 1 Kalkulatora: {calc_results.get('gate_1_decision')}
"""

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=AIEvaluationResult,
                    temperature=0.2
                )
            )

            if response.text:
                data = json.loads(response.text)
                return AIEvaluationResult(**data)

        except Exception as e:
            print(f"[AI Evaluator Error] Błąd Gemini API: {e}. Uruchamiam inteligentny fallback algorytmiczny.")

    # FALLBACK INTELIGENTNY (Gdy brak klucza API lub błąd sieci)
    return generate_rule_based_evaluation(listing_dict, calc_results)


def generate_rule_based_evaluation(
    listing_dict: Dict[str, Any],
    calc_results: Dict[str, Any]
) -> AIEvaluationResult:
    """Automatyczny generator oceny oparty na precyzyjnej matematyce Nesta Tracker"""
    roi = calc_results.get("roi_target", 0.0)
    profit = calc_results.get("company_net_profit_pln", 0.0)
    gate = calc_results.get("gate_1_decision", "STOP")
    area = float(listing_dict.get("area_m2") or 45.0)
    b_type = (listing_dict.get("building_type") or "").lower()
    heating = (listing_dict.get("heating_source") or "").lower()
    floor = listing_dict.get("floor")

    pros = []
    red_flags = []
    neg_args = []

    # Ocena punktowa
    score = 50
    if roi >= 0.20 and profit >= 40000:
        score = 92
        rec = RecommendationEnum.HOT_DEAL
    elif roi >= 0.16 and profit >= 30000:
        score = 82
        rec = RecommendationEnum.HOT_DEAL
    elif roi >= 0.12 and profit >= 20000:
        score = 65
        rec = RecommendationEnum.WORTH_CHECKING
    elif calc_results.get("walk_away_price", 0) > 0:
        score = 45
        rec = RecommendationEnum.MONITOR_PRICE_DROP
    else:
        score = 25
        rec = RecommendationEnum.REJECT

    # Atuty i negocjacje
    if "kamienic" in b_type:
        scope = RenovationScopeEnum.FULL_GENERAL
        if "kaf" in heating:
            pros.append("Piece kaflowe w kamienicy – niska konkurencja kupujących, duży potencjał negocjacyjny.")
            neg_args.append("Wymóg kompletnej instalacji gazowej/SEC wraz z demontażem pieców to wydatek rzędu 25-35 tys. zł.")
        if area >= 45:
            layout = "Duża przestrzeń kamieniczna – wysoki potencjał wydzielenia 3. pokoju lub garderoby."
        else:
            layout = "Klasyczny układ 2-pokojowy z możliwością otwarcia kuchni na salon."
    elif "plyta" in b_type or "płyta" in b_type:
        scope = RenovationScopeEnum.MEDIUM
        layout = "Standardowy układ wielkiej płyty – wysoka płynność na rynku szczecińskim po estetycznym remoncie."
    else:
        scope = RenovationScopeEnum.MEDIUM
        layout = "Rozkładowe pokoje, łatwa adaptacja pod klienta docelowego."

    if floor == 0:
        red_flags.append("Parter – weryfikacja czy okna nie wychodzą na ciemną oficynę lub śmietnik.")
        neg_args.append("Partery sprzedają się dłużej i z 5% dyskontem.")
    elif floor is not None and floor >= 4 and not listing_dict.get("has_elevator"):
        red_flags.append("Ostatnie piętro bez windy – dłuższy czas sprzedaży lokalu.")
        neg_args.append("Brak windy na 4. piętrze drastycznie zawęża grono kupujących.")

    if listing_dict.get("has_balcony"):
        pros.append("Posiada balkon/taras (+3% do ceny sprzedaży).")
    else:
        red_flags.append("Brak balkonu.")

    walk_away = calc_results.get("walk_away_price", 0.0)
    price = float(listing_dict.get("price_pln") or 0.0)
    if walk_away < price:
        diff_zl = price - walk_away
        neg_args.append(f"Cena ofertowa przekracza budżet inwestycyjny o {diff_zl:,.0f} zł – celować w ofertę kotwiczącą: {calc_results.get('anchor_price', 0):,.0f} zł.")

    return AIEvaluationResult(
        deal_score=score,
        recommendation=rec,
        estimated_renovation_scope=scope,
        estimated_renovation_cost_pln=int(calc_results.get("estimated_renovation", 0)),
        estimated_arv_pln=int(calc_results.get("arv_target", 0)),
        estimated_gross_margin_pln=int(profit),
        room_layout_potential=layout,
        pros=pros or ["Dobra lokalizacja w Szczecinie", "Odpowiedni metraż pod szybki obrót"],
        red_flags=red_flags or ["Konieczność weryfikacji instalacji elektrycznej i stanu pionów"],
        negotiation_arguments=neg_args or ["Konieczność generalnego remontu pod klucz"]
    )
