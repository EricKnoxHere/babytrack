# BabyTrack — Task Board

## Status
- [ ] = pending
- [x] = done
- [~] = in progress

---

## Completed

### Data Layer
- [x] Baby CRUD (create, get, update, delete)
- [x] Feeding CRUD + filtering by day/range
- [x] Diaper CRUD + filtering by day/range
- [x] Weight CRUD + range queries
- [x] Conversation & message storage
- [x] Report generation & caching
- [x] SQLite schema with FK constraints

### RAG Pipeline
- [x] SFP medical guidelines indexed (LlamaIndex + bge-small-en-v1.5)
- [x] Semantic retrieval + context formatting
- [x] Claude-powered analysis grounded in guidelines
- [x] Source attribution in responses

### API (FastAPI)
- [x] Full REST CRUD: babies, feedings, diapers, weights
- [x] AI analysis endpoint
- [x] Conversation/chat endpoints
- [x] Health check

### UI (Streamlit)
- [x] Home dashboard
- [x] Feeding/diaper/weight recording
- [x] AI chat interface
- [x] Mobile-optimised layout

### Eval Framework
- [x] LLM-as-judge (3 scenarios, 5 criteria)
- [x] RAG vs baseline comparison

### Deployment
- [x] Self-hosted via ngrok tunnel (static domain)
- [x] CSV import scripts (Romane data)

### Tests
- [x] 151 tests across 8 suites (zero network calls)

---

## Backlog
- [ ] Sleep tracking
- [ ] Growth curve visualisation (percentiles)
- [ ] Multi-user authentication
- [ ] Push notifications (feeding reminders)
- [ ] Screenshot/GIF for portfolio
