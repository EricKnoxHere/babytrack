"""CRUD async pour les biberons / allaitements."""

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
    """Enregistre un biberon / allaitement et retourne l'enregistrement complet."""
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
    """Retourne un biberon par son id, ou None."""
    async with db.execute("SELECT * FROM feedings WHERE id = ?", (feeding_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_feeding(row) if row else None


async def get_feedings_by_baby(db: aiosqlite.Connection, baby_id: int) -> list[Feeding]:
    """Retourne tous les biberons d'un bébé, du plus récent au plus ancien."""
    rows = await db.execute_fetchall(
        "SELECT * FROM feedings WHERE baby_id = ? ORDER BY fed_at DESC", (baby_id,)
    )
    return [_row_to_feeding(r) for r in rows]


async def get_feedings_by_day(
    db: aiosqlite.Connection, baby_id: int, day: date
) -> list[Feeding]:
    """Retourne les biberons d'un bébé pour un jour donné (date locale)."""
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
    """Retourne les biberons entre start (inclus) et end (inclus)."""
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
    """Supprime un biberon. Retourne True si supprimé."""
    cursor = await db.execute("DELETE FROM feedings WHERE id = ?", (feeding_id,))
    await db.commit()
    return cursor.rowcount > 0
