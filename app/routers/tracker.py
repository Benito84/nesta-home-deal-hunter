"""
Router Domenowy: Integracja z Nesta Master Tracker API v4.04 i Feedback Loop.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (Sekcja 1.1).
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session
from app.core.database import get_session
from app.models.listing import Listing
from app.models.benchmarks import UserFeedbackHistory, GoldenRule
from app.integrations.tracker_client import push_to_nesta_tracker

router = APIRouter(tags=["Tracker"])

@router.post("/api/v1/listings/{listing_id}/sync-tracker")
def sync_tracker_endpoint(listing_id: int, force: bool = False, session: Session = Depends(get_session)):
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Oferta nie istnieje")

    ok, msg, data = push_to_nesta_tracker(listing, force=force)
    if ok:
        listing.tracker_synced = True
        listing.tracker_staging_id = data.get("staging_id")
        session.add(listing)
        session.commit()
        return {"status": "success", "message": msg, "staging_id": listing.tracker_staging_id}
    else:
        return JSONResponse(status_code=400, content={"status": "error", "message": msg, "data": data})

@router.post("/api/v1/listings/{listing_id}/feedback")
def feedback_endpoint(
    listing_id: int,
    decision: str = Form(...),
    reason_category: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    promote_to_rule: bool = Form(False),
    session: Session = Depends(get_session)
):
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Oferta nie istnieje")

    comment_clean = comment.strip() if comment else None

    fb = UserFeedbackHistory(
        listing_id=listing.id,
        decision=decision,
        reason_category=reason_category,
        comment=comment_clean
    )
    session.add(fb)

    rule_created = False
    if decision == "REJECTED":
        listing.status = "REJECTED"
        listing.is_active = False  # Usuwamy z aktywnego widoku tablicy okazji
        listing.updated_at = datetime.now(timezone.utc)
        session.add(listing)

        # Opcjonalna automatyczna promocja komentarza do Złotej Zasady AI
        if promote_to_rule and comment_clean:
            cat = reason_category.lower() if reason_category else "general"
            new_rule = GoldenRule(
                rule_text=comment_clean,
                category=cat,
                weight=1.3,
                source="feedback_promotion",
                is_active=True
            )
            session.add(new_rule)
            rule_created = True

    elif decision in ["INTERESTED", "QUALIFIED"]:
        listing.status = "QUALIFIED"
        listing.updated_at = datetime.now(timezone.utc)
        session.add(listing)

    session.commit()

    msg = "Feedback zapisany do pamięci podręcznej AI."
    if rule_created:
        msg += " Utworzono także nową stałą Złotą Zasadę dla silnika analizy."

    return {
        "status": "success",
        "message": msg,
        "listing_id": listing.id,
        "is_active": listing.is_active,
        "rule_created": rule_created
    }
