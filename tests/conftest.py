"""Fixtures partagées entre les tests."""

import pytest
import pytest_asyncio
import aiosqlite

from app.services.database import _CREATE_BABIES, _CREATE_FEEDINGS


@pytest_asyncio.fixture
async def db():
    """Base SQLite en mémoire, tables créées et fermées après chaque test."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(_CREATE_BABIES)
        await conn.execute(_CREATE_FEEDINGS)
        await conn.commit()
        yield conn
