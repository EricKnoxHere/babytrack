"""Persistence for AI analysis reports."""

import json
from datetime import datetime

import asyncpg

from app.models.report import AnalysisReport, AnalysisReportSummary, ReportSource


def _row_to_report(row: asyncpg.Record) -> AnalysisReport:
    sources_data = row["sources_json"]
    if isinstance(sources_data, str):
        sources_data = json.loads(sources_data)
    sources = [ReportSource(**s) for s in (sources_data or [])]
    return AnalysisReport(
        id=row["id"],
        baby_id=row["baby_id"],
        period_label=row["period_label"],
        start_datetime=row["start_datetime"],
        end_datetime=row["end_datetime"],
        is_partial=row["is_partial"],
        analysis=row["analysis"],
        sources=sources,
        created_at=row["created_at"],
    )


def _row_to_summary(row: asyncpg.Record) -> AnalysisReportSummary:
    return AnalysisReportSummary(
        id=row["id"],
        baby_id=row["baby_id"],
        period_label=row["period_label"],
        start_datetime=row["start_datetime"],
        end_datetime=row["end_datetime"],
        is_partial=row["is_partial"],
        created_at=row["created_at"],
    )


async def save_report(
    db: asyncpg.Connection,
    baby_id: int,
    period_label: str,
    start_datetime: datetime,
    end_datetime: datetime,
    is_partial: bool,
    analysis: str,
    sources: list[dict],
) -> AnalysisReport:
    """Persist an analysis report and return the full record."""
    row = await db.fetchrow(
        """INSERT INTO analysis_reports
               (baby_id, period_label, start_datetime, end_datetime, is_partial, analysis, sources_json)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb) RETURNING *""",
        baby_id,
        period_label,
        start_datetime,
        end_datetime,
        is_partial,
        analysis,
        json.dumps(sources),
    )
    return _row_to_report(row)


async def get_report(
    db: asyncpg.Connection, report_id: int
) -> AnalysisReport | None:
    """Return a specific report by id."""
    row = await db.fetchrow(
        "SELECT * FROM analysis_reports WHERE id = $1", report_id
    )
    return _row_to_report(row) if row else None


async def list_reports(
    db: asyncpg.Connection,
    baby_id: int,
    limit: int = 20,
) -> list[AnalysisReportSummary]:
    """Return the most recent report summaries for a baby."""
    rows = await db.fetch(
        """SELECT id, baby_id, period_label, start_datetime, end_datetime, is_partial, created_at
           FROM analysis_reports
           WHERE baby_id = $1
           ORDER BY created_at DESC, id DESC
           LIMIT $2""",
        baby_id, limit,
    )
    return [_row_to_summary(r) for r in rows]


async def delete_report(db: asyncpg.Connection, report_id: int) -> bool:
    """Delete a report. Returns True if deleted."""
    result = await db.execute(
        "DELETE FROM analysis_reports WHERE id = $1", report_id
    )
    return result == "DELETE 1"
