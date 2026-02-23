"""Endpoints pour les biberons / allaitements."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DbDep
from app.models.feeding import Feeding, FeedingCreate
from app.services import baby_service, feeding_service

router = APIRouter(prefix="/feedings", tags=["feedings"])


@router.post("", response_model=Feeding, status_code=status.HTTP_201_CREATED)
async def add_feeding(payload: FeedingCreate, db: DbDep) -> Feeding:
    """Enregistre un biberon ou un allaitement."""
    # Vérifier que le bébé existe
    baby = await baby_service.get_baby(db, payload.baby_id)
    if not baby:
        raise HTTPException(
            status_code=404,
            detail=f"Bébé {payload.baby_id} introuvable",
        )
    return await feeding_service.add_feeding(db, payload)


@router.get("/{baby_id}", response_model=list[Feeding])
async def get_feedings(
    baby_id: int,
    db: DbDep,
    day: Optional[date] = Query(None, description="Filtrer par jour (YYYY-MM-DD)"),
    start: Optional[date] = Query(None, description="Début de plage (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="Fin de plage (YYYY-MM-DD)"),
) -> list[Feeding]:
    """
    Retourne les biberons d'un bébé.

    - Sans paramètre : tout l'historique
    - `?day=YYYY-MM-DD` : une journée précise
    - `?start=YYYY-MM-DD&end=YYYY-MM-DD` : une plage de dates
    """
    # Vérifier que le bébé existe
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Bébé {baby_id} introuvable")

    if day:
        return await feeding_service.get_feedings_by_day(db, baby_id, day)
    if start and end:
        if end < start:
            raise HTTPException(status_code=400, detail="'end' doit être >= 'start'")
        return await feeding_service.get_feedings_by_range(db, baby_id, start, end)

    return await feeding_service.get_feedings_by_baby(db, baby_id)


@router.delete("/{feeding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feeding(feeding_id: int, db: DbDep) -> None:
    """Supprime un biberon."""
    deleted = await feeding_service.delete_feeding(db, feeding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Biberon {feeding_id} introuvable")
