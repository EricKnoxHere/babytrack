"""AI analysis endpoints — free datetime range, partial-day aware."""

import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.dependencies import DbDep
from app.models.report import AnalysisReport, AnalysisReportSummary
from app.services import baby_service, diaper_service, feeding_service, report_service, weight_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

# Gap below which we consider the window "still ongoing"
_PARTIAL_THRESHOLD_MINUTES = 30


class SourceReference(BaseModel):
    source: str
    score: Optional[float] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    chat_history: list[ChatMessage] = []


class AnalysisResponse(BaseModel):
    baby_id: int
    baby_name: str
    period_label: str
    start_datetime: datetime
    end_datetime: datetime
    is_partial: bool
    analysis: str
    sources: list[SourceReference] = []
    report_id: Optional[int] = None


def _make_period_label(start: datetime, end: datetime, is_partial: bool) -> str:
    same_day = start.date() == end.date()
    if same_day:
        label = f"{start.strftime('%d/%m/%Y')} · {start.strftime('%H:%M')} → {end.strftime('%H:%M')}"
    else:
        label = f"{start.strftime('%d/%m/%Y %H:%M')} → {end.strftime('%d/%m/%Y %H:%M')}"
    return label + (" (ongoing)" if is_partial else "")


@router.get("/{baby_id}", response_model=AnalysisResponse)
async def analyze_baby_feedings(
    baby_id: int,
    request: Request,
    db: DbDep,
    start: Optional[datetime] = Query(
        None,
        description="Window start (ISO datetime). Default: today at 00:00.",
    ),
    end: Optional[datetime] = Query(
        None,
        description="Window end (ISO datetime). Default: now.",
    ),
    question: Optional[str] = Query(
        None,
        description="Parent's free-text question. When provided, Claude gives a short conversational answer instead of a full report.",
    ),
) -> AnalysisResponse:
    """
    Analyse feedings in a freely defined datetime window.

    - Default: today from midnight to now (partial day).
    - Pass start + end to analyse any custom range.
    - The response includes an is_partial flag and a temporal context
      so Claude evaluates pace on ongoing windows, not totals.
    """
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")

    # Lazy import RAG only when needed (avoids loading torch/sentence-transformers at startup)
    from app.rag.analyzer import AnalysisContext, _expected_feedings_per_hour, analyze_feedings

    now = datetime.now()
    end_dt = end or now
    start_dt = start or datetime(now.year, now.month, now.day, 0, 0, 0)

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="'end' must be after 'start'")

    # Partial: end is within the last PARTIAL_THRESHOLD_MINUTES
    is_partial = (now - end_dt).total_seconds() < _PARTIAL_THRESHOLD_MINUTES * 60

    hours_elapsed = (end_dt - start_dt).total_seconds() / 3600

    # Feedings in the requested window
    feedings = await feeding_service.get_feedings_by_datetime_range(db, baby_id, start_dt, end_dt)
    if not feedings and not question:
        # No feedings + no question = nothing to analyze (report mode)
        raise HTTPException(
            status_code=404,
            detail=f"No feedings recorded between {start_dt.strftime('%d/%m %H:%M')} and {end_dt.strftime('%d/%m %H:%M')}",
        )
    if not feedings:
        feedings = []  # conversational mode: answer from RAG context + baby profile

    # Baseline: previous equivalent window
    baseline_start = start_dt - timedelta(hours=hours_elapsed)
    baseline_end = start_dt
    baseline_feedings = await feeding_service.get_feedings_by_datetime_range(
        db, baby_id, baseline_start, baseline_end
    )
    baseline_count = len(baseline_feedings)
    baseline_volume = sum(f.quantity_ml for f in baseline_feedings)
    same_day_baseline = baseline_start.date() == baseline_end.date()
    baseline_label = (
        f"{baseline_start.strftime('%d/%m %H:%M')} → {baseline_end.strftime('%H:%M')}"
        if same_day_baseline
        else f"{baseline_start.strftime('%d/%m %H:%M')} → {baseline_end.strftime('%d/%m %H:%M')}"
    )

    # Expected feedings for this window based on age
    age_days = (now.date() - baby.birth_date).days
    rate = _expected_feedings_per_hour(age_days)
    feedings_expected = max(1, round(rate * hours_elapsed))

    ctx = AnalysisContext(
        start=start_dt,
        end=end_dt,
        is_partial=is_partial,
        hours_elapsed=hours_elapsed,
        feedings_expected=feedings_expected,
        baseline_count=baseline_count,
        baseline_volume_ml=baseline_volume,
        baseline_label=baseline_label,
    )

    # Weights: last 30 days for growth context
    weights = await weight_service.get_weights_by_date_range(
        db, baby_id, (end_dt - timedelta(days=30)).date(), end_dt.date()
    )

    # Diapers in the window for hydration context
    diapers = await diaper_service.get_diapers_by_datetime_range(db, baby_id, start_dt, end_dt)

    rag_index = getattr(request.app.state, "rag_index", None)
    period_label = _make_period_label(start_dt, end_dt, is_partial)

    loop = asyncio.get_event_loop()
    analysis_text, sources = await loop.run_in_executor(
        None,
        partial(
            analyze_feedings,
            baby=baby,
            feedings=feedings,
            ctx=ctx,
            index=rag_index,
            weights=weights or None,
            diapers=diapers or None,
            question=question,
        ),
    )

    report = await report_service.save_report(
        db=db,
        baby_id=baby_id,
        period_label=period_label,
        start_datetime=start_dt,
        end_datetime=end_dt,
        is_partial=is_partial,
        analysis=analysis_text,
        sources=sources,
    )

    return AnalysisResponse(
        baby_id=baby_id,
        baby_name=baby.name,
        period_label=period_label,
        start_datetime=start_dt,
        end_datetime=end_dt,
        is_partial=is_partial,
        analysis=analysis_text,
        sources=[SourceReference(**s) for s in sources],
        report_id=report.id,
    )


