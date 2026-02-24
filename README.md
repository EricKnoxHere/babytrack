# 🍼 BabyTrack

> **Portfolio project — Solutions Architect, Applied AI @ Anthropic**

BabyTrack is a production-grade RAG application built to demonstrate how Claude can be integrated into a regulated-data context — from architecture design to evaluation framework.

**The premise:** parents of newborns track every feeding (time, volume, type) but have no way to interpret that data against medical guidelines. BabyTrack closes that gap: it retrieves relevant WHO/SFP recommendations at query time and uses Claude to turn raw feeding logs into structured, personalised guidance.

→ **[Live demo](#)** · [Eval results](#-evaluation-framework)

---

## What this project demonstrates

This isn't just a working app — it's designed to reflect the decisions an SA would need to make and explain when helping an enterprise customer adopt Claude.

| Skill | Implementation |
|-------|---------------|
| **RAG architecture** | LlamaIndex + HuggingFace embeddings, persisted vector index, configurable top-k retrieval |
| **Claude integration** | Structured prompting, grounded on retrieved context, error handling for production |
| **Evaluation framework** | LLM-as-judge scoring (5 criteria), RAG vs baseline comparison — [`evals/`](evals/README.md) |
| **API design** | FastAPI with async SQLite, Pydantic v2 validation, dependency injection |
| **Deployment readiness** | Render config, `.env` management, 59 tests · 0 failures · zero network calls |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       STREAMLIT UI                          │
│  Feeding entry · Dashboard · AI Analysis                    │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI (main.py)                        │
│  POST /babies  ·  POST /feedings  ·  GET /analysis/{id}    │
└───────────┬─────────────────────────┬───────────────────────┘
            │                         │
            ▼                         ▼
┌───────────────────┐     ┌───────────────────────────────────┐
│  SQLite           │     │         RAG PIPELINE               │
│  (aiosqlite)      │     │                                   │
│  ─────────────    │     │  data/docs/                       │
│  babies           │     │  ├── who_infant_feeding.md        │
│  feedings         │     │  └── sfp_infant_feeding_guide.md  │
└───────────────────┘     │           │                        │
                          │           ▼                        │
                          │  LlamaIndex VectorStoreIndex       │
                          │  BAAI/bge-small-en-v1.5            │
                          │           │ top-4 chunks           │
                          │           ▼                        │
                          │  ┌─────────────────────┐          │
                          │  │     Claude Haiku     │          │
                          │  │  Structured prompt   │          │
                          │  └─────────────────────┘          │
                          └───────────────────────────────────┘
```

### Analysis flow (step by step)

1. `GET /analysis/{baby_id}?period=day` fetches feedings from SQLite
2. A **RAG query** is built dynamically: baby's age + feeding type → semantic search
3. LlamaIndex retrieves the **top-4 relevant chunks** from WHO/SFP medical guides
4. A structured prompt is sent to **Claude** with baby profile + feedings + medical context
5. Claude returns a markdown analysis (positives · attention points · recommendations · summary)
6. The response is displayed in the Streamlit UI

---

## 📊 Evaluation framework

One of the hardest questions in enterprise LLM adoption is: *"How do we know it's working?"*

BabyTrack includes a full evaluation framework in [`evals/`](evals/README.md) that addresses this directly:

- **LLM-as-judge** — Claude scores its own outputs against a 5-criterion rubric
- **RAG vs baseline** — quantified comparison: analysis with vs without medical context
- **Targeted test cases** — normal newborn, low-intake warning, 2-month milestone

```
Test case                      RAG   Baseline   Uplift
─────────────────────────────────────────────────────
newborn_normal                 9/10      7/10      +2
newborn_low_volume             8/10      5/10      +3
infant_2months_normal          9/10      7/10      +2
─────────────────────────────────────────────────────
Average                        8.7/10    6.3/10    +2.3
```

> These are illustrative scores — run `python evals/eval_analysis.py` for live results against the deployed model.

---

## Key technical decisions

| Decision | Rationale |
|----------|-----------|
| **FastAPI + async** | Native async matches aiosqlite; auto-generated OpenAPI simplifies customer integration demos |
| **SQLite → PostgreSQL path** | SQLite for zero-config portability; the service layer is DB-agnostic for easy migration |
| **LlamaIndex** | Mature RAG abstraction with index persistence — reduces cold-start latency from ~40s to <1s after first run |
| **BAAI/bge-small-en-v1.5** | 130 MB, runs fully offline — no embedding API dependency, relevant for enterprise data privacy requirements |
| **Claude Haiku** | Fast and cost-effective for structured analysis; easily swappable to Sonnet/Opus for higher-stakes domains |
| **Streamlit** | Rapid interactive demo surface; in production this would be replaced by a customer's existing frontend |

### How this scales to enterprise

A customer integrating this pattern into their stack would typically need to address:

- **Data privacy** — embeddings computed locally (no data leaves the perimeter)
- **Knowledge base refresh** — LlamaIndex supports incremental indexing; guideline updates don't require full reindex
- **Multi-tenancy** — the current SQLite model maps cleanly to a PostgreSQL schema with tenant isolation
- **Observability** — add eval runs to CI/CD to catch quality regressions on prompt or model changes

---

## Running locally

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# → Add your ANTHROPIC_API_KEY

# 3. Start the API
uvicorn main:app --reload

# 4. Start the UI (new terminal)
streamlit run ui/app.py
# → http://localhost:8501
```

---

## Tests

```bash
pytest tests/ -v
# 59 tests · 0 failures · zero network calls
```

| Layer | Tests | What's covered |
|-------|-------|----------------|
| Data layer | 21 | Async CRUD, cascade delete, edge cases |
| RAG pipeline | 18 | Indexer, retriever, analyzer (MockEmbedding + mock Anthropic) |
| API | 20 | All endpoints, validation, error cases |

---

## Deployment (Render)

The repo includes a `render.yaml` for one-click deployment (API + UI as separate services).

```bash
# 1. Fork the repo · Connect Render to GitHub
# 2. New Blueprint → point to repo → Render detects render.yaml
# 3. Set ANTHROPIC_API_KEY in the Render dashboard
# 4. Deploy
```

> On Render's free tier, SQLite is ephemeral — data resets on restart. Sufficient for a portfolio demo; production would use a managed PostgreSQL instance.

---

## Project structure

```
babytrack/
├── main.py                  # FastAPI entry point + lifespan (DB init, RAG index load)
├── app/
│   ├── models/              # Pydantic v2 — Baby, Feeding
│   ├── services/            # Async CRUD (aiosqlite)
│   ├── rag/                 # indexer · retriever · analyzer
│   └── api/routes/          # health · babies · feedings · analysis
├── evals/                   # Evaluation framework (LLM-as-judge + RAG comparison)
├── ui/
│   ├── app.py               # Streamlit dashboard (3 pages)
│   └── api_client.py        # Typed HTTP wrapper
└── data/
    ├── docs/                # WHO/SFP medical guides (markdown)
    └── index/               # Persisted vector index (gitignored)
```

---

*Built as part of an SA Applied AI portfolio — Anthropic Paris.*
