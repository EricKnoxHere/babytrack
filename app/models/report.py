"""Analysis report model."""

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportSource(BaseModel):
    source: str
    score: Optional[float] = None


class AnalysisReport(BaseModel):
    """Full report record returned from the database."""
    id: int
    baby_id: int
    period_label: str
    start_datetime: datetime
    end_datetime: datetime
    is_partial: bool
    analysis: str
    sources: list[ReportSource] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisReportSummary(BaseModel):
    """Lightweight listing model — no full analysis text."""
    id: int
    baby_id: int
    period_label: str
    start_datetime: datetime
    end_datetime: datetime
    is_partial: bool
    created_at: datetime
