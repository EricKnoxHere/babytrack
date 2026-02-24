"""AI analysis endpoints for feedings via Claude + RAG."""

import asyncio
import logging
from datetime import date, timedelta
from functools import partial
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.dependencies import DbDep
from app.models.report import AnalysisReport, AnalysisReportSummary
from app.rag.analyzer import analyze_feedings
from app.services import baby_service, feeding_service, report_service, weight_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

PeriodType = Literal["day", "week"]


class SourceReference(BaseModel):
    source: str
    score: Optional[float] = None


class AnalysisResponse(BaseModel):
    baby_id: int
    baby_name: str
    period: PeriodType
    period_label: str
    analysis: str
    sources: list[SourceReference] = []
    report_id: Optional[int] = None  # id of the persisted report


@router.get("/{baby_id}", response_model=AnalysisResponse)
async def analyze_baby_feedings(
    baby_id: int,
    request: Request,
    db: DbDep,
    period: PeriodType = Query("day", description="Analysis period: 'day' or 'week'"),
    reference_date: Optional[date] = Query(
        None,
        description="Reference date (default: today). Format YYYY-MM-DD",
    ),
) -> AnalysisResponse:
    """
    Analyze a baby's feeding data via Claude + WHO/SFP RAG context.
    The result is automatically saved and accessible via GET /analysis/{baby_id}/history.
    """
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")

    ref = reference_date or date.today()

    if period == "day":
        feedings = await feeding_service.get_feedings_by_day(db, baby_id, ref)
        period_label = f"day of {ref.strftime('%m/%d/%Y')}"
    else:
        start = ref - timedelta(days=6)
        feedings = await feeding_service.get_feedings_by_range(db, baby_id, start, ref)
        period_label = f"week from {start.strftime('%m/%d/%Y')} to {ref.strftime('%m/%d/%Y')}"

    if not feedings:
        raise HTTPException(
            status_code=404,
            detail=f"No feedings recorded for the {period_label}",
        )

    # Fetch recent weight entries (last 30 days) to provide growth context + notes
    weight_start = ref - timedelta(days=30) if period == "day" else ref - timedelta(days=13)
    weights = await weight_service.get_weights_by_date_range(db, baby_id, weight_start, ref)

    rag_index = getattr(request.app.state, "rag_index", None)

    loop = asyncio.get_event_loop()
    analysis_text, sources = await loop.run_in_executor(
        None,
        partial(
            analyze_feedings,
            baby=baby,
            feedings=feedings,
            period_label=period_label,
            index=rag_index,
            weights=weights or None,
        ),
    )

    # Persist the report
    report = await report_service.save_report(
        db=db,
        baby_id=baby_id,
        period=period,
        period_label=period_label,
        analysis=analysis_text,
        sources=sources,
    )

    return AnalysisResponse(
        baby_id=baby_id,
        baby_name=baby.name,
        period=period,
        period_label=period_label,
        analysis=analysis_text,
        sources=[SourceReference(**s) for s in sources],
        report_id=report.id,
    )


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
    baby_id: int,
    report_id: int,
    db: DbDep,
) -> AnalysisReport:
    """Return the full text of a specific past analysis report."""
    report = await report_service.get_report(db, report_id)
    if not report or report.baby_id != baby_id:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report


@router.delete("/{baby_id}/history/{report_id}", status_code=204)
async def delete_analysis_report(
    baby_id: int,
    report_id: int,
    db: DbDep,
) -> None:
    """Delete a specific past analysis report."""
    report = await report_service.get_report(db, report_id)
    if not report or report.baby_id != baby_id:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    await report_service.delete_report(db, report_id)
