"""Unit tests for weight_service."""

from datetime import date, datetime

import pytest

from app.models.baby import BabyCreate
from app.models.weight import WeightCreate, WeightUpdate
from app.services.baby_service import create_baby
from app.services.weight_service import (
    add_weight,
    delete_weight,
    get_weight,
    get_weights_by_baby,
    update_weight,
)

pytestmark = pytest.mark.asyncio


async def _make_baby(db):
    return await create_baby(
        db, BabyCreate(name="Louise", birth_date=date(2024, 1, 15), birth_weight_grams=3200)
    )


async def test_add_weight(db):
    baby = await _make_baby(db)
    weight = await add_weight(
        db,
        WeightCreate(
            baby_id=baby.id,
            measured_at=datetime(2024, 1, 15, 9, 0),
            weight_g=3200,
            notes="at birth",
        ),
    )
    assert weight.id is not None
    assert weight.weight_g == 3200
    assert weight.notes == "at birth"


async def test_get_weight(db):
    baby = await _make_baby(db)
    created = await add_weight(
        db,
        WeightCreate(
            baby_id=baby.id,
            measured_at=datetime(2024, 1, 15, 9, 0),
            weight_g=3200,
        ),
    )
    fetched = await get_weight(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.weight_g == 3200


async def test_get_weight_not_found(db):
    assert await get_weight(db, 9999) is None


async def test_get_weights_by_baby(db):
    baby = await _make_baby(db)
    await add_weight(
        db,
        WeightCreate(
            baby_id=baby.id,
            measured_at=datetime(2024, 1, 15, 9, 0),
            weight_g=3200,
        ),
    )
    await add_weight(
        db,
        WeightCreate(
            baby_id=baby.id,
            measured_at=datetime(2024, 1, 22, 9, 0),
            weight_g=3500,
        ),
    )
    weights = await get_weights_by_baby(db, baby.id)
    assert len(weights) == 2
    # Should be chronologically ordered
    assert weights[0].weight_g < weights[1].weight_g


async def test_get_weights_by_baby_empty(db):
    baby = await _make_baby(db)
    assert await get_weights_by_baby(db, baby.id) == []


async def test_update_weight(db):
    baby = await _make_baby(db)
    weight = await add_weight(
        db,
        WeightCreate(
            baby_id=baby.id,
            measured_at=datetime(2024, 1, 15, 9, 0),
            weight_g=3200,
        ),
    )
    updated = await update_weight(db, weight.id, WeightUpdate(weight_g=3250))
    assert updated is not None
    assert updated.weight_g == 3250


async def test_update_weight_not_found(db):
    result = await update_weight(db, 9999, WeightUpdate(weight_g=3300))
    assert result is None


async def test_delete_weight(db):
    baby = await _make_baby(db)
    weight = await add_weight(
        db,
        WeightCreate(
            baby_id=baby.id,
            measured_at=datetime(2024, 1, 15, 9, 0),
            weight_g=3200,
        ),
    )
    assert await delete_weight(db, weight.id) is True
    assert await get_weight(db, weight.id) is None


async def test_delete_weight_not_found(db):
    assert await delete_weight(db, 9999) is False
