"""Reusable FastAPI dependencies (DB, RAG index)."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated, Optional

import asyncpg
from fastapi import Depends, Request

from app.services.database import get_db as _get_db

logger = logging.getLogger(__name__)


async def db_dependency() -> AsyncGenerator[asyncpg.Connection, None]:
    """Provide a PostgreSQL connection for the duration of the request."""
    async with _get_db() as conn:
        yield conn


DbDep = Annotated[asyncpg.Connection, Depends(db_dependency)]


def get_rag_index(request: Request):
    """
    Return the RAG index from application state.
    Attempts lazy loading on first call if not already loaded.
    Returns None if loading fails or index not found.
    """
    # Already loaded
    if hasattr(request.app.state, "rag_index") and request.app.state.rag_index is not None:
        return request.app.state.rag_index
    
    # Try lazy loading only once
    if hasattr(request.app.state, "_rag_index_load_attempted"):
        return None
    
    try:
        from app.rag.indexer import load_index
        index_path = Path(getattr(request.app.state, "rag_index_path", "data/index"))
        index = load_index(index_path)
        request.app.state.rag_index = index
        logger.info("RAG index loaded lazily on first use")
        return index
    except FileNotFoundError:
        logger.debug("RAG index not found at %s — continuing without context", 
                    getattr(request.app.state, "rag_index_path", "data/index"))
    except Exception as e:
        logger.warning("Failed to load RAG index lazily: %s — continuing without context", e)
    finally:
        # Mark as attempted so we don't retry every request
        request.app.state._rag_index_load_attempted = True
    
    return None


RagIndexDep = Annotated[Optional[object], Depends(get_rag_index)]
