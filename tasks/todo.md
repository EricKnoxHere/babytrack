# BabyTrack — Task Board

## Status
- [ ] = pending
- [x] = done
- [~] = in progress
- [!] = blocked

---

## Phase 1 — Data Layer ✅

### Models
- [x] Créer `app/models/baby.py` — modèle Baby (nom, date de naissance, poids initial)
- [x] Créer `app/models/feeding.py` — modèle Feeding (timestamp, quantité ml, type biberon/allaitement)
- [x] Créer `app/services/database.py` — init SQLite, create_tables()
- [x] Écrire migrations initiales (CREATE TABLE IF NOT EXISTS dans database.py)

### CRUD
- [x] `app/services/baby_service.py` — create, get, update, delete baby
- [x] `app/services/feeding_service.py` — add_feeding, get_feedings_by_day, get_feedings_by_range
- [x] Tests unitaires pour les services (tests/) — 21/21 passed

---

## Phase 2 — RAG Pipeline ✅

### Knowledge Base
- [x] Guides OMS alimentation nourrisson → `data/docs/oms_alimentation_nourrisson.md`
- [x] Guide SFP (Société Française de Pédiatrie) → `data/docs/sfp_guide_alimentation_nourrisson.md`
- [x] Stockés en markdown structuré dans `data/docs/`

### LlamaIndex
- [x] Installer dépendances : llama-index-core, llama-index-llms-anthropic, llama-index-embeddings-huggingface, anthropic
- [x] Créer `app/rag/indexer.py` — ingestion et indexation (VectorStoreIndex, persistance)
- [x] Créer `app/rag/retriever.py` — recherche sémantique + format_context
- [x] Créer `app/rag/analyzer.py` — analyse biberons via Claude + contexte RAG
- [x] Tests : 18/18 passés (MockEmbedding, mock Anthropic, zéro réseau)

---

## Phase 3 — API FastAPI ✅

### Endpoints
- [x] `POST /babies` — créer un bébé
- [x] `POST /feedings` — enregistrer un biberon
- [x] `GET /feedings/{baby_id}` — historique biberons (filtres: day, start/end)
- [x] `GET /analysis/{baby_id}` — analyse IA de la journée/semaine
- [x] `GET /health` — healthcheck

### Intégration
- [x] Brancher analyzer RAG sur l'endpoint `/analysis`
- [x] Gestion des erreurs et validation (Pydantic)
- [x] Tests d'intégration API (20/20 passent)

---

## Phase 4 — UI Streamlit

### Dashboard
- [x] Page d'accueil — saisie biberon rapide
- [x] Graphique biberons/jour (quantité et fréquence)
- [x] Section analyse IA — résumé quotidien
- [!] Courbe de poids — nécessite une table weight_entries (post-MVP)

### Polish portfolio
- [x] README.md — architecture RAG documentée avec schéma
- [x] Config déploiement Render (render.yaml + .env.example)
- [ ] Screenshot/GIF pour le portfolio

---

## Backlog (post-MVP)
- [ ] Suivi couches
- [ ] Suivi sommeil
- [ ] Multi-enfants
- [ ] Authentification

---

## Review

### Phase 1 — 2026-02-23
- 19/19 tests unitaires passent (pytest-asyncio, DB en mémoire)
- Models Pydantic v2 : Baby, BabyCreate, BabyUpdate, Feeding, FeedingCreate, FeedingUpdate
- Services async aiosqlite : CRUD complet + get_by_day + get_by_range + cascade delete
- Foreign keys SQLite activées, schéma strict (CHECK constraints)
- Virtualenv `.venv` avec toutes les dépendances installées