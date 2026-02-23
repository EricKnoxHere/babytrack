# BabyTrack — Task Board

## Status
- [ ] = pending
- [x] = done
- [~] = in progress
- [!] = blocked

---

## Phase 1 — Data Layer ✅

### Models
- [x] Create `app/models/baby.py` — Baby model (name, date of birth, birth weight)
- [x] Create `app/models/feeding.py` — Feeding model (timestamp, quantity ml, type bottle/breastfeeding)
- [x] Create `app/services/database.py` — SQLite init, create_tables()
- [x] Write initial migrations (CREATE TABLE IF NOT EXISTS in database.py)

### CRUD
- [x] `app/services/baby_service.py` — create, get, update, delete baby
- [x] `app/services/feeding_service.py` — add_feeding, get_feedings_by_day, get_feedings_by_range
- [x] Unit tests for services (tests/) — 21/21 passed

---

## Phase 2 — RAG Pipeline ✅

### Knowledge Base
- [x] WHO infant feeding guidelines → `data/docs/oms_alimentation_nourrisson.md`
- [x] SFP (French Paediatric Society) guide → `data/docs/sfp_guide_alimentation_nourrisson.md`
- [x] Stored as structured markdown in `data/docs/`

### LlamaIndex
- [x] Install dependencies: llama-index-core, llama-index-llms-anthropic, llama-index-embeddings-huggingface, anthropic
- [x] Create `app/rag/indexer.py` — ingestion and indexing (VectorStoreIndex, persistence)
- [x] Create `app/rag/retriever.py` — semantic search + format_context
- [x] Create `app/rag/analyzer.py` — feeding analysis via Claude + RAG context
- [x] Tests: 18/18 passed (MockEmbedding, mock Anthropic, zero network)

---

## Phase 3 — FastAPI ✅

### Endpoints
- [x] `POST /babies` — create a baby
- [x] `POST /feedings` — log a feeding
- [x] `GET /feedings/{baby_id}` — feeding history (filters: day, start/end)
- [x] `GET /analysis/{baby_id}` — AI analysis for the day/week
- [x] `GET /health` — health check

### Integration
- [x] Wire RAG analyzer to `/analysis` endpoint
- [x] Error handling and validation (Pydantic)
- [x] API integration tests (20/20 passing)

---

## Phase 4 — Streamlit UI ✅

### Dashboard
- [x] Home page — quick feeding entry
- [x] Feedings per day chart (volume and frequency)
- [x] AI analysis section — daily summary
- [!] Weight curve — requires a weight_entries table (post-MVP)

### Portfolio polish
- [x] README.md — documented RAG architecture with diagram
- [x] Render deployment config (render.yaml + .env.example)
- [ ] Screenshot/GIF for the portfolio

---

## Backlog (post-MVP)
- [ ] Diaper tracking
- [ ] Sleep tracking
- [ ] Multiple children
- [ ] Authentication

---

## Review

### Phase 1 — 2026-02-23
- 19/19 unit tests passing (pytest-asyncio, in-memory DB)
- Pydantic v2 models: Baby, BabyCreate, BabyUpdate, Feeding, FeedingCreate, FeedingUpdate
- Async aiosqlite services: full CRUD + get_by_day + get_by_range + cascade delete
- SQLite foreign keys enabled, strict schema (CHECK constraints)
- Virtualenv `.venv` with all dependencies installed
