# 🍼 BabyTrack

> **Portfolio project** — Solutions Architect @ Anthropic  
> Démonstration de RAG en production : FastAPI + SQLite + LlamaIndex + Claude

---

## ✨ Ce que ça fait

BabyTrack est une application de suivi d'alimentation nourrisson avec **analyse IA personnalisée**.

- 📝 **Enregistrer** chaque biberon (type, volume, heure)
- 📊 **Visualiser** la consommation du jour et les tendances sur 7–14 jours
- 🤖 **Analyser** les données via Claude, enrichi par des recommandations OMS/SFP (RAG)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       STREAMLIT UI                          │
│  Dashboard · Saisie biberon · Analyse IA                    │
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
│  feedings         │     │  ├── oms_alimentation.md          │
└───────────────────┘     │  └── sfp_guide.md                 │
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

### Flux d'analyse IA

1. L'endpoint `GET /analysis/{baby_id}` reçoit `period=day|week`
2. Les biberons sont récupérés depuis SQLite
3. Une **query RAG** est construite (âge du bébé + type d'alimentation)
4. LlamaIndex récupère les **top-4 chunks** pertinents OMS/SFP
5. Un prompt structuré est envoyé à **Claude** avec le contexte médical
6. La réponse markdown est retournée et affichée dans l'UI

---

## 🚀 Lancer le projet

```bash
# 1. Installer les dépendances
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configurer la clé API Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Construire l'index RAG (une seule fois)
python -c "from app.rag.indexer import build_index; build_index()"

# 4. Démarrer l'API
uvicorn main:app --reload

# 5. Démarrer l'UI (nouveau terminal)
streamlit run ui/app.py
```

Ouvrir : http://localhost:8501

---

## 🧪 Tests

```bash
pytest tests/ -v
# 59 tests · 0 échec · zéro appel réseau
```

| Phase | Tests | Couverture |
|-------|-------|------------|
| Data Layer (SQLite CRUD) | 21 | Models, services async |
| RAG Pipeline (LlamaIndex + Claude) | 18 | Indexer, retriever, analyzer (mocks) |
| API FastAPI | 20 | Tous les endpoints, cas d'erreur |

---

## 📁 Structure

```
babytrack/
├── main.py                  # Entry point FastAPI + lifespan
├── app/
│   ├── models/              # Pydantic v2 — Baby, Feeding
│   ├── services/            # CRUD async (aiosqlite)
│   ├── rag/                 # LlamaIndex — indexer, retriever, analyzer
│   └── api/
│       ├── dependencies.py  # Injection DB + RAG
│       └── routes/          # health, babies, feedings, analysis
├── ui/
│   ├── app.py               # Streamlit dashboard
│   └── api_client.py        # Wrapper HTTP
├── data/
│   ├── docs/                # Guides médicaux OMS/SFP (markdown)
│   └── index/               # Index vectoriel persisté (gitignored)
└── tests/                   # pytest · asyncio_mode=auto
```

---

## 🔑 Choix techniques

| Choix | Pourquoi |
|-------|---------|
| **FastAPI** | Async natif, OpenAPI auto-générée, validation Pydantic |
| **SQLite + aiosqlite** | Zero-config, démo portable, foreign keys strict |
| **LlamaIndex** | Abstraction RAG mature, persistance d'index, top-k configurable |
| **BAAI/bge-small-en-v1.5** | Embeddings légers (130 MB), multilingues, hors-ligne |
| **Claude 3 Haiku** | Rapide, économique, excellent en analyse structurée |
| **Streamlit** | Démo interactive rapide, idéal portfolio |

---

## 📌 Roadmap

- [x] Phase 1 — Data Layer (SQLite CRUD)
- [x] Phase 2 — RAG Pipeline
- [x] Phase 3 — API FastAPI
- [x] Phase 4 — UI Streamlit
- [ ] Déploiement démo (Render / Railway)
- [ ] Multi-enfants · Suivi sommeil · Auth

---

*Projet développé dans le cadre d'un dossier SA Applied AI — Anthropic Paris.*
