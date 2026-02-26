"""Unit tests for conversation_service."""

from datetime import datetime

import pytest

from app.models.baby import BabyCreate
from app.services.baby_service import create_baby
from app.services.conversation_service import (
    delete_conversation,
    get_conversation,
    list_conversations,
    save_conversation,
    update_conversation,
)

pytestmark = pytest.mark.asyncio


async def _make_baby(db):
    return await create_baby(
        db, BabyCreate(name="Louise", birth_date="2026-02-16", birth_weight_grams=3200)
    )


async def test_save_conversation(db):
    baby = await _make_baby(db)
    messages = [
        {"role": "user", "content": "How is Louise?"},
        {"role": "assistant", "content": "She's doing great!"},
    ]
    conv = await save_conversation(db, baby.id, "Morning chat", messages)
    assert conv is not None
    assert conv["id"] is not None
    assert conv["title"] == "Morning chat"
    assert len(conv["messages"]) == 2
    assert conv["baby_id"] == baby.id


async def test_get_conversation(db):
    baby = await _make_baby(db)
    saved = await save_conversation(db, baby.id, "Test", [{"role": "user", "content": "hi"}])
    fetched = await get_conversation(db, saved["id"])
    assert fetched is not None
    assert fetched["id"] == saved["id"]
    assert fetched["messages"] == saved["messages"]


async def test_get_conversation_not_found(db):
    assert await get_conversation(db, 9999) is None


async def test_list_conversations(db):
    baby = await _make_baby(db)
    await save_conversation(db, baby.id, "Chat 1", [])
    await save_conversation(db, baby.id, "Chat 2", [])
    await save_conversation(db, baby.id, "Chat 3", [])

    convs = await list_conversations(db, baby.id)
    assert len(convs) == 3
    titles = {c["title"] for c in convs}
    assert titles == {"Chat 1", "Chat 2", "Chat 3"}


async def test_list_conversations_limit(db):
    baby = await _make_baby(db)
    for i in range(5):
        await save_conversation(db, baby.id, f"Chat {i}", [])

    convs = await list_conversations(db, baby.id, limit=2)
    assert len(convs) == 2


async def test_list_conversations_empty(db):
    baby = await _make_baby(db)
    assert await list_conversations(db, baby.id) == []


async def test_update_conversation_title(db):
    baby = await _make_baby(db)
    conv = await save_conversation(db, baby.id, "Original", [])
    updated = await update_conversation(db, conv["id"], title="Renamed")
    assert updated is not None
    assert updated["title"] == "Renamed"


async def test_update_conversation_messages(db):
    baby = await _make_baby(db)
    conv = await save_conversation(db, baby.id, "Test", [])
    new_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]
    updated = await update_conversation(db, conv["id"], messages=new_messages)
    assert updated is not None
    assert len(updated["messages"]) == 2


async def test_update_conversation_no_fields(db):
    """Update with no fields = returns unchanged record."""
    baby = await _make_baby(db)
    conv = await save_conversation(db, baby.id, "Test", [])
    updated = await update_conversation(db, conv["id"])
    assert updated is not None
    assert updated["title"] == "Test"


async def test_update_conversation_not_found(db):
    result = await update_conversation(db, 9999, title="nope")
    assert result is None


async def test_delete_conversation(db):
    baby = await _make_baby(db)
    conv = await save_conversation(db, baby.id, "To delete", [])
    assert await delete_conversation(db, conv["id"]) is True
    assert await get_conversation(db, conv["id"]) is None


async def test_delete_conversation_not_found(db):
    assert await delete_conversation(db, 9999) is False


async def test_cascade_delete_baby(db):
    """Deleting a baby cascades to delete its conversations."""
    from app.services.baby_service import delete_baby

    baby = await _make_baby(db)
    await save_conversation(db, baby.id, "Chat 1", [])
    await save_conversation(db, baby.id, "Chat 2", [])

    await delete_baby(db, baby.id)
    assert await list_conversations(db, baby.id) == []
