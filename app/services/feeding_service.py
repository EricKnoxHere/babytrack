"""Async CRUD operations for feedings / breastfeeding sessions."""

from datetime import date, datetime

import aiosqlite

from app.models.feeding import Feeding, FeedingCreate, FeedingUpdate


def _row_to_feeding(row: aiosqlite.Row) -> Feeding:
    return Feeding(
        id=row["id"],
        baby_id=row["baby_id"],
        fed_at=datetime.fromisoformat(row["fed_at"]),
        quantity_ml=row["quantity_ml"],
        feeding_type=row["feeding_type"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def add_feeding(db: aiosqlite.Connection, feeding: FeedingCreate) -> Feeding:
    """Record a feeding session and return the full record."""
    cursor = await db.execute(
        """INSERT INTO feedings (baby_id, fed_at, quantity_ml, feeding_type, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (
            feeding.baby_id,
            feeding.fed_at.isoformat(),
            feeding.quantity_ml,
            feeding.feeding_type,
            feeding.notes,
        ),
    )
    await db.commit()
    rows = await db.execute_fetchall(
        "SELECT * FROM feedings WHERE id = ?", (cursor.lastrowid,)
    )
    return _row_to_feeding(rows[0])


async def get_feeding(db: aiosqlite.Connection, feeding_id: int) -> Feeding | None:
    """Return a feeding by id, or None."""
    async with db.execute("SELECT * FROM feedings WHERE id = ?", (feeding_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_feeding(row) if row else None


async def get_feedings_by_baby(db: aiosqlite.Connection, baby_id: int) -> list[Feeding]:
    """Return all feedings for a baby, most recent first."""
    rows = await db.execute_fetchall(
        "SELECT * FROM feedings WHERE baby_id = ? ORDER BY fed_at DESC", (baby_id,)
    )
    return [_row_to_feeding(r) for r in rows]


async def get_feedings_by_day(
    db: aiosqlite.Connection, baby_id: int, day: date
) -> list[Feeding]:
    """Return feedings for a baby on a given day (local date)."""
    day_str = day.isoformat()  # 'YYYY-MM-DD'
    rows = await db.execute_fetchall(
        """SELECT * FROM feedings
           WHERE baby_id = ?
             AND date(fed_at) = ?
           ORDER BY fed_at""",
        (baby_id, day_str),
    )
    return [_row_to_feeding(r) for r in rows]


async def get_feedings_by_range(
    db: aiosqlite.Connection, baby_id: int, start: date, end: date
) -> list[Feeding]:
    """Return feedings between start (inclusive) and end (inclusive)."""
    rows = await db.execute_fetchall(
        """SELECT * FROM feedings
           WHERE baby_id = ?
             AND date(fed_at) >= ?
             AND date(fed_at) <= ?
           ORDER BY fed_at""",
        (baby_id, start.isoformat(), end.isoformat()),
    )
    return [_row_to_feeding(r) for r in rows]


async def delete_feeding(db: aiosqlite.Connection, feeding_id: int) -> bool:
    """Delete a feeding. Returns True if deleted."""
    cursor = await db.execute("DELETE FROM feedings WHERE id = ?", (feeding_id,))
    await db.commit()
    return cursor.rowcount > 0
