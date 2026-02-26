"""Records — Unified table of all feedings and weights."""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from ui import api_client as api


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    st.markdown("## 📋 Records")

    # ── Load data ────────────────────────────────────────────────────────────

    try:
        feedings = api.get_feedings(baby["id"])
    except Exception:
        feedings = []

    try:
        weights = api.get_weights(baby["id"])
    except Exception:
        weights = []

    # ── Build unified rows ───────────────────────────────────────────────────

    rows = []

    for f in feedings:
        icon = "🍼 Bottle" if f["feeding_type"] == "bottle" else "🤱 Breast"
        rows.append({
            "type": icon,
            "date": datetime.fromisoformat(f["fed_at"]).strftime("%Y-%m-%d %H:%M"),
            "value": f"{f['quantity_ml']} ml",
            "notes": f.get("notes") or "",
            "_sort": f["fed_at"],
            "_kind": "feeding",
            "_id": f["id"],
        })

    for w in weights:
        rows.append({
            "type": "⚖️ Weight",
            "date": datetime.fromisoformat(w["measured_at"]).strftime("%Y-%m-%d %H:%M"),
            "value": f"{w['weight_g']} g",
            "notes": w.get("notes") or "",
            "_sort": w["measured_at"],
            "_kind": "weight",
            "_id": w["id"],
        })

    # Sort newest first
    rows.sort(key=lambda r: r["_sort"], reverse=True)

    if not rows:
        st.info("No records yet. Add a bottle or weight entry using the sidebar.")
        return

    # ── Filter ───────────────────────────────────────────────────────────────

    filter_options = ["All", "🍼 Bottle", "🤱 Breast", "⚖️ Weight"]
    selected_filter = st.selectbox(
        "Filter by type",
        filter_options,
        index=0,
        key="record_filter",
        label_visibility="collapsed",
    )

    if selected_filter != "All":
        rows = [r for r in rows if r["type"] == selected_filter]

    st.caption(f"{len(rows)} records")

    # ── Display table ────────────────────────────────────────────────────────

    display_rows = [
        {"Type": r["type"], "Date": r["date"], "Value": r["value"], "Notes": r["notes"]}
        for r in rows
    ]

    df = pd.DataFrame(display_rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(len(df) * 35 + 38, 600),
    )

    # ── Delete section ───────────────────────────────────────────────────────

    with st.expander("🗑️ Delete a record"):
        st.caption("Enter the row number (1-based) from the table above to delete it.")
        del_idx = st.number_input(
            "Row #", min_value=1, max_value=len(rows), value=1, step=1, key="del_row"
        )
        if st.button("Delete", type="primary", key="del_confirm"):
            target = rows[del_idx - 1]
            try:
                if target["_kind"] == "feeding":
                    api.delete_feeding(target["_id"])
                else:
                    # No delete_weight in api_client, use raw request
                    resp = requests.delete(
                        f"{api.API_BASE}/weights/{target['_id']}", timeout=api.TIMEOUT
                    )
                    resp.raise_for_status()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
