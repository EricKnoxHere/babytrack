"""Analyse des données de biberons via Claude + contexte RAG OMS/SFP."""

import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import anthropic
from llama_index.core import VectorStoreIndex

from app.models.baby import Baby
from app.models.feeding import Feeding
from .retriever import format_context, retrieve_context

logger = logging.getLogger(__name__)

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")
MAX_TOKENS = int(os.getenv("ANALYZER_MAX_TOKENS", "1024"))


def _summarize_feedings(feedings: list[Feeding]) -> str:
    """Construit un résumé textuel structuré des biberons pour le prompt."""
    if not feedings:
        return "Aucun biberon enregistré sur cette période."

    total_ml = sum(f.quantity_ml for f in feedings)
    count = len(feedings)
    types = {f.feeding_type for f in feedings}
    type_label = {
        frozenset({"bottle"}): "biberon uniquement",
        frozenset({"breastfeeding"}): "allaitement uniquement",
        frozenset({"bottle", "breastfeeding"}): "mixte (biberon + allaitement)",
    }.get(frozenset(types), ", ".join(types))

    # Détail chronologique
    lines = [
        f"- {f.fed_at.strftime('%H:%M')} : {f.quantity_ml} ml ({f.feeding_type})"
        + (f" — note : {f.notes}" if f.notes else "")
        for f in sorted(feedings, key=lambda x: x.fed_at)
    ]

    return (
        f"Nombre de prises : {count}\n"
        f"Volume total : {total_ml} ml\n"
        f"Type d'alimentation : {type_label}\n"
        f"Détail chronologique :\n" + "\n".join(lines)
    )


def _build_prompt(
    baby: Baby,
    feedings: list[Feeding],
    period_label: str,
    rag_context: str,
) -> str:
    feeding_summary = _summarize_feedings(feedings)
    age_days = (date.today() - baby.birth_date).days
    age_weeks = age_days // 7
    age_months = age_days // 30

    if age_days < 14:
        age_str = f"{age_days} jours"
    elif age_weeks < 8:
        age_str = f"{age_weeks} semaines"
    else:
        age_str = f"{age_months} mois"

    return f"""Tu es un assistant pédiatrique expert en nutrition nourrisson.
Analyse les données d'alimentation du bébé et fournis des recommandations bienveillantes, précises et actionnables.
Appuie-toi sur le contexte médical OMS/SFP fourni ci-dessous.

## Contexte médical de référence (OMS / SFP)
{rag_context}

## Profil du bébé
- Nom : {baby.name}
- Âge : {age_str}
- Poids de naissance : {baby.birth_weight_grams} g

## Données d'alimentation — {period_label}
{feeding_summary}

## Analyse demandée
Réponds en français, de façon structurée, avec les sections suivantes :

### ✅ Points positifs
Cite ce qui est bien (volumes, fréquence, régularité).

### ⚠️ Points d'attention
Signale les écarts par rapport aux recommandations OMS/SFP pour cet âge (volumes trop faibles/élevés, intervalles trop longs/courts, etc.).

### 💡 Recommandations
Donne 2–3 actions concrètes et adaptées à l'âge du bébé.

### 📊 Synthèse
Une phrase de synthèse sur l'alimentation de la période analysée.

Sois rassurant si les données sont normales. Recommande de consulter un pédiatre uniquement si une anomalie significative est détectée.
"""


def analyze_feedings(
    baby: Baby,
    feedings: list[Feeding],
    period_label: str = "la période",
    index: Optional[VectorStoreIndex] = None,
    index_dir: Optional[Path] = None,
) -> str:
    """
    Analyse les biberons d'un bébé via Claude + contexte RAG OMS/SFP.

    Args:
        baby: Profil complet du bébé.
        feedings: Liste des biberons à analyser.
        period_label: Label lisible de la période (ex: "journée du 23/02/2026").
        index: Index vectoriel pré-chargé (optionnel, évite le rechargement).
        index_dir: Chemin vers l'index (si index non fourni).

    Returns:
        Analyse textuelle structurée en markdown.
    """
    # 1. Construire la query RAG selon l'âge et le type d'alimentation
    age_days = (date.today() - baby.birth_date).days
    feeding_types = {f.feeding_type for f in feedings}
    query = (
        f"recommandations volume biberon fréquence alimentation nourrisson "
        f"{age_days // 30} mois "
        f"{'biberon lait artificiel' if 'bottle' in feeding_types else 'allaitement maternel'}"
    )

    # 2. Récupérer le contexte médical
    kwargs = {"query": query, "top_k": 4}
    if index is not None:
        kwargs["index"] = index
    elif index_dir is not None:
        kwargs["index_dir"] = index_dir

    try:
        nodes = retrieve_context(**kwargs)
        rag_context = format_context(nodes)
    except Exception as exc:
        logger.warning("RAG retrieval échoué (%s) — analyse sans contexte", exc)
        rag_context = "Contexte médical non disponible (index absent ou erreur)."

    # 3. Construire et envoyer le prompt à Claude
    prompt = _build_prompt(baby, feedings, period_label, rag_context)

    client = anthropic.Anthropic()  # utilise ANTHROPIC_API_KEY de l'environnement
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    analysis = message.content[0].text
    logger.info("Analyse générée pour %s (%d tokens)", baby.name, message.usage.output_tokens)
    return analysis
