"""Dépendances FastAPI réutilisables (DB, index RAG)."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated, Optional

import aiosqlite
from fastapi import Depends, Request

from app.services.database import get_db as _get_db

logger = logging.getLogger(__name__)


async def db_dependency() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Fournit une connexion SQLite pour la durée de la requête."""
    async with _get_db() as conn:
        yield conn


DbDep = Annotated[aiosqlite.Connection, Depends(db_dependency)]


def get_rag_index(request: Request):
    """Retourne l'index RAG depuis l'état de l'application (peut être None)."""
    return getattr(request.app.state, "rag_index", None)


RagIndexDep = Annotated[Optional[object], Depends(get_rag_index)]
