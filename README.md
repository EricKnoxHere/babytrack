# 🍼 BabyTrack

> **Portfolio project** — Solutions Architect @ Anthropic  
> Production RAG demonstration: FastAPI + SQLite + LlamaIndex + Claude

---

## ✨ What it does

BabyTrack is an infant feeding tracker with **personalized AI analysis**.

- 📝 **Record** every feeding (type, volume, time)
- 📊 **Visualize** daily intake and 7–14-day trends
- 🤖 **Analyze** data via Claude, enriched by WHO/SFP recommendations (RAG)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       STREAMLIT UI                          │
│  Dashboard · Feeding entry · AI Analysis                    │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP (requests)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI (main.py)                        │
│                                                             │
│  GET /health          POST /babies        POST /feedings    │
│  GET /babies          GET  /babies/{id}   GET  /feedings/   │
│  GET /analysis/{id}                                         │
└───────────┬─────────────────────────┬───────────────────────┘
            │                         │
            ▼                         ▼
┌───────────────────┐     ┌───────────────────────────────────┐
│  SQLite (aiosqlite│     │         RAG PIPELINE               │
│  ─────────────── │     │                                   │
│  babies           │     │  data/docs/                       │
│  feedings         │     │  ├── who_infant_feeding.md        │
└───────────────────┘     │  └── sfp_infant_feeding_guide.md  │
                          │           │                        │
                          │           ▼                        │
                          │  LlamaIndex VectorStoreIndex       │
                          │  (BAAI/bge-small-en-v1.5)         │
                          │           │                        │
                          │           ▼ top-k chunks           │
                          │  ┌─────────────────────┐          │
                          │  │  Claude 3 Haiku      │          │
                          │  │  (Anthropic API)     │          │
                          │  └─────────────────────┘          │
                          └───────────────────────────────────┘
```

### AI Analysis Flow

1. The `GET /analysis/{baby_id}` endpoint receives `period=day|week`
2. Feedings are fetched from SQLite
3. A **RAG query** is built (baby age + feeding type)
4. LlamaIndex retrieves the **top-4 relevant chunks** from WHO/SFP guides
5. A structured prompt is sent to **Claude** with the medical context
6. The markdown response is returned and displayed in the UI

---

## 🚀 Running the project

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure the Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Build the RAG index (one-time)
python -c "from app.rag.indexer import build_index; build_index()"

# 4. Start the API
uvicorn main:app --reload

# 5. Start the UI (new terminal)
streamlit run ui/app.py
```

Open: http://localhost:8501

---

## 🧪 Tests

```bash
pytest tests/ -v
# 59 tests · 0 failures · zero network calls
```

| Phase | Tests | Coverage |
|-------|-------|----------|
| Data Layer (SQLite CRUD) | 21 | Models, async services |
| RAG Pipeline (LlamaIndex + Claude) | 18 | Indexer, retriever, analyzer (mocks) |
| FastAPI API | 20 | All endpoints, error cases |

---

## 📁 Structure

```
babytrack/
├── main.py                  # FastAPI entry point + lifespan
├── app/
│   ├── models/              # Pydantic v2 — Baby, Feeding
│   ├── services/            # Async CRUD (aiosqlite)
│   ├── rag/                 # LlamaIndex — indexer, retriever, analyzer
│   └── api/
│       ├── dependencies.py  # DB + RAG injection
│       └── routes/          # health, babies, feedings, analysis
├── ui/
│   ├── app.py               # Streamlit dashboard
│   └── api_client.py        # HTTP wrapper
├── data/
│   ├── docs/                # WHO/SFP medical guides (markdown)
│   └── index/               # Persisted vector index (gitignored)
└── tests/                   # pytest · asyncio_mode=auto
```

---

## 🔑 Technical decisions

| Decision | Why |
|----------|-----|
| **FastAPI** | Native async, auto-generated OpenAPI, Pydantic validation |
| **SQLite + aiosqlite** | Zero-config, portable demo, strict foreign keys |
| **LlamaIndex** | Mature RAG abstraction, index persistence, configurable top-k |
| **BAAI/bge-small-en-v1.5** | Lightweight embeddings (130 MB), multilingual, offline |
| **Claude 3 Haiku** | Fast, cost-effective, excellent for structured analysis |
| **Streamlit** | Rapid interactive demo, ideal for portfolios |

---

## ☁️ Render Deployment

The repo includes a ready-to-use `render.yaml` (2 services: API + UI).

```bash
# 1. Fork the repo on GitHub
# 2. Connect Render to your GitHub account
# 3. "New Blueprint" → point to the repo → Render detects render.yaml
# 4. Add the ANTHROPIC_API_KEY environment variable in the dashboard
# 5. Deploy!
```

> ⚠️ On Render's free tier, SQLite is ephemeral (`/tmp`).
> Data is lost on restart — sufficient for a portfolio demo.

---

## 📌 Roadmap

- [x] Phase 1 — Data Layer (SQLite CRUD)
- [x] Phase 2 — RAG Pipeline
- [x] Phase 3 — FastAPI API
- [x] Phase 4 — Streamlit UI
- [x] Render deployment config (`render.yaml` + `.env.example`)
- [ ] DB persistence (PostgreSQL) · Multi-child · Auth

---

*Project developed as part of an SA Applied AI portfolio — Anthropic Paris.*
