"""
Nesta Home Deal Hunter - Calculator Engine
Wierne przeniesienie silnika kalkulacji z Nesta Home Master Tracker.
Obsługuje specyfikę Szczecina, 9 dzielnic, koszty remontu, holdingu,
progresywną taksę notarialną, prowizję koordynatora i bramkę 1 (DZWONIMY/STOP).
"""

from typing import Dict, Any, Optional, Tuple, List

# --- DOMYŚLNE STAWKI RYNKOWE DLA DZIELNIC SZCZECINA ---
DEFAULT_DISTRICT_RATES: Dict[str, Dict[str, float]] = {
    "Śródmieście": {"avg_renovation_m2": 9500.0, "ready_min_m2": 12500.0, "ready_avg_m2": 13500.0, "ready_max_m2": 14500.0},
    "Centrum": {"avg_renovation_m2": 9500.0, "ready_min_m2": 12000.0, "ready_avg_m2": 13000.0, "ready_max_m2": 14000.0},
    "Turzyn": {"avg_renovation_m2": 7800.0, "ready_min_m2": 10500.0, "ready_avg_m2": 11500.0, "ready_max_m2": 12500.0},
    "Niebuszewo": {"avg_renovation_m2": 8500.0, "ready_min_m2": 11000.0, "ready_avg_m2": 12000.0, "ready_max_m2": 13000.0},
    "Pogodno": {"avg_renovation_m2": 10000.0, "ready_min_m2": 13000.0, "ready_avg_m2": 14000.0, "ready_max_m2": 15000.0},
    "Gumieńce": {"avg_renovation_m2": 9000.0, "ready_min_m2": 11800.0, "ready_avg_m2": 12800.0, "ready_max_m2": 13800.0},
    "Pomorzany": {"avg_renovation_m2": 8200.0, "ready_min_m2": 10800.0, "ready_avg_m2": 11800.0, "ready_max_m2": 12800.0},
    "Warszewo": {"avg_renovation_m2": 9200.0, "ready_min_m2": 12000.0, "ready_avg_m2": 13000.0, "ready_max_m2": 14000.0},
    "Prawobrzeże": {"avg_renovation_m2": 7800.0, "ready_min_m2": 10200.0, "ready_avg_m2": 11200.0, "ready_max_m2": 12200.0},
    "Inna": {"avg_renovation_m2": 9500.0, "ready_min_m2": 12000.0, "ready_avg_m2": 13000.0, "ready_max_m2": 14000.0}
}

DEFAULT_NOTARY_FEE_PLN: float = 1850.0
DEFAULT_HOLDING_UTILITIES_MONTHLY_PLN: float = 120.0
DEFAULT_HOLDING_INSURANCE_MONTHLY_PLN: float = 60.0
DEFAULT_MARKETING_SALES_PLN: float = 3000.0
DEFAULT_DESIGN_PROJECT_PLN: float = 1200.0
MIN_REP_COMMISSION_PLN: float = 10000.0
DEFAULT_MIN_ROI: float = 0.16
DEFAULT_REP_COMMISSION_PCT: float = 0.12
DEFAULT_NEGOTIATION_BUFFER_PCT: float = 0.02


def calculate_property_multiplier(
    building_type: Optional[str] = None,
    building_year: Optional[int] = None,
    floor: Optional[int] = None,
    total_floors: Optional[int] = None,
    has_elevator: Optional[bool] = None,
    has_balcony: Optional[bool] = None,
    balcony_type: Optional[str] = None
) -> Tuple[float, Dict[str, float], List[str]]:
    adjustments: Dict[str, float] = {}
    labels: List[str] = []

    # 1. Typ budynku
    if building_type:
        bt_norm = building_type.strip().lower()
        if any(w in bt_norm for w in ["wielka", "plyta", "płyta"]):
            adjustments["building"] = -0.04
            labels.append("Wielka płyta (-4%)")
        elif "kamienic" in bt_norm:
            adjustments["building"] = -0.02
            labels.append("Kamienica (-2%)")
        elif any(w in bt_norm for w in ["apartament", "nowe", "deweloper"]):
            adjustments["building"] = 0.05
            labels.append("Nowe budownictwo (+5%)")
        else:
            adjustments["building"] = 0.0

    # 2. Kondygnacja i Winda
    if floor is not None:
        is_elev = bool(has_elevator) if has_elevator is not None else False
        if floor == 0:
            adjustments["floor_elevator"] = -0.05
            labels.append("Parter (-5%)")
        elif floor >= 4 and not is_elev:
            adjustments["floor_elevator"] = -0.08
            labels.append(f"{floor}. p. bez windy (-8%)")
        elif floor == 3 and not is_elev:
            adjustments["floor_elevator"] = -0.06
            labels.append("3. p. bez windy (-6%)")
        elif total_floors and floor == total_floors and floor >= 3 and not is_elev:
            adjustments["floor_elevator"] = -0.07
            labels.append(f"Ostatnie p. ({floor}/{total_floors}) bez windy (-7%)")
        elif floor >= 5 and is_elev:
            adjustments["floor_elevator"] = 0.01
            labels.append(f"{floor}. p. z windą (+1%)")
        else:
            adjustments["floor_elevator"] = 0.0

    # 3. Balkon / Taras / Loggia
    if has_balcony is True or (isinstance(has_balcony, int) and has_balcony == 1):
        adjustments["balcony"] = 0.03
        b_name = balcony_type or "Balkon"
        labels.append(f"{b_name} (+3%)")
    elif has_balcony is False:
        adjustments["balcony"] = -0.02
        labels.append("Brak balkonu (-2%)")

    total_delta = sum(adjustments.values())
    multiplier = round(max(0.75, min(1.25, 1.0 + total_delta)), 4)
    return multiplier, adjustments, labels


