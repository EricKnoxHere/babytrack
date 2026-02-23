"""Endpoints CRUD pour les bébés."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DbDep
from app.models.baby import Baby, BabyCreate, BabyUpdate
from app.services import baby_service

router = APIRouter(prefix="/babies", tags=["babies"])


@router.post("", response_model=Baby, status_code=status.HTTP_201_CREATED)
async def create_baby(payload: BabyCreate, db: DbDep) -> Baby:
    """Crée un nouveau bébé."""
    return await baby_service.create_baby(db, payload)


@router.get("", response_model=list[Baby])
async def list_babies(db: DbDep) -> list[Baby]:
    """Retourne tous les bébés enregistrés."""
    return await baby_service.get_all_babies(db)


@router.get("/{baby_id}", response_model=Baby)
async def get_baby(baby_id: int, db: DbDep) -> Baby:
    """Retourne un bébé par son identifiant."""
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Bébé {baby_id} introuvable")
    return baby


@router.patch("/{baby_id}", response_model=Baby)
async def update_baby(baby_id: int, payload: BabyUpdate, db: DbDep) -> Baby:
    """Met à jour les informations d'un bébé (champs partiels)."""
    baby = await baby_service.update_baby(db, baby_id, payload)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Bébé {baby_id} introuvable")
    return baby


@router.delete("/{baby_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_baby(baby_id: int, db: DbDep) -> None:
    """Supprime un bébé et tous ses biberons (cascade)."""
    deleted = await baby_service.delete_baby(db, baby_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Bébé {baby_id} introuvable")
