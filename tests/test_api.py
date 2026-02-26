"""FastAPI integration tests.

Strategy:
- Shared PostgreSQL connection for all tests in the module (requires DATABASE_URL).
- Real app lifespan (main.py) — DB dependency is overridden.
- analyze_feedings is mocked to avoid calling Claude / the network.
"""

from __future__ import annotations

import os

import pytest
import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, MagicMock

from app.api.dependencies import db_dependency
from app.services.database import (
    _CREATE_ANALYSIS_REPORTS,
    _CREATE_BABIES,
    _CREATE_CONVERSATIONS,
    _CREATE_DIAPERS,
    _CREATE_FEEDINGS,
    _CREATE_WEIGHTS,
)
from main import app

_TEST_DSN = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "")


# ---------------------------------------------------------------------------
# Fixture: shared PostgreSQL connection for the entire module
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def mem_db():
    """PostgreSQL connection, reused across all module tests with rollback."""
    if not _TEST_DSN:
        pytest.skip("No TEST_DATABASE_URL or DATABASE_URL set — skipping API tests")

    conn = await asyncpg.connect(_TEST_DSN)
    tr = conn.transaction()
    await tr.start()

    await conn.execute(_CREATE_BABIES)
    await conn.execute(_CREATE_FEEDINGS)
    await conn.execute(_CREATE_WEIGHTS)
    await conn.execute(_CREATE_ANALYSIS_REPORTS)
    await conn.execute(_CREATE_DIAPERS)
    await conn.execute(_CREATE_CONVERSATIONS)

    yield conn

    await tr.rollback()
    await conn.close()


@pytest_asyncio.fixture(scope="module")
async def client(mem_db: asyncpg.Connection):
    """HTTP test client with PostgreSQL DB and mocked RAG."""

    async def override_db():
        yield mem_db

    app.dependency_overrides[db_dependency] = override_db
    app.state.rag_index = None  # no RAG index in tests

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
    """Missing required field → 422."""
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
    """Second feeding to have enough data for /feedings/{id}."""
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