def calculate_notary_fee(price_pln: float) -> float:
    if price_pln <= 0:
        return 0.0

    if price_pln <= 3000:
        base_fee = 100.0
    elif price_pln <= 10000:
        base_fee = 100.0 + (price_pln - 3000) * 0.03
    elif price_pln <= 30000:
        base_fee = 310.0 + (price_pln - 10000) * 0.02
    elif price_pln <= 60000:
        base_fee = 710.0 + (price_pln - 30000) * 0.01
    elif price_pln <= 1000000:
        base_fee = 1010.0 + (price_pln - 60000) * 0.004
    elif price_pln <= 2000000:
        base_fee = 4770.0 + (price_pln - 1000000) * 0.002
    else:
        base_fee = 6770.0 + (price_pln - 2000000) * 0.0025

    vat = base_fee * 0.23
    court_and_copies = 426.40
    return round(base_fee + vat + court_and_copies, 2)


def get_renovation_rate_for_building_type(building_type: Optional[str]) -> float:
    if not building_type:
        return 1900.0
    bt = building_type.strip().lower()
    if any(w in bt for w in ["apartament", "nowe", "deweloper"]):
        return 1500.0
    if any(w in bt for w in ["wielka", "plyta", "płyta", "blok"]):
        return 1700.0
    if any(w in bt for w in ["kamienic", "stara"]):
        return 1900.0
    return 1900.0


