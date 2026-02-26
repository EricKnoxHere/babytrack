"""Home — Unified feed tracker + analytics."""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from datetime import date, datetime, timedelta
from ui import api_client as api


# ── Period helpers ────────────────────────────────────────────────────────────

_PERIODS = {
    "Aujourd'hui": 0,
    "7 jours": 7,
    "14 jours": 14,
    "30 jours": 30,
}


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    # ── Header ────────────────────────────────────────────────────────────────

    birth_str = baby.get("birth_date") or baby.get("created_at", "")[:10]
    birth = date.fromisoformat(birth_str[:10])
    age_days = (date.today() - birth).days
    age_label = f"{age_days // 30}m {age_days % 30}j" if age_days >= 30 else f"{age_days}j"

    col_title, col_period = st.columns([3, 2])
    with col_title:
        st.markdown(f"## 🍼 {baby['name']} <span style='color:#94a3b8;font-size:1rem;font-weight:400'>{age_label}</span>", unsafe_allow_html=True)
    with col_period:
        period_label = st.radio(
            "period",
            list(_PERIODS.keys()),
            horizontal=True,
            label_visibility="collapsed",
            key="home_period",
        )

    period_days = _PERIODS[period_label]
    today = date.today()

    if period_days == 0:
        start_date = today
        end_date = today
    else:
        end_date = today
        start_date = today - timedelta(days=period_days - 1)

    # ── Quick action buttons ──────────────────────────────────────────────────

    st.markdown("")
    qa_col1, qa_col2, qa_col3, qa_spacer = st.columns([1, 1, 1, 3])

    active = st.session_state.get("_home_widget")

    with qa_col1:
        if st.button(
            "🍼 Biberon" if active != "feeding" else "✕ Fermer",
            use_container_width=True,
            type="primary" if active == "feeding" else "secondary",
            key="qa_feeding",
        ):
            st.session_state._home_widget = None if active == "feeding" else "feeding"
            st.rerun()

    with qa_col2:
        if st.button(
            "⚖️ Poids" if active != "weight" else "✕ Fermer",
            use_container_width=True,
            type="primary" if active == "weight" else "secondary",
            key="qa_weight",
        ):
            st.session_state._home_widget = None if active == "weight" else "weight"
            st.rerun()

    with qa_col3:
        if st.button("💬 Chat", use_container_width=True, type="secondary", key="qa_chat"):
            st.session_state._nav_page = "💬 Chat"
            st.rerun()

    # ── Inline forms ─────────────────────────────────────────────────────────

    if active == "feeding":
        _form_feeding(baby)
    elif active == "weight":
        _form_weight(baby)

    st.markdown("---")

    # ── Load data ─────────────────────────────────────────────────────────────

    try:
        feedings = api.get_feedings(
            baby["id"],
            day=today if period_days == 0 else None,
            start=start_date if period_days > 0 else None,
            end=end_date if period_days > 0 else None,
        )
    except Exception:
        feedings = []

    try:
        weights = api.get_weights(baby["id"])
    except Exception:
        weights = []

    # ── Metrics ───────────────────────────────────────────────────────────────

    total_ml = sum(f["quantity_ml"] for f in feedings)
    count = len(feedings)
    current_weight = weights[-1]["weight_g"] if weights else None

    if feedings:
        last = max(feedings, key=lambda f: f["fed_at"])
        last_dt = datetime.fromisoformat(last["fed_at"])
        mins_ago = int((datetime.now() - last_dt).total_seconds() / 60)
        since_last = f"{mins_ago}min" if mins_ago < 60 else f"{mins_ago // 60}h{mins_ago % 60:02d}"
        last_time = last_dt.strftime("%H:%M")
    else:
        since_last = "—"
        last_time = "—"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Volume", f"{total_ml} ml")
    m2.metric("Biberons", count)
    m3.metric("Dernier", last_time, since_last if feedings else None)
    m4.metric("Poids actuel", f"{current_weight} g" if current_weight else "—")

    # ── Charts (only for multi-day periods) ───────────────────────────────────

    if period_days > 0 and feedings:
        daily: dict = defaultdict(lambda: {"ml": 0, "n": 0})
        for f in feedings:
            d = f["fed_at"][:10]
            daily[d]["ml"] += f["quantity_ml"]
            daily[d]["n"] += 1

        day_range = [(start_date + timedelta(days=i)).isoformat() for i in range(period_days)]
        vols = [daily[d]["ml"] for d in day_range]
        counts_day = [daily[d]["n"] for d in day_range]
        labels_x = [(start_date + timedelta(days=i)).strftime("%d/%m") for i in range(period_days)]

        col_v, col_c = st.columns(2)
        with col_v:
            fig = go.Figure(go.Bar(
                x=labels_x, y=vols,
                marker_color="#3b82f6",
                text=[f"{v}" if v else "" for v in vols],
                textposition="outside",
            ))
            fig.update_layout(
                title="Volume / jour (ml)", height=280,
                margin=dict(t=36, b=0, l=0, r=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_c:
            fig = go.Figure(go.Bar(
                x=labels_x, y=counts_day,
                marker_color="#10b981",
                text=[str(n) if n else "" for n in counts_day],
                textposition="outside",
            ))
            fig.update_layout(
                title="Biberons / jour", height=280,
                margin=dict(t=36, b=0, l=0, r=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    elif period_days > 0 and not feedings:
        st.info("Aucun biberon sur cette période.")

    # ── Feeding timeline ──────────────────────────────────────────────────────

    st.markdown("---")
    title = "Biberons d'aujourd'hui" if period_days == 0 else f"Biberons — {period_label.lower()}"
    st.markdown(f"#### {title}")

    if not feedings:
        st.caption("Rien encore — ajoute un biberon avec le bouton ci-dessus.")
    else:
        for f in sorted(feedings, key=lambda x: x["fed_at"], reverse=True):
            t = datetime.fromisoformat(f["fed_at"]).strftime("%d/%m %H:%M" if period_days > 0 else "%H:%M")
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            note = f"  ·  _{f['notes']}_" if f.get("notes") else ""
            qty_label = f"{f['quantity_ml']} ml"

            row_info, row_del = st.columns([8, 1])
            with row_info:
                st.markdown(f"`{t}`  {icon} **{qty_label}**{note}")
            with row_del:
                if st.button("✕", key=f"del_f_{f['id']}", help="Supprimer"):
                    try:
                        api.delete_feeding(f["id"])
                        st.rerun()
                    except Exception:
                        pass

    # ── Weight curve ──────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("#### ⚖️ Courbe de poids")

    if weights:
        w_labels = [datetime.fromisoformat(w["measured_at"]).strftime("%d/%m") for w in weights]
        w_vals = [w["weight_g"] for w in weights]

        fig = go.Figure(go.Scatter(
            x=w_labels, y=w_vals,
            mode="lines+markers",
            line=dict(color="#3b82f6", width=3),
            marker=dict(size=7, color="#3b82f6"),
            hovertemplate="%{y} g<extra></extra>",
        ))
        fig.update_layout(
            height=260,
            margin=dict(t=10, b=0, l=0, r=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        if len(weights) >= 2:
            gain = weights[-1]["weight_g"] - weights[0]["weight_g"]
            sign = "+" if gain >= 0 else ""
            st.caption(f"📈 {sign}{gain} g depuis la première mesure")
    else:
        st.caption("Aucune donnée de poids — ajoute une mesure avec le bouton ⚖️ ci-dessus.")


# ── Inline forms ──────────────────────────────────────────────────────────────

def _form_feeding(baby: dict):
    with st.container():
        st.markdown(
            "<div style='background:#f0f9ff;border:1px solid #bae6fd;"
            "border-radius:12px;padding:1rem 1.25rem;margin-bottom:1rem'>",
            unsafe_allow_html=True,
        )
        st.markdown("**🍼 Nouveau biberon**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            fed_date = st.date_input("Date", value=date.today(), key="ff_date", label_visibility="collapsed")
        with c2:
            fed_time = st.time_input("Heure", value=datetime.now().time(), key="ff_time", label_visibility="collapsed")
        with c3:
            qty = st.number_input("ml", 1, 500, 90, step=10, key="ff_qty")
        with c4:
            ftype = st.selectbox(
                "Type", ["bottle", "breastfeeding"],
                format_func=lambda t: "🍼 Biberon" if t == "bottle" else "🤱 Sein",
                key="ff_type",
                label_visibility="collapsed",
            )
        notes = st.text_input("Notes (optionnel)", key="ff_notes", placeholder="ex : bébé avait faim")
        col_save, col_cancel = st.columns([1, 4])
        with col_save:
            if st.button("✅ Enregistrer", type="primary", use_container_width=True, key="ff_save"):
                fed_at = datetime.combine(fed_date, fed_time).isoformat()
                try:
                    api.add_feeding(baby["id"], fed_at, int(qty), ftype, notes or None)
                    st.session_state._home_widget = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")
        st.markdown("</div>", unsafe_allow_html=True)


def _form_weight(baby: dict):
    with st.container():
        st.markdown(
            "<div style='background:#f0fdf4;border:1px solid #bbf7d0;"
            "border-radius:12px;padding:1rem 1.25rem;margin-bottom:1rem'>",
            unsafe_allow_html=True,
        )
        st.markdown("**⚖️ Nouvelle mesure de poids**")
        c1, c2, c3 = st.columns(3)
        with c1:
            w_date = st.date_input("Date", value=date.today(), key="wf_date", label_visibility="collapsed")
        with c2:
            w_time = st.time_input("Heure", value=datetime.now().time(), key="wf_time", label_visibility="collapsed")
        with c3:
            w_g = st.number_input("Poids (g)", 500, 20000, 3200, step=50, key="wf_g")
        w_notes = st.text_input("Notes (optionnel)", key="wf_notes", placeholder="ex : visite pédiatre")
        col_save, col_cancel = st.columns([1, 4])
        with col_save:
            if st.button("✅ Enregistrer", type="primary", use_container_width=True, key="wf_save"):
                w_at = datetime.combine(w_date, w_time).isoformat()
                try:
                    api.add_weight(baby["id"], w_at, int(w_g), w_notes or None)
                    st.session_state._home_widget = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")
        st.markdown("</div>", unsafe_allow_html=True)
