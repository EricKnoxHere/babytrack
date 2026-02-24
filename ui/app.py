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
# Config & styling
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BabyTrack",
    page_icon="🍼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better visuals
st.markdown("""
<style>
    /* Main container padding */
    .main { padding-top: 0; }
    
    /* Custom metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-card.positive {
        background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
    }
    .metric-card.warning {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    }
    .metric-card.danger {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    }
    
    /* Better headers */
    h1, h2, h3 { color: #1a2332; font-weight: 700; }
    
    /* Sidebar polish */
    [data-testid="stSidebar"] { background: #f8fafc; }
    
    /* Button styling */
    button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

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


def format_time(dt_str: str) -> str:
    """Format ISO datetime to HH:MM."""
    return datetime.fromisoformat(dt_str).strftime("%H:%M")


def format_datetime(dt_str: str) -> str:
    """Format ISO datetime to dd/mm HH:MM."""
    return datetime.fromisoformat(dt_str).strftime("%d/%m %H:%M")


def display_feeding_with_actions(f: dict, baby_id: int):
    """Display a feeding with edit/delete buttons."""
    col1, col2, col3 = st.columns([3, 0.8, 0.8])
    
    icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
    t = format_datetime(f["fed_at"])
    note = f" · _{f['notes']}_" if f.get("notes") else ""
    
    with col1:
        st.markdown(f"`{t}` {icon} **{f['quantity_ml']}ml**{note}")
    
    with col2:
        if st.button("✏️", key=f"edit_{f['id']}", help="Edit"):
            st.session_state[f"edit_feeding_{f['id']}"] = True
    
    with col3:
        if st.button("🗑️", key=f"del_{f['id']}", help="Delete"):
            try:
                api.delete_feeding(f["id"])
                st.success("✅ Deleted")
                st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")
    
    # Edit form if activated
    if st.session_state.get(f"edit_feeding_{f['id']}"): 
        st.divider()
        st.subheader(f"Edit feeding (ID: {f['id']})")
        with st.form(f"edit_form_{f['id']}"):
            fed_dt = datetime.fromisoformat(f["fed_at"])
            new_date = st.date_input("Date", value=fed_dt.date(), key=f"ed_{f['id']}_date")
            new_time = st.time_input("Time", value=fed_dt.time(), key=f"ed_{f['id']}_time")
            new_qty = st.number_input("Quantity (ml)", value=f["quantity_ml"], min_value=1, max_value=500, key=f"ed_{f['id']}_qty")
            new_type = st.selectbox("Type", ["bottle", "breastfeeding"], index=0 if f["feeding_type"] == "bottle" else 1, key=f"ed_{f['id']}_type")
            new_notes = st.text_input("Notes", value=f.get("notes") or "", key=f"ed_{f['id']}_notes")
            
            if st.form_submit_button("💾 Save changes", use_container_width=True):
                try:
                    new_fed_at = datetime.combine(new_date, new_time).isoformat()
                    api.update_feeding(f["id"], {
                        "fed_at": new_fed_at,
                        "quantity_ml": int(new_qty),
                        "feeding_type": new_type,
                        "notes": new_notes or None,
                    })
                    st.success("✅ Updated")
                    st.session_state[f"edit_feeding_{f['id']}"] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — baby selection
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🍼 BabyTrack")
    st.caption("Infant feeding tracker · RAG + Claude")
    st.divider()

    # API status
    if not api_ok():
        st.error("❌ API offline — run `uvicorn main:app --reload`")
        st.stop()

    rag_status = api.health().get("rag_available", False)
    if rag_status:
        st.success("✅ RAG active")
    else:
        st.warning("⚠️ RAG inactive (analysis without medical context)")
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
            baby_name = st.text_input("First name", placeholder="e.g. Louise")
            baby_dob = st.date_input("Date of birth", value=date.today() - timedelta(days=30))
            baby_weight = st.number_input("Birth weight (g)", min_value=500, max_value=6000, value=3300)
            if st.form_submit_button("✅ Create", use_container_width=True):
                try:
                    baby = api.create_baby(baby_name, baby_dob, int(baby_weight))
                    st.success(f"✅ {baby['name']} created!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        st.stop()

    if not babies:
        st.info("📭 No babies yet. Create one to get started!")
        st.stop()

    baby_options = {f"{b['name']} (id {b['id']}) · {(date.today() - datetime.fromisoformat(b['created_at']).date()).days}d old": b for b in babies}
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

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Add new feeding")
        with st.form("add_feeding"):
            fed_date = st.date_input("Date", value=date.today())
            fed_time = st.time_input("Time", value=datetime.now().time())
            quantity = st.number_input("Quantity (ml)", min_value=1, max_value=500, value=90, step=5)
            f_type = st.selectbox("Type", ["bottle", "breastfeeding"], format_func=feeding_type_label)
            notes = st.text_input("Notes (optional)", placeholder="e.g. baby seemed satisfied")
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
                st.success(f"✅ Saved: {feeding['quantity_ml']}ml {feeding_type_label(f_type)} at {format_time(fed_at)}")
            except requests.HTTPError as e:
                try:
                    detail = e.response.json().get("detail", str(e))
                except Exception:
                    detail = e.response.text or str(e)
                st.error(f"Error: {detail}")

    # Today's overview
    with col2:
        st.subheader("Today's feedings")
        try:
            today_feedings = api.get_feedings(selected_baby["id"], day=date.today())
        except Exception:
            today_feedings = []

        if today_feedings:
            total = sum(f["quantity_ml"] for f in today_feedings)
            col_t1, col_t2 = st.columns(2)
            col_t1.metric("Total", f"{total} ml")
            col_t2.metric("Feedings", len(today_feedings))
            
            st.divider()
            for f in sorted(today_feedings, key=lambda x: x["fed_at"]):
                display_feeding_with_actions(f, selected_baby["id"])
        else:
            st.info("No feedings logged today yet.")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2 — Dashboard
# ─────────────────────────────────────────────────────────────────────────────

elif page == "📊 Dashboard":
    st.header(f"📊 Dashboard — {selected_baby['name']}")

    # Date range selector
    col_range1, col_range2 = st.columns([2, 1])
    with col_range1:
        end_date = st.date_input("Up to", value=date.today(), key="dash_end_date")
    with col_range2:
        nb_days = st.selectbox("Period", [7, 14, 30], format_func=lambda n: f"{n} days", key="dash_period")

    start_date = end_date - timedelta(days=nb_days - 1)

    try:
        feedings = api.get_feedings(selected_baby["id"], start=start_date, end=end_date)
    except Exception as e:
        st.error(f"Could not load feedings: {e}")
        feedings = []

    if not feedings:
        st.info("No feedings recorded for this period.")
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

    # Metrics
    total_ml = sum(f["quantity_ml"] for f in feedings)
    avg_per_day = total_ml / nb_days if nb_days else 0
    avg_per_feeding = total_ml / len(feedings) if feedings else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total volume", f"{total_ml} ml", "📊")
    m2.metric("Daily average", f"{avg_per_day:.0f} ml", "📈")
    m3.metric("Per feeding avg", f"{avg_per_feeding:.0f} ml", "🍼")
    m4.metric("Num feedings", len(feedings), "📝")

    st.divider()

    # Graphs
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        fig_vol = go.Figure()
        fig_vol.add_bar(
            x=days_range, y=totals, name="Volume (ml)",
            marker_color="#4F86C6",
            text=totals, textposition="outside",
        )
        fig_vol.update_layout(
            title="Total volume per day",
            xaxis_title="Date", yaxis_title="ml",
            xaxis=dict(tickformat="%d/%m"),
            height=400, margin=dict(t=50, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_vol, use_container_width=True)

    with col_g2:
        fig_count = go.Figure()
        fig_count.add_bar(
            x=days_range, y=counts, name="Feedings",
            marker_color="#7BC67E",
            text=counts, textposition="outside",
        )
        fig_count.update_layout(
            title="Number of feedings per day",
            xaxis=dict(tickformat="%d/%m"),
            height=400, margin=dict(t=50, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_count, use_container_width=True)

    # Feeding type breakdown
    col_pie1, col_pie2 = st.columns(2)
    with col_pie1:
        type_counts = {"bottle": 0, "breastfeeding": 0}
        for f in feedings:
            type_counts[f["feeding_type"]] += 1
        fig_pie = px.pie(
            names=["🍼 Bottle", "🤱 Breastfeeding"],
            values=list(type_counts.values()),
            title="Feeding type breakdown",
            color_discrete_sequence=["#4F86C6", "#F4A460"],
        )
        fig_pie.update_layout(height=400, margin=dict(t=50, b=30))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_pie2:
        # Recent feedings
        st.subheader("Recent feedings")
        recent = sorted(feedings, key=lambda x: x["fed_at"], reverse=True)[:10]
        for f in recent:
            display_feeding_with_actions(f, selected_baby["id"])

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3 — AI Analysis
# ─────────────────────────────────────────────────────────────────────────────

elif page == "🤖 AI Analysis":
    st.header(f"🤖 AI Analysis — {selected_baby['name']}")
    st.caption("Powered by Claude · WHO/SFP medical context via RAG")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        period = st.radio("Period", ["day", "week"], format_func=lambda p: "Daily" if p == "day" else "Weekly", horizontal=True)
    with col2:
        ref_date = st.date_input("Reference date", value=date.today())
    with col3:
        st.write("")  # spacing
        analyze_btn = st.button("🔍 Analyse", use_container_width=False, type="primary")

    if analyze_btn:
        with st.spinner("Claude is analysing the data..."):
            try:
                result = api.get_analysis(
                    baby_id=selected_baby["id"],
                    period=period,
                    reference_date=ref_date,
                )
                st.success(f"✅ Analysis for: **{result['period_label']}**")
                st.divider()
                st.markdown(result["analysis"])
            except requests.HTTPError as e:
                try:
                    detail = e.response.json().get("detail", str(e))
                except Exception:
                    detail = e.response.text or str(e)
                if e.response.status_code == 404:
                    st.warning(f"⚠️ {detail}")
                else:
                    st.error(f"HTTP {e.response.status_code}: {detail}")
                with st.expander("Debug: Raw response"):
                    st.code(e.response.text or "(empty)")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
