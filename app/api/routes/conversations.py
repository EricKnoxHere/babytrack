"""Endpoints for chat conversation persistence."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import DbDep
from app.services import baby_service, conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    baby_id: int
    title: str
    messages: list[dict]


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[list[dict]] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, db: DbDep) -> dict:
    """Save a new conversation."""
    baby = await baby_service.get_baby(db, payload.baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {payload.baby_id} not found")
    return await conversation_service.save_conversation(
        db, payload.baby_id, payload.title, payload.messages
    )


@router.get("/{baby_id}")
async def list_conversations(
    baby_id: int,
    db: DbDep,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """List conversation summaries for a baby."""
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")
    return await conversation_service.list_conversations(db, baby_id, limit)


@router.get("/detail/{conversation_id}")
async def get_conversation(conversation_id: int, db: DbDep) -> dict:
    """Get full conversation with messages."""
    conv = await conversation_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/detail/{conversation_id}")
async def update_conversation(
    conversation_id: int, payload: ConversationUpdate, db: DbDep
) -> dict:
    """Update a conversation's title or messages."""
    conv = await conversation_service.update_conversation(
        db, conversation_id, payload.title, payload.messages
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/detail/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: int, db: DbDep) -> None:
    """Delete a conversation."""
    deleted = await conversation_service.delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
