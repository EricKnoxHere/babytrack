"""BabyTrack — Interface Streamlit.

Lancer : streamlit run ui/app.py
API attendue sur http://localhost:8000 (ou BABYTRACK_API_URL).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import plotly.graph_objects as go
import requests
import streamlit as st

import ui.api_client as api

# ── Config page ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BabyTrack",
    page_icon="🍼",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _api_ok() -> bool:
    """Teste si l'API est joignable."""
    try:
        api.health()
        return True
    except Exception:
        return False


def _fmt_date(d: str | date) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return d.strftime("%d/%m/%Y")


# ── Sidebar ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🍼 BabyTrack")
    st.caption("Suivi alimentation nourrisson · IA Claude + RAG")
    st.divider()

    # Status API
    if _api_ok():
        st.success("API connectée", icon="✅")
    else:
        st.error("API non joignable — lance `uvicorn main:app`", icon="🔴")
        st.stop()

    # Sélection / création bébé
    st.subheader("👶 Bébé")
    babies = api.list_babies()

    if not babies:
        st.info("Aucun bébé enregistré.")
        with st.expander("➕ Créer un bébé", expanded=True):
            with st.form("new_baby"):
                n_name = st.text_input("Prénom")
                n_dob = st.date_input("Date de naissance", value=date.today())
                n_weight = st.number_input("Poids de naissance (g)", min_value=500, max_value=6000, value=3200)
                if st.form_submit_button("Créer"):
                    try:
                        api.create_baby(n_name, n_dob, int(n_weight))
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        st.stop()

    baby_names = {b["id"]: f"{b['name']} (né·e {_fmt_date(b['birth_date'])})" for b in babies}
    selected_id = st.selectbox(
        "Choisir un bébé",
        options=list(baby_names.keys()),
        format_func=lambda x: baby_names[x],
    )
    baby = next(b for b in babies if b["id"] == selected_id)

    # Âge
    dob = date.fromisoformat(baby["birth_date"])
    age_days = (date.today() - dob).days
    if age_days < 14:
        age_str = f"{age_days} j"
    elif age_days < 60:
        age_str = f"{age_days // 7} sem"
    else:
        age_str = f"{age_days // 30} mois"
    st.caption(f"🎂 {age_str} · {baby['birth_weight_grams']} g à la naissance")

    # Créer un second bébé
    with st.expander("➕ Ajouter un bébé"):
        with st.form("add_baby"):
            a_name = st.text_input("Prénom")
            a_dob = st.date_input("Date de naissance", value=date.today(), key="add_dob")
            a_weight = st.number_input("Poids de naissance (g)", min_value=500, max_value=6000, value=3200, key="add_w")
            if st.form_submit_button("Créer"):
                try:
                    api.create_baby(a_name, a_dob, int(a_weight))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.divider()

    # Navigation
    page = st.radio(
        "Navigation",
        ["📊 Tableau de bord", "🍼 Saisir un biberon", "🤖 Analyse IA"],
        label_visibility="collapsed",
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — TABLEAU DE BORD
# ══════════════════════════════════════════════════════════════════════════════

if page == "📊 Tableau de bord":
    st.header(f"📊 Tableau de bord — {baby['name']}")

    col_date, col_range = st.columns([2, 3])
    with col_date:
        view_date = st.date_input("Journée", value=date.today(), key="dash_date")
    with col_range:
        n_days = st.slider("Tendance sur N jours", min_value=3, max_value=14, value=7)

    st.divider()

    # ── Stats du jour ───────────────────────────────────────────────────────
    feedings_day = api.get_feedings(selected_id, day=view_date)

    c1, c2, c3, c4 = st.columns(4)
    total_ml = sum(f["quantity_ml"] for f in feedings_day)
    nb = len(feedings_day)
    avg_ml = total_ml // nb if nb else 0

    c1.metric("Biberons aujourd'hui", nb)
    c2.metric("Volume total (ml)", total_ml)
    c3.metric("Volume moyen (ml)", avg_ml)
    c4.metric("Dernier biberon", feedings_day[0]["fed_at"][11:16] + " 🕐" if feedings_day else "—")

    if not feedings_day:
        st.info("Aucune prise enregistrée pour cette journée.")
    else:
        # ── Graphique du jour : quantité par heure ──────────────────────────
        hours = [datetime.fromisoformat(f["fed_at"]).hour for f in feedings_day]
        qtys = [f["quantity_ml"] for f in feedings_day]
        times = [f["fed_at"][11:16] for f in feedings_day]

        fig_day = go.Figure()
        fig_day.add_trace(go.Bar(
            x=times,
            y=qtys,
            marker_color=["#4A90D9" if f["feeding_type"] == "bottle" else "#E8916A" for f in feedings_day],
            text=[f"{q} ml" for q in qtys],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y} ml<extra></extra>",
        ))
        fig_day.update_layout(
            title=f"Biberons du {_fmt_date(view_date)}",
            xaxis_title="Heure",
            yaxis_title="ml",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=320,
            margin=dict(t=50, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_day, use_container_width=True)

    st.divider()

    # ── Tendance sur N jours ────────────────────────────────────────────────
    st.subheader(f"Tendance — {n_days} derniers jours")
    start_trend = view_date - timedelta(days=n_days - 1)
    feedings_range = api.get_feedings(selected_id, start=start_trend, end=view_date)

    if not feedings_range:
        st.info("Pas de données sur cette période.")
    else:
        # Agrégation par jour
        from collections import defaultdict
        daily: dict[str, dict] = defaultdict(lambda: {"total": 0, "count": 0})
        for f in feedings_range:
            d = f["fed_at"][:10]
            daily[d]["total"] += f["quantity_ml"]
            daily[d]["count"] += 1

        days_sorted = sorted(daily.keys())
        totals = [daily[d]["total"] for d in days_sorted]
        counts = [daily[d]["count"] for d in days_sorted]
        labels = [_fmt_date(d) for d in days_sorted]

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(
            x=labels, y=totals, name="Volume total (ml)",
            marker_color="#4A90D9", opacity=0.85,
            yaxis="y1",
        ))
        fig_trend.add_trace(go.Scatter(
            x=labels, y=counts, name="Nb de prises",
            mode="lines+markers",
            line=dict(color="#E8916A", width=2),
            marker=dict(size=6),
            yaxis="y2",
        ))
        fig_trend.update_layout(
            yaxis=dict(title="Volume (ml)", side="left"),
            yaxis2=dict(title="Nb prises", side="right", overlaying="y", showgrid=False),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=320,
            margin=dict(t=30, b=40),
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # Tableau récapitulatif
        with st.expander("📋 Détail par jour"):
            import pandas as pd
            rows = [
                {"Date": _fmt_date(d), "Nb prises": daily[d]["count"], "Volume (ml)": daily[d]["total"]}
                for d in days_sorted
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — SAISIE RAPIDE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🍼 Saisir un biberon":
    st.header(f"🍼 Saisir un biberon — {baby['name']}")

    with st.form("add_feeding", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            f_date = st.date_input("Date", value=date.today())
            f_time = st.time_input("Heure", value=datetime.now().time())
            f_qty = st.number_input("Quantité (ml)", min_value=1, max_value=500, value=90, step=5)
        with col2:
            f_type = st.selectbox(
                "Type",
                options=["bottle", "breastfeeding"],
                format_func=lambda x: "🍼 Biberon" if x == "bottle" else "🤱 Allaitement",
            )
            f_notes = st.text_area("Notes (optionnel)", height=100, placeholder="ex: agité, a tout bu...")

        submitted = st.form_submit_button("✅ Enregistrer", use_container_width=True, type="primary")

    if submitted:
        fed_at = datetime.combine(f_date, f_time).isoformat()
        try:
            result = api.add_feeding(selected_id, fed_at, int(f_qty), f_type, f_notes or None)
            st.success(f"Biberon enregistré ✅ — {result['quantity_ml']} ml à {result['fed_at'][11:16]}")
        except requests.HTTPError as e:
            st.error(f"Erreur API : {e.response.text}")
        except Exception as e:
            st.error(str(e))

    # Historique du jour en bas
    st.divider()
    st.subheader("Aujourd'hui")
    today_feedings = api.get_feedings(selected_id, day=date.today())
    if not today_feedings:
        st.caption("Aucune prise enregistrée aujourd'hui.")
    else:
        for f in today_feedings:
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            note_str = f" — *{f['notes']}*" if f.get("notes") else ""
            st.markdown(f"- **{f['fed_at'][11:16]}** {icon} {f['quantity_ml']} ml{note_str}")
        total = sum(f["quantity_ml"] for f in today_feedings)
        st.caption(f"Total : **{total} ml** en {len(today_feedings)} prise(s)")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — ANALYSE IA
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🤖 Analyse IA":
    st.header(f"🤖 Analyse IA — {baby['name']}")
    st.caption("Analyse alimentaire via Claude 3 Haiku + contexte médical OMS/SFP (RAG)")

    col1, col2 = st.columns(2)
    with col1:
        period = st.radio("Période", ["Journée", "Semaine"], horizontal=True)
        period_key = "day" if period == "Journée" else "week"
    with col2:
        ref_date = st.date_input("Date de référence", value=date.today(), key="analysis_date")

    analyze = st.button("🔍 Analyser", type="primary", use_container_width=True)

    if analyze:
        with st.spinner("Claude analyse les données… ⏳"):
            try:
                result = api.get_analysis(selected_id, period=period_key, reference_date=ref_date)
                st.success(f"Analyse de la **{result['period_label']}**")
                st.divider()
                st.markdown(result["analysis"])
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    st.warning("Aucun biberon enregistré pour cette période. Saisir des données d'abord.")
                else:
                    st.error(f"Erreur API : {e.response.text}")
            except Exception as e:
                st.error(f"Erreur : {e}")
