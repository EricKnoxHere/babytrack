"""Lightweight HTTP client for the BabyTrack API."""

from __future__ import annotations

import csv
import os
from datetime import date, datetime
from io import StringIO
from typing import Any, Optional

import requests

API_BASE = os.getenv("BABYTRACK_API_URL", "http://localhost:8000")
TIMEOUT = 10          # seconds — fast endpoints
ANALYSIS_TIMEOUT = 120  # seconds — RAG + Claude can be slow on first run


def _get(path: str, params: dict | None = None, timeout: int = TIMEOUT) -> Any:
    try:
        resp = requests.get(f"{API_BASE}{path}", params=params, timeout=timeout, verify=True)
    except Exception:
        # Fallback: disable SSL verification if certificate issues on Render
        resp = requests.get(f"{API_BASE}{path}", params=params, timeout=timeout, verify=False)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict, timeout: int = TIMEOUT) -> Any:
    try:
        resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout, verify=True)
    except Exception:
        # Fallback: disable SSL verification if certificate issues on Render
        resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout, verify=False)
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


# ── Diapers ────────────────────────────────────────────────────────────


def add_diaper(
    baby_id: int,
    changed_at: str,
    has_pee: bool = True,
    has_poop: bool = False,
    notes: Optional[str] = None,
) -> dict:
    payload: dict = {
        "baby_id": baby_id,
        "changed_at": changed_at,
        "has_pee": has_pee,
        "has_poop": has_poop,
    }
    if notes:
        payload["notes"] = notes
    return _post("/diapers", payload)


def get_diapers(
    baby_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> list[dict]:
    params: dict = {}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    return _get(f"/diapers/{baby_id}", params=params)


def update_diaper(diaper_id: int, updates: dict) -> dict:
    """Update a diaper record (only non-None fields)."""
    return _request("PATCH", f"/diapers/{diaper_id}", updates)


def delete_diaper(diaper_id: int) -> None:
    """Delete a diaper record."""
    resp = requests.delete(f"{API_BASE}/diapers/{diaper_id}", timeout=TIMEOUT)
    resp.raise_for_status()


# ── Conversations ─────────────────────────────────────────────────────


def save_conversation(baby_id: int, title: str, messages: list[dict]) -> dict:
    return _post("/conversations", {
        "baby_id": baby_id,
        "title": title,
        "messages": messages,
    })


def update_conversation(conversation_id: int, title: Optional[str] = None, messages: Optional[list[dict]] = None) -> dict:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if messages is not None:
        payload["messages"] = messages
    return _request("PATCH", f"/conversations/detail/{conversation_id}", payload)


def list_conversations(baby_id: int, limit: int = 20) -> list[dict]:
    return _get(f"/conversations/{baby_id}", params={"limit": limit})


def get_conversation(conversation_id: int) -> dict:
    return _get(f"/conversations/detail/{conversation_id}")


def delete_conversation(conversation_id: int) -> None:
    resp = requests.delete(f"{API_BASE}/conversations/detail/{conversation_id}", timeout=TIMEOUT)
    resp.raise_for_status()


# ── AI Analysis ────────────────────────────────────────────────────────────


def get_analysis(
    baby_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    question: Optional[str] = None,
) -> dict:
    """
    Request an AI analysis for a datetime window.
    Defaults to today 00:00 → now (partial day) if no range given.
    Pass question to get a conversational answer instead of a full report.
    """
    params: dict = {}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    if question:
        params["question"] = question
    return _get(f"/analysis/{baby_id}", params=params, timeout=ANALYSIS_TIMEOUT)


def chat(
    baby_id: int,
    question: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Chat endpoint with conversation history for contextual follow-ups.
    """
    payload: dict = {"question": question}
    if start:
        payload["start"] = start.isoformat()
    if end:
        payload["end"] = end.isoformat()
    if chat_history:
        payload["chat_history"] = [
            {"role": m["role"], "content": m["content"]}
            for m in chat_history
        ]
    return _post(f"/analysis/{baby_id}/chat", payload, timeout=ANALYSIS_TIMEOUT)


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
