"""Async CRUD operations for babies."""

from datetime import datetime

import asyncpg

from app.models.baby import Baby, BabyCreate, BabyUpdate


def _row_to_baby(row: asyncpg.Record) -> Baby:
    return Baby(
        id=row["id"],
        name=row["name"],
        birth_date=row["birth_date"],
        birth_weight_grams=row["birth_weight_grams"],
        created_at=row["created_at"],
    )


async def create_baby(db: asyncpg.Connection, baby: BabyCreate) -> Baby:
    """Insert a new baby and return the full record."""
    row = await db.fetchrow(
        "INSERT INTO babies (name, birth_date, birth_weight_grams) VALUES ($1, $2, $3) RETURNING *",
        baby.name, baby.birth_date.isoformat(), baby.birth_weight_grams,
    )
    return _row_to_baby(row)


async def get_baby(db: asyncpg.Connection, baby_id: int) -> Baby | None:
    """Return a baby by id, or None if not found."""
    row = await db.fetchrow("SELECT * FROM babies WHERE id = $1", baby_id)
    return _row_to_baby(row) if row else None


async def get_all_babies(db: asyncpg.Connection) -> list[Baby]:
    """Return all registered babies."""
    rows = await db.fetch("SELECT * FROM babies ORDER BY created_at")
    return [_row_to_baby(r) for r in rows]


async def update_baby(db: asyncpg.Connection, baby_id: int, data: BabyUpdate) -> Baby | None:
    """Update provided fields and return the updated baby, or None."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        return await get_baby(db, baby_id)

    # Serialize dates
    if "birth_date" in updates:
        updates["birth_date"] = updates["birth_date"].isoformat()

    set_clauses = []
    values = []
    for i, (k, v) in enumerate(updates.items(), 1):
        set_clauses.append(f"{k} = ${i}")
        values.append(v)
    values.append(baby_id)
    query = f"UPDATE babies SET {', '.join(set_clauses)} WHERE id = ${len(values)} RETURNING *"
    row = await db.fetchrow(query, *values)
    return _row_to_baby(row) if row else None


async def delete_baby(db: asyncpg.Connection, baby_id: int) -> bool:
    """Delete a baby (and its feedings via cascade). Returns True if deleted."""
    result = await db.execute("DELETE FROM babies WHERE id = $1", baby_id)
    return result == "DELETE 1"
