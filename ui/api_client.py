"""Client HTTP léger pour l'API BabyTrack."""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Optional

import requests

API_BASE = os.getenv("BABYTRACK_API_URL", "http://localhost:8000")
TIMEOUT = 10  # secondes


def _get(path: str, params: dict | None = None) -> Any:
    resp = requests.get(f"{API_BASE}{path}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> Any:
    resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Bébés ──────────────────────────────────────────────────────────────────


def list_babies() -> list[dict]:
    return _get("/babies")


def create_baby(name: str, birth_date: date, birth_weight_grams: int) -> dict:
    return _post("/babies", {
        "name": name,
        "birth_date": birth_date.isoformat(),
        "birth_weight_grams": birth_weight_grams,
    })


# ── Biberons ───────────────────────────────────────────────────────────────


def add_feeding(
    baby_id: int,
    fed_at: str,
    quantity_ml: int,
    feeding_type: str,
    notes: Optional[str] = None,
) -> dict:
    payload: dict = {
        "baby_id": baby_id,
        "fed_at": fed_at,
        "quantity_ml": quantity_ml,
        "feeding_type": feeding_type,
    }
    if notes:
        payload["notes"] = notes
    return _post("/feedings", payload)


def get_feedings(
    baby_id: int,
    day: Optional[date] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> list[dict]:
    params: dict = {}
    if day:
        params["day"] = day.isoformat()
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    return _get(f"/feedings/{baby_id}", params=params)


# ── Analyse IA ─────────────────────────────────────────────────────────────


def get_analysis(
    baby_id: int,
    period: str = "day",
    reference_date: Optional[date] = None,
) -> dict:
    params: dict = {"period": period}
    if reference_date:
        params["reference_date"] = reference_date.isoformat()
    return _get(f"/analysis/{baby_id}", params=params)


# ── Healthcheck ────────────────────────────────────────────────────────────


def health() -> dict:
    return _get("/health")
