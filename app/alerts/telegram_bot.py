"""
Moduł powiadomień Telegram dla Nesta Deal Hunter.
Wysyła natychmiastowe alerty o okazjach inwestycyjnych z oceną "DZWONIMY / SUPER OKAZJA".
"""

from typing import Optional
import httpx
from app.core.config import settings
from app.models.listing import Listing

def send_telegram_deal_alert(listing: Listing) -> bool:
    """
    Wysyła sformatowaną kartę okazji na dedykowany kanał/czat Telegram.
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        # Brak konfiguracji tokena - pomijamy bez błędu
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    gate = listing.gate_1_decision or "STOP"
    gate_emoji = "🔥 DZWONIMY" if gate == "DZWONIMY" else ("⚡ LICYTUJ" if gate == "LICYTUJ" else "ℹ️ INFO")

    # Tworzenie treści wiadomości
    text = f"""<b>{gate_emoji} | Deal Score: {listing.deal_score}/100</b>
📍 <b>{listing.district}</b>{f', {listing.street}' if listing.street else ''}
📐 Metraż: <b>{listing.area_m2} m²</b> ({listing.rooms or '?'} pok.)
💰 Cena ofertowa: <b>{listing.price_pln:,.0f} PLN</b> ({listing.price_per_m2:,.0f} zł/m²)

📊 <b>ANALIZA INWESTYCYJNA NESTA HOME:</b>
• Szacowany remont: <b>{listing.estimated_renovation or 0:,.0f} PLN</b>
• ARV (Wartość po remoncie): <b>{listing.arv_target or 0:,.0f} PLN</b>
• Czysty zysk spółki: <b>{listing.company_net_profit_pln or 0:,.0f} PLN</b>
• Zwrot ROI: <b>{(listing.roi_target or 0)*100:.1f}%</b>
• <b>Walk-Away Price:</b> <code>{listing.walk_away_price or 0:,.0f} PLN</code>
• Oferta otwarcia (Anchor): <code>{listing.anchor_price or 0:,.0f} PLN</code>

🏢 Typ budynku: {listing.building_type or 'Brak danych'}
🔥 Ogrzewanie: <b>{listing.heating_source or 'Brak danych'}</b>
🪜 Piętro: {listing.floor if listing.floor is not None else '?'}/{listing.total_floors or '?'}

💡 <b>Atuty:</b> {', '.join(listing.pros or ['Dobra lokalizacja'])[:200]}
⚠️ <b>Ryzyka:</b> {', '.join(listing.red_flags or ['Brak'])[:200]}

🔗 <a href="{listing.url or '#'}">Link do ogłoszenia źródłowego</a>
"""

    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram Alert Error]: {e}")
        return False
