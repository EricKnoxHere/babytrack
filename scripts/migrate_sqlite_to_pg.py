#!/usr/bin/env python3
"""
Migrate data from local SQLite (data/babytrack.db) to Supabase PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_pg.py

Requires DATABASE_URL env var pointing to your Supabase PostgreSQL instance.
"""

import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

import asyncpg

SQLITE_PATH = "data/babytrack.db"
PG_DSN = os.getenv("DATABASE_URL", "")

# DDL for PostgreSQL tables (same as database.py)
TABLES_DDL = [
    """CREATE TABLE IF NOT EXISTS babies (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL, birth_date TEXT NOT NULL,
        birth_weight_grams INTEGER NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS feedings (
        id SERIAL PRIMARY KEY, baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
        fed_at TIMESTAMP NOT NULL, quantity_ml INTEGER NOT NULL CHECK(quantity_ml > 0),
        feeding_type TEXT NOT NULL, notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS weight_entries (
        id SERIAL PRIMARY KEY, baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
        measured_at TIMESTAMP NOT NULL, weight_g INTEGER NOT NULL CHECK(weight_g > 0),
        notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS analysis_reports (
        id SERIAL PRIMARY KEY, baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
        period_label TEXT NOT NULL, start_datetime TIMESTAMP NOT NULL, end_datetime TIMESTAMP NOT NULL,
        is_partial BOOLEAN NOT NULL DEFAULT FALSE, analysis TEXT NOT NULL,
        sources_json JSONB NOT NULL DEFAULT '[]', created_at TIMESTAMP NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS diapers (
        id SERIAL PRIMARY KEY, baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
        changed_at TIMESTAMP NOT NULL, has_pee BOOLEAN NOT NULL DEFAULT TRUE,
        has_poop BOOLEAN NOT NULL DEFAULT FALSE, notes TEXT, created_at TIMESTAMP NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS chat_conversations (
        id SERIAL PRIMARY KEY, baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
        title TEXT NOT NULL, messages_json JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMP NOT NULL DEFAULT now(), updated_at TIMESTAMP NOT NULL DEFAULT now()
    )""",
]


def parse_dt(s: str | None) -> datetime | None:
    """Parse an ISO datetime string from SQLite."""
    if not s:
        return None
    return datetime.fromisoformat(s)


async def migrate():
    if not PG_DSN:
        print("❌ DATABASE_URL not set. Add it to .env first.")
        sys.exit(1)

    if not Path(SQLITE_PATH).exists():
        print(f"❌ SQLite DB not found at {SQLITE_PATH}")
        sys.exit(1)

    # Connect to SQLite
    lite = sqlite3.connect(SQLITE_PATH)
    lite.row_factory = sqlite3.Row
    print(f"✅ Connected to SQLite: {SQLITE_PATH}")

    # Connect to PostgreSQL
    pg = await asyncpg.connect(PG_DSN)
    print(f"✅ Connected to PostgreSQL")

    # Create tables
    for ddl in TABLES_DDL:
        await pg.execute(ddl)
    print("✅ Tables created")

    # --- Migrate babies ---
    babies = lite.execute("SELECT * FROM babies ORDER BY id").fetchall()
    for b in babies:
        await pg.execute(
            """INSERT INTO babies (id, name, birth_date, birth_weight_grams, created_at)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (id) DO NOTHING""",
            b["id"], b["name"], b["birth_date"], b["birth_weight_grams"],
            parse_dt(b["created_at"]) or datetime.now(),
        )
    print(f"✅ Migrated {len(babies)} babies")

    # --- Migrate feedings ---
    feedings = lite.execute("SELECT * FROM feedings ORDER BY id").fetchall()
    for f in feedings:
        await pg.execute(
            """INSERT INTO feedings (id, baby_id, fed_at, quantity_ml, feeding_type, notes, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               ON CONFLICT (id) DO NOTHING""",
            f["id"], f["baby_id"], parse_dt(f["fed_at"]),
            f["quantity_ml"], f["feeding_type"], f["notes"],
            parse_dt(f["created_at"]) or datetime.now(),
        )
    print(f"✅ Migrated {len(feedings)} feedings")

    # --- Migrate weight_entries ---
    weights = lite.execute("SELECT * FROM weight_entries ORDER BY id").fetchall()
    for w in weights:
        await pg.execute(
            """INSERT INTO weight_entries (id, baby_id, measured_at, weight_g, notes, created_at)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (id) DO NOTHING""",
            w["id"], w["baby_id"], parse_dt(w["measured_at"]),
            w["weight_g"], w["notes"],
            parse_dt(w["created_at"]) or datetime.now(),
        )
    print(f"✅ Migrated {len(weights)} weight entries")

    # --- Migrate diapers ---
    diapers = lite.execute("SELECT * FROM diapers ORDER BY id").fetchall()
    for d in diapers:
        await pg.execute(
            """INSERT INTO diapers (id, baby_id, changed_at, has_pee, has_poop, notes, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               ON CONFLICT (id) DO NOTHING""",
            d["id"], d["baby_id"], parse_dt(d["changed_at"]),
            bool(d["has_pee"]), bool(d["has_poop"]), d["notes"],
            parse_dt(d["created_at"]) or datetime.now(),
        )
    print(f"✅ Migrated {len(diapers)} diapers")

    # --- Migrate analysis_reports ---
    reports = lite.execute("SELECT * FROM analysis_reports ORDER BY id").fetchall()
    for r in reports:
        sources = r["sources_json"] or "[]"
        await pg.execute(
            """INSERT INTO analysis_reports
                   (id, baby_id, period_label, start_datetime, end_datetime, is_partial, analysis, sources_json, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
               ON CONFLICT (id) DO NOTHING""",
            r["id"], r["baby_id"], r["period_label"],
            parse_dt(r["start_datetime"]), parse_dt(r["end_datetime"]),
            bool(r["is_partial"]), r["analysis"], sources,
            parse_dt(r["created_at"]) or datetime.now(),
        )
    print(f"✅ Migrated {len(reports)} analysis reports")

    # --- Migrate chat_conversations ---
    convos = lite.execute("SELECT * FROM chat_conversations ORDER BY id").fetchall()
    for c in convos:
        msgs = c["messages_json"] or "[]"
        await pg.execute(
            """INSERT INTO chat_conversations
                   (id, baby_id, title, messages_json, created_at, updated_at)
               VALUES ($1, $2, $3, $4::jsonb, $5, $6)
               ON CONFLICT (id) DO NOTHING""",
            c["id"], c["baby_id"], c["title"], msgs,
            parse_dt(c["created_at"]) or datetime.now(),
            parse_dt(c["updated_at"]) or datetime.now(),
        )
    print(f"✅ Migrated {len(convos)} conversations")

    # Reset sequences to max(id) + 1 so new inserts get correct IDs
    for table, col in [
        ("babies", "id"), ("feedings", "id"), ("weight_entries", "id"),
        ("diapers", "id"), ("analysis_reports", "id"), ("chat_conversations", "id"),
    ]:
        max_id = await pg.fetchval(f"SELECT COALESCE(MAX({col}), 0) FROM {table}")
        if max_id > 0:
            await pg.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), $1, true)", max_id)
    print("✅ Sequences reset")

    await pg.close()
    lite.close()
    print("\n🎉 Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
