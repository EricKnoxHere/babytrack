"""Home — Feed tracker + analytics."""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from datetime import date, datetime, timedelta
from ui import api_client as api


# ── Period helpers ────────────────────────────────────────────────────────────

_PERIOD_OPTIONS = ["Today", "7 days", "14 days", "30 days"]
_PERIOD_DAYS = {"Today": 0, "7 days": 7, "14 days": 14, "30 days": 30}


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    # ── Baby info ──────────────────────────────────────────────────────────────

    birth_str = baby.get("birth_date") or baby.get("created_at", "")[:10]
    birth = date.fromisoformat(birth_str[:10])
    age_days = (date.today() - birth).days
    age_label = f"{age_days // 30}mo {age_days % 30}d" if age_days >= 30 else f"{age_days} days old"

    # ── Header (full width) ──────────────────────────────────────────────────

    st.markdown(
        f"## 🍼 {baby['name']} "
        f"<span style='color:#94a3b8;font-size:1rem;font-weight:400'>{age_label}</span>",
        unsafe_allow_html=True,
    )

    # ── Quick action buttons ──────────────────────────────────────────────────

    active = st.session_state.get("_home_widget")
    qa1, qa2, _sp = st.columns([1, 1, 5])

    with qa1:
        if st.button(
            "✕ Close" if active == "feeding" else "+ Bottle 🍼",
            use_container_width=True,
            type="primary" if active == "feeding" else "secondary",
            key="qa_feeding",
        ):
            st.session_state._home_widget = None if active == "feeding" else "feeding"
            st.rerun()

    with qa2:
        if st.button(
            "✕ Close" if active == "weight" else "+ Weight ⚖️",
            use_container_width=True,
            type="primary" if active == "weight" else "secondary",
            key="qa_weight",
        ):
            st.session_state._home_widget = None if active == "weight" else "weight"
            st.rerun()

    # ── Inline form ──────────────────────────────────────────────────────────

    if active == "feeding":
        _form_feeding(baby)
    elif active == "weight":
        _form_weight(baby)

    # ── Load data ────────────────────────────────────────────────────────────

    today = date.today()
    try:
        today_feedings = api.get_feedings(baby["id"], day=today)
    except Exception:
        today_feedings = []

    try:
        all_feedings = api.get_feedings(baby["id"], start=birth, end=today)
    except Exception:
        all_feedings = []

    try:
        weights = api.get_weights(baby["id"])
    except Exception:
        weights = []

    # ── 3-column widget row ───────────────────────────────────────────────────

    st.markdown("")
    col_today, col_vol, col_wt = st.columns(3)

    with col_today:
        _widget_today(today_feedings, weights)

    with col_vol:
        _widget_volume_chart(all_feedings, birth, today)

    with col_wt:
        _widget_weight_chart(weights)

    # ── Period selector + timeline ────────────────────────────────────────────

    st.markdown("---")
    period_label = st.radio(
        "Show feedings for",
        _PERIOD_OPTIONS,
        horizontal=True,
        key="home_period",
    )
    period_days = _PERIOD_DAYS[period_label]

    if period_days == 0:
        timeline_feedings = today_feedings
    else:
        cutoff = today - timedelta(days=period_days - 1)
        timeline_feedings = [
            f for f in all_feedings
            if f["fed_at"][:10] >= cutoff.isoformat()
        ]

    _feeding_timeline(timeline_feedings, period_days)


# ── Widget: Today's numbers ───────────────────────────────────────────────────

def _widget_today(feedings: list, weights: list):
    total_ml = sum(f["quantity_ml"] for f in feedings)
    count = len(feedings)
    current_weight = weights[-1]["weight_g"] if weights else None

    if feedings:
        last = max(feedings, key=lambda f: f["fed_at"])
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

    st.markdown("**Today**")
    st.metric("Volume", f"{total_ml} ml")
    st.metric("Feedings", count)
    st.metric("Last feeding", last_time, since_str)
    st.metric("Current weight", f"{current_weight} g" if current_weight else "—")


# ── Widget: Daily volume since birth ──────────────────────────────────────────

def _widget_volume_chart(all_feedings: list, birth: date, today: date):
    st.markdown("**Daily volume (ml)**")

    if not all_feedings:
        st.caption("No feeding data yet.")
        return

    daily: dict = defaultdict(int)
    for f in all_feedings:
        daily[f["fed_at"][:10]] += f["quantity_ml"]

    total_days = (today - birth).days + 1
    days = [birth + timedelta(days=i) for i in range(total_days)]
    vols = [daily.get(d.isoformat(), 0) for d in days]
    labels = [d.strftime("%d/%m") for d in days]

    # Line + fill for long histories, bars for short
    if total_days > 30:
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
        height=260,
        margin=dict(t=4, b=0, l=0, r=0),
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


