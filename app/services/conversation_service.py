"""Async CRUD for chat conversation persistence."""

import json
from datetime import datetime

import aiosqlite


async def save_conversation(
    db: aiosqlite.Connection,
    baby_id: int,
    title: str,
    messages: list[dict],
) -> dict:
    """Save or create a conversation. Returns the saved record."""
    messages_json = json.dumps(messages, ensure_ascii=False)
    cursor = await db.execute(
        """INSERT INTO chat_conversations (baby_id, title, messages_json)
           VALUES (?, ?, ?)""",
        (baby_id, title, messages_json),
    )
    await db.commit()
    return await get_conversation(db, cursor.lastrowid)


async def update_conversation(
    db: aiosqlite.Connection,
    conversation_id: int,
    title: str | None = None,
    messages: list[dict] | None = None,
) -> dict | None:
    """Update an existing conversation's title and/or messages."""
    fields = []
    values = []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if messages is not None:
        fields.append("messages_json = ?")
        values.append(json.dumps(messages, ensure_ascii=False))
    if not fields:
        return await get_conversation(db, conversation_id)

    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(conversation_id)

    query = f"UPDATE chat_conversations SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, values)
    await db.commit()
    return await get_conversation(db, conversation_id)


async def get_conversation(db: aiosqlite.Connection, conversation_id: int) -> dict | None:
    """Return a full conversation by id."""
    async with db.execute(
        "SELECT * FROM chat_conversations WHERE id = ?", (conversation_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


async def list_conversations(
    db: aiosqlite.Connection, baby_id: int, limit: int = 20
) -> list[dict]:
    """Return conversation summaries for a baby, most recent first."""
    rows = await db.execute_fetchall(
        """SELECT id, baby_id, title, created_at, updated_at
           FROM chat_conversations
           WHERE baby_id = ?
           ORDER BY updated_at DESC
           LIMIT ?""",
        (baby_id, limit),
    )
    return [
        {
            "id": r["id"],
            "baby_id": r["baby_id"],
            "title": r["title"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


async def delete_conversation(db: aiosqlite.Connection, conversation_id: int) -> bool:
    """Delete a conversation. Returns True if deleted."""
    cursor = await db.execute(
        "DELETE FROM chat_conversations WHERE id = ?", (conversation_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


def _row_to_dict(row: aiosqlite.Row) -> dict:
    return {
        "id": row["id"],
        "baby_id": row["baby_id"],
        "title": row["title"],
        "messages": json.loads(row["messages_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
