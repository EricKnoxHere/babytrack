"""Dashboard — Charts, weight tracking, and past AI reports."""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from datetime import date, datetime, timedelta
from ui import api_client as api


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    st.markdown(f"## 📊 Dashboard – {baby['name']}")

    # ── Period selector ──────────────────────────────────────────────────────

    col_p, col_d = st.columns([1, 1])
    with col_p:
        days = st.selectbox("Period", [7, 14, 30], format_func=lambda n: f"{n} days", key="d_period")
    with col_d:
        end_date = st.date_input("Up to", value=date.today(), key="d_end")

    start_date = end_date - timedelta(days=days - 1)

    # ── Load data ────────────────────────────────────────────────────────────

    try:
        feedings = api.get_feedings(baby["id"], start=start_date, end=end_date)
    except Exception:
        feedings = []

    try:
        weights = api.get_weights(baby["id"])
    except Exception:
        weights = []

    if not feedings:
        st.info("No feedings for this period.")
        _render_weight_section(baby, weights)
        _render_reports_section(baby)
        return

    # ── Metrics ──────────────────────────────────────────────────────────────

    total_ml = sum(f["quantity_ml"] for f in feedings)
    avg_day = total_ml / days
    avg_feed = total_ml / len(feedings)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total volume", f"{total_ml} ml")
    c2.metric("Daily avg", f"{avg_day:.0f} ml")
    c3.metric("Per feeding", f"{avg_feed:.0f} ml")

    # ── Charts ───────────────────────────────────────────────────────────────

    daily = defaultdict(lambda: {"ml": 0, "n": 0})
    for f in feedings:
        d = f["fed_at"][:10]
        daily[d]["ml"] += f["quantity_ml"]
        daily[d]["n"] += 1

    day_range = [(start_date + timedelta(days=i)).isoformat() for i in range(days)]
    vols = [daily[d]["ml"] for d in day_range]
    counts = [daily[d]["n"] for d in day_range]

    col_v, col_c = st.columns(2)

    with col_v:
        fig = go.Figure(go.Bar(x=day_range, y=vols, marker_color="#3b82f6", text=vols, textposition="outside"))
        fig.update_layout(title="Volume / day", xaxis_tickformat="%d/%m", height=350, margin=dict(t=40, b=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_c:
        fig = go.Figure(go.Bar(x=day_range, y=counts, marker_color="#10b981", text=counts, textposition="outside"))
        fig.update_layout(title="Feedings / day", xaxis_tickformat="%d/%m", height=350, margin=dict(t=40, b=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Weight section ───────────────────────────────────────────────────────

    _render_weight_section(baby, weights)

    # ── Past AI reports ──────────────────────────────────────────────────────

    _render_reports_section(baby)


# ── Weight sub-section ───────────────────────────────────────────────────────

def _render_weight_section(baby: dict, weights: list):
    st.markdown("---")
    st.markdown("#### ⚖️ Weight")

    # Log weight form
    with st.expander("➕ Log weight", expanded=False):
        col_l, col_r = st.columns(2)
        with col_l:
            w_date = st.date_input("Date", value=date.today(), key="w_date")
            w_time = st.time_input("Time", value=datetime.now().time(), key="w_time")
        with col_r:
            w_g = st.number_input("Weight (g)", 500, 20000, 3200, step=50, key="w_g")
        w_notes = st.text_input("Notes", key="w_notes", placeholder="e.g. pediatrician visit")

        if st.button("✅ Save weight", use_container_width=True, type="primary", key="w_save"):
            w_at = datetime.combine(w_date, w_time).isoformat()
            try:
                api.add_weight(baby["id"], w_at, int(w_g), w_notes or None)
                st.success("Saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # Growth chart
    if weights:
        w_dates = [datetime.fromisoformat(w["measured_at"]).strftime("%d/%m") for w in weights]
        w_vals = [w["weight_g"] for w in weights]

        fig = go.Figure(go.Scatter(x=w_dates, y=w_vals, mode="lines+markers",
                                   line=dict(color="#3b82f6", width=3), marker=dict(size=7)))
        fig.update_layout(title="Growth curve", height=300, margin=dict(t=40, b=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        if len(weights) >= 2:
            gain = weights[-1]["weight_g"] - weights[0]["weight_g"]
            st.caption(f"📈 +{gain}g since first measurement")
    else:
        st.caption("No weight data yet.")


# ── Reports sub-section ──────────────────────────────────────────────────────

def _render_reports_section(baby: dict):
    st.markdown("---")
    st.markdown("#### 🤖 Past AI analyses")

    try:
        reports = api.list_analysis_history(baby["id"], limit=10)
    except Exception:
        reports = []

    if not reports:
        st.caption("No reports yet — use the Chat page to analyze.")
        return

    for r in reports:
        created = datetime.fromisoformat(r["created_at"]).strftime("%d/%m %H:%M")
        badge = "🕐" if r.get("is_partial") else "✅"

        with st.expander(f"{badge} {r['period_label']}  ·  {created}"):
            try:
                full = api.get_analysis_report(baby["id"], r["id"])
                st.markdown(full["analysis"])
                if full.get("sources"):
                    st.caption("📚 " + " · ".join(s["source"] for s in full["sources"]))
            except Exception as e:
                st.error(f"Could not load: {e}")
