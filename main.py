"""BabyTrack API application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # load .env before anything reads os.getenv()

from fastapi import FastAPI

from app.api.routes import analysis_router, babies_router, feedings_router, health_router, weights_router
from app.rag.indexer import INDEX_DIR, load_index
from app.services.database import create_tables

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

    # RAG index (optional — analysis works without context if absent)
    index_path = Path(INDEX_DIR)
    try:
        app.state.rag_index = load_index(index_path)
        logger.info("RAG index loaded from %s", index_path)
    except FileNotFoundError:
        app.state.rag_index = None
        logger.warning(
            "RAG index not found (%s). Analysis will run without medical context. "
            "Run `python -m app.rag.indexer` to build it.",
            index_path,
        )

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
app.include_router(analysis_router)
