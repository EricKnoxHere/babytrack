"""Unit tests for report_service."""

from datetime import date

import pytest

from app.models.baby import BabyCreate
from app.services.baby_service import create_baby
from app.services.report_service import (
    delete_report,
    get_report,
    list_reports,
    save_report,
)

pytestmark = pytest.mark.asyncio

_ANALYSIS_TEXT = "### ✅ All looks good.\n\nFeedings are within normal range."
_SOURCES = [{"source": "who_infant_feeding.md", "score": 0.92}]


async def _make_baby(db):
    return await create_baby(
        db, BabyCreate(name="Louise", birth_date=date(2026, 2, 16), birth_weight_grams=3200)
    )


async def test_save_report(db):
    baby = await _make_baby(db)
    report = await save_report(
        db,
        baby_id=baby.id,
        period="day",
        period_label="day of 02/24/2026",
        analysis=_ANALYSIS_TEXT,
        sources=_SOURCES,
    )
    assert report.id is not None
    assert report.baby_id == baby.id
    assert report.analysis == _ANALYSIS_TEXT
    assert len(report.sources) == 1
    assert report.sources[0].source == "who_infant_feeding.md"


async def test_get_report(db):
    baby = await _make_baby(db)
    saved = await save_report(db, baby.id, "day", "day of 02/24/2026", _ANALYSIS_TEXT, _SOURCES)
    fetched = await get_report(db, saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.analysis == _ANALYSIS_TEXT


async def test_get_report_not_found(db):
    assert await get_report(db, 9999) is None


async def test_list_reports(db):
    baby = await _make_baby(db)
    await save_report(db, baby.id, "day", "day 1", _ANALYSIS_TEXT, [])
    await save_report(db, baby.id, "week", "week 1", _ANALYSIS_TEXT, [])
    await save_report(db, baby.id, "day", "day 2", _ANALYSIS_TEXT, [])

    reports = await list_reports(db, baby.id)
    assert len(reports) == 3
    # Most recent first (highest id first when timestamps are equal)
    assert reports[0].id > reports[1].id > reports[2].id


async def test_list_reports_limit(db):
    baby = await _make_baby(db)
    for i in range(5):
        await save_report(db, baby.id, "day", f"day {i}", _ANALYSIS_TEXT, [])

    reports = await list_reports(db, baby.id, limit=3)
    assert len(reports) == 3


async def test_list_reports_empty(db):
    baby = await _make_baby(db)
    assert await list_reports(db, baby.id) == []


async def test_delete_report(db):
    baby = await _make_baby(db)
    report = await save_report(db, baby.id, "day", "day 1", _ANALYSIS_TEXT, [])
    assert await delete_report(db, report.id) is True
    assert await get_report(db, report.id) is None


async def test_delete_report_not_found(db):
    assert await delete_report(db, 9999) is False


async def test_cascade_delete_on_baby_delete(db):
    """Deleting a baby should cascade-delete its reports."""
    from app.services.baby_service import delete_baby

    baby = await _make_baby(db)
    await save_report(db, baby.id, "day", "day 1", _ANALYSIS_TEXT, [])
    await save_report(db, baby.id, "week", "week 1", _ANALYSIS_TEXT, [])

    await delete_baby(db, baby.id)
    assert await list_reports(db, baby.id) == []
