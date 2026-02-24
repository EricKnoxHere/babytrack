"""Shared fixtures across tests."""

import pytest
import pytest_asyncio
import aiosqlite

from app.services.database import _CREATE_BABIES, _CREATE_FEEDINGS, _CREATE_WEIGHTS


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database, tables created and closed after each test."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(_CREATE_BABIES)
        await conn.execute(_CREATE_FEEDINGS)
        await conn.execute(_CREATE_WEIGHTS)
        await conn.commit()
        yield conn
