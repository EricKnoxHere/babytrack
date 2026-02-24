# BabyTrack — Evaluation Framework

> *"How do you know Claude is giving good answers?"*
> This is the first question any enterprise customer will ask before going to production.
> This folder answers it.

---

## What it measures

The eval script runs **3 clinical scenarios** (healthy newborn, low-intake alert, mixed feeding)
and scores each Claude response on a structured rubric — both **with and without RAG context**
— to quantify the value of grounding.

### Scoring rubric (LLM-as-judge, 0–3 per criterion)

| Criterion | What it checks |
|-----------|---------------|
| `age_appropriate` | Does the analysis cite norms specific to the baby's age? |
| `rag_grounded` | Does it reflect WHO/SFP recommendations from the retrieved context? |
| `actionable` | Are the recommendations concrete and immediately usable? |
| `safety_flag` | Does it correctly raise (or withhold) a clinical concern? |
| `tone` | Reassuring when data is normal; appropriately concerned when not |

**Max score: 15 per scenario.**
The judge is Claude itself — a standard LLM-as-judge pattern used in production eval pipelines.

---

## Running the evals

```bash
cd ~/Documents/babytrack
source .venv/bin/activate
python evals/eval_analysis.py
```

Results are printed to stdout and saved as JSON in `evals/results/eval_<timestamp>.json`.

> ⚠️ Each run makes ~9 Claude API calls (3 scenarios × 2 variants + 3 judges).
> Cost: < $0.01 with claude-haiku.

---

## What the output looks like

```
============================================================
  BabyTrack — Evaluation Run
  Model: claude-haiku-4-5-20251001
============================================================

📋  Scenario: newborn_healthy
    7-day-old, volumes and frequency within WHO norms
    → Running with RAG...    done
    → Running without RAG... done
    → Judging...             done

    Criterion               RAG   Baseline
    --------------------------------------
    age_appropriate           3          2
    rag_grounded              3          1
    actionable                3          2
    safety_flag               3          3
    tone                      3          2
    ──────────────────────────────────────
    TOTAL (/15)              15         10
    Sections present: RAG=4/4  Baseline=4/4
    RAG comment:      Excellent age-specific analysis with clear WHO references.
    Baseline comment: Reasonable but generic — lacks specific volume thresholds.

============================================================
  SUMMARY (3 scenarios)
  Average score — RAG: 14.0/15  |  Baseline: 9.7/15
  RAG improvement:     +4.3 points (29%)
============================================================
```

---

## Why this matters (SA perspective)

Before deploying any LLM in a regulated or high-stakes domain, customers need to answer:

1. **Is the output correct?** — structural checks ensure required sections are always present
2. **Is it grounded?** — RAG vs baseline comparison quantifies hallucination risk reduction
3. **Does it catch edge cases?** — the low-intake scenario tests safety-critical detection
4. **Can we track quality over time?** — JSON results enable regression testing across model versions

This framework demonstrates the eval-first mindset that production AI deployments require
— and maps directly to how you'd help an enterprise customer build confidence before go-live.

---

## Extending this framework

Real-world additions for enterprise deployment:

- **Human baseline**: have a paediatrician score the same outputs to calibrate the judge
- **Regression suite**: run on every model upgrade to catch quality regressions
- **Latency + cost tracking**: add `usage.input_tokens` / `output_tokens` to the results JSON
- **Domain-specific scenarios**: e.g. premature infants, CMPA cases, post-surgery recovery
- **A/B prompt testing**: compare prompt variants systematically before shipping changes
