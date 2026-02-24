# 🍼 BabyTrack

> **Portfolio project — Solutions Architect @ Anthropic**
> Demonstrating how RAG + Claude can be deployed responsibly in a regulated, high-stakes domain.

---

## The idea

A paediatrician has limited time. A new parent has infinite anxiety. There's a gap.

BabyTrack closes it: an infant feeding tracker that doesn't just store data, but analyses it — grounded in WHO and SFP medical guidelines — and surfaces personalised, actionable recommendations via Claude.

The real point isn't the app. It's what building it required me to think about:

- How do you ground an LLM in a specific knowledge base without hallucination risk?
- How do you measure whether the grounding actually helps?
- How do you build an API that an enterprise team could extend, not just a demo that runs on localhost?

---

## What it does

| Feature | What you can do |
|---------|-----------------|
| **📝 Feeding log** | Record bottle/breastfeeding with timestamps, volumes, notes. Edit or delete any entry. |
| **⚖️ Weight tracking** | Log growth checkpoints. View historical data and trends. |
| **📊 Analytics** | Visualise 7–30 day feeding patterns: volume trends, frequency, type breakdown. |
| **📥 CSV export** | Download all feeding data for external analysis or sharing. |
| **🤖 AI analysis** | Claude-powered recommendations grounded in WHO/SFP guidelines via RAG. Shows which medical documents were cited. |
| **✅ Quality evaluation** | LLM-as-judge framework scores output quality. Demonstrates RAG value vs baseline. |
| **🔌 REST API** | Full CRUD on babies, feedings, weights. OpenAPI auto-docs. Production-ready async architecture. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       STREAMLIT UI                          │
│  Dashboard · Feeding entry · AI Analysis                    │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI (main.py)                        │
│  POST /babies   POST /feedings   GET /analysis/{id}        │
│  GET  /babies   GET  /feedings   GET /health               │
└───────────┬─────────────────────────┬───────────────────────┘
            │                         │
            ▼                         ▼
┌───────────────────┐     ┌───────────────────────────────────┐
│  SQLite           │     │         RAG PIPELINE               │
│  ─────────────── │     │                                   │
│  babies           │     │  data/docs/                       │
│  feedings         │     │  ├── who_infant_feeding.md        │
└───────────────────┘     │  └── sfp_infant_feeding_guide.md  │
                          │           │                        │
                          │    LlamaIndex VectorStoreIndex     │
                          │    (BAAI/bge-small-en-v1.5)       │
                          │           │  top-k chunks          │
                          │           ▼                        │
                          │  ┌─────────────────────┐          │
                          │  │  Claude Haiku        │          │
                          │  │  (Anthropic API)     │          │
                          │  └─────────────────────┘          │
                          └───────────────────────────────────┘
```

### Why RAG here?

A generic LLM knows roughly what WHO recommendations say. A RAG-grounded LLM cites the *specific thresholds and intervals* from the actual guidelines — the difference between "drink more water" and "a 7-day-old should receive 60–90 ml per feed every 2–3 hours."

In a regulated domain (medical, legal, financial), that precision gap is the entire value proposition of RAG.

---

## Evaluation framework

Before shipping any LLM feature to production, the right question is: *how do you know it's giving good answers?*

The `evals/` folder answers this. An LLM-as-judge script runs 3 clinical scenarios (healthy newborn, low-intake alert, mixed feeding) and scores each Claude response across 5 criteria, with and without RAG context:

| Criterion | What it checks |
|-----------|---------------|
| `age_appropriate` | References norms specific to the baby's age |
| `rag_grounded` | Reflects retrieved WHO/SFP guidelines, not generic knowledge |
| `actionable` | Recommendations are concrete and immediately usable |
| `safety_flag` | Correctly raises or withholds a clinical concern |
| `tone` | Reassuring when warranted; appropriately concerned when not |

```bash
python evals/eval_analysis.py
# → Scores per scenario, RAG vs baseline delta, saved to evals/results/
```

Results from a sample run:

```
Average score — RAG: 15.0/15  |  Baseline: 14.7/15
RAG improvement: +0.3 points across scenarios
Sections present: 4/4 on all runs
```

The eval framework is as important as the application itself — it's the scaffolding you'd build with any enterprise customer before a production go-live.

> See `evals/README.md` for the full methodology and how to extend it.

---

## Enterprise considerations

This is a portfolio demo, but the architecture decisions reflect real deployment constraints:

| Concern | Decision made | Enterprise path |
|---------|--------------|-----------------|
| **Data isolation** | SQLite per deployment | Swap to PostgreSQL; one schema per tenant |
| **Hallucination risk** | RAG-grounded prompts + structural output format | Eval suite + human review for high-stakes outputs |
| **Observability** | Structured logging, token counts captured | Feed into Datadog / CloudWatch |
| **Auth** | Not implemented | Add OAuth2 / SSO at the API gateway layer |
| **Index freshness** | Manual rebuild | Trigger on document update via webhook |
| **Cost control** | Haiku model, 1024 max tokens | Budget alerts + model tiering by use case |

---

## Features added in v0.4

- ✅ **Full CRUD for feedings** — create, read, update, delete with inline edit forms
- ✅ **Weight tracking** — record growth checkpoints, view history
- ✅ **CSV export** — download feeding data for external analysis
- ✅ **RAG source attribution** — see which medical guideline each recommendation comes from
- ✅ **Streamlit UI overhaul** — custom theme, responsive layout, edit/delete buttons, tabs for different data types
- ✅ **Eval framework** — LLM-as-judge scoring on 5 criteria; RAG vs baseline comparison
- ✅ **README rewrite** — SA/business-focused narrative + architecture diagrams

---

## Running locally

```bash
# 1. Install & activate
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. API key
cp .env.example .env
# Edit .env → add ANTHROPIC_API_KEY

