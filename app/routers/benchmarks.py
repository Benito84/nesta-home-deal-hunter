"""
Router Domenowy: Kalibracja Benchmarków Dzielnicowych i Złotych Zasad (Active Learning).
Zgodnie ze Standardem Architektury Nesta Home Master Tracker (Sekcja 1.1).
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.templates import templates
from app.models.benchmarks import DistrictBenchmark, GoldenRule, UserFeedbackHistory, SystemPromptSetting
from app.engine.ai_evaluator import build_system_prompt

router = APIRouter(tags=["Benchmarks"])

@router.get("/benchmarks", response_class=HTMLResponse)
def benchmarks_view(request: Request, session: Session = Depends(get_session)):
    benchmarks = session.exec(select(DistrictBenchmark).order_by(DistrictBenchmark.district)).all()
    rules = session.exec(select(GoldenRule).order_by(GoldenRule.created_at.desc())).all()
    feedback = session.exec(select(UserFeedbackHistory).order_by(UserFeedbackHistory.created_at.desc()).limit(30)).all()
    
    setting = session.exec(select(SystemPromptSetting).where(SystemPromptSetting.key == "global_directives")).first()
    if not setting:
        setting = SystemPromptSetting(key="global_directives", custom_directives="")
        session.add(setting)
        session.commit()

    prompt_preview = build_system_prompt(session)

    return templates.TemplateResponse(
        request=request,
        name="benchmarks.html",
        context={
            "benchmarks": benchmarks,
            "rules": rules,
            "feedback": feedback,
            "directives": setting.custom_directives,
            "prompt_preview": prompt_preview
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
        bm.updated_at = datetime.now(timezone.utc)
        session.add(bm)
        session.commit()
    return RedirectResponse(url="/benchmarks", status_code=303)

@router.post("/benchmarks/update-directives")
def update_directives_post(
    directives: str = Form(""),
    session: Session = Depends(get_session)
):
    """Zapisuje globalne wytyczne inwestycyjne zarządu dla promptu AI"""
    setting = session.exec(select(SystemPromptSetting).where(SystemPromptSetting.key == "global_directives")).first()
    if not setting:
        setting = SystemPromptSetting(key="global_directives", custom_directives=directives.strip())
    else:
        setting.custom_directives = directives.strip()
        setting.updated_at = datetime.now(timezone.utc)

    session.add(setting)
    session.commit()
    return RedirectResponse(url="/benchmarks#directives-section", status_code=303)

@router.post("/benchmarks/add-rule")
def add_golden_rule(
    rule_text: str = Form(...),
    category: str = Form("general"),
    weight: float = Form(1.0),
    session: Session = Depends(get_session)
):
    new_rule = GoldenRule(
        rule_text=rule_text.strip(),
        category=category,
        weight=weight,
        source="manual",
        is_active=True
    )
    session.add(new_rule)
    session.commit()
    return RedirectResponse(url="/benchmarks#rules-section", status_code=303)

@router.post("/benchmarks/rules/{rule_id}/delete")
def delete_golden_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(GoldenRule, rule_id)
    if rule:
        session.delete(rule)
        session.commit()
    return RedirectResponse(url="/benchmarks#rules-section", status_code=303)

@router.post("/benchmarks/rules/{rule_id}/toggle")
def toggle_golden_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(GoldenRule, rule_id)
    if rule:
        rule.is_active = not rule.is_active
        session.add(rule)
        session.commit()
    return RedirectResponse(url="/benchmarks#rules-section", status_code=303)

@router.post("/benchmarks/feedback/{feedback_id}/promote")
def promote_feedback_to_rule(feedback_id: int, session: Session = Depends(get_session)):
    """Przenosi komentarz inwestorski z historii decyzji bezpośrednio do stałych Złotych Zasad AI"""
    fb = session.get(UserFeedbackHistory, feedback_id)
    if not fb or not fb.comment:
        raise HTTPException(status_code=400, detail="Brak komentarza w podanym feedbacku")

    cat = (fb.reason_category or "general").lower()
    rule = GoldenRule(
        rule_text=fb.comment.strip(),
        category=cat,
        weight=1.3,
        source="feedback_promotion",
        is_active=True
    )
    session.add(rule)
    session.commit()
    return RedirectResponse(url="/benchmarks#rules-section", status_code=303)
