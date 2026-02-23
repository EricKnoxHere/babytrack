"""Reusable FastAPI dependencies (DB, RAG index)."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated, Optional

import aiosqlite
from fastapi import Depends, Request

from app.services.database import get_db as _get_db

logger = logging.getLogger(__name__)


async def db_dependency() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Provide a SQLite connection for the duration of the request."""
    async with _get_db() as conn:
        yield conn


DbDep = Annotated[aiosqlite.Connection, Depends(db_dependency)]


def get_rag_index(request: Request):
    """Return the RAG index from application state (may be None)."""
    return getattr(request.app.state, "rag_index", None)


RagIndexDep = Annotated[Optional[object], Depends(get_rag_index)]
