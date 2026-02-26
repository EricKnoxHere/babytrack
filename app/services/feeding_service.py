"""Async CRUD operations for feedings / breastfeeding sessions."""

from datetime import date, datetime

import asyncpg

from app.models.feeding import Feeding, FeedingCreate, FeedingUpdate


def _row_to_feeding(row: asyncpg.Record) -> Feeding:
    return Feeding(
        id=row["id"],
        baby_id=row["baby_id"],
        fed_at=row["fed_at"],
        quantity_ml=row["quantity_ml"],
        feeding_type=row["feeding_type"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


async def add_feeding(db: asyncpg.Connection, feeding: FeedingCreate) -> Feeding:
    """Record a feeding session and return the full record."""
    row = await db.fetchrow(
        """INSERT INTO feedings (baby_id, fed_at, quantity_ml, feeding_type, notes)
           VALUES ($1, $2, $3, $4, $5) RETURNING *""",
        feeding.baby_id,
        feeding.fed_at,
        feeding.quantity_ml,
        feeding.feeding_type,
        feeding.notes,
    )
    return _row_to_feeding(row)


async def get_feeding(db: asyncpg.Connection, feeding_id: int) -> Feeding | None:
    """Return a feeding by id, or None."""
    row = await db.fetchrow("SELECT * FROM feedings WHERE id = $1", feeding_id)
    return _row_to_feeding(row) if row else None


async def get_feedings_by_baby(db: asyncpg.Connection, baby_id: int) -> list[Feeding]:
    """Return all feedings for a baby, most recent first."""
    rows = await db.fetch(
        "SELECT * FROM feedings WHERE baby_id = $1 ORDER BY fed_at DESC", baby_id
    )
    return [_row_to_feeding(r) for r in rows]


async def get_feedings_by_day(
    db: asyncpg.Connection, baby_id: int, day: date
) -> list[Feeding]:
    """Return feedings for a baby on a given day (local date)."""
    rows = await db.fetch(
        """SELECT * FROM feedings
           WHERE baby_id = $1
             AND fed_at::date = $2
           ORDER BY fed_at""",
        baby_id, day,
    )
    return [_row_to_feeding(r) for r in rows]


async def get_feedings_by_range(
    db: asyncpg.Connection, baby_id: int, start: date, end: date
) -> list[Feeding]:
    """Return feedings between start (inclusive) and end (inclusive) calendar dates."""
    rows = await db.fetch(
        """SELECT * FROM feedings
           WHERE baby_id = $1
             AND fed_at::date >= $2
             AND fed_at::date <= $3
           ORDER BY fed_at""",
        baby_id, start, end,
    )
    return [_row_to_feeding(r) for r in rows]


async def get_feedings_by_datetime_range(
    db: asyncpg.Connection, baby_id: int, start: datetime, end: datetime
) -> list[Feeding]:
    """Return feedings strictly between two datetime bounds (microsecond precision)."""
    rows = await db.fetch(
        """SELECT * FROM feedings
           WHERE baby_id = $1
             AND fed_at >= $2
             AND fed_at <= $3
           ORDER BY fed_at""",
        baby_id, start, end,
    )
    return [_row_to_feeding(r) for r in rows]


async def update_feeding(
    db: asyncpg.Connection, feeding_id: int, update: FeedingUpdate
) -> Feeding | None:
    """Update a feeding record. Only non-None fields are updated."""
    feeding = await get_feeding(db, feeding_id)
    if not feeding:
        return None

    fields = []
    values = []
    idx = 1
    if update.fed_at is not None:
        fields.append(f"fed_at = ${idx}")
        values.append(update.fed_at)
        idx += 1
    if update.quantity_ml is not None:
        fields.append(f"quantity_ml = ${idx}")
        values.append(update.quantity_ml)
        idx += 1
    if update.feeding_type is not None:
        fields.append(f"feeding_type = ${idx}")
        values.append(update.feeding_type)
        idx += 1
    if update.notes is not None:
        fields.append(f"notes = ${idx}")
        values.append(update.notes)
        idx += 1

    if not fields:
        return feeding

    values.append(feeding_id)
    query = f"UPDATE feedings SET {', '.join(fields)} WHERE id = ${idx} RETURNING *"
    row = await db.fetchrow(query, *values)
    return _row_to_feeding(row) if row else None


async def delete_feeding(db: asyncpg.Connection, feeding_id: int) -> bool:
    """Delete a feeding. Returns True if deleted."""
    result = await db.execute("DELETE FROM feedings WHERE id = $1", feeding_id)
    return result == "DELETE 1"
