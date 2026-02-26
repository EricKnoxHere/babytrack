"""Shared fixtures across tests — PostgreSQL via asyncpg."""

import os

import pytest
import pytest_asyncio
import asyncpg

from app.services.database import (
    _CREATE_ANALYSIS_REPORTS,
    _CREATE_BABIES,
    _CREATE_CONVERSATIONS,
    _CREATE_DIAPERS,
    _CREATE_FEEDINGS,
    _CREATE_WEIGHTS,
)

# Use TEST_DATABASE_URL or fall back to DATABASE_URL
_TEST_DSN = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db():
    """PostgreSQL connection with tables, rolled back after each test."""
    if not _TEST_DSN:
        pytest.skip("No TEST_DATABASE_URL or DATABASE_URL set — skipping DB tests")

    conn = await asyncpg.connect(_TEST_DSN)

    # Start a transaction that we'll roll back at the end
    tr = conn.transaction()
    await tr.start()

    # Create tables inside the transaction
    await conn.execute(_CREATE_BABIES)
    await conn.execute(_CREATE_FEEDINGS)
    await conn.execute(_CREATE_WEIGHTS)
    await conn.execute(_CREATE_ANALYSIS_REPORTS)
    await conn.execute(_CREATE_DIAPERS)
    await conn.execute(_CREATE_CONVERSATIONS)

    yield conn

    # Roll back everything — clean slate for next test
    await tr.rollback()
    await conn.close()
