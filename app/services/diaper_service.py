"""Async CRUD operations for diaper changes (pee / poop tracking)."""

from datetime import date, datetime

import asyncpg

from app.models.diaper import Diaper, DiaperCreate, DiaperUpdate


def _row_to_diaper(row: asyncpg.Record) -> Diaper:
    return Diaper(
        id=row["id"],
        baby_id=row["baby_id"],
        changed_at=row["changed_at"],
        has_pee=row["has_pee"],
        has_poop=row["has_poop"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


async def add_diaper(db: asyncpg.Connection, diaper: DiaperCreate) -> Diaper:
    """Record a diaper change and return the full record."""
    row = await db.fetchrow(
        """INSERT INTO diapers (baby_id, changed_at, has_pee, has_poop, notes)
           VALUES ($1, $2, $3, $4, $5) RETURNING *""",
        diaper.baby_id,
        diaper.changed_at,
        diaper.has_pee,
        diaper.has_poop,
        diaper.notes,
    )
    return _row_to_diaper(row)


async def get_diaper(db: asyncpg.Connection, diaper_id: int) -> Diaper | None:
    """Return a diaper record by id, or None."""
    row = await db.fetchrow("SELECT * FROM diapers WHERE id = $1", diaper_id)
    return _row_to_diaper(row) if row else None


async def get_diapers_by_baby(db: asyncpg.Connection, baby_id: int) -> list[Diaper]:
    """Return all diaper changes for a baby, most recent first."""
    rows = await db.fetch(
        "SELECT * FROM diapers WHERE baby_id = $1 ORDER BY changed_at DESC", baby_id
    )
    return [_row_to_diaper(r) for r in rows]


async def get_diapers_by_range(
    db: asyncpg.Connection, baby_id: int, start: date, end: date
) -> list[Diaper]:
    """Return diapers between start and end calendar dates (inclusive)."""
    rows = await db.fetch(
        """SELECT * FROM diapers
           WHERE baby_id = $1
             AND changed_at::date >= $2
             AND changed_at::date <= $3
           ORDER BY changed_at""",
        baby_id, start, end,
    )
    return [_row_to_diaper(r) for r in rows]


async def get_diapers_by_datetime_range(
    db: asyncpg.Connection, baby_id: int, start: datetime, end: datetime
) -> list[Diaper]:
    """Return diapers between two datetime bounds."""
    rows = await db.fetch(
        """SELECT * FROM diapers
           WHERE baby_id = $1
             AND changed_at >= $2
             AND changed_at <= $3
           ORDER BY changed_at""",
        baby_id, start, end,
    )
    return [_row_to_diaper(r) for r in rows]


async def update_diaper(
    db: asyncpg.Connection, diaper_id: int, update: DiaperUpdate
) -> Diaper | None:
    """Update a diaper record. Only non-None fields are updated."""
    diaper = await get_diaper(db, diaper_id)
    if not diaper:
        return None

    fields = []
    values = []
    idx = 1
    if update.changed_at is not None:
        fields.append(f"changed_at = ${idx}")
        values.append(update.changed_at)
        idx += 1
    if update.has_pee is not None:
        fields.append(f"has_pee = ${idx}")
        values.append(update.has_pee)
        idx += 1
    if update.has_poop is not None:
        fields.append(f"has_poop = ${idx}")
        values.append(update.has_poop)
        idx += 1
    if update.notes is not None:
        fields.append(f"notes = ${idx}")
        values.append(update.notes)
        idx += 1

    if not fields:
        return diaper

    values.append(diaper_id)
    query = f"UPDATE diapers SET {', '.join(fields)} WHERE id = ${idx} RETURNING *"
    row = await db.fetchrow(query, *values)
    return _row_to_diaper(row) if row else None


async def delete_diaper(db: asyncpg.Connection, diaper_id: int) -> bool:
    """Delete a diaper record. Returns True if deleted."""
    result = await db.execute("DELETE FROM diapers WHERE id = $1", diaper_id)
    return result == "DELETE 1"
