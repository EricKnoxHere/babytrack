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

    # ── Header ───────────────────────────────────────────────────────────────

    st.markdown("## 🏠 Home")

    today = date.today()

    # ── Load data ────────────────────────────────────────────────────────────

    try:
        all_feedings = api.get_feedings(baby["id"], start=birth, end=today)
    except Exception:
        all_feedings = []

    try:
        weights = api.get_weights(baby["id"])
    except Exception:
        weights = []

    try:
        all_diapers = api.get_diapers(baby["id"], start=birth, end=today)
    except Exception:
        all_diapers = []

    # ── Today's data for metrics ─────────────────────────────────────────────

    today_feedings = [f for f in all_feedings if f["fed_at"][:10] == today.isoformat()]
    today_diapers = [d for d in all_diapers if d["changed_at"][:10] == today.isoformat()]

    # ── Metrics row (always today) ───────────────────────────────────────────

    total_ml = sum(f["quantity_ml"] for f in today_feedings)
    count = len(today_feedings)
    current_weight = weights[-1]["weight_g"] if weights else None

    if today_feedings:
        last = max(today_feedings, key=lambda f: f["fed_at"])
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

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total volume", f"{total_ml} ml")
    m2.metric("Feedings", count)
    m3.metric("Last feeding", last_time, since_str)
    m4.metric("Current weight", f"{current_weight} g" if current_weight else "—")
    diaper_count = len(today_diapers)
    pee_count = sum(1 for d in today_diapers if d.get("has_pee"))
    poop_count = sum(1 for d in today_diapers if d.get("has_poop"))
    m5.metric("Diapers", f"{diaper_count}", f"💧{pee_count} 💩{poop_count}")

    # ── Period selector for charts ───────────────────────────────────────────

    period_label = st.selectbox(
        "Period",
        list(_PERIODS.keys()),
        index=2,                       # default = "Last week"
        key="home_period",
        label_visibility="collapsed",
    )

    period_days = _PERIODS[period_label]

    if period_days == 0:
        start_date = today
    elif period_days == -1:
        start_date = birth
    else:
        start_date = today - timedelta(days=period_days - 1)

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

    # ── Diaper chart (full width) ────────────────────────────────────────────

    st.markdown("#### Diapers per day")

    if not all_diapers:
        st.caption("No diaper data yet.")
    else:
        daily_pee: dict = defaultdict(int)
        daily_poop: dict = defaultdict(int)
        for d in all_diapers:
            day_str = d["changed_at"][:10]
            if day_str >= start_date.isoformat():
                if d.get("has_pee"):
                    daily_pee[day_str] += 1
                if d.get("has_poop"):
                    daily_poop[day_str] += 1

        chart_days_count = (today - start_date).days + 1
        days = [start_date + timedelta(days=i) for i in range(chart_days_count)]
        pee_vals = [daily_pee.get(d.isoformat(), 0) for d in days]
        poop_vals = [daily_poop.get(d.isoformat(), 0) for d in days]
        labels = [d.strftime("%d/%m") for d in days]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=pee_vals, name="💧 Pee",
            marker_color="#60a5fa",
        ))
        fig.add_trace(go.Bar(
            x=labels, y=poop_vals, name="💩 Poop",
            marker_color="#f59e0b",
        ))
        fig.update_layout(
            barmode="stack",
            height=300,
            margin=dict(t=8, b=0, l=0, r=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9", title="count", dtick=1),
            xaxis=dict(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

        recorded_days = len(set(list(daily_pee.keys()) + list(daily_poop.keys())))
        total_changes = len([d for d in all_diapers if d["changed_at"][:10] >= start_date.isoformat()])
        if recorded_days:
            st.caption(f"Avg {total_changes / recorded_days:.1f} changes/day over {recorded_days} recorded days")