@router.post("/{baby_id}/chat", response_model=AnalysisResponse)
async def chat_with_history(
    baby_id: int,
    body: ChatRequest,
    request: Request,
    db: DbDep,
) -> AnalysisResponse:
    """
    Chat endpoint that accepts conversation history for contextual follow-ups.
    """
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")

    from app.rag.analyzer import AnalysisContext, _expected_feedings_per_hour, analyze_feedings

    now = datetime.now()
    end_dt = body.end or now
    start_dt = body.start or datetime(now.year, now.month, now.day, 0, 0, 0)

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="'end' must be after 'start'")

    is_partial = (now - end_dt).total_seconds() < _PARTIAL_THRESHOLD_MINUTES * 60
    hours_elapsed = (end_dt - start_dt).total_seconds() / 3600

    feedings = await feeding_service.get_feedings_by_datetime_range(db, baby_id, start_dt, end_dt)
    if not feedings:
        feedings = []

    baseline_start = start_dt - timedelta(hours=hours_elapsed)
    baseline_end = start_dt
    baseline_feedings = await feeding_service.get_feedings_by_datetime_range(
        db, baby_id, baseline_start, baseline_end
    )
    baseline_count = len(baseline_feedings)
    baseline_volume = sum(f.quantity_ml for f in baseline_feedings)
    same_day_baseline = baseline_start.date() == baseline_end.date()
    baseline_label = (
        f"{baseline_start.strftime('%d/%m %H:%M')} → {baseline_end.strftime('%H:%M')}"
        if same_day_baseline
        else f"{baseline_start.strftime('%d/%m %H:%M')} → {baseline_end.strftime('%d/%m %H:%M')}"
    )

    age_days = (now.date() - baby.birth_date).days
    rate = _expected_feedings_per_hour(age_days)
    feedings_expected = max(1, round(rate * hours_elapsed))

    ctx = AnalysisContext(
        start=start_dt,
        end=end_dt,
        is_partial=is_partial,
        hours_elapsed=hours_elapsed,
        feedings_expected=feedings_expected,
        baseline_count=baseline_count,
        baseline_volume_ml=baseline_volume,
        baseline_label=baseline_label,
    )

    weights = await weight_service.get_weights_by_date_range(
        db, baby_id, (end_dt - timedelta(days=30)).date(), end_dt.date()
    )

    # Diapers in the window for hydration context
    diapers = await diaper_service.get_diapers_by_datetime_range(db, baby_id, start_dt, end_dt)

    rag_index = getattr(request.app.state, "rag_index", None)
    period_label = _make_period_label(start_dt, end_dt, is_partial)

    # Convert chat history to plain dicts
    history = [{"role": m.role, "content": m.content} for m in body.chat_history]

    loop = asyncio.get_event_loop()
    analysis_text, sources = await loop.run_in_executor(
        None,
        partial(
            analyze_feedings,
            baby=baby,
            feedings=feedings,
            ctx=ctx,
            index=rag_index,
            weights=weights or None,
            diapers=diapers or None,
            question=body.question,
            chat_history=history,
        ),
    )

    # Don't save chat messages as reports (only save explicit report requests)
    report_id = None
    if _is_report_request_label(body.question):
        report = await report_service.save_report(
            db=db,
            baby_id=baby_id,
            period_label=period_label,
            start_datetime=start_dt,
            end_datetime=end_dt,
            is_partial=is_partial,
            analysis=analysis_text,
            sources=sources,
        )
        report_id = report.id

    return AnalysisResponse(
        baby_id=baby_id,
        baby_name=baby.name,
        period_label=period_label,
        start_datetime=start_dt,
        end_datetime=end_dt,
        is_partial=is_partial,
        analysis=analysis_text,
        sources=[SourceReference(**s) for s in sources],
        report_id=report_id,
    )


def _is_report_request_label(question: str | None) -> bool:
    """Check if question is a report request (mirrors analyzer logic)."""
    if not question:
        return True
    q = question.lower().strip()
    report_kw = {"analyze", "analyse", "analysis", "report", "bilan", "detailed", "rapport", "complet"}
    return any(kw in q for kw in report_kw)


@router.get("/{baby_id}/history", response_model=list[AnalysisReportSummary])
async def list_analysis_history(
    baby_id: int,
    db: DbDep,
    limit: int = Query(20, ge=1, le=100),
) -> list[AnalysisReportSummary]:
    """Return the list of past analysis reports for a baby (newest first)."""
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")
    return await report_service.list_reports(db, baby_id, limit=limit)


@router.get("/{baby_id}/history/{report_id}", response_model=AnalysisReport)
async def get_analysis_report(
    baby_id: int, report_id: int, db: DbDep
) -> AnalysisReport:
    """Return the full text of a specific past analysis report."""
    report = await report_service.get_report(db, report_id)
    if not report or report.baby_id != baby_id:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report


@router.delete("/{baby_id}/history/{report_id}", status_code=204)
async def delete_analysis_report(
    baby_id: int, report_id: int, db: DbDep
) -> None:
    """Delete a specific past analysis report."""
    report = await report_service.get_report(db, report_id)
    if not report or report.baby_id != baby_id:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    await report_service.delete_report(db, report_id)
