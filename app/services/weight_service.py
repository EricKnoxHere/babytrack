"""Async CRUD operations for weight entries."""

from datetime import date, datetime

import asyncpg

from app.models.weight import Weight, WeightCreate, WeightUpdate


def _row_to_weight(row: asyncpg.Record) -> Weight:
    return Weight(
        id=row["id"],
        baby_id=row["baby_id"],
        measured_at=row["measured_at"],
        weight_g=row["weight_g"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


async def add_weight(db: asyncpg.Connection, weight: WeightCreate) -> Weight:
    """Record a weight measurement."""
    row = await db.fetchrow(
        """INSERT INTO weight_entries (baby_id, measured_at, weight_g, notes)
           VALUES ($1, $2, $3, $4) RETURNING *""",
        weight.baby_id,
        weight.measured_at,
        weight.weight_g,
        weight.notes,
    )
    return _row_to_weight(row)


async def get_weight(db: asyncpg.Connection, weight_id: int) -> Weight | None:
    """Return a weight entry by id, or None."""
    row = await db.fetchrow("SELECT * FROM weight_entries WHERE id = $1", weight_id)
    return _row_to_weight(row) if row else None


async def get_weights_by_baby(db: asyncpg.Connection, baby_id: int) -> list[Weight]:
    """Return all weight entries for a baby, chronologically ordered."""
    rows = await db.fetch(
        "SELECT * FROM weight_entries WHERE baby_id = $1 ORDER BY measured_at ASC",
        baby_id,
    )
    return [_row_to_weight(r) for r in rows]


async def get_weights_by_date_range(
    db: asyncpg.Connection, baby_id: int, start: date, end: date
) -> list[Weight]:
    """Return weight entries between start and end (inclusive)."""
    rows = await db.fetch(
        """SELECT * FROM weight_entries
           WHERE baby_id = $1
             AND measured_at::date >= $2
             AND measured_at::date <= $3
           ORDER BY measured_at ASC""",
        baby_id, start, end,
    )
    return [_row_to_weight(r) for r in rows]


async def update_weight(
    db: asyncpg.Connection, weight_id: int, update: WeightUpdate
) -> Weight | None:
    """Update a weight entry. Only non-None fields are updated."""
    weight = await get_weight(db, weight_id)
    if not weight:
        return None

    fields = []
    values = []
    idx = 1
    if update.measured_at is not None:
        fields.append(f"measured_at = ${idx}")
        values.append(update.measured_at)
        idx += 1
    if update.weight_g is not None:
        fields.append(f"weight_g = ${idx}")
        values.append(update.weight_g)
        idx += 1
    if update.notes is not None:
        fields.append(f"notes = ${idx}")
        values.append(update.notes)
        idx += 1

    if not fields:
        return weight

    values.append(weight_id)
    query = f"UPDATE weight_entries SET {', '.join(fields)} WHERE id = ${idx} RETURNING *"
    row = await db.fetchrow(query, *values)
    return _row_to_weight(row) if row else None


async def delete_weight(db: asyncpg.Connection, weight_id: int) -> bool:
    """Delete a weight entry. Returns True if deleted."""
    result = await db.execute("DELETE FROM weight_entries WHERE id = $1", weight_id)
    return result == "DELETE 1"
