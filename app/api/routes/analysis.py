"""Endpoint d'analyse IA des biberons via Claude + RAG."""

import asyncio
import logging
from datetime import date, timedelta
from functools import partial
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.dependencies import DbDep
from app.rag.analyzer import analyze_feedings
from app.services import baby_service, feeding_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

PeriodType = Literal["day", "week"]


class AnalysisResponse(BaseModel):
    baby_id: int
    baby_name: str
    period: PeriodType
    period_label: str
    analysis: str


@router.get("/{baby_id}", response_model=AnalysisResponse)
async def analyze_baby_feedings(
    baby_id: int,
    request: Request,
    db: DbDep,
    period: PeriodType = Query("day", description="Période d'analyse : 'day' ou 'week'"),
    reference_date: Optional[date] = Query(
        None,
        description="Date de référence (défaut : aujourd'hui). Format YYYY-MM-DD",
    ),
) -> AnalysisResponse:
    """
    Analyse l'alimentation d'un bébé via Claude + contexte RAG OMS/SFP.

    - `period=day` (défaut) : analyse la journée de `reference_date`
    - `period=week` : analyse les 7 derniers jours à partir de `reference_date`
    """
    # 1. Vérifier que le bébé existe
    baby = await baby_service.get_baby(db, baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Bébé {baby_id} introuvable")

    # 2. Résoudre les dates
    ref = reference_date or date.today()

    if period == "day":
        feedings = await feeding_service.get_feedings_by_day(db, baby_id, ref)
        period_label = f"journée du {ref.strftime('%d/%m/%Y')}"
    else:  # week
        start = ref - timedelta(days=6)
        feedings = await feeding_service.get_feedings_by_range(db, baby_id, start, ref)
        period_label = f"semaine du {start.strftime('%d/%m/%Y')} au {ref.strftime('%d/%m/%Y')}"

    if not feedings:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun biberon enregistré pour la {period_label}",
        )

    # 3. Récupérer l'index RAG depuis l'état de l'app (peut être None)
    rag_index = getattr(request.app.state, "rag_index", None)

    # 4. Appeler le analyzer dans un thread (il est synchrone / bloquant)
    loop = asyncio.get_event_loop()
    analysis_text = await loop.run_in_executor(
        None,
        partial(
            analyze_feedings,
            baby=baby,
            feedings=feedings,
            period_label=period_label,
            index=rag_index,
        ),
    )

    return AnalysisResponse(
        baby_id=baby_id,
        baby_name=baby.name,
        period=period,
        period_label=period_label,
        analysis=analysis_text,
    )
