"""Unit tests for feeding_service."""

from datetime import date, datetime, timezone

import pytest

from app.models.baby import BabyCreate
from app.models.feeding import FeedingCreate, FeedingUpdate
from app.services.baby_service import create_baby
from app.services.feeding_service import (
    add_feeding,
    delete_feeding,
    get_feeding,
    get_feedings_by_baby,
    get_feedings_by_day,
    get_feedings_by_range,
    update_feeding,
)

pytestmark = pytest.mark.asyncio


async def _make_baby(db):
    return await create_baby(
        db, BabyCreate(name="Léa", birth_date=date(2024, 1, 15), birth_weight_grams=3200)
    )


def _feeding(baby_id: int, day: date, hour: int, ml: int = 120, ftype="bottle") -> FeedingCreate:
    return FeedingCreate(
        baby_id=baby_id,
        fed_at=datetime(day.year, day.month, day.day, hour, 0, 0),
        quantity_ml=ml,
        feeding_type=ftype,
    )


async def test_add_feeding(db):
    baby = await _make_baby(db)
    feeding = await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8))
    assert feeding.id is not None
    assert feeding.quantity_ml == 120
    assert feeding.feeding_type == "bottle"


async def test_get_feeding(db):
    baby = await _make_baby(db)
    created = await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8))
    fetched = await get_feeding(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id


async def test_get_feeding_not_found(db):
    assert await get_feeding(db, 9999) is None


async def test_get_feedings_by_baby(db):
    baby = await _make_baby(db)
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8))
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 12, ml=90))
    feedings = await get_feedings_by_baby(db, baby.id)
    assert len(feedings) == 2


async def test_get_feedings_by_baby_empty(db):
    baby = await _make_baby(db)
    assert await get_feedings_by_baby(db, baby.id) == []


async def test_get_feedings_by_day(db):
    baby = await _make_baby(db)
    day = date(2024, 2, 5)
    await add_feeding(db, _feeding(baby.id, day, 6))
    await add_feeding(db, _feeding(baby.id, day, 10))
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 6), 8))  # different day

    feedings = await get_feedings_by_day(db, baby.id, day)
    assert len(feedings) == 2
    assert all(f.fed_at.date() == day for f in feedings)


async def test_get_feedings_by_day_empty(db):
    baby = await _make_baby(db)
    assert await get_feedings_by_day(db, baby.id, date(2024, 2, 5)) == []


async def test_get_feedings_by_range(db):
    baby = await _make_baby(db)
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8))
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 3), 8))
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 5), 8))
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 10), 8))  # outside range

    feedings = await get_feedings_by_range(db, baby.id, date(2024, 2, 1), date(2024, 2, 5))
    assert len(feedings) == 3


async def test_get_feedings_by_range_inclusive(db):
    """start and end bounds are inclusive."""
    baby = await _make_baby(db)
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8))
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 7), 8))

    feedings = await get_feedings_by_range(db, baby.id, date(2024, 2, 1), date(2024, 2, 7))
    assert len(feedings) == 2


async def test_update_feeding(db):
    baby = await _make_baby(db)
    feeding = await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8, ml=100))
    updated = await update_feeding(db, feeding.id, FeedingUpdate(quantity_ml=150))
    assert updated is not None
    assert updated.quantity_ml == 150
    assert updated.feeding_type == "bottle"  # unchanged


async def test_update_feeding_multiple_fields(db):
    baby = await _make_baby(db)
    feeding = await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8, ml=100))
    updated = await update_feeding(
        db,
        feeding.id,
        FeedingUpdate(quantity_ml=200, notes="updated test"),
    )
    assert updated.quantity_ml == 200
    assert updated.notes == "updated test"


async def test_update_feeding_not_found(db):
    result = await update_feeding(db, 9999, FeedingUpdate(quantity_ml=100))
    assert result is None


async def test_delete_feeding(db):
    baby = await _make_baby(db)
    feeding = await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8))
    assert await delete_feeding(db, feeding.id) is True
    assert await get_feeding(db, feeding.id) is None


async def test_delete_feeding_not_found(db):
    assert await delete_feeding(db, 9999) is False


async def test_cascade_delete_baby(db):
    """Deleting a baby cascades to delete its feedings."""
    from app.services.baby_service import delete_baby

    baby = await _make_baby(db)
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 8))
    await add_feeding(db, _feeding(baby.id, date(2024, 2, 1), 12))

    await delete_baby(db, baby.id)
    assert await get_feedings_by_baby(db, baby.id) == []
