"""Point d'entrée de l'application BabyTrack API."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.routes import analysis_router, babies_router, feedings_router, health_router
from app.rag.indexer import INDEX_DIR, load_index
from app.services.database import create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise la base de données et charge l'index RAG au démarrage."""
    # Base de données
    await create_tables()
    logger.info("Tables SQLite initialisées")

    # Index RAG (optionnel — l'analyse tourne sans contexte si absent)
    index_path = Path(INDEX_DIR)
    try:
        app.state.rag_index = load_index(index_path)
        logger.info("Index RAG chargé depuis %s", index_path)
    except FileNotFoundError:
        app.state.rag_index = None
        logger.warning(
            "Index RAG absent (%s). L'analyse fonctionnera sans contexte médical. "
            "Lance `python -m app.rag.indexer` pour le construire.",
            index_path,
        )

    yield

    # Shutdown — rien à libérer pour l'instant
    logger.info("BabyTrack API arrêtée")


app = FastAPI(
    title="BabyTrack API",
    description=(
        "API de suivi d'alimentation nourrisson avec analyse IA (Claude + RAG OMS/SFP). "
        "Projet portfolio — Solutions Architect Anthropic."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(babies_router)
app.include_router(feedings_router)
app.include_router(analysis_router)
