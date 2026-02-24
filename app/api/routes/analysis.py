"""AI analysis endpoint for feedings via Claude + RAG."""

import asyncio
import logging
from datetime import date, timedelta
from functools import partial
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.dependencies import DbDep
from app.rag.analyzer import analyze_feedings
from app.services import baby_service, feeding_service

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

    - `period=day` (default): analyzes the day of `reference_date`
    - `period=week`: analyzes the 7 days leading up to `reference_date`
    """
    # 1. Verify the baby exists
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")

    # 2. Resolve dates
    ref = reference_date or date.today()

    if period == "day":
        feedings = await feeding_service.get_feedings_by_day(db, baby_id, ref)
        period_label = f"day of {ref.strftime('%m/%d/%Y')}"
    else:  # week
        start = ref - timedelta(days=6)
        feedings = await feeding_service.get_feedings_by_range(db, baby_id, start, ref)
        period_label = f"week from {start.strftime('%m/%d/%Y')} to {ref.strftime('%m/%d/%Y')}"

    if not feedings:
        raise HTTPException(
            status_code=404,
            detail=f"No feedings recorded for the {period_label}",
        )

    # 3. Get the RAG index from app state (may be None)
    rag_index = getattr(request.app.state, "rag_index", None)

    # 4. Call the analyzer in a thread (it is synchronous / blocking)
    loop = asyncio.get_event_loop()
    analysis_text, sources = await loop.run_in_executor(
        None,
        partial(
            analyze_feedings,
            baby=baby,
            feedings=feedings,
            period_label=period_label,
            index=rag_index,
        ),
    )

    return AnalysisResponse(
        baby_id=baby_id,
        baby_name=baby.name,
        period=period,
        period_label=period_label,
        analysis=analysis_text,
        sources=[SourceReference(**s) for s in sources],
    )
