"""Async CRUD operations for weight entries."""

from datetime import date, datetime

import aiosqlite

from app.models.weight import Weight, WeightCreate, WeightUpdate


def _row_to_weight(row: aiosqlite.Row) -> Weight:
    return Weight(
        id=row["id"],
        baby_id=row["baby_id"],
        measured_at=datetime.fromisoformat(row["measured_at"]),
        weight_g=row["weight_g"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def add_weight(db: aiosqlite.Connection, weight: WeightCreate) -> Weight:
    """Record a weight measurement."""
    cursor = await db.execute(
        """INSERT INTO weight_entries (baby_id, measured_at, weight_g, notes)
           VALUES (?, ?, ?, ?)""",
        (
            weight.baby_id,
            weight.measured_at.isoformat(),
            weight.weight_g,
            weight.notes,
        ),
    )
    await db.commit()
    rows = await db.execute_fetchall(
        "SELECT * FROM weight_entries WHERE id = ?", (cursor.lastrowid,)
    )
    return _row_to_weight(rows[0])


async def get_weight(db: aiosqlite.Connection, weight_id: int) -> Weight | None:
    """Return a weight entry by id, or None."""
    async with db.execute("SELECT * FROM weight_entries WHERE id = ?", (weight_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_weight(row) if row else None


async def get_weights_by_baby(db: aiosqlite.Connection, baby_id: int) -> list[Weight]:
    """Return all weight entries for a baby, chronologically ordered."""
    rows = await db.execute_fetchall(
        "SELECT * FROM weight_entries WHERE baby_id = ? ORDER BY measured_at ASC",
        (baby_id,),
    )
    return [_row_to_weight(r) for r in rows]


async def get_weights_by_date_range(
    db: aiosqlite.Connection, baby_id: int, start: date, end: date
) -> list[Weight]:
    """Return weight entries between start and end (inclusive)."""
    rows = await db.execute_fetchall(
        """SELECT * FROM weight_entries
           WHERE baby_id = ?
             AND date(measured_at) >= ?
             AND date(measured_at) <= ?
           ORDER BY measured_at ASC""",
        (baby_id, start.isoformat(), end.isoformat()),
    )
    return [_row_to_weight(r) for r in rows]


async def update_weight(
    db: aiosqlite.Connection, weight_id: int, update: WeightUpdate
) -> Weight | None:
    """Update a weight entry. Only non-None fields are updated."""
    weight = await get_weight(db, weight_id)
    if not weight:
        return None

    fields = []
    values = []
    if update.measured_at is not None:
        fields.append("measured_at = ?")
        values.append(update.measured_at.isoformat())
    if update.weight_g is not None:
        fields.append("weight_g = ?")
        values.append(update.weight_g)
    if update.notes is not None:
        fields.append("notes = ?")
        values.append(update.notes)

    if not fields:
        return weight

    values.append(weight_id)
    query = f"UPDATE weight_entries SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, values)
    await db.commit()

    return await get_weight(db, weight_id)


async def delete_weight(db: aiosqlite.Connection, weight_id: int) -> bool:
    """Delete a weight entry. Returns True if deleted."""
    cursor = await db.execute("DELETE FROM weight_entries WHERE id = ?", (weight_id,))
    await db.commit()
    return cursor.rowcount > 0
