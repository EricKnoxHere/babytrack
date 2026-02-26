"""BabyTrack API application entry point."""

import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # load .env before anything reads os.getenv()

from fastapi import FastAPI

from app.api.routes import (
    analysis_router, babies_router, conversations_router,
    diapers_router, feedings_router, health_router, weights_router,
)
from app.services.database import create_tables

# Do NOT import RAG at startup (sentence-transformers + torch = 600MB+)
INDEX_DIR = Path(os.getenv("INDEX_DIR", "data/index"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database and load the RAG index at startup."""
    # Database
    await create_tables()
    logger.info("SQLite tables initialized")

    # RAG index — mark for lazy loading
    # Do NOT attempt to load at startup (can timeout on cold start)
    app.state.rag_index = None
    app.state.rag_index_path = Path(INDEX_DIR)
    logger.info("RAG index will load on first use (lazy loading)")

    yield

    # Shutdown — nothing to release for now
    logger.info("BabyTrack API stopped")


app = FastAPI(
    title="BabyTrack API",
    description=(
        "Infant feeding tracker API with AI analysis (Claude + WHO/SFP RAG). "
        "Portfolio project — Solutions Architect Anthropic."
    ),
    version="0.4.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(babies_router)
app.include_router(feedings_router)
app.include_router(weights_router)
app.include_router(diapers_router)
app.include_router(analysis_router)
app.include_router(conversations_router)
