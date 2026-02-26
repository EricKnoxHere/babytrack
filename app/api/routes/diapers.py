"""Endpoints for diaper changes (pee / poop tracking)."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DbDep
from app.models.diaper import Diaper, DiaperCreate, DiaperUpdate
from app.services import baby_service, diaper_service

router = APIRouter(prefix="/diapers", tags=["diapers"])


@router.post("", response_model=Diaper, status_code=status.HTTP_201_CREATED)
async def add_diaper(payload: DiaperCreate, db: DbDep) -> Diaper:
    """Record a diaper change."""
    baby = await baby_service.get_baby(db, payload.baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {payload.baby_id} not found")
    return await diaper_service.add_diaper(db, payload)


@router.get("/{baby_id}", response_model=list[Diaper])
async def get_diapers(
    baby_id: int,
    db: DbDep,
    start: Optional[date] = Query(None, description="Range start (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="Range end (YYYY-MM-DD)"),
) -> list[Diaper]:
    """Return diaper changes for a baby, optionally filtered by date range."""
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")

    if start and end:
        if end < start:
            raise HTTPException(status_code=400, detail="'end' must be >= 'start'")
        return await diaper_service.get_diapers_by_range(db, baby_id, start, end)

    return await diaper_service.get_diapers_by_baby(db, baby_id)


@router.patch("/{diaper_id}", response_model=Diaper)
async def update_diaper(diaper_id: int, payload: DiaperUpdate, db: DbDep) -> Diaper:
    """Update a diaper record (all fields optional)."""
    diaper = await diaper_service.update_diaper(db, diaper_id, payload)
    if not diaper:
        raise HTTPException(status_code=404, detail=f"Diaper {diaper_id} not found")
    return diaper


@router.delete("/{diaper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diaper(diaper_id: int, db: DbDep) -> None:
    """Delete a diaper record."""
    deleted = await diaper_service.delete_diaper(db, diaper_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Diaper {diaper_id} not found")