def calculate_investment(
    area_m2: float,
    price_pln: float,
    district_rates: Dict[str, float],
    agency_fee_pct: float = 0.03,
    renovation_cost_m2: Optional[float] = None,
    min_roi: float = 0.16,
    transaction_cost_pct: Optional[float] = None,
    negotiation_buffer_pct: float = 0.02,
    rep_commission_pct: float = 0.12,
    pcc_tax_pct: float = 0.02,
    notary_fee_pln: Optional[float] = 1850.0,
    has_agency_fee: Optional[bool] = None,
    admin_rent: float = 0.0,
    holding_months: Optional[int] = None,
    exit_strategy: str = "fast_flip",
    building_type: Optional[str] = None,
    building_year: Optional[int] = None,
    floor: Optional[int] = None,
    total_floors: Optional[int] = None,
    has_elevator: Optional[bool] = None,
    has_balcony: Optional[bool] = None,
    balcony_type: Optional[str] = None,
    custom_arv_m2: Optional[float] = None,
    holding_utilities_pln: Optional[float] = None,
    holding_insurance_pln: Optional[float] = None,
    marketing_sales_pln: float = 3000.0,
    design_project_pln: Optional[float] = None,
    is_auction: bool = False,
    auction_date: Optional[str] = None,
    auction_type: Optional[str] = None,
    deposit_amount: Optional[float] = None,
    appraisal_value: Optional[float] = None
) -> Dict[str, Any]:
    if not area_m2 or area_m2 <= 0 or not price_pln or price_pln <= 0:
        return {}

    if pcc_tax_pct is not None and pcc_tax_pct > 1.0:
        pcc_tax_pct = pcc_tax_pct / 100.0
    if agency_fee_pct is not None and agency_fee_pct > 1.0:
        agency_fee_pct = agency_fee_pct / 100.0
    if rep_commission_pct is not None and rep_commission_pct > 1.0:
        rep_commission_pct = rep_commission_pct / 100.0
    if negotiation_buffer_pct is not None and negotiation_buffer_pct > 1.0:
        negotiation_buffer_pct = negotiation_buffer_pct / 100.0
    if min_roi is not None and min_roi > 1.0:
        min_roi = min_roi / 100.0

    price_per_m2 = price_pln / area_m2
    market_avg_m2 = district_rates.get("avg_renovation_m2", 9500.0)
    market_diff_pct = (price_per_m2 - market_avg_m2) / market_avg_m2

    ready_min_m2 = district_rates.get("ready_min_m2", 12000.0)
    ready_avg_m2 = district_rates.get("ready_avg_m2", 13000.0)
    ready_max_m2 = district_rates.get("ready_max_m2", 14000.0)

    clean_strat = (exit_strategy or "fast_flip").lower().strip()
    if clean_strat in ["fast_flip", "fast", "p25", "conservative"]:
        base_ready_m2 = ready_min_m2
        exit_strategy = "fast_flip"
        strat_months = 3
    elif clean_strat in ["premium", "p75", "max"]:
        base_ready_m2 = ready_max_m2
        exit_strategy = "premium"
        strat_months = 5
    else:
        base_ready_m2 = ready_avg_m2
        exit_strategy = "balanced"
        strat_months = 4

    effective_holding_months = holding_months if holding_months is not None else strat_months

    if renovation_cost_m2 is None or renovation_cost_m2 <= 0:
        actual_reno_rate = get_renovation_rate_for_building_type(building_type)
    else:
        actual_reno_rate = float(renovation_cost_m2)
    estimated_renovation = area_m2 * actual_reno_rate

    pcc_amount = price_pln * (pcc_tax_pct if pcc_tax_pct is not None else 0.02)
    actual_notary_fee = float(notary_fee_pln) if (notary_fee_pln is not None and float(notary_fee_pln) > 0) else DEFAULT_NOTARY_FEE_PLN

    actual_agency_fee_pct = 0.0
    if is_auction:
        if has_agency_fee is True and agency_fee_pct:
            actual_agency_fee_pct = agency_fee_pct
        else:
            actual_agency_fee_pct = 0.0
    elif has_agency_fee is not False and has_agency_fee != 0:
        actual_agency_fee_pct = agency_fee_pct if agency_fee_pct is not None else 0.03
    agency_fee_amount = price_pln * actual_agency_fee_pct

    if transaction_cost_pct is not None and notary_fee_pln is None and pcc_tax_pct == 0.02:
        total_transaction_costs = price_pln * (transaction_cost_pct + actual_agency_fee_pct)
    else:
        total_transaction_costs = pcc_amount + actual_notary_fee + agency_fee_amount

    holding_rent_amount = (admin_rent or 0.0) * effective_holding_months
    utilities_monthly_rate = DEFAULT_HOLDING_UTILITIES_MONTHLY_PLN
    insurance_monthly_rate = DEFAULT_HOLDING_INSURANCE_MONTHLY_PLN
    holding_utilities_amount = holding_utilities_pln if holding_utilities_pln is not None else (effective_holding_months * utilities_monthly_rate)
    holding_insurance_amount = holding_insurance_pln if holding_insurance_pln is not None else (effective_holding_months * insurance_monthly_rate)
    marketing_sales_amount = marketing_sales_pln if marketing_sales_pln is not None else DEFAULT_MARKETING_SALES_PLN
    design_project_amount = design_project_pln if design_project_pln is not None else DEFAULT_DESIGN_PROJECT_PLN
    total_holding_and_marketing = holding_rent_amount + holding_utilities_amount + holding_insurance_amount + marketing_sales_amount + design_project_amount

    total_investment = price_pln + total_transaction_costs + estimated_renovation + total_holding_and_marketing

    multiplier, prop_adjustments, prop_labels = calculate_property_multiplier(
        building_type=building_type,
        building_year=building_year,
        floor=floor,
        total_floors=total_floors,
        has_elevator=has_elevator,
        has_balcony=has_balcony,
        balcony_type=balcony_type
    )

    if custom_arv_m2 and custom_arv_m2 > 0:
        effective_ready_m2 = custom_arv_m2
        avg_market_ready = (ready_avg_m2 * multiplier) if (ready_avg_m2 and ready_avg_m2 > 0) else (base_ready_m2 * multiplier if base_ready_m2 > 0 else 1.0)
        ratio = custom_arv_m2 / avg_market_ready if avg_market_ready > 0 else 1.0
        arv_target = area_m2 * effective_ready_m2
        arv_min = area_m2 * round(ready_min_m2 * multiplier * ratio, 2)
        arv_avg = arv_target
        arv_max = area_m2 * round(ready_max_m2 * multiplier * ratio, 2)
    else:
        effective_ready_m2 = round(base_ready_m2 * multiplier, 2)
        arv_target = area_m2 * effective_ready_m2
        arv_min = area_m2 * round(ready_min_m2 * multiplier, 2)
        arv_avg = area_m2 * round(ready_avg_m2 * multiplier, 2)
        arv_max = area_m2 * round(ready_max_m2 * multiplier, 2)

    def calc_profit_details(arv_val: float):
        net_sale = arv_val * (1.0 - negotiation_buffer_pct)
        diff = net_sale - total_investment
        if diff > 0:
            comm = round(max(MIN_REP_COMMISSION_PLN, diff * rep_commission_pct), 2)
            net_prof = round(diff - comm, 2)
            return net_prof, comm, round(diff, 2)
        return round(diff, 2), 0.0, round(diff, 2)

    gross_profit, grzegorz_comm, total_diff = calc_profit_details(arv_target)
    gross_profit_min, _, _ = calc_profit_details(arv_min)
    gross_profit_avg, _, _ = calc_profit_details(arv_avg)
    gross_profit_max, _, _ = calc_profit_details(arv_max)

    roi_target = round(gross_profit / total_investment, 4) if total_investment > 0 else 0.0
    roi_min = round(gross_profit_min / total_investment, 4) if total_investment > 0 else 0.0
    roi_avg = round(gross_profit_avg / total_investment, 4) if total_investment > 0 else 0.0
    roi_max = round(gross_profit_max / total_investment, 4) if total_investment > 0 else 0.0

    ann_factor = 12.0 / effective_holding_months if effective_holding_months > 0 else 2.4
    roi_annual_target = round(roi_target * ann_factor, 4)
    roi_annual_min = round(roi_min * (12.0 / 3.0), 4)
    roi_annual_avg = round(roi_avg * (12.0 / 4.0), 4)
    roi_annual_max = round(roi_max * (12.0 / 5.0), 4)

    net_sale_target = round(arv_target * (1.0 - negotiation_buffer_pct), 2)
    net_sale_m2 = round(effective_ready_m2 * (1.0 - negotiation_buffer_pct), 2)

    eff_trans_pct = total_transaction_costs / price_pln if price_pln > 0 else 0.04
    target_l = (arv_target * (1.0 - negotiation_buffer_pct)) / (1.0 + min_roi / (1.0 - rep_commission_pct))
    net_budget = target_l - estimated_renovation - total_holding_and_marketing
    walk_away_price = net_budget / (1.0 + eff_trans_pct)

    if walk_away_price > 0:
        actual_tc_wa = (
            walk_away_price * (pcc_tax_pct if pcc_tax_pct is not None else 0.02)
            + actual_notary_fee
            + (walk_away_price * actual_agency_fee_pct)
        )
        eff_trans_pct_wa = actual_tc_wa / walk_away_price
        walk_away_price = net_budget / (1.0 + eff_trans_pct_wa)

    if is_auction:
        gate_1 = "LICYTUJ" if walk_away_price >= price_pln else "STOP"
    else:
        # Bramka 1: DZWONIMY jeśli ROI >= min_roi ORAZ zysk netto >= 30 000 zł
        gate_1 = "DZWONIMY" if (roi_target >= round(min_roi, 4) and gross_profit >= 30000.0) else "STOP"

    deposit_required = round(deposit_amount if (deposit_amount is not None and float(deposit_amount) > 0) else (price_pln * 0.10), 2)
    bidding_spread = round(max(0.0, walk_away_price - price_pln), 2)
    anchor_price = walk_away_price * 0.82

    return {
        "price_per_m2": round(price_per_m2, 2),
        "market_avg_m2": round(market_avg_m2, 2),
        "market_diff_pct": round(market_diff_pct, 4),
        "estimated_renovation": round(estimated_renovation, 2),
        "total_investment": round(total_investment, 2),
        "arv_target": round(arv_target, 2),
        "arv_min": round(arv_min, 2),
        "arv_avg": round(arv_avg, 2),
        "arv_max": round(arv_max, 2),
        "base_ready_m2": round(base_ready_m2, 2),
        "effective_ready_m2": round(effective_ready_m2, 2),
        "property_multiplier": multiplier,
        "property_adjustments": prop_adjustments,
        "property_adjustment_labels": prop_labels,
        "exit_strategy": exit_strategy,
        "gross_profit": round(gross_profit, 2),
        "gross_profit_target": round(gross_profit, 2),
        "gross_profit_min": round(gross_profit_min, 2),
        "gross_profit_avg": round(gross_profit_avg, 2),
        "gross_profit_max": round(gross_profit_max, 2),
        "grzegorz_commission_pln": grzegorz_comm,
        "company_net_profit_pln": round(gross_profit, 2),
        "profit_before_rep_commission": total_diff,
        "holding_utilities_pln": round(holding_utilities_amount, 2),
        "holding_insurance_pln": round(holding_insurance_amount, 2),
        "marketing_sales_pln": round(marketing_sales_amount, 2),
        "design_project_pln": round(design_project_amount, 2),
        "total_holding_and_marketing": round(total_holding_and_marketing, 2),
        "rep_commission_pct": rep_commission_pct,
        "roi_target": round(roi_target, 4),
        "roi_annual": round(roi_annual_target, 4),
        "net_sale_target": net_sale_target,
        "net_sale_m2": net_sale_m2,
        "negotiation_buffer_pct": negotiation_buffer_pct,
        "holding_months": effective_holding_months,
        "gate_1_decision": gate_1,
        "walk_away_price": round(walk_away_price, 2),
        "anchor_price": round(anchor_price, 2),
        "transaction_costs_breakdown": {
            "pcc_pln": round(pcc_amount, 2),
            "notary_fee_pln": round(actual_notary_fee, 2),
            "agency_fee_pln": round(agency_fee_amount, 2),
            "agency_fee_pct": round(actual_agency_fee_pct, 4),
            "total_transaction_costs": round(total_transaction_costs, 2),
            "admin_rent_holding_pln": round(holding_rent_amount, 2),
            "holding_utilities_pln": round(holding_utilities_amount, 2),
            "holding_insurance_pln": round(holding_insurance_amount, 2),
            "marketing_sales_pln": round(marketing_sales_amount, 2),
            "design_project_pln": round(design_project_amount, 2),
            "total_holding_and_marketing": round(total_holding_and_marketing, 2),
            "grzegorz_commission_pln": grzegorz_comm
        }
    }


