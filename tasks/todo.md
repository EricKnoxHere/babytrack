# BabyTrack — Task Board

## Status
- [ ] = pending
- [x] = done
- [~] = in progress
- [!] = blocked

---

## Phase 1 — Data Layer

### Models
- [ ] Créer `app/models/baby.py` — modèle Baby (nom, date de naissance, poids initial)
- [ ] Créer `app/models/feeding.py` — modèle Feeding (timestamp, quantité ml, type biberon/allaitement)
- [ ] Créer `app/services/database.py` — init SQLite, create_tables()
- [ ] Écrire migrations initiales

### CRUD
- [ ] `app/services/baby_service.py` — create, get, update baby
- [ ] `app/services/feeding_service.py` — add_feeding, get_feedings_by_day, get_feedings_by_range
- [ ] Tests unitaires pour les services (tests/)

---

## Phase 2 — RAG Pipeline

### Knowledge Base
- [ ] Télécharger recommandations OMS alimentation nourrisson (PDF)
- [ ] Télécharger guide SFP (Société Française de Pédiatrie)
- [ ] Convertir PDFs en markdown avec markdown-converter
- [ ] Stocker dans `data/docs/`

### LlamaIndex
- [ ] Installer dépendances : llama-index, anthropic
- [ ] Créer `app/rag/indexer.py` — ingestion et indexation des docs
- [ ] Créer `app/rag/retriever.py` — recherche sémantique
- [ ] Créer `app/rag/analyzer.py` — analyse biberons via Claude + contexte RAG
- [ ] Tests : vérifier que les recommandations OMS sont bien retriévées

---

## Phase 3 — API FastAPI

### Endpoints
- [ ] `POST /babies` — créer un bébé
- [ ] `POST /feedings` — enregistrer un biberon
- [ ] `GET /feedings/{baby_id}` — historique biberons
- [ ] `GET /analysis/{baby_id}` — analyse IA de la journée/semaine
- [ ] `GET /health` — healthcheck

### Intégration
- [ ] Brancher analyzer RAG sur l'endpoint `/analysis`
- [ ] Gestion des erreurs et validation (Pydantic)
- [ ] Tests d'intégration API

---

## Phase 4 — UI Streamlit

### Dashboard
- [ ] Page d'accueil — saisie biberon rapide
- [ ] Graphique biberons/jour (quantité et fréquence)
- [ ] Section analyse IA — résumé quotidien
- [ ] Courbe de poids (si données disponibles)

### Polish portfolio
- [ ] README.md — architecture RAG documentée avec schéma
- [ ] Déploiement démo (Render ou Railway, free tier)
- [ ] Screenshot/GIF pour le portfolio

---

## Backlog (post-MVP)
- [ ] Suivi couches
- [ ] Suivi sommeil
- [ ] Multi-enfants
- [ ] Authentification

---

## Review
_(à remplir après chaque phase)_