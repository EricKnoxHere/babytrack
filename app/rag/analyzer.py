"""Feeding analysis via Claude + WHO/SFP RAG context."""

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import anthropic
from llama_index.core import VectorStoreIndex

from app.models.baby import Baby
from app.models.feeding import Feeding
from app.models.weight import Weight
from .retriever import format_context, retrieve_context

logger = logging.getLogger(__name__)

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("ANALYZER_MAX_TOKENS", "1200"))


# ─── Analysis context ─────────────────────────────────────────────────────────

@dataclass
class AnalysisContext:
    """Temporal metadata passed to the prompt so Claude reasons correctly."""
    start: datetime
    end: datetime
    is_partial: bool           # window is still ongoing (end ≈ now)
    hours_elapsed: float       # length of the window in hours
    feedings_expected: int     # age-based estimate for the full window
    baseline_count: int        # feedings in the previous equivalent window
    baseline_volume_ml: int    # total ml in the previous equivalent window
    baseline_label: str        # human-readable label for the baseline window


def _expected_feedings_per_hour(age_days: int) -> float:
    """Returns approximate feedings/hour based on baby age."""
    if age_days < 30:
        return 9 / 24      # ~9/day for newborns
    elif age_days < 60:
        return 7.5 / 24
    elif age_days < 120:
        return 6 / 24
    else:
        return 5 / 24


# ─── Summarisers ──────────────────────────────────────────────────────────────

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

    lines = [
        f"- {f.fed_at.strftime('%d/%m %H:%M')} : {f.quantity_ml} ml ({f.feeding_type})"
        + (f" — note: {f.notes}" if f.notes else "")
        for f in sorted(feedings, key=lambda x: x.fed_at)
    ]

    return (
        f"Number of feedings: {count}\n"
        f"Total volume: {total_ml} ml\n"
        f"Feeding type: {type_label}\n"
        f"Chronological detail:\n" + "\n".join(lines)
    )


def _summarize_weights(weights: list[Weight]) -> str:
    """Builds a short weight summary for the prompt."""
    if not weights:
        return ""
    lines = [
        f"- {w.measured_at.strftime('%d/%m %H:%M')}: {w.weight_g}g"
        + (f" — note: {w.notes}" if w.notes else "")
        for w in sorted(weights, key=lambda x: x.measured_at)
    ]
    return "\n".join(lines)


def _extract_contextual_events(
    feedings: list[Feeding],
    weights: list[Weight],
) -> str:
    """Collects all non-empty notes into a chronological event log."""
    events: list[tuple[datetime, str, str]] = []

    for f in feedings:
        if f.notes and f.notes.strip():
            events.append((f.fed_at, "feeding", f.notes.strip()))
    for w in weights:
        if w.notes and w.notes.strip():
            events.append((w.measured_at, "weight", w.notes.strip()))

    if not events:
        return ""

    events.sort(key=lambda x: x[0])
    return "\n".join(
        f"- {ts.strftime('%d/%m %H:%M')} [{kind}]: {note}"
        for ts, kind, note in events
    )


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _build_prompt(
    baby: Baby,
    feedings: list[Feeding],
    rag_context: str,
    ctx: AnalysisContext,
    weights: list[Weight] | None = None,
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

    # ── Temporal context block ────────────────────────────────────────────────
    if ctx.is_partial:
        pace = len(feedings) / ctx.hours_elapsed if ctx.hours_elapsed > 0 else 0
        projected = round(pace * 24)
        partial_note = (
            f"⏳ PARTIAL: {len(feedings)} feeds in {ctx.hours_elapsed:.0f}h → ~{projected}/day pace. "
            f"Evaluate rate, not totals."
        )
    else:
        partial_note = "✅ Complete window."

    baseline_note = (
        f"{ctx.baseline_count} feeds / {ctx.baseline_volume_ml}ml (previous equivalent period)"
        if ctx.baseline_count > 0
        else "No previous data to compare."
    )

    temporal_section = f"""## Window
{ctx.start.strftime('%d/%m %H:%M')} → {ctx.end.strftime('%d/%m %H:%M')} ({ctx.hours_elapsed:.0f}h) | {partial_note}
Baseline: {baseline_note}
"""

    # ── Contextual events ─────────────────────────────────────────────────────
    contextual_events = _extract_contextual_events(feedings, weights or [])
    context_section = ""
    if contextual_events:
        context_section = f"""## Parent notes
{contextual_events}

"""

    # ── Weight section ────────────────────────────────────────────────────────
    weight_section = ""
    if weights:
        weight_section = f"\n## Weight measurements\n{_summarize_weights(weights)}\n"

    return f"""You are a pediatric assistant specialising in infant nutrition.
Analyse the baby's feeding data and provide kind, precise, and actionable recommendations.
Base your response on the WHO/SFP medical context provided below.

{temporal_section}
{context_section}## Medical reference context (WHO / SFP)
{rag_context}

## Baby profile
- Name: {baby.name}
- Age: {age_str}
- Birth weight: {baby.birth_weight_grams} g
{weight_section}
## Feeding data — {ctx.start.strftime('%d/%m/%Y %H:%M')} to {ctx.end.strftime('%d/%m/%Y %H:%M')}
{feeding_summary}

## Analysis (concise format)
**✅ Positive:** What's going well.
**⚠️ Concerns:** {"Pace off-track?" if ctx.is_partial else "Deviations from norms?"}
**💡 Action:** 2–3 concrete steps.
**📊 Summary:** One sentence.
"""


# ─── Public API ───────────────────────────────────────────────────────────────

def analyze_feedings(
    baby: Baby,
    feedings: list[Feeding],
    ctx: AnalysisContext,
    index: Optional[VectorStoreIndex] = None,
    index_dir: Optional[Path] = None,
    weights: list[Weight] | None = None,
) -> tuple[str, list[dict]]:
    """
    Analyses a baby's feedings via Claude + WHO/SFP RAG context.

    Args:
        baby: Full baby profile.
        feedings: Feedings within the analysis window.
        ctx: Temporal context (window, partial flag, baseline).
        index: Pre-loaded vector index (optional).
        index_dir: Path to the index (if index not provided).
        weights: Recent weight measurements + notes (optional).

    Returns:
        Tuple of (analysis text, list of source dicts).
    """
    age_days = (date.today() - baby.birth_date).days
    feeding_types = {f.feeding_type for f in feedings} or {"bottle"}
    query = (
        f"recommended bottle volume feeding frequency infant "
        f"{age_days // 30} months "
        f"{'bottle formula' if 'bottle' in feeding_types else 'breastfeeding'}"
    )

    kwargs: dict = {"query": query, "top_k": 4}
    if index is not None:
        kwargs["index"] = index
    elif index_dir is not None:
        kwargs["index_dir"] = index_dir

    sources: list[dict] = []
    try:
        nodes = retrieve_context(**kwargs)
        rag_context = format_context(nodes)
        for node in nodes:
            sources.append({
                "source": node.metadata.get("file_name", "unknown"),
                "score": round(node.score, 3) if node.score is not None else None,
            })
    except Exception as exc:
        logger.warning("RAG retrieval failed (%s) — analysing without context", exc)
        rag_context = "Medical context unavailable."

    prompt = _build_prompt(baby, feedings, rag_context, ctx, weights=weights)

    client = anthropic.Anthropic()
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
    logger.info("Analysis for %s (%dh window, partial=%s)", baby.name, ctx.hours_elapsed, ctx.is_partial)
    return analysis, sources
