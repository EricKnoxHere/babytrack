from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WeightBase(BaseModel):
    baby_id: int
    measured_at: datetime
    weight_g: int = Field(..., gt=0, description="Weight in grams")
    notes: Optional[str] = Field(None, max_length=500)


class WeightCreate(WeightBase):
    """Payload to record a weight measurement."""
    pass


class WeightUpdate(BaseModel):
    """Payload to update a weight record — all fields optional."""
    measured_at: Optional[datetime] = None
    weight_g: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = Field(None, max_length=500)


class Weight(WeightBase):
    """Full weight record returned from the database."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
