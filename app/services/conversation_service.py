"""Async CRUD for chat conversation persistence."""

import json
from datetime import datetime

import asyncpg


async def save_conversation(
    db: asyncpg.Connection,
    baby_id: int,
    title: str,
    messages: list[dict],
) -> dict:
    """Save or create a conversation. Returns the saved record."""
    row = await db.fetchrow(
        """INSERT INTO chat_conversations (baby_id, title, messages_json)
           VALUES ($1, $2, $3::jsonb) RETURNING *""",
        baby_id, title, json.dumps(messages, ensure_ascii=False),
    )
    return _row_to_dict(row)


async def update_conversation(
    db: asyncpg.Connection,
    conversation_id: int,
    title: str | None = None,
    messages: list[dict] | None = None,
) -> dict | None:
    """Update an existing conversation's title and/or messages."""
    fields = []
    values = []
    idx = 1
    if title is not None:
        fields.append(f"title = ${idx}")
        values.append(title)
        idx += 1
    if messages is not None:
        fields.append(f"messages_json = ${idx}::jsonb")
        values.append(json.dumps(messages, ensure_ascii=False))
        idx += 1
    if not fields:
        return await get_conversation(db, conversation_id)

    fields.append(f"updated_at = ${idx}")
    values.append(datetime.now())
    idx += 1
    values.append(conversation_id)

    query = f"UPDATE chat_conversations SET {', '.join(fields)} WHERE id = ${idx} RETURNING *"
    row = await db.fetchrow(query, *values)
    return _row_to_dict(row) if row else None


async def get_conversation(db: asyncpg.Connection, conversation_id: int) -> dict | None:
    """Return a full conversation by id."""
    row = await db.fetchrow(
        "SELECT * FROM chat_conversations WHERE id = $1", conversation_id
    )
    if not row:
        return None
    return _row_to_dict(row)


async def list_conversations(
    db: asyncpg.Connection, baby_id: int, limit: int = 20
) -> list[dict]:
    """Return conversation summaries for a baby, most recent first."""
    rows = await db.fetch(
        """SELECT id, baby_id, title, created_at, updated_at
           FROM chat_conversations
           WHERE baby_id = $1
           ORDER BY updated_at DESC
           LIMIT $2""",
        baby_id, limit,
    )
    return [
        {
            "id": r["id"],
            "baby_id": r["baby_id"],
            "title": r["title"],
            "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else r["created_at"],
            "updated_at": r["updated_at"].isoformat() if isinstance(r["updated_at"], datetime) else r["updated_at"],
        }
        for r in rows
    ]


async def delete_conversation(db: asyncpg.Connection, conversation_id: int) -> bool:
    """Delete a conversation. Returns True if deleted."""
    result = await db.execute(
        "DELETE FROM chat_conversations WHERE id = $1", conversation_id
    )
    return result == "DELETE 1"


def _row_to_dict(row: asyncpg.Record) -> dict:
    messages = row["messages_json"]
    # asyncpg may return JSONB as already-parsed Python object or as string
    if isinstance(messages, str):
        messages = json.loads(messages)
    return {
        "id": row["id"],
        "baby_id": row["baby_id"],
        "title": row["title"],
        "messages": messages,
        "created_at": row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else row["created_at"],
        "updated_at": row["updated_at"].isoformat() if isinstance(row["updated_at"], datetime) else row["updated_at"],
    }
