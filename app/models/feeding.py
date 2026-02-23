from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


FeedingType = Literal["bottle", "breastfeeding"]


class FeedingBase(BaseModel):
    baby_id: int
    fed_at: datetime
    quantity_ml: int = Field(..., gt=0, description="Quantité en millilitres")
    feeding_type: FeedingType
    notes: Optional[str] = Field(None, max_length=500)


class FeedingCreate(FeedingBase):
    """Payload pour enregistrer un biberon / allaitement."""
    pass


class FeedingUpdate(BaseModel):
    """Payload pour mettre à jour une prise — tous les champs sont optionnels."""
    fed_at: Optional[datetime] = None
    quantity_ml: Optional[int] = Field(None, gt=0)
    feeding_type: Optional[FeedingType] = None
    notes: Optional[str] = Field(None, max_length=500)


class Feeding(FeedingBase):
    """Modèle complet retourné par la base de données."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
