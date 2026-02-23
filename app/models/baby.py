from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class BabyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    birth_date: date
    birth_weight_grams: int = Field(..., gt=0, description="Poids de naissance en grammes")


class BabyCreate(BabyBase):
    """Payload pour créer un bébé."""
    pass


class BabyUpdate(BaseModel):
    """Payload pour mettre à jour un bébé — tous les champs sont optionnels."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    birth_weight_grams: Optional[int] = Field(None, gt=0)


class Baby(BabyBase):
    """Modèle complet retourné par la base de données."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
