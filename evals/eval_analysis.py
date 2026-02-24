"""
BabyTrack — Evaluation Framework for Claude AI Analysis
========================================================

Measures output quality across two dimensions:
  1. Structural completeness  — are all required sections present?
  2. LLM-as-judge scoring     — Claude grades its own output against a rubric

Also runs a RAG vs no-RAG comparison to quantify the value of grounding.

Usage:
    cd ~/Documents/babytrack
    source .venv/bin/activate
    python evals/eval_analysis.py

Results are written to evals/results/eval_<timestamp>.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from app.models.baby import Baby
from app.models.feeding import Feeding
from app.rag.analyzer import CLAUDE_MODEL, _build_prompt, _summarize_feedings
from app.rag.indexer import INDEX_DIR, build_index, load_index
from app.rag.retriever import format_context, retrieve_context

logging.basicConfig(level=logging.WARNING)

# ─── Test scenarios ───────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": "newborn_healthy",
        "description": "7-day-old, volumes and frequency within WHO norms",
        "baby": Baby(
            id=1, name="Louise", birth_date=date(2026, 2, 16),
            birth_weight_grams=3200, created_at=datetime(2026, 2, 16, 9, 0),
        ),
        "feedings": [
            Feeding(id=i, baby_id=1,
                    fed_at=datetime(2026, 2, 23, 6 + i * 3, 0),
                    quantity_ml=70 + i * 5, feeding_type="bottle",
                    created_at=datetime(2026, 2, 23, 6 + i * 3, 1))
            for i in range(6)
        ],
        "period_label": "day of 23/02/2026",
        "expect_positive": True,
    },
    {
        "id": "newborn_low_intake",
        "description": "7-day-old, volumes too low (40 ml/feed), too few feeds",
        "baby": Baby(
            id=1, name="Louise", birth_date=date(2026, 2, 16),
            birth_weight_grams=3200, created_at=datetime(2026, 2, 16, 9, 0),
        ),
        "feedings": [
            Feeding(id=i, baby_id=1,
                    fed_at=datetime(2026, 2, 23, 8 + i * 6, 0),
                    quantity_ml=40, feeding_type="bottle",
                    created_at=datetime(2026, 2, 23, 8 + i * 6, 1))
            for i in range(3)
        ],
        "period_label": "day of 23/02/2026",
        "expect_positive": False,
    },
    {
        "id": "2month_mixed_feeding",
        "description": "2-month-old, mixed bottle + breastfeeding, healthy volumes",
        "baby": Baby(
            id=2, name="Tom", birth_date=date(2025, 12, 23),
            birth_weight_grams=3500, created_at=datetime(2025, 12, 23, 9, 0),
        ),
        "feedings": [
            Feeding(id=i, baby_id=2,
                    fed_at=datetime(2026, 2, 23, 6 + i * 3, 30),
                    quantity_ml=110 + (i % 2) * 20,
                    feeding_type="bottle" if i % 2 == 0 else "breastfeeding",
                    created_at=datetime(2026, 2, 23, 6 + i * 3, 31))
            for i in range(6)
        ],
        "period_label": "day of 23/02/2026",
        "expect_positive": True,
    },
]

REQUIRED_SECTIONS = ["✅", "⚠️", "💡", "📊"]

# ─── Rubric for LLM-as-judge ──────────────────────────────────────────────────

JUDGE_PROMPT = """You are evaluating an AI-generated infant feeding analysis.
Score the response on each criterion from 0 to 3:

  3 = Excellent  2 = Good  1 = Partial  0 = Missing / Wrong

Criteria:
1. age_appropriate   — Does the analysis reference norms specific to the baby's age?
2. rag_grounded      — Does it cite or reflect WHO/SFP medical recommendations?
3. actionable        — Are the recommendations concrete and implementable?
4. safety_flag       — Does it correctly flag (or not flag) a concern given the data?
                       Score 3 if the flag matches reality, 0 if it misses a real issue.
5. tone              — Reassuring where warranted, appropriately concerned when needed.

Baby profile: {baby_profile}
Expected positive outcome: {expect_positive}

Analysis to evaluate:
---
{analysis}
---

