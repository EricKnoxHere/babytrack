"""Import Louise's feeding data from the Google Forms CSV export.

Usage:
    cd /Users/opronier/Documents/babytrack
    source .venv/bin/activate
    python scripts/import_louise_csv.py
"""

import csv
import requests
from datetime import datetime

API = "http://localhost:8000"
CSV_PATH = "/Users/opronier/Downloads/Louise Réponses formulaire.csv"


def parse_csv():
    """Parse the CSV and return a list of feeding entries."""
    entries = []
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_raw = row.get("Horodateur", "").strip()
            ml_raw = row.get("Repas (ml)", "").strip()
            if not ts_raw or not ml_raw:
                continue
            try:
                fed_at = datetime.strptime(ts_raw, "%d/%m/%Y %H:%M:%S")
                quantity_ml = int(ml_raw)
            except (ValueError, TypeError):
                continue
            if quantity_ml <= 0:
                continue

            # Build notes from urines/selles columns
            notes_parts = []
            urines = row.get("Urines", "").strip()
            selles = row.get("Selles", "").strip()
            if urines == "Oui":
                notes_parts.append("urines: yes")
            if selles == "Oui":
                notes_parts.append("stools: yes")
            elif selles == "Non":
                notes_parts.append("stools: no")

            entries.append({
                "fed_at": fed_at.isoformat(),
                "quantity_ml": quantity_ml,
                "feeding_type": "bottle",
                "notes": ", ".join(notes_parts) if notes_parts else None,
            })
    return entries


def main():
    # Find Louise's baby_id
    babies = requests.get(f"{API}/babies", timeout=5).json()
    louise = next((b for b in babies if b["name"].lower() == "louise"), None)

    if not louise:
        print("❌ Baby 'Louise' not found. Creating...")
        louise = requests.post(f"{API}/babies", json={
            "name": "Louise",
            "birth_date": "2026-02-16",
            "birth_weight_grams": 3200,
        }, timeout=5).json()
        print(f"✅ Created Louise (id={louise['id']})")

    baby_id = louise["id"]

    # Get existing feedings to avoid duplicates
    existing = requests.get(f"{API}/feedings/{baby_id}", timeout=5).json()
    existing_times = {f["fed_at"][:19] for f in existing}  # truncate to seconds

    entries = parse_csv()
    imported = 0
    skipped = 0

    for entry in entries:
        if entry["fed_at"][:19] in existing_times:
            skipped += 1
            continue

        payload = {"baby_id": baby_id, **entry}
        resp = requests.post(f"{API}/feedings", json=payload, timeout=5)
        if resp.status_code in (200, 201):
            imported += 1
        else:
            print(f"⚠️  Failed: {entry['fed_at']} — {resp.status_code} {resp.text}")

    print(f"\n✅ Done: {imported} imported, {skipped} skipped (already exist)")
    print(f"Total entries in CSV: {len(entries)}")


if __name__ == "__main__":
    main()
