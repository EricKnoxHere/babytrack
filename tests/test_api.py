"""Tests d'intégration de l'API FastAPI.

Stratégie :
- Base SQLite en mémoire partagée par tous les tests du module.
- Lifespan du vrai app (main.py) — on override la dépendance DB.
- analyze_feedings mocké pour ne pas appeler Claude / le réseau.
"""

from __future__ import annotations

import pytest
import aiosqlite
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, MagicMock

from app.api.dependencies import db_dependency
from app.services.database import _CREATE_BABIES, _CREATE_FEEDINGS
from main import app


# ---------------------------------------------------------------------------
# Fixture : base SQLite en mémoire partagée pour tout le module
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def mem_db():
    """Connexion SQLite en mémoire, réutilisée pour tous les tests du module."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(_CREATE_BABIES)
        await conn.execute(_CREATE_FEEDINGS)
        await conn.commit()
        yield conn


@pytest_asyncio.fixture(scope="module")
async def client(mem_db: aiosqlite.Connection):
    """Client HTTP de test avec DB in-memory et RAG mocké."""

    async def override_db():
        yield mem_db

    app.dependency_overrides[db_dependency] = override_db
    app.state.rag_index = None  # pas d'index RAG en test

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["rag_available"] is False


# ---------------------------------------------------------------------------
# /babies
# ---------------------------------------------------------------------------

async def test_create_baby(client: AsyncClient):
    resp = await client.post(
        "/babies",
        json={"name": "Lena", "birth_date": "2025-01-15", "birth_weight_grams": 3200},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Lena"
    assert data["id"] == 1


async def test_create_baby_invalid(client: AsyncClient):
    """Champ manquant → 422."""
    resp = await client.post("/babies", json={"name": "X"})
    assert resp.status_code == 422


async def test_list_babies(client: AsyncClient):
    resp = await client.get("/babies")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_baby(client: AsyncClient):
    resp = await client.get("/babies/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Lena"


async def test_get_baby_not_found(client: AsyncClient):
    resp = await client.get("/babies/9999")
    assert resp.status_code == 404


async def test_update_baby(client: AsyncClient):
    resp = await client.patch("/babies/1", json={"name": "Léna"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Léna"


# ---------------------------------------------------------------------------
# /feedings
# ---------------------------------------------------------------------------

async def test_add_feeding(client: AsyncClient):
    resp = await client.post(
        "/feedings",
        json={
            "baby_id": 1,
            "fed_at": "2025-01-15T08:00:00",
            "quantity_ml": 90,
            "feeding_type": "bottle",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["quantity_ml"] == 90
    assert data["feeding_type"] == "bottle"


async def test_add_feeding_unknown_baby(client: AsyncClient):
    resp = await client.post(
        "/feedings",
        json={
            "baby_id": 9999,
            "fed_at": "2025-01-15T08:00:00",
            "quantity_ml": 80,
            "feeding_type": "bottle",
        },
    )
    assert resp.status_code == 404


async def test_add_second_feeding(client: AsyncClient):
    """Second biberon pour avoir des données suffisantes pour /feedings/{id}."""
    resp = await client.post(
        "/feedings",
        json={
            "baby_id": 1,
            "fed_at": "2025-01-15T11:00:00",
            "quantity_ml": 100,
            "feeding_type": "bottle",
        },
    )
    assert resp.status_code == 201


async def test_get_feedings_all(client: AsyncClient):
    resp = await client.get("/feedings/1")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_feedings_by_day(client: AsyncClient):
    resp = await client.get("/feedings/1?day=2025-01-15")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_feedings_by_day_empty(client: AsyncClient):
    resp = await client.get("/feedings/1?day=2025-01-16")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_feedings_range(client: AsyncClient):
    resp = await client.get("/feedings/1?start=2025-01-15&end=2025-01-15")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_feedings_invalid_range(client: AsyncClient):
    resp = await client.get("/feedings/1?start=2025-01-20&end=2025-01-10")
    assert resp.status_code == 400


async def test_get_feedings_baby_not_found(client: AsyncClient):
    resp = await client.get("/feedings/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /analysis
# ---------------------------------------------------------------------------

MOCK_ANALYSIS = "✅ Analyse simulée : tout va bien !"


async def test_analysis_day(client: AsyncClient):
    with patch("app.api.routes.analysis.analyze_feedings", return_value=MOCK_ANALYSIS):
        resp = await client.get("/analysis/1?period=day&reference_date=2025-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["baby_id"] == 1
    assert data["baby_name"] == "Léna"  # nom mis à jour via PATCH
    assert data["period"] == "day"
    assert data["analysis"] == MOCK_ANALYSIS


async def test_analysis_week(client: AsyncClient):
    with patch("app.api.routes.analysis.analyze_feedings", return_value=MOCK_ANALYSIS):
        resp = await client.get("/analysis/1?period=week&reference_date=2025-01-21")
    assert resp.status_code == 200
    assert resp.json()["period"] == "week"


async def test_analysis_no_feedings(client: AsyncClient):
    """Période sans biberon → 404."""
    resp = await client.get("/analysis/1?period=day&reference_date=2024-01-01")
    assert resp.status_code == 404


async def test_analysis_baby_not_found(client: AsyncClient):
    resp = await client.get("/analysis/9999?period=day&reference_date=2025-01-15")
    assert resp.status_code == 404
