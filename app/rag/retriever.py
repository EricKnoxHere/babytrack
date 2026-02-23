"""Recherche sémantique dans l'index vectoriel."""

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
    Recherche les passages les plus pertinents pour une query donnée.

    Args:
        query: Question ou contexte à rechercher.
        top_k: Nombre de passages à retourner.
        index: Index pré-chargé (évite un rechargement si fourni).
        index_dir: Dossier de l'index (utilisé si index=None).

    Returns:
        Liste de NodeWithScore triée par pertinence décroissante.
    """
    if index is None:
        try:
            index = load_index(index_dir)
        except FileNotFoundError:
            logger.warning("Index absent — construction en cours...")
            index = build_index(index_dir=index_dir)

    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    logger.debug("Retrieval '%s' → %d passages", query[:60], len(nodes))
    return nodes


def format_context(nodes: list[NodeWithScore]) -> str:
    """Formate les passages récupérés en un bloc de contexte pour le LLM."""
    if not nodes:
        return "Aucun contexte médical disponible."

    parts = []
    for i, node in enumerate(nodes, 1):
        score = f"{node.score:.3f}" if node.score is not None else "N/A"
        source = node.metadata.get("file_name", "source inconnue")
        parts.append(
            f"--- Extrait {i} (source: {source}, score: {score}) ---\n"
            f"{node.text.strip()}"
        )
    return "\n\n".join(parts)
