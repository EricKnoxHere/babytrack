"""Ingestion et indexation des documents médicaux via LlamaIndex."""

import logging
import os
from pathlib import Path

from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

logger = logging.getLogger(__name__)

DOCS_DIR = Path(os.getenv("DOCS_DIR", "data/docs"))
INDEX_DIR = Path(os.getenv("INDEX_DIR", "data/index"))

# Modèle d'embedding léger et rapide (130 MB, multilingue)
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"


def _get_embed_model() -> HuggingFaceEmbedding:
    return HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)


def build_index(
    docs_dir: Path = DOCS_DIR,
    index_dir: Path = INDEX_DIR,
    force_rebuild: bool = False,
) -> VectorStoreIndex:
    """
    Ingère les documents markdown/PDF de docs_dir et construit un index vectoriel.
    L'index est persisté dans index_dir pour les appels suivants.

    Args:
        docs_dir: Dossier contenant les guides médicaux.
        index_dir: Dossier de persistance de l'index.
        force_rebuild: Si True, reconstruit même si l'index existe déjà.
    """
    embed_model = _get_embed_model()
    index_dir.mkdir(parents=True, exist_ok=True)

    # Chargement depuis le cache si disponible
    if not force_rebuild and (index_dir / "docstore.json").exists():
        logger.info("Chargement de l'index depuis le cache : %s", index_dir)
        storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
        return load_index_from_storage(storage_context, embed_model=embed_model)

    logger.info("Construction de l'index depuis : %s", docs_dir)
    documents = SimpleDirectoryReader(
        input_dir=str(docs_dir),
        required_exts=[".md", ".pdf", ".txt"],
        recursive=True,
    ).load_data()

    if not documents:
        raise FileNotFoundError(f"Aucun document trouvé dans {docs_dir}")

    logger.info("%d document(s) chargé(s)", len(documents))

    index = VectorStoreIndex.from_documents(
        documents,
        embed_model=embed_model,
        show_progress=True,
    )
    index.storage_context.persist(persist_dir=str(index_dir))
    logger.info("Index persisté dans : %s", index_dir)
    return index


def load_index(index_dir: Path = INDEX_DIR) -> VectorStoreIndex:
    """
    Charge un index déjà construit depuis le disque.
    Lève FileNotFoundError si l'index n'existe pas.
    """
    if not (index_dir / "docstore.json").exists():
        raise FileNotFoundError(
            f"Index introuvable dans {index_dir}. Lance build_index() d'abord."
        )
    embed_model = _get_embed_model()
    storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
    return load_index_from_storage(storage_context, embed_model=embed_model)
