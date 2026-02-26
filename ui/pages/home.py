"""Home — Today's summary + quick feeding entry."""

import streamlit as st
from datetime import date, datetime, timedelta
from ui import api_client as api


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    # ── Header ───────────────────────────────────────────────────────────────

    birth = date.fromisoformat(baby["birth_date"]) if "birth_date" in baby else datetime.fromisoformat(baby["created_at"]).date()
    age_days = (date.today() - birth).days

    st.markdown(f"## 🍼 {baby['name']}  ·  {age_days} days old")

    # ── Today's data ─────────────────────────────────────────────────────────

    try:
        today_feedings = api.get_feedings(baby["id"], day=date.today())
    except Exception:
        today_feedings = []

    total_ml = sum(f["quantity_ml"] for f in today_feedings)
    count = len(today_feedings)

    # Time since last feeding
    if today_feedings:
        last = max(today_feedings, key=lambda f: f["fed_at"])
        last_dt = datetime.fromisoformat(last["fed_at"])
        mins_ago = int((datetime.now() - last_dt).total_seconds() / 60)
        if mins_ago < 60:
            since_last = f"{mins_ago}min ago"
        else:
            since_last = f"{mins_ago // 60}h{mins_ago % 60:02d} ago"
        last_time = last_dt.strftime("%H:%M")
    else:
        since_last = "—"
        last_time = "—"

    # ── Metrics (3 columns) ──────────────────────────────────────────────────

    c1, c2, c3 = st.columns(3)
    c1.metric("Volume today", f"{total_ml} ml")
    c2.metric("Feedings", count)
    c3.metric("Last feeding", last_time, since_last)

    st.markdown("")  # spacer

    # ── New feeding (expander, closed by default) ────────────────────────────

    with st.expander("➕ **Log a feeding**", expanded=False):
        col_l, col_r = st.columns(2)

        with col_l:
            fed_date = st.date_input("Date", value=date.today(), key="h_date")
            fed_time = st.time_input("Time", value=datetime.now().time(), key="h_time")

        with col_r:
            qty = st.number_input("Quantity (ml)", 1, 500, 90, step=10, key="h_qty")
            ftype = st.selectbox("Type", ["bottle", "breastfeeding"],
                                 format_func=lambda t: "🍼 Bottle" if t == "bottle" else "🤱 Breast",
                                 key="h_type")

        notes = st.text_input("Notes (optional)", key="h_notes", placeholder="e.g. baby seemed hungry")

        if st.button("✅ Save", use_container_width=True, type="primary", key="h_save"):
            fed_at = datetime.combine(fed_date, fed_time).isoformat()
            try:
                api.add_feeding(baby["id"], fed_at, int(qty), ftype, notes or None)
                st.success("Saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Timeline ─────────────────────────────────────────────────────────────

    st.markdown("#### Today's feedings")

    if not today_feedings:
        st.caption("Nothing yet — log your first feeding above.")
    else:
        for f in sorted(today_feedings, key=lambda x: x["fed_at"], reverse=True):
            t = datetime.fromisoformat(f["fed_at"]).strftime("%H:%M")
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            note = f"  ·  _{f['notes']}_" if f.get("notes") else ""

            col_info, col_del = st.columns([6, 1])
            with col_info:
                st.markdown(f"`{t}`  {icon} **{f['quantity_ml']} ml**{note}")
            with col_del:
                if st.button("✕", key=f"del_{f['id']}", help="Delete"):
                    try:
                        api.delete_feeding(f["id"])
                        st.rerun()
                    except Exception:
                        pass
