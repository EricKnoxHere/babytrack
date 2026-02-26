"""Import Romane's feeding & diaper data from the Google Forms CSV export.

Handles:
- Deleting all existing babies (cascade deletes associated data)
- Creating Romane (born 2026-02-16, 09:17, 3210g)
- Parsing CSV with actual_time = Horodateur - "Il y a X minutes"
- Duplicate Feb 21 rows: first occurrence becomes Feb 20 data
- Creating feedings (when Repas (ml) > 0) and diapers (when Urines/Selles present)

Usage:
    cd /Users/opronier/Documents/babytrack
    source .venv/bin/activate
    python scripts/import_romane_csv.py
"""

import csv
import requests
from datetime import datetime, timedelta

API = "http://localhost:8000"
CSV_PATH = "/Users/opronier/Downloads/Romane Réponses formulaire.csv"


def delete_all_babies():
    """Delete every baby (cascade removes all associated data)."""
    babies = requests.get(f"{API}/babies", timeout=5).json()
    for b in babies:
        resp = requests.delete(f"{API}/babies/{b['id']}", timeout=5)
        status = "OK" if resp.status_code == 204 else f"ERR {resp.status_code}"
        print(f"  {status} Deleted {b['name']} (id={b['id']})")
    if not babies:
        print("  (no babies to delete)")


def create_romane():
    """Create baby Romane."""
    resp = requests.post(f"{API}/babies", json={
        "name": "Romane",
        "birth_date": "2026-02-16",
        "birth_weight_grams": 3210,
    }, timeout=5)
    baby = resp.json()
    print(f"Created Romane (id={baby['id']})")
    return baby["id"]


def parse_csv():
    """Parse CSV into feeding and diaper entries."""
    feedings = []
    diapers = []
    seen_horodateurs = set()

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_raw = row.get("Horodateur", "").strip()
            if not ts_raw:
                continue

            try:
                horodateur = datetime.strptime(ts_raw, "%d/%m/%Y %H:%M:%S")
            except (ValueError, TypeError):
                continue

            # Handle duplicates: first occurrence of Feb 21 -> shift to Feb 20
            is_duplicate = ts_raw in seen_horodateurs
            seen_horodateurs.add(ts_raw)

            if not is_duplicate and horodateur.date() == datetime(2026, 2, 21).date():
                horodateur = horodateur - timedelta(days=1)

            # Adjust for "Il y a X minutes"
            minutes_ago_raw = row.get("Il y a X minutes", "").strip()
            if minutes_ago_raw:
                try:
                    minutes_ago = int(float(minutes_ago_raw))
                    horodateur = horodateur - timedelta(minutes=minutes_ago)
                except (ValueError, TypeError):
                    pass

            # Parse feeding
            ml_raw = row.get("Repas (ml)", "").strip()
            if ml_raw:
                try:
                    quantity_ml = int(float(ml_raw))
                    if quantity_ml > 0:
                        feedings.append({
                            "fed_at": horodateur.isoformat(),
                            "quantity_ml": quantity_ml,
                            "feeding_type": "bottle",
                        })
                except (ValueError, TypeError):
                    pass

            # Parse diaper
            urines = row.get("Urines", "").strip()
            selles = row.get("Selles", "").strip()
            has_pee = urines == "Oui"
            has_poop = selles == "Oui"

            if has_pee or has_poop:
                diapers.append({
                    "changed_at": horodateur.isoformat(),
                    "has_pee": has_pee,
                    "has_poop": has_poop,
                })

    return feedings, diapers


def main():
    print("Deleting all existing babies...")
    delete_all_babies()

    print("\nCreating Romane...")
    baby_id = create_romane()

    print("\nParsing CSV...")
    feedings, diapers = parse_csv()
    print(f"  Found {len(feedings)} feedings, {len(diapers)} diaper changes")

    print("\nImporting feedings...")
    f_ok = f_err = 0
    for entry in feedings:
        payload = {"baby_id": baby_id, **entry}
        resp = requests.post(f"{API}/feedings", json=payload, timeout=5)
        if resp.status_code in (200, 201):
            f_ok += 1
        else:
            f_err += 1
            print(f"  FAIL: {entry['fed_at']} {entry['quantity_ml']}ml - {resp.status_code}")
    print(f"  {f_ok} feedings imported, {f_err} errors")

    print("\nImporting diapers...")
    d_ok = d_err = 0
    for entry in diapers:
        payload = {"baby_id": baby_id, **entry}
        resp = requests.post(f"{API}/diapers", json=payload, timeout=5)
        if resp.status_code in (200, 201):
            d_ok += 1
        else:
            d_err += 1
            print(f"  FAIL: {entry['changed_at']} - {resp.status_code}")
    print(f"  {d_ok} diapers imported, {d_err} errors")

    print("\nDone!")


if __name__ == "__main__":
    main()