# 3. Start services
uvicorn main:app --reload
# (in another terminal)
streamlit run ui/app.py
```

Open UI: **http://localhost:8501**  
API docs: **http://localhost:8000/docs**

---

## Tests

```bash
pytest tests/ -v
# 74 tests · 0 failures · zero network calls
```

| Suite | Tests | What's covered |
|-------|-------|---------------|
| Data layer — Feedings | 21 | CRUD, filtering by day/range, cascade deletes |
| Data layer — Weights | 9 | Add, get, update, delete, range queries |
| RAG pipeline | 18 | Indexer, retriever, analyzer (MockEmbedding + mock Anthropic) |
| FastAPI | 20+ | Feedings, weights, babies, analysis endpoints; PATCH/DELETE |

---

## Project structure

```
babytrack/
├── main.py                  # FastAPI entry point + lifespan
├── app/
│   ├── models/              # Pydantic v2 — Baby, Feeding
│   ├── services/            # Async CRUD (aiosqlite)
│   ├── rag/                 # LlamaIndex — indexer, retriever, analyzer
│   └── api/routes/          # health, babies, feedings, analysis
├── evals/                   # LLM-as-judge eval framework
│   ├── eval_analysis.py     # 3 scenarios · 5 criteria · RAG vs baseline
│   └── results/             # JSON results per run
├── ui/
│   ├── app.py               # Streamlit dashboard
│   └── api_client.py        # HTTP wrapper
└── data/
    ├── docs/                # WHO/SFP medical guidelines (markdown)
    └── index/               # Persisted vector index (gitignored)
```

---

## Key technical decisions

| Decision | Rationale |
|----------|-----------|
| **FastAPI** | Native async, auto OpenAPI, Pydantic validation — what most enterprise Python teams are standardising on |
| **SQLite + aiosqlite** | Zero-config for a demo; same service layer works with PostgreSQL |
| **LlamaIndex** | Mature RAG abstraction with index persistence — not reinventing retrieval |
| **BAAI/bge-small-en-v1.5** | 130 MB, runs offline, multilingual — no embedding API dependency |
| **Structured prompt output** | Fixed markdown sections make parsing and eval deterministic |
| **LLM-as-judge** | Industry-standard pattern for scalable output evaluation without human labellers |

---

## Deployment (Render)

`render.yaml` is included — two services (API + UI), auto-deployed from GitHub.

```bash
# Fork → connect Render → "New Blueprint" → add ANTHROPIC_API_KEY → deploy
```

> ⚠️ Free tier uses ephemeral storage. For persistence, swap SQLite for Render PostgreSQL (one config change in `database.py`).

---

*Built as part of an SA Applied AI portfolio — Anthropic Paris.*
*The goal was not to build a baby app. The goal was to build something that shows how I think about RAG architecture, eval, and production deployment.*
