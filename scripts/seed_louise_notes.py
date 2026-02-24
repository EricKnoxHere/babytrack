"""Seed realistic weight entries and parent notes for Louise."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

WEIGHT_ENTRIES = [
    ("2026-02-16 09:30:00", 3200, "birth weight — maternity ward"),
    ("2026-02-18 10:15:00", 3050, "day 2 — pediatrician checkup, slight jaundice noted"),
    ("2026-02-20 09:00:00", 2980, "day 4 — morning before first feed, lowest point"),
    ("2026-02-21 11:30:00", 3010, None),
    ("2026-02-22 09:45:00", 3095, "day 6 — good weight gain, regaining well"),
    ("2026-02-23 10:00:00", 3165, "morning before bath"),
    ("2026-02-24 09:30:00", 3210, "day 8 — back above birth weight! 🎉"),
]

# (fed_at prefix YYYY-MM-DD HH, note)
FEEDING_NOTES = [
    ("2026-02-16 09", "first feed after birth, took a while to latch"),
    ("2026-02-17 02", "very sleepy, had to wake her up"),
    ("2026-02-18 06", "seemed uncomfortable, lots of gas"),
    ("2026-02-18 15", "cried a lot before feeding, very hungry"),
    ("2026-02-19 03", "difficult night, only took half the bottle then fell asleep"),
    ("2026-02-20 08", "hot day, seems more thirsty than usual"),
    ("2026-02-20 20", "spat up a bit after"),
    ("2026-02-21 06", "great feed, took everything and more"),
    ("2026-02-22 10", "bath day — was calmer than usual after"),
    ("2026-02-23 07", "slept 4h between feeds for the first time"),
    ("2026-02-23 19", "a bit fussy, maybe a growth spurt starting?"),
    ("2026-02-24 08", "back to normal rhythm, very alert"),
]


async def main():
    import aiosqlite
    db_path = os.getenv("DATABASE_URL", "data/babytrack.db")

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # 1. Add weight entries
        for measured_at, weight_g, notes in WEIGHT_ENTRIES:
            await db.execute(
                "INSERT INTO weight_entries (baby_id, measured_at, weight_g, notes) VALUES (?,?,?,?)",
                (1, measured_at, weight_g, notes),
            )
        await db.commit()
        print(f"✅ Added {len(WEIGHT_ENTRIES)} weight entries")

        # 2. Add notes to matching feedings (match by day+hour prefix)
        notes_added = 0
        for prefix, note in FEEDING_NOTES:
            async with db.execute(
                "SELECT id FROM feedings WHERE baby_id=1 AND fed_at LIKE ? LIMIT 1",
                (f"{prefix}%",),
            ) as cur:
                row = await cur.fetchone()
            if row:
                await db.execute("UPDATE feedings SET notes=? WHERE id=?", (note, row["id"]))
                notes_added += 1
        await db.commit()
        print(f"✅ Added notes to {notes_added}/{len(FEEDING_NOTES)} feedings")

        # Summary
        print("\n📊 Weight curve:")
        async with db.execute(
            "SELECT measured_at, weight_g, notes FROM weight_entries WHERE baby_id=1 ORDER BY measured_at"
        ) as cur:
            for r in await cur.fetchall():
                note = f" — {r['notes']}" if r["notes"] else ""
                print(f"  {r['measured_at'][:10]}  {r['weight_g']}g{note}")

        print("\n📝 Feedings with notes:")
        async with db.execute(
            "SELECT fed_at, quantity_ml, notes FROM feedings WHERE baby_id=1 AND notes IS NOT NULL ORDER BY fed_at"
        ) as cur:
            for r in await cur.fetchall():
                print(f"  {r['fed_at'][:16]}  {r['quantity_ml']}ml  \"{r['notes']}\"")


if __name__ == "__main__":
    asyncio.run(main())
