"""Healthcheck endpoint."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    rag_available: bool


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Return service status and RAG availability."""
    rag_available = getattr(request.app.state, "rag_index", None) is not None
    return HealthResponse(status="ok", rag_available=rag_available)