def calculate_offer(offer_dict: Dict[str, Any], custom_rates: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, Any]:
    district = offer_dict.get("district") or "Centrum"
    rates_db = custom_rates or DEFAULT_DISTRICT_RATES
    rates = rates_db.get(district, rates_db.get("Centrum", DEFAULT_DISTRICT_RATES["Centrum"]))

    area_m2 = float(offer_dict.get("area_m2") or 0.0)
    price_pln = float(offer_dict.get("price_pln") or 0.0)
    if area_m2 <= 0 or price_pln <= 0:
        return {}

    b_type = offer_dict.get("building_type")
    reno_rate = offer_dict.get("renovation_cost_m2")
    if reno_rate is None:
        reno_rate = get_renovation_rate_for_building_type(b_type)

    return calculate_investment(
        area_m2=area_m2,
        price_pln=price_pln,
        district_rates=rates,
        agency_fee_pct=float(offer_dict.get("agency_fee_pct", 0.03)),
        renovation_cost_m2=float(reno_rate),
        pcc_tax_pct=float(offer_dict.get("pcc_tax_pct", 0.02)),
        notary_fee_pln=float(offer_dict.get("notary_fee_pln", DEFAULT_NOTARY_FEE_PLN)),
        has_agency_fee=offer_dict.get("has_agency_fee", True),
        admin_rent=float(offer_dict.get("admin_rent", 0.0) or 0.0),
        exit_strategy=offer_dict.get("exit_strategy", "fast_flip"),
        custom_arv_m2=float(offer_dict["custom_arv_m2"]) if offer_dict.get("custom_arv_m2") else None,
        building_type=b_type,
        building_year=int(offer_dict["building_year"]) if offer_dict.get("building_year") else None,
        floor=int(offer_dict["floor"]) if offer_dict.get("floor") is not None else None,
        total_floors=int(offer_dict["total_floors"]) if offer_dict.get("total_floors") is not None else None,
        has_elevator=bool(offer_dict["has_elevator"]) if offer_dict.get("has_elevator") is not None else None,
        has_balcony=bool(offer_dict["has_balcony"]) if offer_dict.get("has_balcony") is not None else None,
        balcony_type=offer_dict.get("balcony_type"),
        marketing_sales_pln=float(offer_dict.get("marketing_sales_pln", DEFAULT_MARKETING_SALES_PLN)),
        design_project_pln=float(offer_dict.get("design_project_pln", DEFAULT_DESIGN_PROJECT_PLN)),
        is_auction=bool(offer_dict.get("is_auction", False))
    )
