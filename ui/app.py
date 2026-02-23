"""BabyTrack — Streamlit Dashboard.

Run: streamlit run ui/app.py
     (API must be running on localhost:8000)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path regardless of how Streamlit is invoked
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timedelta
from typing import Optional

import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

import ui.api_client as api

# ─────────────────────────────────────────────────────────────────────────────
# Global config
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BabyTrack",
    page_icon="🍼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def api_ok() -> bool:
    """Checks that the API is responding."""
    try:
        h = api.health()
        return h.get("status") == "ok"
    except Exception:
        return False


def feeding_type_label(t: str) -> str:
    return {"bottle": "🍼 Bottle", "breastfeeding": "🤱 Breastfeeding"}.get(t, t)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — baby selection
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🍼 BabyTrack")
    st.caption("Infant feeding tracker · RAG + Claude")
    st.divider()

    # API status
    if not api_ok():
        st.error("❌ API offline\n\n`uvicorn main:app --reload`")
        st.stop()

    rag_status = api.health().get("rag_available", False)
    st.caption(f"RAG: {'✅ active' if rag_status else '⚠️ inactive (analysis without context)'}")
    st.divider()

    # Load babies
    try:
        babies = api.list_babies()
    except Exception as e:
        st.error(f"Could not load babies: {e}")
        st.stop()

    # Selector or creation
    st.subheader("👶 Baby")
    mode = st.radio("", ["Select", "Create"], horizontal=True, label_visibility="collapsed")

    if mode == "Create":
        with st.form("new_baby"):
            baby_name = st.text_input("First name")
            baby_dob = st.date_input("Date of birth", value=date.today() - timedelta(days=30))
            baby_weight = st.number_input("Birth weight (g)", min_value=500, max_value=6000, value=3300)
            if st.form_submit_button("✅ Create"):
                try:
                    baby = api.create_baby(baby_name, baby_dob, int(baby_weight))
                    st.success(f"Baby **{baby['name']}** created!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        st.stop()

    if not babies:
        st.info("No babies registered. Create one first.")
        st.stop()

    baby_options = {f"{b['name']} (id {b['id']})": b for b in babies}
    selected_label = st.selectbox("", list(baby_options.keys()), label_visibility="collapsed")
    selected_baby: dict = baby_options[selected_label]

    st.divider()
    st.subheader("📅 Navigation")
    page = st.radio(
        "",
        ["🍼 Quick entry", "📊 Dashboard", "🤖 AI Analysis"],
        label_visibility="collapsed",
    )

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1 — Quick entry
# ─────────────────────────────────────────────────────────────────────────────

if page == "🍼 Quick entry":
    st.header(f"🍼 Log feeding — {selected_baby['name']}")

    with st.form("add_feeding"):
        col1, col2 = st.columns(2)
        with col1:
            fed_date = st.date_input("Date", value=date.today())
            fed_time = st.time_input("Time", value=datetime.now().time())
        with col2:
            quantity = st.number_input("Quantity (ml)", min_value=1, max_value=500, value=90, step=5)
            f_type = st.selectbox("Type", ["bottle", "breastfeeding"],
                                  format_func=feeding_type_label)
        notes = st.text_input("Notes (optional)", placeholder="e.g. a bit fussy afterwards")

        submitted = st.form_submit_button("✅ Save", use_container_width=True)

    if submitted:
        fed_at = datetime.combine(fed_date, fed_time).isoformat()
        try:
            feeding = api.add_feeding(
                baby_id=selected_baby["id"],
                fed_at=fed_at,
                quantity_ml=int(quantity),
                feeding_type=f_type,
                notes=notes or None,
            )
            st.success(f"✅ Feeding saved: **{feeding['quantity_ml']} ml** at **{fed_time.strftime('%H:%M')}**")
        except requests.HTTPError as e:
            st.error(f"API error: {e.response.json().get('detail', str(e))}")

    # Today's overview
    st.divider()
    st.subheader(f"Feedings on {date.today().strftime('%d/%m/%Y')}")
    try:
        today_feedings = api.get_feedings(selected_baby["id"], day=date.today())
    except Exception:
        today_feedings = []

    if today_feedings:
        total = sum(f["quantity_ml"] for f in today_feedings)
        st.metric("Total today", f"{total} ml", f"{len(today_feedings)} feeding(s)")
        for f in sorted(today_feedings, key=lambda x: x["fed_at"]):
            t = datetime.fromisoformat(f["fed_at"]).strftime("%H:%M")
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            note = f" — _{f['notes']}_" if f.get("notes") else ""
            st.markdown(f"- `{t}` {icon} **{f['quantity_ml']} ml**{note}")
    else:
        st.info("No feedings recorded today.")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2 — Dashboard
# ─────────────────────────────────────────────────────────────────────────────

elif page == "📊 Dashboard":
    st.header(f"📊 Dashboard — {selected_baby['name']}")

    # Date range selector
    col1, col2 = st.columns([2, 1])
    with col1:
        end_date = st.date_input("Up to", value=date.today())
    with col2:
        nb_days = st.selectbox("Period", [7, 14, 30], format_func=lambda n: f"{n} days")

    start_date = end_date - timedelta(days=nb_days - 1)

    try:
        feedings = api.get_feedings(selected_baby["id"], start=start_date, end=end_date)
    except Exception as e:
        st.error(f"Could not load feedings: {e}")
        feedings = []

    if not feedings:
        st.info("No data for this period.")
        st.stop()

    # Aggregate data by day
    from collections import defaultdict
    daily: dict[str, dict] = defaultdict(lambda: {"total_ml": 0, "count": 0})
    for f in feedings:
        day = f["fed_at"][:10]
        daily[day]["total_ml"] += f["quantity_ml"]
        daily[day]["count"] += 1

    days_range = [
        (start_date + timedelta(days=i)).isoformat()
        for i in range(nb_days)
    ]
    totals = [daily[d]["total_ml"] for d in days_range]
    counts = [daily[d]["count"] for d in days_range]

    # ── Chart 1: volume per day ─────────────────────────────────────────────
    fig_vol = go.Figure()
    fig_vol.add_bar(
        x=days_range, y=totals, name="Volume (ml)",
        marker_color="#4F86C6",
        text=totals, textposition="outside",
    )
    fig_vol.update_layout(
        title="Total volume per day (ml)",
        xaxis_title="Date", yaxis_title="ml",
        xaxis=dict(tickformat="%d/%m"),
        height=350, margin=dict(t=50, b=30),
    )
    st.plotly_chart(fig_vol, use_container_width=True)

    # ── Chart 2: number of feedings ────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        fig_count = go.Figure()
        fig_count.add_bar(
            x=days_range, y=counts, name="Number of feedings",
            marker_color="#7BC67E",
            text=counts, textposition="outside",
        )
        fig_count.update_layout(
            title="Number of feedings per day",
            xaxis=dict(tickformat="%d/%m"),
            height=300, margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig_count, use_container_width=True)

    with col_b:
        # Bottle vs breastfeeding breakdown
        type_counts = {"bottle": 0, "breastfeeding": 0}
        for f in feedings:
            type_counts[f["feeding_type"]] += 1
        fig_pie = px.pie(
            names=["🍼 Bottle", "🤱 Breastfeeding"],
            values=list(type_counts.values()),
            title="Feeding type breakdown",
            color_discrete_sequence=["#4F86C6", "#F4A460"],
        )
        fig_pie.update_layout(height=300, margin=dict(t=50, b=30))
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Global metrics ─────────────────────────────────────────────────────
    st.divider()
    total_ml = sum(f["quantity_ml"] for f in feedings)
    avg_per_day = total_ml / nb_days if nb_days else 0
    avg_per_feeding = total_ml / len(feedings) if feedings else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Period total", f"{total_ml} ml")
    m2.metric("Average / day", f"{avg_per_day:.0f} ml")
    m3.metric("Average / feeding", f"{avg_per_feeding:.0f} ml")
    m4.metric("Total feedings", len(feedings))

    # ── Detailed timeline ──────────────────────────────────────────────────
    with st.expander("📋 Feeding detail"):
        for f in sorted(feedings, key=lambda x: x["fed_at"], reverse=True):
            dt = datetime.fromisoformat(f["fed_at"])
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            note = f" — _{f['notes']}_" if f.get("notes") else ""
            st.markdown(
                f"`{dt.strftime('%d/%m %H:%M')}` {icon} **{f['quantity_ml']} ml**{note}"
            )

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3 — AI Analysis
# ─────────────────────────────────────────────────────────────────────────────

elif page == "🤖 AI Analysis":
    st.header(f"🤖 AI Analysis — {selected_baby['name']}")
    st.caption("Powered by Claude · WHO/SFP medical context via RAG")

    col1, col2 = st.columns(2)
    with col1:
        period = st.radio("Period", ["day", "week"],
                          format_func=lambda p: "📅 Day" if p == "day" else "📆 Week",
                          horizontal=True)
    with col2:
        ref_date = st.date_input("Reference date", value=date.today())

    analyze_btn = st.button("🔍 Analyse", use_container_width=True, type="primary")

    if analyze_btn:
        with st.spinner("Claude is analysing the data..."):
            try:
                result = api.get_analysis(
                    baby_id=selected_baby["id"],
                    period=period,
                    reference_date=ref_date,
                )
                st.success(f"Analysis generated for: **{result['period_label']}**")
                st.divider()
                st.markdown(result["analysis"])
            except requests.HTTPError as e:
                detail = e.response.json().get("detail", str(e))
                if e.response.status_code == 404:
                    st.warning(f"⚠️ {detail}")
                else:
                    st.error(f"Error: {detail}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
