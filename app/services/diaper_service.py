"""Async CRUD operations for diaper changes (pee / poop tracking)."""

from datetime import date, datetime

import aiosqlite

from app.models.diaper import Diaper, DiaperCreate, DiaperUpdate


def _row_to_diaper(row: aiosqlite.Row) -> Diaper:
    return Diaper(
        id=row["id"],
        baby_id=row["baby_id"],
        changed_at=datetime.fromisoformat(row["changed_at"]),
        has_pee=bool(row["has_pee"]),
        has_poop=bool(row["has_poop"]),
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def add_diaper(db: aiosqlite.Connection, diaper: DiaperCreate) -> Diaper:
    """Record a diaper change and return the full record."""
    cursor = await db.execute(
        """INSERT INTO diapers (baby_id, changed_at, has_pee, has_poop, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (
            diaper.baby_id,
            diaper.changed_at.isoformat(),
            int(diaper.has_pee),
            int(diaper.has_poop),
            diaper.notes,
        ),
    )
    await db.commit()
    rows = await db.execute_fetchall(
        "SELECT * FROM diapers WHERE id = ?", (cursor.lastrowid,)
    )
    return _row_to_diaper(rows[0])


async def get_diaper(db: aiosqlite.Connection, diaper_id: int) -> Diaper | None:
    """Return a diaper record by id, or None."""
    async with db.execute("SELECT * FROM diapers WHERE id = ?", (diaper_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_diaper(row) if row else None


async def get_diapers_by_baby(db: aiosqlite.Connection, baby_id: int) -> list[Diaper]:
    """Return all diaper changes for a baby, most recent first."""
    rows = await db.execute_fetchall(
        "SELECT * FROM diapers WHERE baby_id = ? ORDER BY changed_at DESC", (baby_id,)
    )
    return [_row_to_diaper(r) for r in rows]


async def get_diapers_by_range(
    db: aiosqlite.Connection, baby_id: int, start: date, end: date
) -> list[Diaper]:
    """Return diapers between start and end calendar dates (inclusive)."""
    rows = await db.execute_fetchall(
        """SELECT * FROM diapers
           WHERE baby_id = ?
             AND date(changed_at) >= ?
             AND date(changed_at) <= ?
           ORDER BY changed_at""",
        (baby_id, start.isoformat(), end.isoformat()),
    )
    return [_row_to_diaper(r) for r in rows]


async def get_diapers_by_datetime_range(
    db: aiosqlite.Connection, baby_id: int, start: datetime, end: datetime
) -> list[Diaper]:
    """Return diapers between two datetime bounds."""
    rows = await db.execute_fetchall(
        """SELECT * FROM diapers
           WHERE baby_id = ?
             AND changed_at >= ?
             AND changed_at <= ?
           ORDER BY changed_at""",
        (baby_id, start.isoformat(), end.isoformat()),
    )
    return [_row_to_diaper(r) for r in rows]


async def update_diaper(
    db: aiosqlite.Connection, diaper_id: int, update: DiaperUpdate
) -> Diaper | None:
    """Update a diaper record. Only non-None fields are updated."""
    diaper = await get_diaper(db, diaper_id)
    if not diaper:
        return None

    fields = []
    values = []
    if update.changed_at is not None:
        fields.append("changed_at = ?")
        values.append(update.changed_at.isoformat())
    if update.has_pee is not None:
        fields.append("has_pee = ?")
        values.append(int(update.has_pee))
    if update.has_poop is not None:
        fields.append("has_poop = ?")
        values.append(int(update.has_poop))
    if update.notes is not None:
        fields.append("notes = ?")
        values.append(update.notes)

    if not fields:
        return diaper

    values.append(diaper_id)
    query = f"UPDATE diapers SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, values)
    await db.commit()
    return await get_diaper(db, diaper_id)


async def delete_diaper(db: aiosqlite.Connection, diaper_id: int) -> bool:
    """Delete a diaper record. Returns True if deleted."""
    cursor = await db.execute("DELETE FROM diapers WHERE id = ?", (diaper_id,))
    await db.commit()
    return cursor.rowcount > 0
