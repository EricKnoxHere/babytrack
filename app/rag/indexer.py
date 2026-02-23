"""Ingestion and indexing of medical documents via LlamaIndex."""

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

# Lightweight and fast embedding model (130 MB, multilingual)
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"


def _get_embed_model() -> HuggingFaceEmbedding:
    return HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)


def build_index(
    docs_dir: Path = DOCS_DIR,
    index_dir: Path = INDEX_DIR,
    force_rebuild: bool = False,
) -> VectorStoreIndex:
    """
    Ingests markdown/PDF documents from docs_dir and builds a vector index.
    The index is persisted in index_dir for subsequent calls.

    Args:
        docs_dir: Directory containing the medical guidelines.
        index_dir: Directory for index persistence.
        force_rebuild: If True, rebuilds even if an index already exists.
    """
    embed_model = _get_embed_model()
    index_dir.mkdir(parents=True, exist_ok=True)

    # Load from cache if available
    if not force_rebuild and (index_dir / "docstore.json").exists():
        logger.info("Loading index from cache: %s", index_dir)
        storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
        return load_index_from_storage(storage_context, embed_model=embed_model)

    logger.info("Building index from: %s", docs_dir)
    documents = SimpleDirectoryReader(
        input_dir=str(docs_dir),
        required_exts=[".md", ".pdf", ".txt"],
        recursive=True,
    ).load_data()

    if not documents:
        raise FileNotFoundError(f"No documents found in {docs_dir}")

    logger.info("%d document(s) loaded", len(documents))

    index = VectorStoreIndex.from_documents(
        documents,
        embed_model=embed_model,
        show_progress=True,
    )
    index.storage_context.persist(persist_dir=str(index_dir))
    logger.info("Index persisted to: %s", index_dir)
    return index


def load_index(index_dir: Path = INDEX_DIR) -> VectorStoreIndex:
    """
    Loads an already-built index from disk.
    Raises FileNotFoundError if the index does not exist.
    """
    if not (index_dir / "docstore.json").exists():
        raise FileNotFoundError(
            f"Index not found in {index_dir}. Run build_index() first."
        )
    embed_model = _get_embed_model()
    storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
    return load_index_from_storage(storage_context, embed_model=embed_model)