async def test_update_feeding(client: AsyncClient):
    # Get a feeding first
    resp = await client.get("/feedings/1")
    feedings = resp.json()
    if feedings:
        feeding_id = feedings[0]["id"]
        resp = await client.patch(
            f"/feedings/{feeding_id}",
            json={"quantity_ml": 200},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity_ml"] == 200


async def test_update_feeding_not_found(client: AsyncClient):
    resp = await client.patch("/feedings/9999", json={"quantity_ml": 100})
    assert resp.status_code == 404


async def test_delete_feeding(client: AsyncClient):
    # Get a feeding first
    resp = await client.get("/feedings/1")
    feedings = resp.json()
    if feedings:
        feeding_id = feedings[0]["id"]
        resp = await client.delete(f"/feedings/{feeding_id}")
        assert resp.status_code == 204
        # Verify it's gone
        resp = await client.get(f"/feedings/1")
        remaining = resp.json()
        assert all(f["id"] != feeding_id for f in remaining)


# ---------------------------------------------------------------------------
# /analysis
# ---------------------------------------------------------------------------

MOCK_ANALYSIS_TEXT = "✅ Simulated analysis: all looks good!"
MOCK_SOURCES = [
    {"source": "who_infant_feeding.md", "score": 0.92},
    {"source": "sfp_guide.md", "score": 0.85},
]
MOCK_ANALYSIS = (MOCK_ANALYSIS_TEXT, MOCK_SOURCES)


async def test_analysis_day(client: AsyncClient):
    with patch("app.rag.analyzer.analyze_feedings", return_value=MOCK_ANALYSIS):
        resp = await client.get("/analysis/1?start=2025-01-15T00:00:00&end=2025-01-15T23:59:59")
    assert resp.status_code == 200
    data = resp.json()
    assert data["baby_id"] == 1
    assert data["baby_name"] == "Léna"
    assert data["analysis"] == MOCK_ANALYSIS_TEXT
    assert len(data["sources"]) == 2


async def test_analysis_week(client: AsyncClient):
    with patch("app.rag.analyzer.analyze_feedings", return_value=MOCK_ANALYSIS):
        resp = await client.get("/analysis/1?start=2025-01-15T00:00:00&end=2025-01-21T23:59:59")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis"] == MOCK_ANALYSIS_TEXT
    assert len(data["sources"]) == 2


async def test_analysis_no_feedings(client: AsyncClient):
    """Range with no feedings → 404."""
    resp = await client.get("/analysis/1?start=2024-01-01T00:00:00&end=2024-01-02T23:59:59")
    assert resp.status_code == 404


async def test_analysis_baby_not_found(client: AsyncClient):
    resp = await client.get("/analysis/9999?period=day&reference_date=2025-01-15")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /diapers
# ---------------------------------------------------------------------------

async def test_add_diaper(client: AsyncClient):
    resp = await client.post(
        "/diapers",
        json={
            "baby_id": 1,
            "changed_at": "2025-01-15T09:00:00",
            "has_pee": True,
            "has_poop": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_pee"] is True
    assert data["has_poop"] is False
    assert data["baby_id"] == 1


async def test_add_diaper_with_poop(client: AsyncClient):
    resp = await client.post(
        "/diapers",
        json={
            "baby_id": 1,
            "changed_at": "2025-01-15T14:00:00",
            "has_pee": True,
            "has_poop": True,
            "notes": "big one",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["has_poop"] is True
    assert resp.json()["notes"] == "big one"


async def test_add_diaper_unknown_baby(client: AsyncClient):
    resp = await client.post(
        "/diapers",
        json={
            "baby_id": 9999,
            "changed_at": "2025-01-15T09:00:00",
            "has_pee": True,
            "has_poop": False,
        },
    )
    assert resp.status_code == 404


async def test_get_diapers_all(client: AsyncClient):
    resp = await client.get("/diapers/1")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_diapers_by_range(client: AsyncClient):
    resp = await client.get("/diapers/1?start=2025-01-15&end=2025-01-15")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_diapers_invalid_range(client: AsyncClient):
    resp = await client.get("/diapers/1?start=2025-01-20&end=2025-01-10")
    assert resp.status_code == 400


async def test_get_diapers_baby_not_found(client: AsyncClient):
    resp = await client.get("/diapers/9999")
    assert resp.status_code == 404


async def test_update_diaper(client: AsyncClient):
    resp = await client.get("/diapers/1")
    diapers = resp.json()
    if diapers:
        diaper_id = diapers[0]["id"]
        resp = await client.patch(
            f"/diapers/{diaper_id}",
            json={"has_poop": True},
        )
        assert resp.status_code == 200
        assert resp.json()["has_poop"] is True


async def test_update_diaper_not_found(client: AsyncClient):
    resp = await client.patch("/diapers/9999", json={"has_pee": False})
    assert resp.status_code == 404


async def test_delete_diaper(client: AsyncClient):
    # Add one to delete
    resp = await client.post(
        "/diapers",
        json={
            "baby_id": 1,
            "changed_at": "2025-01-15T20:00:00",
            "has_pee": True,
            "has_poop": False,
        },
    )
    diaper_id = resp.json()["id"]
    resp = await client.delete(f"/diapers/{diaper_id}")
    assert resp.status_code == 204


async def test_delete_diaper_not_found(client: AsyncClient):
    resp = await client.delete("/diapers/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /conversations
# ---------------------------------------------------------------------------

async def test_create_conversation(client: AsyncClient):
    resp = await client.post(
        "/conversations",
        json={
            "baby_id": 1,
            "title": "Morning chat",
            "messages": [
                {"role": "user", "content": "How is Léna?"},
                {"role": "assistant", "content": "She's doing great!"},
            ],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Morning chat"
    assert len(data["messages"]) == 2


async def test_create_conversation_unknown_baby(client: AsyncClient):
    resp = await client.post(
        "/conversations",
        json={"baby_id": 9999, "title": "test", "messages": []},
    )
    assert resp.status_code == 404


async def test_list_conversations(client: AsyncClient):
    resp = await client.get("/conversations/1")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert resp.json()[0]["title"] == "Morning chat"


async def test_list_conversations_baby_not_found(client: AsyncClient):
    resp = await client.get("/conversations/9999")
    assert resp.status_code == 404


async def test_get_conversation_detail(client: AsyncClient):
    # Get the conversation id from listing
    listing = await client.get("/conversations/1")
    conv_id = listing.json()[0]["id"]
    resp = await client.get(f"/conversations/detail/{conv_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Morning chat"
    assert len(data["messages"]) == 2


async def test_get_conversation_not_found(client: AsyncClient):
    resp = await client.get("/conversations/detail/9999")
    assert resp.status_code == 404


async def test_update_conversation(client: AsyncClient):
    listing = await client.get("/conversations/1")
    conv_id = listing.json()[0]["id"]
    resp = await client.patch(
        f"/conversations/detail/{conv_id}",
        json={"title": "Updated title"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"


async def test_update_conversation_not_found(client: AsyncClient):
    resp = await client.patch(
        "/conversations/detail/9999",
        json={"title": "nope"},
    )
    assert resp.status_code == 404


async def test_delete_conversation(client: AsyncClient):
    # Create and delete
    resp = await client.post(
        "/conversations",
        json={"baby_id": 1, "title": "To delete", "messages": []},
    )
    conv_id = resp.json()["id"]
    resp = await client.delete(f"/conversations/detail/{conv_id}")
    assert resp.status_code == 204


async def test_delete_conversation_not_found(client: AsyncClient):
    resp = await client.delete("/conversations/detail/9999")
    assert resp.status_code == 404
