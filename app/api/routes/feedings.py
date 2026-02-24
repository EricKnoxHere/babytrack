"""Endpoints for feedings / breastfeedings."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DbDep
from app.models.feeding import Feeding, FeedingCreate, FeedingUpdate
from app.services import baby_service, feeding_service

router = APIRouter(prefix="/feedings", tags=["feedings"])


@router.post("", response_model=Feeding, status_code=status.HTTP_201_CREATED)
async def add_feeding(payload: FeedingCreate, db: DbDep) -> Feeding:
    """Record a bottle feeding or breastfeeding session."""
    # Verify the baby exists
    baby = await baby_service.get_baby(db, payload.baby_id)
    if not baby:
        raise HTTPException(
            status_code=404,
            detail=f"Baby {payload.baby_id} not found",
        )
    return await feeding_service.add_feeding(db, payload)


@router.get("/{baby_id}", response_model=list[Feeding])
async def get_feedings(
    baby_id: int,
    db: DbDep,
    day: Optional[date] = Query(None, description="Filter by day (YYYY-MM-DD)"),
    start: Optional[date] = Query(None, description="Range start (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="Range end (YYYY-MM-DD)"),
) -> list[Feeding]:
    """
    Return feedings for a baby.

    - No parameter: full history
    - `?day=YYYY-MM-DD`: a specific day
    - `?start=YYYY-MM-DD&end=YYYY-MM-DD`: a date range
    """
    # Verify the baby exists
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby {baby_id} not found")

    if day:
        return await feeding_service.get_feedings_by_day(db, baby_id, day)
    if start and end:
        if end < start:
            raise HTTPException(status_code=400, detail="'end' must be >= 'start'")
        return await feeding_service.get_feedings_by_range(db, baby_id, start, end)

    return await feeding_service.get_feedings_by_baby(db, baby_id)


@router.patch("/{feeding_id}", response_model=Feeding)
async def update_feeding(feeding_id: int, payload: FeedingUpdate, db: DbDep) -> Feeding:
    """Update a feeding record (all fields optional)."""
    feeding = await feeding_service.update_feeding(db, feeding_id, payload)
    if not feeding:
        raise HTTPException(status_code=404, detail=f"Feeding {feeding_id} not found")
    return feeding


@router.delete("/{feeding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feeding(feeding_id: int, db: DbDep) -> None:
    """Delete a feeding record."""
    deleted = await feeding_service.delete_feeding(db, feeding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Feeding {feeding_id} not found")
