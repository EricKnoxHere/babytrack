"""Pydantic models for diaper (pee / poop) tracking."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DiaperBase(BaseModel):
    baby_id: int
    changed_at: datetime
    has_pee: bool = True
    has_poop: bool = False
    notes: Optional[str] = Field(None, max_length=500)


class DiaperCreate(DiaperBase):
    """Payload to record a diaper change."""
    pass


class DiaperUpdate(BaseModel):
    """Payload to update a diaper record — all fields optional."""
    changed_at: Optional[datetime] = None
    has_pee: Optional[bool] = None
    has_poop: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)


class Diaper(DiaperBase):
    """Full model returned from the database."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
