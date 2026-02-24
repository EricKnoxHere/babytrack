"""Lightweight HTTP client for the BabyTrack API."""

from __future__ import annotations

import csv
import os
from datetime import date
from io import StringIO
from typing import Any, Optional

import requests

API_BASE = os.getenv("BABYTRACK_API_URL", "http://localhost:8000")
TIMEOUT = 10          # seconds — fast endpoints
ANALYSIS_TIMEOUT = 120  # seconds — RAG + Claude can be slow on first run


def _get(path: str, params: dict | None = None, timeout: int = TIMEOUT) -> Any:
    resp = requests.get(f"{API_BASE}{path}", params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict, timeout: int = TIMEOUT) -> Any:
    resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ── Babies ─────────────────────────────────────────────────────────────────


def list_babies() -> list[dict]:
    return _get("/babies")


def create_baby(name: str, birth_date: date, birth_weight_grams: int) -> dict:
    return _post("/babies", {
        "name": name,
        "birth_date": birth_date.isoformat(),
        "birth_weight_grams": birth_weight_grams,
    })


# ── Feedings ───────────────────────────────────────────────────────────────


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


def update_feeding(feeding_id: int, updates: dict) -> dict:
    """Update a feeding record (only non-None fields)."""
    return _request("PATCH", f"/feedings/{feeding_id}", updates)


def delete_feeding(feeding_id: int) -> None:
    """Delete a feeding record."""
    resp = requests.delete(f"{API_BASE}/feedings/{feeding_id}", timeout=TIMEOUT)
    resp.raise_for_status()


def _request(method: str, path: str, payload: dict) -> dict:
    """Make a custom HTTP request."""
    url = f"{API_BASE}{path}"
    if method == "PATCH":
        resp = requests.patch(url, json=payload, timeout=TIMEOUT)
    else:
        raise ValueError(f"Unsupported method: {method}")
    resp.raise_for_status()
    return resp.json()


# ── Weights ───────────────────────────────────────────────────────────


def add_weight(
    baby_id: int,
    measured_at: str,
    weight_g: int,
    notes: Optional[str] = None,
) -> dict:
    payload: dict = {
        "baby_id": baby_id,
        "measured_at": measured_at,
        "weight_g": weight_g,
    }
    if notes:
        payload["notes"] = notes
    return _post("/weights", payload)


def get_weights(
    baby_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> list[dict]:
    params: dict = {}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    return _get(f"/weights/{baby_id}", params=params)


# ── AI Analysis ────────────────────────────────────────────────────────────


def get_analysis(
    baby_id: int,
    period: str = "day",
    reference_date: Optional[date] = None,
) -> dict:
    params: dict = {"period": period}
    if reference_date:
        params["reference_date"] = reference_date.isoformat()
    return _get(f"/analysis/{baby_id}", params=params, timeout=ANALYSIS_TIMEOUT)


def list_analysis_history(baby_id: int, limit: int = 20) -> list[dict]:
    """Return the list of past analysis report summaries."""
    return _get(f"/analysis/{baby_id}/history", params={"limit": limit})


def get_analysis_report(baby_id: int, report_id: int) -> dict:
    """Return the full text of a specific past analysis report."""
    return _get(f"/analysis/{baby_id}/history/{report_id}")


def delete_analysis_report(baby_id: int, report_id: int) -> None:
    """Delete a past analysis report."""
    resp = requests.delete(f"{API_BASE}/analysis/{baby_id}/history/{report_id}", timeout=TIMEOUT)
    resp.raise_for_status()


# ── Data export ───────────────────────────────────────────────────────


def feedings_to_csv(feedings: list[dict]) -> str:
    """Convert feedings list to CSV string."""
    if not feedings:
        return ""
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["fed_at", "quantity_ml", "feeding_type", "notes"])
    writer.writeheader()
    for f in feedings:
        writer.writerow({
            "fed_at": f["fed_at"],
            "quantity_ml": f["quantity_ml"],
            "feeding_type": f["feeding_type"],
            "notes": f.get("notes", ""),
        })
    return output.getvalue()


def weights_to_csv(weights: list[dict]) -> str:
    """Convert weights list to CSV string."""
    if not weights:
        return ""
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["measured_at", "weight_g", "notes"])
    writer.writeheader()
    for w in weights:
        writer.writerow({
            "measured_at": w["measured_at"],
            "weight_g": w["weight_g"],
            "notes": w.get("notes", ""),
        })
    return output.getvalue()


# ── Health check ───────────────────────────────────────────────────────────


def health() -> dict:
    return _get("/health")
