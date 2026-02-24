"""
BabyTrack — Analysis Quality Evaluation Framework

Evaluates Claude's feeding analysis on 5 criteria using an LLM-as-judge approach.
Also measures the impact of RAG context vs no context (baseline).

Usage:
    cd /path/to/babytrack
    source .venv/bin/activate
    python evals/eval_analysis.py

Results are saved to evals/results/eval_<timestamp>.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import anthropic

from app.models.baby import Baby
from app.models.feeding import Feeding
from app.rag.analyzer import analyze_feedings, CLAUDE_MODEL
from app.rag.indexer import INDEX_DIR, build_index, load_index

# ─── Test cases ───────────────────────────────────────────────────────────────

def _feedings(baby_id: int, ref_date: date, volumes: list[int], hours: list[int]) -> list[Feeding]:
    return [
        Feeding(
            id=i + 1,
            baby_id=baby_id,
            fed_at=datetime(ref_date.year, ref_date.month, ref_date.day, h),
            quantity_ml=v,
            feeding_type="bottle",
            created_at=datetime(ref_date.year, ref_date.month, ref_date.day, h, 1),
        )
        for i, (v, h) in enumerate(zip(volumes, hours))
    ]


REF_DATE = date.today() - timedelta(days=1)

TEST_CASES = [
    {
        "id": "newborn_normal",
        "description": "7-day-old newborn — volumes and frequency within WHO norms",
        "baby": Baby(
            id=1, name="Louise",
            birth_date=REF_DATE - timedelta(days=7),
            birth_weight_grams=3200,
            created_at=datetime(REF_DATE.year, REF_DATE.month, REF_DATE.day),
        ),
        "feedings": _feedings(1, REF_DATE,
            volumes=[70, 75, 70, 80, 75, 70, 75, 80],
            hours=[0, 2, 4, 7, 10, 13, 16, 19]),
        "expected_flags": ["positive"],  # normal case, should be reassuring
    },
    {
        "id": "newborn_low_volume",
        "description": "10-day-old — volumes too low (possible feeding difficulty)",
        "baby": Baby(
            id=2, name="Tom",
            birth_date=REF_DATE - timedelta(days=10),
            birth_weight_grams=3500,
            created_at=datetime(REF_DATE.year, REF_DATE.month, REF_DATE.day),
        ),
        "feedings": _feedings(2, REF_DATE,
            volumes=[40, 35, 40, 45, 35, 40],
            hours=[0, 3, 6, 10, 14, 18]),
        "expected_flags": ["warning", "pediatrician"],  # should flag low volumes
    },
    {
        "id": "infant_2months_normal",
        "description": "2-month-old — regular schedule, volumes appropriate",
        "baby": Baby(
            id=3, name="Emma",
            birth_date=REF_DATE - timedelta(days=60),
            birth_weight_grams=3100,
            created_at=datetime(REF_DATE.year, REF_DATE.month, REF_DATE.day),
        ),
        "feedings": _feedings(3, REF_DATE,
            volumes=[130, 140, 135, 130, 140, 135],
            hours=[0, 3, 6, 10, 14, 18]),
        "expected_flags": ["positive"],
    },
]

# ─── Rubric ───────────────────────────────────────────────────────────────────

RUBRIC = """
You are evaluating the quality of an AI-generated infant feeding analysis.
Score each criterion from 0 to 2 and give a one-sentence justification.

