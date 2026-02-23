from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


FeedingType = Literal["bottle", "breastfeeding"]


class FeedingBase(BaseModel):
    baby_id: int
    fed_at: datetime
    quantity_ml: int = Field(..., gt=0, description="Quantity in milliliters")
    feeding_type: FeedingType
    notes: Optional[str] = Field(None, max_length=500)


class FeedingCreate(FeedingBase):
    """Payload to record a bottle feeding or breastfeeding session."""
    pass


class FeedingUpdate(BaseModel):
    """Payload to update a feeding record — all fields are optional."""
    fed_at: Optional[datetime] = None
    quantity_ml: Optional[int] = Field(None, gt=0)
    feeding_type: Optional[FeedingType] = None
    notes: Optional[str] = Field(None, max_length=500)


class Feeding(FeedingBase):
    """Full model returned from the database."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
