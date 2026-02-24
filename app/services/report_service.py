"""Persistence for AI analysis reports."""

import json
from datetime import datetime

import aiosqlite

from app.models.report import AnalysisReport, AnalysisReportSummary, ReportSource


def _row_to_report(row: aiosqlite.Row) -> AnalysisReport:
    sources = [ReportSource(**s) for s in json.loads(row["sources_json"] or "[]")]
    return AnalysisReport(
        id=row["id"],
        baby_id=row["baby_id"],
        period=row["period"],
        period_label=row["period_label"],
        analysis=row["analysis"],
        sources=sources,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_summary(row: aiosqlite.Row) -> AnalysisReportSummary:
    return AnalysisReportSummary(
        id=row["id"],
        baby_id=row["baby_id"],
        period=row["period"],
        period_label=row["period_label"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def save_report(
    db: aiosqlite.Connection,
    baby_id: int,
    period: str,
    period_label: str,
    analysis: str,
    sources: list[dict],
) -> AnalysisReport:
    """Persist an analysis report and return the full record."""
    cursor = await db.execute(
        """INSERT INTO analysis_reports (baby_id, period, period_label, analysis, sources_json)
           VALUES (?, ?, ?, ?, ?)""",
        (baby_id, period, period_label, analysis, json.dumps(sources)),
    )
    await db.commit()
    rows = await db.execute_fetchall(
        "SELECT * FROM analysis_reports WHERE id = ?", (cursor.lastrowid,)
    )
    return _row_to_report(rows[0])


async def get_report(
    db: aiosqlite.Connection, report_id: int
) -> AnalysisReport | None:
    """Return a specific report by id."""
    async with db.execute(
        "SELECT * FROM analysis_reports WHERE id = ?", (report_id,)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_report(row) if row else None


async def list_reports(
    db: aiosqlite.Connection,
    baby_id: int,
    limit: int = 20,
) -> list[AnalysisReportSummary]:
    """Return the most recent report summaries for a baby."""
    rows = await db.execute_fetchall(
        """SELECT id, baby_id, period, period_label, created_at
           FROM analysis_reports
           WHERE baby_id = ?
           ORDER BY created_at DESC, id DESC
           LIMIT ?""",
        (baby_id, limit),
    )
    return [_row_to_summary(r) for r in rows]


async def delete_report(db: aiosqlite.Connection, report_id: int) -> bool:
    """Delete a report. Returns True if deleted."""
    cursor = await db.execute(
        "DELETE FROM analysis_reports WHERE id = ?", (report_id,)
    )
    await db.commit()
    return cursor.rowcount > 0
