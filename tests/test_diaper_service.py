"""Unit tests for diaper_service."""

from datetime import date, datetime

import pytest

from app.models.baby import BabyCreate
from app.models.diaper import DiaperCreate, DiaperUpdate
from app.services.baby_service import create_baby
from app.services.diaper_service import (
    add_diaper,
    delete_diaper,
    get_diaper,
    get_diapers_by_baby,
    get_diapers_by_datetime_range,
    get_diapers_by_range,
    update_diaper,
)

pytestmark = pytest.mark.asyncio


async def _make_baby(db):
    return await create_baby(
        db, BabyCreate(name="Léa", birth_date=date(2024, 1, 15), birth_weight_grams=3200)
    )


def _diaper(
    baby_id: int,
    day: date,
    hour: int = 10,
    has_pee: bool = True,
    has_poop: bool = False,
    notes: str | None = None,
) -> DiaperCreate:
    return DiaperCreate(
        baby_id=baby_id,
        changed_at=datetime(day.year, day.month, day.day, hour, 0, 0),
        has_pee=has_pee,
        has_poop=has_poop,
        notes=notes,
    )


async def test_add_diaper(db):
    baby = await _make_baby(db)
    diaper = await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    assert diaper.id is not None
    assert diaper.has_pee is True
    assert diaper.has_poop is False


async def test_add_diaper_with_poop(db):
    baby = await _make_baby(db)
    diaper = await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), has_poop=True))
    assert diaper.has_poop is True


async def test_add_diaper_with_notes(db):
    baby = await _make_baby(db)
    diaper = await add_diaper(
        db, _diaper(baby.id, date(2024, 2, 1), notes="greenish color")
    )
    assert diaper.notes == "greenish color"


async def test_get_diaper(db):
    baby = await _make_baby(db)
    created = await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    fetched = await get_diaper(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.has_pee == created.has_pee


async def test_get_diaper_not_found(db):
    assert await get_diaper(db, 9999) is None


async def test_get_diapers_by_baby(db):
    baby = await _make_baby(db)
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 8))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 12, has_poop=True))
    diapers = await get_diapers_by_baby(db, baby.id)
    assert len(diapers) == 2


async def test_get_diapers_by_baby_empty(db):
    baby = await _make_baby(db)
    assert await get_diapers_by_baby(db, baby.id) == []


async def test_get_diapers_by_baby_ordered_desc(db):
    """Most recent first."""
    baby = await _make_baby(db)
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 8))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 2), 8))
    diapers = await get_diapers_by_baby(db, baby.id)
    assert diapers[0].changed_at > diapers[1].changed_at


async def test_get_diapers_by_range(db):
    baby = await _make_baby(db)
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 3)))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 5)))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 10)))  # outside

    diapers = await get_diapers_by_range(db, baby.id, date(2024, 2, 1), date(2024, 2, 5))
    assert len(diapers) == 3


async def test_get_diapers_by_range_inclusive(db):
    """start and end bounds are inclusive."""
    baby = await _make_baby(db)
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 7)))

    diapers = await get_diapers_by_range(db, baby.id, date(2024, 2, 1), date(2024, 2, 7))
    assert len(diapers) == 2


async def test_get_diapers_by_datetime_range(db):
    baby = await _make_baby(db)
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 8))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 12))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 20))

    diapers = await get_diapers_by_datetime_range(
        db, baby.id,
        datetime(2024, 2, 1, 0, 0),
        datetime(2024, 2, 1, 14, 0),
    )
    assert len(diapers) == 2  # 8:00 and 12:00, not 20:00


async def test_update_diaper(db):
    baby = await _make_baby(db)
    diaper = await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    updated = await update_diaper(db, diaper.id, DiaperUpdate(has_poop=True))
    assert updated is not None
    assert updated.has_poop is True
    assert updated.has_pee is True  # unchanged


async def test_update_diaper_notes(db):
    baby = await _make_baby(db)
    diaper = await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    updated = await update_diaper(db, diaper.id, DiaperUpdate(notes="dark stool"))
    assert updated.notes == "dark stool"


async def test_update_diaper_no_fields(db):
    """Update with no fields = returns unchanged record."""
    baby = await _make_baby(db)
    diaper = await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    updated = await update_diaper(db, diaper.id, DiaperUpdate())
    assert updated is not None
    assert updated.id == diaper.id


async def test_update_diaper_not_found(db):
    result = await update_diaper(db, 9999, DiaperUpdate(has_pee=False))
    assert result is None


async def test_delete_diaper(db):
    baby = await _make_baby(db)
    diaper = await add_diaper(db, _diaper(baby.id, date(2024, 2, 1)))
    assert await delete_diaper(db, diaper.id) is True
    assert await get_diaper(db, diaper.id) is None


async def test_delete_diaper_not_found(db):
    assert await delete_diaper(db, 9999) is False


async def test_cascade_delete_baby(db):
    """Deleting a baby cascades to delete its diapers."""
    from app.services.baby_service import delete_baby

    baby = await _make_baby(db)
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 8))
    await add_diaper(db, _diaper(baby.id, date(2024, 2, 1), 12))

    await delete_baby(db, baby.id)
    assert await get_diapers_by_baby(db, baby.id) == []
