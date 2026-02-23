"""Feeding analysis via Claude + WHO/SFP RAG context."""

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
    """Builds a structured text summary of feedings for the prompt."""
    if not feedings:
        return "No feedings recorded for this period."

    total_ml = sum(f.quantity_ml for f in feedings)
    count = len(feedings)
    types = {f.feeding_type for f in feedings}
    type_label = {
        frozenset({"bottle"}): "bottle only",
        frozenset({"breastfeeding"}): "breastfeeding only",
        frozenset({"bottle", "breastfeeding"}): "mixed (bottle + breastfeeding)",
    }.get(frozenset(types), ", ".join(types))

    # Chronological detail
    lines = [
        f"- {f.fed_at.strftime('%H:%M')} : {f.quantity_ml} ml ({f.feeding_type})"
        + (f" — note: {f.notes}" if f.notes else "")
        for f in sorted(feedings, key=lambda x: x.fed_at)
    ]

    return (
        f"Number of feedings: {count}\n"
        f"Total volume: {total_ml} ml\n"
        f"Feeding type: {type_label}\n"
        f"Chronological detail:\n" + "\n".join(lines)
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
        age_str = f"{age_days} days"
    elif age_weeks < 8:
        age_str = f"{age_weeks} weeks"
    else:
        age_str = f"{age_months} months"

    return f"""You are a pediatric assistant specialising in infant nutrition.
Analyse the baby's feeding data and provide kind, precise, and actionable recommendations.
Base your response on the WHO/SFP medical context provided below.

## Medical reference context (WHO / SFP)
{rag_context}

## Baby profile
- Name: {baby.name}
- Age: {age_str}
- Birth weight: {baby.birth_weight_grams} g

## Feeding data — {period_label}
{feeding_summary}

## Requested analysis
Respond in English, in a structured format, with the following sections:

### ✅ Positive points
Note what is going well (volumes, frequency, regularity).

### ⚠️ Points of attention
Flag deviations from WHO/SFP recommendations for this age (volumes too low/high, intervals too long/short, etc.).

### 💡 Recommendations
Give 2–3 concrete actions tailored to the baby's age.

### 📊 Summary
A one-sentence summary of the feeding for the analysed period.

Be reassuring if the data is normal. Recommend consulting a paediatrician only if a significant anomaly is detected.
"""


def analyze_feedings(
    baby: Baby,
    feedings: list[Feeding],
    period_label: str = "the period",
    index: Optional[VectorStoreIndex] = None,
    index_dir: Optional[Path] = None,
) -> str:
    """
    Analyses a baby's feedings via Claude + WHO/SFP RAG context.

    Args:
        baby: Full baby profile.
        feedings: List of feedings to analyse.
        period_label: Human-readable period label (e.g. "day of 23/02/2026").
        index: Pre-loaded vector index (optional, avoids reload).
        index_dir: Path to the index (if index not provided).

    Returns:
        Structured markdown text analysis.
    """
    # 1. Build the RAG query based on age and feeding type
    age_days = (date.today() - baby.birth_date).days
    feeding_types = {f.feeding_type for f in feedings}
    query = (
        f"recommended bottle volume feeding frequency infant "
        f"{age_days // 30} months "
        f"{'bottle formula' if 'bottle' in feeding_types else 'breastfeeding'}"
    )

    # 2. Retrieve medical context
    kwargs = {"query": query, "top_k": 4}
    if index is not None:
        kwargs["index"] = index
    elif index_dir is not None:
        kwargs["index_dir"] = index_dir

    try:
        nodes = retrieve_context(**kwargs)
        rag_context = format_context(nodes)
    except Exception as exc:
        logger.warning("RAG retrieval failed (%s) — analysing without context", exc)
        rag_context = "Medical context unavailable (missing index or error)."

    # 3. Build and send the prompt to Claude
    prompt = _build_prompt(baby, feedings, period_label, rag_context)

    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY from environment
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.BadRequestError as exc:
        if "credit balance is too low" in str(exc).lower():
            raise RuntimeError("No more credit") from exc
        raise

    analysis = message.content[0].text
    logger.info("Analysis generated for %s (%d tokens)", baby.name, message.usage.output_tokens)
    return analysis
