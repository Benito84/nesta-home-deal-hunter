"""
Router Domenowy: Kalibracja Benchmarków Dzielnicowych i Złotych Zasad (Active Learning).
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (Sekcja 1.1).
"""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.templates import templates
from app.models.benchmarks import DistrictBenchmark, GoldenRule, UserFeedbackHistory

router = APIRouter(tags=["Benchmarks"])

@router.get("/benchmarks", response_class=HTMLResponse)
def benchmarks_view(request: Request, session: Session = Depends(get_session)):
    benchmarks = session.exec(select(DistrictBenchmark).order_by(DistrictBenchmark.district)).all()
    rules = session.exec(select(GoldenRule).order_by(GoldenRule.created_at.desc())).all()
    feedback = session.exec(select(UserFeedbackHistory).order_by(UserFeedbackHistory.created_at.desc()).limit(15)).all()
    return templates.TemplateResponse(
        request=request,
        name="benchmarks.html",
        context={
            "benchmarks": benchmarks,
            "rules": rules,
            "feedback": feedback
        }
    )

@router.post("/benchmarks/update-rate")
def update_rate_post(
    district_id: int = Form(...),
    avg_renovation_m2: float = Form(...),
    ready_min_m2: float = Form(...),
    ready_avg_m2: float = Form(...),
    ready_max_m2: float = Form(...),
    session: Session = Depends(get_session)
):
    bm = session.get(DistrictBenchmark, district_id)
    if bm:
        bm.avg_renovation_m2 = avg_renovation_m2
        bm.ready_min_m2 = ready_min_m2
        bm.ready_avg_m2 = ready_avg_m2
        bm.ready_max_m2 = ready_max_m2
        session.add(bm)
        session.commit()
    return RedirectResponse(url="/benchmarks", status_code=303)

@router.post("/benchmarks/add-rule")
def add_golden_rule(
    rule_text: str = Form(...),
    category: str = Form("general"),
    weight: float = Form(1.0),
    session: Session = Depends(get_session)
):
    new_rule = GoldenRule(rule_text=rule_text, category=category, weight=weight)
    session.add(new_rule)
    session.commit()
    return RedirectResponse(url="/benchmarks", status_code=303)