Respond ONLY with a JSON object, no explanation:
{{"age_appropriate": <0-3>, "rag_grounded": <0-3>, "actionable": <0-3>, "safety_flag": <0-3>, "tone": <0-3>, "overall_comment": "<one sentence>"}}
"""


# ─── Core functions ───────────────────────────────────────────────────────────

def check_structure(analysis: str) -> dict[str, bool]:
    """Verify all required markdown sections are present."""
    return {sec: sec in analysis for sec in REQUIRED_SECTIONS}


def judge(analysis: str, scenario: dict, client: anthropic.Anthropic) -> dict:
    """Ask Claude to score its own output against the rubric."""
    baby = scenario["baby"]
    age_days = (date(2026, 2, 23) - baby.birth_date).days
    baby_profile = f"{baby.name}, {age_days} days old, {baby.birth_weight_grams}g birth weight"

    prompt = JUDGE_PROMPT.format(
        baby_profile=baby_profile,
        expect_positive=scenario["expect_positive"],
        analysis=analysis,
    )
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


def run_analysis(baby, feedings, period_label, rag_context: str) -> str:
    """Call Claude with the given RAG context (or empty string for no-RAG baseline)."""
    prompt = _build_prompt(baby, feedings, period_label, rag_context)
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ─── Main eval loop ───────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print("  BabyTrack — Evaluation Run")
    print(f"  Model: {CLAUDE_MODEL}")
    print(f"{'='*60}\n")

    client = anthropic.Anthropic()

    # Load RAG index once
    try:
        index = load_index(Path(INDEX_DIR))
    except FileNotFoundError:
        print("⏳  Building RAG index (first run)...")
        index = build_index()
    print("✅  RAG index loaded\n")

    results = []

    for scenario in SCENARIOS:
        print(f"📋  Scenario: {scenario['id']}")
        print(f"    {scenario['description']}")

        baby = scenario["baby"]
        feedings = scenario["feedings"]
        period_label = scenario["period_label"]

        # Build RAG context
        age_days = (date(2026, 2, 23) - baby.birth_date).days
        feeding_types = {f.feeding_type for f in feedings}
        query = (
            f"recommended bottle volume feeding frequency infant "
            f"{age_days // 30} months "
            f"{'bottle formula' if 'bottle' in feeding_types else 'breastfeeding'}"
        )
        nodes = retrieve_context(query, top_k=4, index=index)
        rag_context = format_context(nodes)
        no_rag_context = "No medical context available."

        # Run both variants
        print("    → Running with RAG...", end="", flush=True)
        analysis_rag = run_analysis(baby, feedings, period_label, rag_context)
        print(" done")

        print("    → Running without RAG...", end="", flush=True)
        analysis_baseline = run_analysis(baby, feedings, period_label, no_rag_context)
        print(" done")

        # Structural check
        struct_rag = check_structure(analysis_rag)
        struct_base = check_structure(analysis_baseline)

        # LLM-as-judge
        print("    → Judging...", end="", flush=True)
        scores_rag = judge(analysis_rag, scenario, client)
        scores_base = judge(analysis_baseline, scenario, client)
        print(" done\n")

        rag_total = sum(v for k, v in scores_rag.items() if k != "overall_comment")
        base_total = sum(v for k, v in scores_base.items() if k != "overall_comment")

        print(f"    {'Criterion':<20} {'RAG':>6} {'Baseline':>10}")
        print(f"    {'-'*38}")
        for k in ["age_appropriate", "rag_grounded", "actionable", "safety_flag", "tone"]:
            print(f"    {k:<20} {scores_rag[k]:>6} {scores_base[k]:>10}")
        print(f"    {'─'*38}")
        print(f"    {'TOTAL (/15)':<20} {rag_total:>6} {base_total:>10}")
        print(f"    Sections present: RAG={sum(struct_rag.values())}/4  Baseline={sum(struct_base.values())}/4")
        print(f"    RAG comment:      {scores_rag['overall_comment']}")
        print(f"    Baseline comment: {scores_base['overall_comment']}")
        print()

        results.append({
            "scenario": scenario["id"],
            "description": scenario["description"],
            "rag": {
                "structure": struct_rag,
                "scores": scores_rag,
                "total": rag_total,
                "analysis": analysis_rag,
            },
            "baseline": {
                "structure": struct_base,
                "scores": scores_base,
                "total": base_total,
                "analysis": analysis_baseline,
            },
            "rag_improvement": rag_total - base_total,
        })

    # Summary
    avg_rag = sum(r["rag"]["total"] for r in results) / len(results)
    avg_base = sum(r["baseline"]["total"] for r in results) / len(results)
    avg_delta = avg_rag - avg_base

    print(f"{'='*60}")
    print(f"  SUMMARY ({len(results)} scenarios)")
    print(f"  Average score — RAG: {avg_rag:.1f}/15  |  Baseline: {avg_base:.1f}/15")
    print(f"  RAG improvement:     +{avg_delta:.1f} points ({avg_delta/15*100:.0f}%)")
    print(f"{'='*60}\n")

    # Persist results
    out_dir = Path("evals/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"eval_{ts}.json"
    with open(out_path, "w") as f:
        json.dump({
            "model": CLAUDE_MODEL,
            "run_at": ts,
            "summary": {"avg_rag": avg_rag, "avg_baseline": avg_base, "avg_delta": avg_delta},
            "scenarios": results,
        }, f, indent=2, default=str)
    print(f"📁  Results saved to {out_path}")


if __name__ == "__main__":
    main()
