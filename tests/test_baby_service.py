"""Unit tests for baby_service."""

from datetime import date

import pytest

from app.models.baby import BabyCreate, BabyUpdate
from app.services.baby_service import (
    create_baby,
    delete_baby,
    get_all_babies,
    get_baby,
    update_baby,
)

pytestmark = pytest.mark.asyncio


_BABY = BabyCreate(name="Léa", birth_date=date(2024, 1, 15), birth_weight_grams=3200)


async def test_create_baby(db):
    baby = await create_baby(db, _BABY)
    assert baby.id is not None
    assert baby.name == "Léa"
    assert baby.birth_weight_grams == 3200
    assert baby.created_at is not None


async def test_get_baby(db):
    created = await create_baby(db, _BABY)
    fetched = await get_baby(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == created.name


async def test_get_baby_not_found(db):
    assert await get_baby(db, 9999) is None


async def test_get_all_babies(db):
    assert await get_all_babies(db) == []
    await create_baby(db, _BABY)
    await create_baby(db, BabyCreate(name="Tom", birth_date=date(2023, 6, 1), birth_weight_grams=3500))
    babies = await get_all_babies(db)
    assert len(babies) == 2


async def test_update_baby(db):
    baby = await create_baby(db, _BABY)
    updated = await update_baby(db, baby.id, BabyUpdate(name="Léa-Rose"))
    assert updated is not None
    assert updated.name == "Léa-Rose"
    assert updated.birth_weight_grams == 3200  # unchanged


async def test_update_baby_no_fields(db):
    """Update with no fields = returns unchanged record."""
    baby = await create_baby(db, _BABY)
    updated = await update_baby(db, baby.id, BabyUpdate())
    assert updated is not None
    assert updated.name == baby.name


async def test_update_baby_not_found(db):
    updated = await update_baby(db, 9999, BabyUpdate(name="Ghost"))
    assert updated is None


async def test_delete_baby(db):
    baby = await create_baby(db, _BABY)
    assert await delete_baby(db, baby.id) is True
    assert await get_baby(db, baby.id) is None


async def test_delete_baby_not_found(db):
    assert await delete_baby(db, 9999) is False
