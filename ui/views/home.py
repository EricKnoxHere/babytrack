"""Home — Dashboard with metrics and charts."""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from datetime import date, datetime, timedelta
from ui import api_client as api


# ── Period config ─────────────────────────────────────────────────────────────

_PERIODS = {
    "Today": 0,
    "Last 3 days": 3,
    "Last week": 7,
    "Last 14 days": 14,
    "Last month": 30,
    "All time": -1,
}


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    # ── Baby info ──────────────────────────────────────────────────────────────

    birth_str = baby.get("birth_date") or baby.get("created_at", "")[:10]
    birth = date.fromisoformat(birth_str[:10])
    age_days = (date.today() - birth).days
    age_label = f"{age_days // 30}mo {age_days % 30}d" if age_days >= 30 else f"{age_days} days old"

    # ── Header row: title + period selector ──────────────────────────────────

    h_col, p_col = st.columns([3, 1])
    with h_col:
        st.markdown(
            f"## 🍼 {baby['name']} "
            f"<span style='color:#94a3b8;font-size:1rem;font-weight:400'>{age_label}</span>",
            unsafe_allow_html=True,
        )
    with p_col:
        period_label = st.selectbox(
            "Period",
            list(_PERIODS.keys()),
            index=0,
            key="home_period",
            label_visibility="collapsed",
        )

    period_days = _PERIODS[period_label]
    today = date.today()

    # Compute date range
    if period_days == 0:
        start_date = today
    elif period_days == -1:
        start_date = birth
    else:
        start_date = today - timedelta(days=period_days - 1)

    # ── Load data ────────────────────────────────────────────────────────────

    try:
        all_feedings = api.get_feedings(baby["id"], start=birth, end=today)
    except Exception:
        all_feedings = []

    try:
        weights = api.get_weights(baby["id"])
    except Exception:
        weights = []

    # Filter feedings for selected period
    if period_days == 0:
        period_feedings = [f for f in all_feedings if f["fed_at"][:10] == today.isoformat()]
    elif period_days == -1:
        period_feedings = all_feedings
    else:
        period_feedings = [
            f for f in all_feedings
            if f["fed_at"][:10] >= start_date.isoformat()
        ]

    # ── Metrics row ──────────────────────────────────────────────────────────

    total_ml = sum(f["quantity_ml"] for f in period_feedings)
    count = len(period_feedings)
    current_weight = weights[-1]["weight_g"] if weights else None

    if period_feedings:
        last = max(period_feedings, key=lambda f: f["fed_at"])
        last_dt = datetime.fromisoformat(last["fed_at"])
        mins_ago = int((datetime.now() - last_dt).total_seconds() / 60)
        since_str = (
            f"{mins_ago}min ago" if mins_ago < 60
            else f"{mins_ago // 60}h{mins_ago % 60:02d} ago"
        )
        last_time = last_dt.strftime("%H:%M")
    else:
        since_str = None
        last_time = "—"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total volume", f"{total_ml} ml")
    m2.metric("Feedings", count)
    m3.metric("Last feeding", last_time, since_str)
    m4.metric("Current weight", f"{current_weight} g" if current_weight else "—")

    # ── Volume chart (full width) ────────────────────────────────────────────

    st.markdown("#### Daily volume (ml)")

    if not all_feedings:
        st.caption("No feeding data yet.")
    else:
        daily: dict = defaultdict(int)
        for f in all_feedings:
            d = f["fed_at"][:10]
            if d >= start_date.isoformat():
                daily[d] += f["quantity_ml"]

        chart_days_count = (today - start_date).days + 1
        days = [start_date + timedelta(days=i) for i in range(chart_days_count)]
        vols = [daily.get(d.isoformat(), 0) for d in days]
        labels = [d.strftime("%d/%m") for d in days]

        if chart_days_count > 30:
            trace = go.Scatter(
                x=labels, y=vols,
                mode="lines",
                line=dict(color="#3b82f6", width=2),
                fill="tozeroy",
                fillcolor="rgba(59,130,246,0.12)",
            )
        else:
            trace = go.Bar(x=labels, y=vols, marker_color="#3b82f6")

        fig = go.Figure(trace)
        fig.update_layout(
            height=300,
            margin=dict(t=8, b=0, l=0, r=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9", title="ml"),
            xaxis=dict(showgrid=False),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        recorded = [v for v in vols if v > 0]
        if recorded:
            avg = sum(recorded) / len(recorded)
            st.caption(f"Avg {avg:.0f} ml/day over {len(recorded)} recorded days")

    # ── Weight curve (full width) ────────────────────────────────────────────

    st.markdown("#### Weight curve")

    if not weights:
        st.caption("No weight data yet.")
    else:
        w_labels = [
            datetime.fromisoformat(w["measured_at"]).strftime("%d/%m") for w in weights
        ]
        w_vals = [w["weight_g"] for w in weights]

        fig = go.Figure(go.Scatter(
            x=w_labels, y=w_vals,
            mode="lines+markers",
            line=dict(color="#10b981", width=3),
            marker=dict(size=6, color="#10b981"),
            hovertemplate="%{y} g<extra></extra>",
        ))
        fig.update_layout(
            height=300,
            margin=dict(t=8, b=0, l=0, r=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9", title="g"),
            xaxis=dict(showgrid=False),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        latest = weights[-1]["weight_g"]
        if len(weights) >= 2:
            gain = latest - weights[0]["weight_g"]
            sign = "+" if gain >= 0 else ""
            st.caption(f"{latest} g  ·  {sign}{gain} g since first measurement")
        else:
            st.caption(f"Current: {latest} g")
