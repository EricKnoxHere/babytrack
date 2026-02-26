"""PostgreSQL initialization and async connection management via asyncpg."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Connection pool (initialized at startup)
_pool: asyncpg.Pool | None = None

__all__ = [
    "DATABASE_URL", "create_tables", "get_db", "init_pool", "close_pool",
    "_CREATE_BABIES", "_CREATE_FEEDINGS", "_CREATE_WEIGHTS",
    "_CREATE_ANALYSIS_REPORTS", "_CREATE_DIAPERS", "_CREATE_CONVERSATIONS",
]

_CREATE_BABIES = """
CREATE TABLE IF NOT EXISTS babies (
    id                  SERIAL PRIMARY KEY,
    name                TEXT    NOT NULL,
    birth_date          TEXT    NOT NULL,
    birth_weight_grams  INTEGER NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT now()
)
"""

_CREATE_FEEDINGS = """
CREATE TABLE IF NOT EXISTS feedings (
    id            SERIAL PRIMARY KEY,
    baby_id       INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    fed_at        TIMESTAMP NOT NULL,
    quantity_ml   INTEGER NOT NULL CHECK(quantity_ml > 0),
    feeding_type  TEXT    NOT NULL CHECK(feeding_type IN ('bottle', 'breastfeeding')),
    notes         TEXT,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
)
"""

_CREATE_WEIGHTS = """
CREATE TABLE IF NOT EXISTS weight_entries (
    id          SERIAL PRIMARY KEY,
    baby_id     INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    measured_at TIMESTAMP NOT NULL,
    weight_g    INTEGER NOT NULL CHECK(weight_g > 0),
    notes       TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
)
"""

_CREATE_ANALYSIS_REPORTS = """
CREATE TABLE IF NOT EXISTS analysis_reports (
    id             SERIAL PRIMARY KEY,
    baby_id        INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    period_label   TEXT    NOT NULL,
    start_datetime TIMESTAMP NOT NULL,
    end_datetime   TIMESTAMP NOT NULL,
    is_partial     BOOLEAN NOT NULL DEFAULT FALSE,
    analysis       TEXT    NOT NULL,
    sources_json   JSONB   NOT NULL DEFAULT '[]',
    created_at     TIMESTAMP NOT NULL DEFAULT now()
)
"""


_CREATE_DIAPERS = """
CREATE TABLE IF NOT EXISTS diapers (
    id          SERIAL PRIMARY KEY,
    baby_id     INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    changed_at  TIMESTAMP NOT NULL,
    has_pee     BOOLEAN NOT NULL DEFAULT TRUE,
    has_poop    BOOLEAN NOT NULL DEFAULT FALSE,
    notes       TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
)
"""

_CREATE_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS chat_conversations (
    id            SERIAL PRIMARY KEY,
    baby_id       INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    title         TEXT    NOT NULL,
    messages_json JSONB   NOT NULL DEFAULT '[]',
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
)
"""


async def init_pool(dsn: str | None = None) -> None:
    """Create the asyncpg connection pool."""
    global _pool
    dsn = dsn or DATABASE_URL
    if not dsn:
        raise ValueError("DATABASE_URL is not set — cannot connect to PostgreSQL")
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def create_tables() -> None:
    """Create all application tables if they don't exist."""
    if not _pool:
        raise RuntimeError("Connection pool not initialized — call init_pool() first")
    async with _pool.acquire() as conn:
        await conn.execute(_CREATE_BABIES)
        await conn.execute(_CREATE_FEEDINGS)
        await conn.execute(_CREATE_WEIGHTS)
        await conn.execute(_CREATE_ANALYSIS_REPORTS)
        await conn.execute(_CREATE_DIAPERS)
        await conn.execute(_CREATE_CONVERSATIONS)


@asynccontextmanager
async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Context manager that provides a PostgreSQL connection from the pool."""
    if not _pool:
        raise RuntimeError("Connection pool not initialized — call init_pool() first")
    async with _pool.acquire() as conn:
        yield conn