# ── Widget: Weight curve since birth ──────────────────────────────────────────

def _widget_weight_chart(weights: list):
    st.markdown("**Weight**")

    if not weights:
        st.caption("No weight data yet.")
        return

    w_labels = [
        datetime.fromisoformat(w["measured_at"]).strftime("%d/%m") for w in weights
    ]
    w_vals = [w["weight_g"] for w in weights]

    fig = go.Figure(go.Scatter(
        x=w_labels, y=w_vals,
        mode="lines+markers",
        line=dict(color="#3b82f6", width=3),
        marker=dict(size=6, color="#3b82f6"),
        hovertemplate="%{y} g<extra></extra>",
    ))
    fig.update_layout(
        height=260,
        margin=dict(t=4, b=0, l=0, r=0),
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


# ── Feeding timeline ──────────────────────────────────────────────────────────

def _feeding_timeline(feedings: list, period_days: int):
    st.markdown("#### Feedings")

    if not feedings:
        st.caption("Nothing recorded yet — log a bottle with the button above.")
        return

    for f in sorted(feedings, key=lambda x: x["fed_at"], reverse=True):
        fmt = "%d/%m %H:%M" if period_days > 0 else "%H:%M"
        t = datetime.fromisoformat(f["fed_at"]).strftime(fmt)
        icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
        note = f"  ·  _{f['notes']}_" if f.get("notes") else ""

        row_info, row_del = st.columns([8, 1])
        with row_info:
            st.markdown(f"`{t}`  {icon} **{f['quantity_ml']} ml**{note}")
        with row_del:
            if st.button("✕", key=f"del_f_{f['id']}", help="Delete"):
                try:
                    api.delete_feeding(f["id"])
                    st.rerun()
                except Exception:
                    pass


# ── Inline forms ──────────────────────────────────────────────────────────────

def _form_feeding(baby: dict):
    st.markdown(
        "<div style='background:#f0f9ff;border:1px solid #bae6fd;"
        "border-radius:12px;padding:1rem 1.25rem;margin:0.5rem 0 1rem'>",
        unsafe_allow_html=True,
    )
    st.markdown("**🍼 Log a bottle**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        fed_date = st.date_input("Date", value=date.today(), key="ff_date")
    with c2:
        fed_time = st.time_input("Time", value=datetime.now().time(), key="ff_time")
    with c3:
        qty = st.number_input("Amount (ml)", 1, 500, 90, step=10, key="ff_qty")
    with c4:
        ftype = st.selectbox(
            "Type", ["bottle", "breastfeeding"],
            format_func=lambda t: "🍼 Bottle" if t == "bottle" else "🤱 Breast",
            key="ff_type",
        )
    notes = st.text_input("Notes (optional)", key="ff_notes", placeholder="e.g. baby was hungry")
    col_save, _ = st.columns([1, 4])
    with col_save:
        if st.button("✅ Save", type="primary", use_container_width=True, key="ff_save"):
            fed_at = datetime.combine(fed_date, fed_time).isoformat()
            try:
                api.add_feeding(baby["id"], fed_at, int(qty), ftype, notes or None)
                st.session_state._home_widget = None
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    st.markdown("</div>", unsafe_allow_html=True)


def _form_weight(baby: dict):
    st.markdown(
        "<div style='background:#f0fdf4;border:1px solid #bbf7d0;"
        "border-radius:12px;padding:1rem 1.25rem;margin:0.5rem 0 1rem'>",
        unsafe_allow_html=True,
    )
    st.markdown("**⚖️ Log weight**")
    c1, c2, c3 = st.columns(3)
    with c1:
        w_date = st.date_input("Date", value=date.today(), key="wf_date")
    with c2:
        w_time = st.time_input("Time", value=datetime.now().time(), key="wf_time")
    with c3:
        w_g = st.number_input("Weight (g)", 500, 20000, 3200, step=50, key="wf_g")
    w_notes = st.text_input("Notes (optional)", key="wf_notes", placeholder="e.g. pediatrician visit")
    col_save, _ = st.columns([1, 4])
    with col_save:
        if st.button("✅ Save", type="primary", use_container_width=True, key="wf_save"):
            w_at = datetime.combine(w_date, w_time).isoformat()
            try:
                api.add_weight(baby["id"], w_at, int(w_g), w_notes or None)
                st.session_state._home_widget = None
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
