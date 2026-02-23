"""CRUD async pour les bébés."""

from datetime import datetime

import aiosqlite

from app.models.baby import Baby, BabyCreate, BabyUpdate


def _row_to_baby(row: aiosqlite.Row) -> Baby:
    return Baby(
        id=row["id"],
        name=row["name"],
        birth_date=row["birth_date"],
        birth_weight_grams=row["birth_weight_grams"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def create_baby(db: aiosqlite.Connection, baby: BabyCreate) -> Baby:
    """Insère un nouveau bébé et retourne l'enregistrement complet."""
    cursor = await db.execute(
        "INSERT INTO babies (name, birth_date, birth_weight_grams) VALUES (?, ?, ?)",
        (baby.name, baby.birth_date.isoformat(), baby.birth_weight_grams),
    )
    await db.commit()
    row = await db.execute_fetchall(
        "SELECT * FROM babies WHERE id = ?", (cursor.lastrowid,)
    )
    return _row_to_baby(row[0])


async def get_baby(db: aiosqlite.Connection, baby_id: int) -> Baby | None:
    """Retourne un bébé par son id, ou None s'il n'existe pas."""
    async with db.execute("SELECT * FROM babies WHERE id = ?", (baby_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_baby(row) if row else None


async def get_all_babies(db: aiosqlite.Connection) -> list[Baby]:
    """Retourne tous les bébés enregistrés."""
    rows = await db.execute_fetchall("SELECT * FROM babies ORDER BY created_at")
    return [_row_to_baby(r) for r in rows]


async def update_baby(db: aiosqlite.Connection, baby_id: int, data: BabyUpdate) -> Baby | None:
    """Met à jour les champs fournis et retourne le bébé mis à jour, ou None."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        return await get_baby(db, baby_id)

    # Sérialise les dates
    if "birth_date" in updates:
        updates["birth_date"] = updates["birth_date"].isoformat()

    cols = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [baby_id]
    await db.execute(f"UPDATE babies SET {cols} WHERE id = ?", values)
    await db.commit()
    return await get_baby(db, baby_id)


async def delete_baby(db: aiosqlite.Connection, baby_id: int) -> bool:
    """Supprime un bébé (et ses biberons en cascade). Retourne True si supprimé."""
    cursor = await db.execute("DELETE FROM babies WHERE id = ?", (baby_id,))
    await db.commit()
    return cursor.rowcount > 0
