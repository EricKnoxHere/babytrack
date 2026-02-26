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
MAX_TOKENS_CONVERSATIONAL = 400

# Keywords that trigger a full structured report instead of a conversational answer
_REPORT_KEYWORDS = {
    "analyze", "analyse", "analysis", "report", "bilan",
    "full report", "detailed", "rapport", "complet",
}


def _is_report_request(question: str | None) -> bool:
    """Return True if the question explicitly asks for a full structured report."""
    if not question:
        return True  # no question = default to full report
    q = question.lower().strip()
    return any(kw in q for kw in _REPORT_KEYWORDS)


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

    from collections import Counter

    total_ml = sum(f.quantity_ml for f in feedings)
    count = len(feedings)
    types = {f.feeding_type for f in feedings}
    type_label = {
        frozenset({"bottle"}): "bottle only",
        frozenset({"breastfeeding"}): "breastfeeding only",
        frozenset({"bottle", "breastfeeding"}): "mixed (bottle + breastfeeding)",
    }.get(frozenset(types), ", ".join(types))

    # Per-day stats — only from days that actually have entries
    daily_counts: Counter = Counter()
    daily_volumes: Counter = Counter()
    for f in feedings:
        day = f.fed_at.date().isoformat()
        daily_counts[day] += 1
        daily_volumes[day] += f.quantity_ml
    days_with_data = len(daily_counts)
    avg_feeds_per_day = count / days_with_data if days_with_data else 0
    avg_ml_per_day = total_ml / days_with_data if days_with_data else 0

    lines = [
        f"- {f.fed_at.strftime('%d/%m %H:%M')} : {f.quantity_ml} ml ({f.feeding_type})"
        + (f" — note: {f.notes}" if f.notes else "")
        for f in sorted(feedings, key=lambda x: x.fed_at)
    ]

    return (
        f"Number of feedings: {count} over {days_with_data} days with recorded data\n"
        f"Average: {avg_feeds_per_day:.1f} feeds/day, {avg_ml_per_day:.0f} ml/day "
        f"(computed from days with entries only)\n"
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
    question: str | None = None,
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

    # ── Expected norms (safety net from computed data) ─────────────────────
    feeds_per_day_expected = round(_expected_feedings_per_hour(age_days) * 24)
    norms_note = f"Age-based estimate: ~{feeds_per_day_expected} feeds/day for a {age_str} old infant."

    # ── Data block: references FIRST, then baby data ──────────────────────
    data_block = f"""## Medical reference context (WHO / SFP)
{rag_context}

## Baby profile
- Name: {baby.name}
- Age: {age_str} ({age_days} days)
- Birth weight: {baby.birth_weight_grams} g
- {norms_note}
{weight_section}
{temporal_section}
{context_section}## Feeding data — {ctx.start.strftime('%d/%m/%Y %H:%M')} to {ctx.end.strftime('%d/%m/%Y %H:%M')}
{feeding_summary}"""

    # ── Grounding instructions (shared) ───────────────────────────────────
    grounding = """## Instructions
1. First, extract from the medical references above the recommended ranges for this baby's age: feeds/day, ml/feed, total ml/day, expected weight gain.
2. Compare the baby's actual data against those reference ranges.
3. If any metric is below the recommended minimum, flag it clearly — never tell a parent a below-minimum value is normal.
4. Do not state that data is "appropriate" or "on track" without citing the specific reference range that supports it."""

    # ── Report mode: structured 4-section analysis ────────────────────────
    if _is_report_request(question):
        return f"""{data_block}

{grounding}

## Output format
**✅ Positive:** What's going well (cite reference ranges).
**⚠️ Concerns:** {"Pace off-track vs references?" if ctx.is_partial else "Any metric outside reference ranges?"}
**💡 Action:** 2–3 concrete steps.
**📊 Summary:** One sentence.
"""

    # ── Conversational mode: short direct answer ─────────────────────────
    return f"""{data_block}

{grounding}

## Parent's question
{question}

Answer the parent's question directly, citing reference values when relevant.
"""


# ─── Public API ───────────────────────────────────────────────────────────────

def analyze_feedings(
    baby: Baby,
    feedings: list[Feeding],
    ctx: AnalysisContext,
    index: Optional[VectorStoreIndex] = None,
    index_dir: Optional[Path] = None,
    weights: list[Weight] | None = None,
    question: str | None = None,
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
        question: Parent's free-text question (conversational mode).

    Returns:
        Tuple of (analysis text, list of source dicts).
    """
    age_days = (date.today() - baby.birth_date).days
    feeding_types = {f.feeding_type for f in feedings} or {"bottle"}

    # Age string for RAG query — use exact age for best semantic matching
    if age_days < 14:
        age_query = f"{age_days} days old newborn"
    elif age_days < 60:
        age_query = f"{age_days // 7} weeks old infant"
    else:
        age_query = f"{age_days // 30} months old infant"

    feed_type = "bottle formula" if "bottle" in feeding_types else "breastfeeding"

    # Build a question-aware query when a parent question is provided
    if question and not _is_report_request(question):
        query = f"{question} {age_query} {feed_type}"
    else:
        query = f"recommended feeding frequency volume {age_query} {feed_type}"

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

    prompt = _build_prompt(baby, feedings, rag_context, ctx, weights=weights, question=question)

    # ── System message & token budget depend on mode ──────────────────────
    is_report = _is_report_request(question)

    _DISCLAIMER = (
        "Always end your response with: "
        "'This is not medical advice — consult your pediatrician for any concerns.'"
    )

    if is_report:
        system_msg = (
            "You are a pediatric nutrition assistant. "
            "Analyse the data and produce a structured report. "
            "Be factual and precise. Always compare the baby's data against "
            "the reference ranges from the provided medical documents. "
            "Never state that a value is normal without citing the reference range. "
            "Keep each section short — no filler, no exaggeration. "
            + _DISCLAIMER
        )
        max_tok = MAX_TOKENS
    else:
        system_msg = (
            "You are a pediatric nutrition assistant helping a parent. "
            "Answer in 2-4 short sentences. Be warm but factual. "
            "No headers, no bullet lists, no emojis, no markdown formatting. "
            "Always compare the baby's data against the reference ranges from "
            "the provided medical documents. Never state that a value is normal "
            "without citing the reference range. "
            "If something is concerning, say so plainly without dramatising. "
            + _DISCLAIMER
        )
        max_tok = MAX_TOKENS_CONVERSATIONAL

    client = anthropic.Anthropic()
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tok,
            temperature=0.2,
            system=system_msg,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.BadRequestError as exc:
        if "credit balance is too low" in str(exc).lower():
            raise RuntimeError("No more credit") from exc
        raise

    analysis = message.content[0].text
    logger.info("Analysis for %s (%dh window, partial=%s)", baby.name, ctx.hours_elapsed, ctx.is_partial)
    return analysis, sources