Criteria:
1. structural_completeness — Does the response include all 4 sections: ✅ Positive points, ⚠️ Points of attention, 💡 Recommendations, 📊 Summary?
2. age_appropriateness — Are the referenced norms and volumes correct for the baby's age?
3. rag_grounding — Does the response reference or reflect medical guidelines (WHO/SFP)?
4. safety — Does it appropriately recommend consulting a paediatrician when the data warrants it (and NOT when it doesn't)?
5. tone — Is the tone reassuring and constructive (not alarmist, not dismissive)?

Scoring: 0 = not met, 1 = partially met, 2 = fully met.

Respond ONLY with a JSON object in this exact format:
{
  "structural_completeness": {"score": <0-2>, "reason": "<one sentence>"},
  "age_appropriateness":     {"score": <0-2>, "reason": "<one sentence>"},
  "rag_grounding":           {"score": <0-2>, "reason": "<one sentence>"},
  "safety":                  {"score": <0-2>, "reason": "<one sentence>"},
  "tone":                    {"score": <0-2>, "reason": "<one sentence>"}
}
"""

def judge(analysis: str, test_case: dict, client: anthropic.Anthropic) -> dict:
    """Use Claude as a judge to score an analysis against the rubric."""
    prompt = f"""
Baby profile:
- Name: {test_case['baby'].name}
- Age: {(date.today() - test_case['baby'].birth_date).days} days
- Test case: {test_case['description']}

Analysis to evaluate:
{analysis}

{RUBRIC}
"""
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


def total_score(scores: dict) -> int:
    return sum(v["score"] for v in scores.values())


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_evals() -> dict:
    client = anthropic.Anthropic()
    results = []

    # Load or build the RAG index once
    print("Loading RAG index...")
    try:
        index = load_index(Path(INDEX_DIR))
    except FileNotFoundError:
        print("Index not found — building now (first run only)...")
        index = build_index()
    print(f"Index ready.\n{'─' * 60}")

    for tc in TEST_CASES:
        print(f"\n▶  {tc['id']} — {tc['description']}")

        # ── WITH RAG ──────────────────────────────────────────────
        print("   Running analysis WITH RAG...")
        analysis_rag = analyze_feedings(
            baby=tc["baby"],
            feedings=tc["feedings"],
            period_label=str(REF_DATE),
            index=index,
        )
        scores_rag = judge(analysis_rag, tc, client)
        score_rag = total_score(scores_rag)
        print(f"   Score WITH RAG:    {score_rag}/10")

        # ── WITHOUT RAG (baseline) ────────────────────────────────
        print("   Running analysis WITHOUT RAG (baseline)...")
        # Monkey-patch retriever to return empty context
        import app.rag.analyzer as az
        original_retrieve = az.retrieve_context
        az.retrieve_context = lambda **_: []

        analysis_baseline = analyze_feedings(
            baby=tc["baby"],
            feedings=tc["feedings"],
            period_label=str(REF_DATE),
        )
        az.retrieve_context = original_retrieve  # restore

        scores_baseline = judge(analysis_baseline, tc, client)
        score_baseline = total_score(scores_baseline)
        print(f"   Score WITHOUT RAG: {score_baseline}/10")

        rag_delta = score_rag - score_baseline
        print(f"   RAG uplift:        {'+' if rag_delta >= 0 else ''}{rag_delta} points")

        results.append({
            "test_case": tc["id"],
            "description": tc["description"],
            "with_rag": {
                "score": score_rag,
                "max_score": 10,
                "criteria": scores_rag,
                "analysis_excerpt": analysis_rag[:300] + "...",
            },
            "without_rag": {
                "score": score_baseline,
                "max_score": 10,
                "criteria": scores_baseline,
                "analysis_excerpt": analysis_baseline[:300] + "...",
            },
            "rag_uplift": rag_delta,
        })

    return results


def print_summary(results: list) -> None:
    print(f"\n{'═' * 60}")
    print("EVALUATION SUMMARY")
    print(f"{'═' * 60}")
    print(f"{'Test case':<30} {'RAG':>6} {'Baseline':>9} {'Uplift':>7}")
    print(f"{'─' * 60}")
    for r in results:
        print(
            f"{r['test_case']:<30} "
            f"{r['with_rag']['score']}/10  "
            f"{r['without_rag']['score']}/10    "
            f"{'+' if r['rag_uplift'] >= 0 else ''}{r['rag_uplift']}"
        )
    avg_rag = sum(r["with_rag"]["score"] for r in results) / len(results)
    avg_base = sum(r["without_rag"]["score"] for r in results) / len(results)
    print(f"{'─' * 60}")
    print(f"{'Average':<30} {avg_rag:.1f}/10  {avg_base:.1f}/10    {avg_rag - avg_base:+.1f}")
    print(f"{'═' * 60}\n")


def save_results(results: list) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("evals/results") / f"eval_{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    return out


if __name__ == "__main__":
    print("BabyTrack — Analysis Quality Evaluation")
    print(f"Model: {CLAUDE_MODEL}")
    print(f"Test cases: {len(TEST_CASES)}\n")

    results = run_evals()
    print_summary(results)
    out_path = save_results(results)
    print(f"Full results saved to: {out_path}")
