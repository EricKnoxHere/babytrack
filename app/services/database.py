"""SQLite initialization and async connection management via aiosqlite."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiosqlite

DATABASE_URL = os.getenv("DATABASE_URL", "data/babytrack.db")

_CREATE_BABIES = """
CREATE TABLE IF NOT EXISTS babies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL,
    birth_date          TEXT    NOT NULL,
    birth_weight_grams  INTEGER NOT NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_FEEDINGS = """
CREATE TABLE IF NOT EXISTS feedings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    baby_id       INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    fed_at        TEXT    NOT NULL,
    quantity_ml   INTEGER NOT NULL CHECK(quantity_ml > 0),
    feeding_type  TEXT    NOT NULL CHECK(feeding_type IN ('bottle', 'breastfeeding')),
    notes         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


async def create_tables(db_url: str = DATABASE_URL) -> None:
    """Create the babies and feedings tables if they don't exist."""
    os.makedirs(os.path.dirname(db_url) if os.path.dirname(db_url) else ".", exist_ok=True)
    async with aiosqlite.connect(db_url) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(_CREATE_BABIES)
        await db.execute(_CREATE_FEEDINGS)
        await db.commit()


@asynccontextmanager
async def get_db(db_url: str = DATABASE_URL) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Context manager that provides a SQLite connection with foreign keys enabled."""
    async with aiosqlite.connect(db_url) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db
