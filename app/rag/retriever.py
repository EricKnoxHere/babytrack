"""Semantic search in the vector index."""

import logging
from pathlib import Path
from typing import Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore

from .indexer import INDEX_DIR, build_index, load_index

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 4


def retrieve_context(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    index: Optional[VectorStoreIndex] = None,
    index_dir: Path = INDEX_DIR,
) -> list[NodeWithScore]:
    """
    Retrieves the most relevant passages for a given query.

    Args:
        query: Question or context to search for.
        top_k: Number of passages to return.
        index: Pre-loaded index (avoids a reload if provided).
        index_dir: Index directory (used if index=None).

    Returns:
        List of NodeWithScore sorted by descending relevance.
    """
    if index is None:
        try:
            index = load_index(index_dir)
        except FileNotFoundError:
            logger.warning("Index not found — building now...")
            index = build_index(index_dir=index_dir)

    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    logger.debug("Retrieval '%s' → %d passages", query[:60], len(nodes))
    return nodes


def format_context(nodes: list[NodeWithScore]) -> str:
    """Formats retrieved passages into a context block for the LLM."""
    if not nodes:
        return "No medical context available."

    parts = []
    for i, node in enumerate(nodes, 1):
        score = f"{node.score:.3f}" if node.score is not None else "N/A"
        source = node.metadata.get("file_name", "unknown source")
        parts.append(
            f"--- Excerpt {i} (source: {source}, score: {score}) ---\n"
            f"{node.text.strip()}"
        )
    return "\n\n".join(parts)
