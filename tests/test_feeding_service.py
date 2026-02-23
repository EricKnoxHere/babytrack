"""Tests unitaires pour feeding_service."""

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
)

pytestmark = pytest.mark.asyncio


async def _make_baby(db):
    return await create_baby(
        db, BabyCreate(name="Léa", birth_date=date(2024, 1, 15), birth_weight_grams=3200)
    )


def _dt(year, month, day, hour=12, minute=0):
    return datetime(year, month, day, hour, minute)


async def test_add_feeding(db):
    baby = await _make_baby(db)
    feeding = await add_feeding(
        db,
        FeedingCreate(
            baby_id=baby.id,
            fed_at=_dt(2024, 3, 10, 9, 0),
            quantity_ml=120,
            feeding_type="bottle",
        ),
    )
    assert feeding.id is not None
    assert feeding.quantity_ml == 120
    assert feeding.feeding_type == "bottle"


async def test_get_feeding(db):
    baby = await _make_baby(db)
    created = await add_feeding(
        db,
        FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10), quantity_ml=80, feeding_type="breastfeeding"),
    )
    fetched = await get_feeding(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id


async def test_get_feeding_not_found(db):
    assert await get_feeding(db, 9999) is None


async def test_get_feedings_by_baby(db):
    baby = await _make_baby(db)
    await add_feeding(db, FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10, 8), quantity_ml=100, feeding_type="bottle"))
    await add_feeding(db, FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10, 12), quantity_ml=120, feeding_type="bottle"))
    feedings = await get_feedings_by_baby(db, baby.id)
    assert len(feedings) == 2
    # Ordre décroissant
    assert feedings[0].fed_at > feedings[1].fed_at


async def test_get_feedings_by_day(db):
    baby = await _make_baby(db)
    await add_feeding(db, FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10, 8), quantity_ml=100, feeding_type="bottle"))
    await add_feeding(db, FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10, 14), quantity_ml=130, feeding_type="bottle"))
    await add_feeding(db, FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 11, 9), quantity_ml=90, feeding_type="breastfeeding"))

    day_feedings = await get_feedings_by_day(db, baby.id, date(2024, 3, 10))
    assert len(day_feedings) == 2

    other_day = await get_feedings_by_day(db, baby.id, date(2024, 3, 11))
    assert len(other_day) == 1


async def test_get_feedings_by_range(db):
    baby = await _make_baby(db)
    for day in [8, 9, 10, 11, 12]:
        await add_feeding(
            db,
            FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, day, 10), quantity_ml=100, feeding_type="bottle"),
        )

    feedings = await get_feedings_by_range(db, baby.id, date(2024, 3, 9), date(2024, 3, 11))
    assert len(feedings) == 3
    assert all(date(2024, 3, 9) <= f.fed_at.date() <= date(2024, 3, 11) for f in feedings)


async def test_get_feedings_empty_baby(db):
    baby = await _make_baby(db)
    assert await get_feedings_by_baby(db, baby.id) == []


async def test_delete_feeding(db):
    baby = await _make_baby(db)
    feeding = await add_feeding(
        db,
        FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10), quantity_ml=100, feeding_type="bottle"),
    )
    assert await delete_feeding(db, feeding.id) is True
    assert await get_feeding(db, feeding.id) is None


async def test_delete_feeding_not_found(db):
    assert await delete_feeding(db, 9999) is False


async def test_cascade_delete(db):
    """Supprimer un bébé doit supprimer ses biberons en cascade."""
    from app.services.baby_service import delete_baby

    baby = await _make_baby(db)
    await add_feeding(db, FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10), quantity_ml=100, feeding_type="bottle"))
    await add_feeding(db, FeedingCreate(baby_id=baby.id, fed_at=_dt(2024, 3, 10, 14), quantity_ml=80, feeding_type="bottle"))

    await delete_baby(db, baby.id)
    feedings = await get_feedings_by_baby(db, baby.id)
    assert feedings == []
