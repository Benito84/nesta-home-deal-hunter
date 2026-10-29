"""
Router Domenowy: Integracja z Nesta Master Tracker API v4.04 i Feedback Loop.
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (Sekcja 1.1).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session
from app.core.database import get_session
from app.models.listing import Listing
from app.models.benchmarks import UserFeedbackHistory
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
    session: Session = Depends(get_session)
):
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Oferta nie istnieje")

    fb = UserFeedbackHistory(
        listing_id=listing.id,
        decision=decision,
        reason_category=reason_category,
        comment=comment
    )
    session.add(fb)
    if decision == "REJECTED":
        listing.status = "REJECTED"
        session.add(listing)
    session.commit()
    return {"status": "success", "message": "Feedback zapisany do pamięci AI"}
