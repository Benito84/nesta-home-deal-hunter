"""
Konektor Tier 2: IMAP Email Alert Parser (Zero-Ban Architecture)
Odczytuje natywne powiadomienia e-mail z portali Otodom i OLX bez ryzyka blokad IP/Cloudflare.
"""

import imaplib
import email
from email.header import decode_header
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from app.core.config import settings
from app.ingestion.base import BaseConnector

class ImapEmailConnector(BaseConnector):
    @property
    def name(self) -> str:
        return "email_imap"

    def fetch_listings(self) -> List[Dict[str, Any]]:
        if not settings.IMAP_HOST or not settings.IMAP_USER or not settings.IMAP_PASSWORD:
            return []

        results = []
        try:
            mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
            mail.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
            mail.select(settings.IMAP_FOLDER)

            # Szukanie nieprzeczytanych wiadomości z portali
            status, messages = mail.search(None, '(UNSEEN)')
            if status != "OK" or not messages[0]:
                mail.logout()
                return results

            msg_ids = messages[0].split()
            for msg_id in msg_ids[-20:]:  # Ostatnie 20 nieprzeczytanych
                res, data = mail.fetch(msg_id, "(RFC822)")
                if res != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Ekstrakcja treści HTML
                body_html = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/html":
                            body_html = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body_html = msg.get_payload(decode=True).decode(errors="ignore")

                if not body_html:
                    continue

                soup = BeautifulSoup(body_html, "html.parser")
                links = soup.select("a[href*='olx.pl'], a[href*='otodom.pl']")

                for a in links:
                    href = a.get("href", "")
                    text = a.get_text(" ", strip=True)

                    # Wyszukiwanie ceny i metrażu w tekście linku/nagłówka
                    price_m = re.search(r"(\d[\d\s]{3,})\s*zł", text)
                    area_m = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", text)

                    if price_m and area_m:
                        price = float(price_m.group(1).replace(" ", ""))
                        area = float(area_m.group(1).replace(",", "."))
                        
                        district = "Centrum"
                        for d in ["Śródmieście", "Centrum", "Turzyn", "Niebuszewo", "Pogodno", "Gumieńce", "Pomorzany", "Warszewo"]:
                            if d.lower() in text.lower():
                                district = d
                                break

                        results.append({
                            "source": "imap_alert",
                            "url": href,
                            "title": f"Alert e-mail: {district}, {area} m2",
                            "description": text,
                            "district": district,
                            "area_m2": area,
                            "price_pln": price,
                            "building_type": "Kamienica" if "kamienic" in text.lower() else "Wielka płyta",
                            "has_agency_fee": False
                        })

            mail.logout()
        except Exception as e:
            print(f"[IMAP Parser Error]: {e}")

        return results
