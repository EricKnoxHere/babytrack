"""Endpoints for weight tracking."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DbDep
from app.models.weight import Weight, WeightCreate, WeightUpdate
from app.services import baby_service, weight_service

router = APIRouter(prefix="/weights", tags=["weights"])


@router.post("", response_model=Weight, status_code=status.HTTP_201_CREATED)
async def add_weight(payload: WeightCreate, db: DbDep) -> Weight:
    """Record a weight measurement."""
    # Verify the baby exists
    baby = await baby_service.get_baby(db, payload.baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {payload.baby_id} not found")
    return await weight_service.add_weight(db, payload)


@router.get("/{baby_id}", response_model=list[Weight])
async def get_weights(
    baby_id: int,
    db: DbDep,
    start: Optional[date] = Query(None, description="Range start (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="Range end (YYYY-MM-DD)"),
) -> list[Weight]:
    """Return weight entries for a baby."""
    # Verify the baby exists
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")

    if start and end:
        if end < start:
            raise HTTPException(status_code=400, detail="'end' must be >= 'start'")
        return await weight_service.get_weights_by_date_range(db, baby_id, start, end)

    return await weight_service.get_weights_by_baby(db, baby_id)


@router.patch("/{weight_id}", response_model=Weight)
async def update_weight(weight_id: int, payload: WeightUpdate, db: DbDep) -> Weight:
    """Update a weight entry."""
    weight = await weight_service.update_weight(db, weight_id, payload)
    if not weight:
        raise HTTPException(status_code=404, detail=f"Weight entry {weight_id} not found")
    return weight


@router.delete("/{weight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_weight(weight_id: int, db: DbDep) -> None:
    """Delete a weight entry."""
    deleted = await weight_service.delete_weight(db, weight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Weight entry {weight_id} not found")
