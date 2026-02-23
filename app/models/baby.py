from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class BabyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    birth_date: date
    birth_weight_grams: int = Field(..., gt=0, description="Birth weight in grams")


class BabyCreate(BabyBase):
    """Payload to create a baby."""
    pass


class BabyUpdate(BaseModel):
    """Payload to update a baby — all fields are optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    birth_weight_grams: Optional[int] = Field(None, gt=0)


class Baby(BabyBase):
    """Full model returned from the database."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
