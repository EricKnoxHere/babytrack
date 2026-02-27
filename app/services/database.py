"""SQLite initialization and async connection management via aiosqlite."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiosqlite

DATABASE_URL = os.getenv("DATABASE_URL", "data/babytrack.db")

__all__ = ["DATABASE_URL", "create_tables", "get_db", "_CREATE_BABIES", "_CREATE_FEEDINGS", "_CREATE_WEIGHTS", "_CREATE_ANALYSIS_REPORTS", "_CREATE_DIAPERS", "_CREATE_CONVERSATIONS"]

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

_CREATE_WEIGHTS = """
CREATE TABLE IF NOT EXISTS weight_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    baby_id     INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    measured_at TEXT    NOT NULL,
    weight_g    INTEGER NOT NULL CHECK(weight_g > 0),
    notes       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_ANALYSIS_REPORTS = """
CREATE TABLE IF NOT EXISTS analysis_reports (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    baby_id        INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    period_label   TEXT    NOT NULL,
    start_datetime TEXT    NOT NULL,
    end_datetime   TEXT    NOT NULL,
    is_partial     INTEGER NOT NULL DEFAULT 0,
    analysis       TEXT    NOT NULL,
    sources_json   TEXT    NOT NULL DEFAULT '[]',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


_CREATE_DIAPERS = """
CREATE TABLE IF NOT EXISTS diapers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    baby_id     INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    changed_at  TEXT    NOT NULL,
    has_pee     INTEGER NOT NULL DEFAULT 1,
    has_poop    INTEGER NOT NULL DEFAULT 0,
    notes       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS chat_conversations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    baby_id       INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    title         TEXT    NOT NULL,
    messages_json TEXT    NOT NULL DEFAULT '[]',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


async def _migrate_analysis_reports(db: aiosqlite.Connection) -> None:
    """Recreate analysis_reports if it uses the old schema (period + no start/end cols)."""
    async with db.execute("PRAGMA table_info(analysis_reports)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    if cols and "start_datetime" not in cols:
        # Old schema detected — migrate (dev data loss accepted)
        await db.execute("DROP TABLE analysis_reports")
        await db.execute(_CREATE_ANALYSIS_REPORTS)
        await db.commit()


async def create_tables(db_url: str = DATABASE_URL) -> None:
    """Create all application tables if they don't exist."""
    os.makedirs(os.path.dirname(db_url) if os.path.dirname(db_url) else ".", exist_ok=True)
    async with aiosqlite.connect(db_url) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(_CREATE_BABIES)
        await db.execute(_CREATE_FEEDINGS)
        await db.execute(_CREATE_WEIGHTS)
        await _migrate_analysis_reports(db)
        await db.execute(_CREATE_ANALYSIS_REPORTS)
        await db.execute(_CREATE_DIAPERS)
        await db.execute(_CREATE_CONVERSATIONS)
        await db.commit()


@asynccontextmanager
async def get_db(db_url: str = DATABASE_URL) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Context manager that provides a SQLite connection with foreign keys enabled."""
    async with aiosqlite.connect(db_url) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db
