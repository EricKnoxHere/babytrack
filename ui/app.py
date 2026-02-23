"""BabyTrack — Dashboard Streamlit.

Lancer : streamlit run ui/app.py
         (l'API doit tourner sur localhost:8000)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

import ui.api_client as api

# ─────────────────────────────────────────────────────────────────────────────
# Config globale
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BabyTrack",
    page_icon="🍼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def api_ok() -> bool:
    """Vérifie que l'API répond."""
    try:
        h = api.health()
        return h.get("status") == "ok"
    except Exception:
        return False


def feeding_type_label(t: str) -> str:
    return {"bottle": "🍼 Biberon", "breastfeeding": "🤱 Allaitement"}.get(t, t)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — sélection du bébé
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🍼 BabyTrack")
    st.caption("Suivi d'alimentation nourrisson · RAG + Claude")
    st.divider()

    # Statut API
    if not api_ok():
        st.error("❌ API hors ligne\n\n`uvicorn main:app --reload`")
        st.stop()

    rag_status = api.health().get("rag_available", False)
    st.caption(f"RAG : {'✅ actif' if rag_status else '⚠️ inactif (analyse sans contexte)'}")
    st.divider()

    # Chargement des bébés
    try:
        babies = api.list_babies()
    except Exception as e:
        st.error(f"Impossible de charger les bébés : {e}")
        st.stop()

    # Sélecteur ou création
    st.subheader("👶 Bébé")
    mode = st.radio("", ["Sélectionner", "Créer"], horizontal=True, label_visibility="collapsed")

    if mode == "Créer":
        with st.form("new_baby"):
            baby_name = st.text_input("Prénom")
            baby_dob = st.date_input("Date de naissance", value=date.today() - timedelta(days=30))
            baby_weight = st.number_input("Poids de naissance (g)", min_value=500, max_value=6000, value=3300)
            if st.form_submit_button("✅ Créer"):
                try:
                    baby = api.create_baby(baby_name, baby_dob, int(baby_weight))
                    st.success(f"Bébé **{baby['name']}** créé !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")
        st.stop()

    if not babies:
        st.info("Aucun bébé enregistré. Crée-en un d'abord.")
        st.stop()

    baby_options = {f"{b['name']} (id {b['id']})": b for b in babies}
    selected_label = st.selectbox("", list(baby_options.keys()), label_visibility="collapsed")
    selected_baby: dict = baby_options[selected_label]

    st.divider()
    st.subheader("📅 Navigation")
    page = st.radio(
        "",
        ["🍼 Saisie rapide", "📊 Tableau de bord", "🤖 Analyse IA"],
        label_visibility="collapsed",
    )

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1 — Saisie rapide
# ─────────────────────────────────────────────────────────────────────────────

if page == "🍼 Saisie rapide":
    st.header(f"🍼 Saisie — {selected_baby['name']}")

    with st.form("add_feeding"):
        col1, col2 = st.columns(2)
        with col1:
            fed_date = st.date_input("Date", value=date.today())
            fed_time = st.time_input("Heure", value=datetime.now().time())
        with col2:
            quantity = st.number_input("Quantité (ml)", min_value=1, max_value=500, value=90, step=5)
            f_type = st.selectbox("Type", ["bottle", "breastfeeding"],
                                  format_func=feeding_type_label)
        notes = st.text_input("Notes (optionnel)", placeholder="ex: un peu agité après")

        submitted = st.form_submit_button("✅ Enregistrer", use_container_width=True)

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
            st.success(f"✅ Biberon enregistré : **{feeding['quantity_ml']} ml** à **{fed_time.strftime('%H:%M')}**")
        except requests.HTTPError as e:
            st.error(f"Erreur API : {e.response.json().get('detail', str(e))}")

    # Aperçu du jour
    st.divider()
    st.subheader(f"Biberons du {date.today().strftime('%d/%m/%Y')}")
    try:
        today_feedings = api.get_feedings(selected_baby["id"], day=date.today())
    except Exception:
        today_feedings = []

    if today_feedings:
        total = sum(f["quantity_ml"] for f in today_feedings)
        st.metric("Total aujourd'hui", f"{total} ml", f"{len(today_feedings)} prise(s)")
        for f in sorted(today_feedings, key=lambda x: x["fed_at"]):
            t = datetime.fromisoformat(f["fed_at"]).strftime("%H:%M")
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            note = f" — _{f['notes']}_" if f.get("notes") else ""
            st.markdown(f"- `{t}` {icon} **{f['quantity_ml']} ml**{note}")
    else:
        st.info("Aucun biberon enregistré aujourd'hui.")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2 — Tableau de bord
# ─────────────────────────────────────────────────────────────────────────────

elif page == "📊 Tableau de bord":
    st.header(f"📊 Tableau de bord — {selected_baby['name']}")

    # Sélecteur de plage
    col1, col2 = st.columns([2, 1])
    with col1:
        end_date = st.date_input("Jusqu'au", value=date.today())
    with col2:
        nb_days = st.selectbox("Période", [7, 14, 30], format_func=lambda n: f"{n} jours")

    start_date = end_date - timedelta(days=nb_days - 1)

    try:
        feedings = api.get_feedings(selected_baby["id"], start=start_date, end=end_date)
    except Exception as e:
        st.error(f"Impossible de charger les biberons : {e}")
        feedings = []

    if not feedings:
        st.info("Aucune donnée sur cette période.")
        st.stop()

    # Préparer les données par jour
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

    # ── Graphique 1 : volume par jour ──────────────────────────────────────
    fig_vol = go.Figure()
    fig_vol.add_bar(
        x=days_range, y=totals, name="Volume (ml)",
        marker_color="#4F86C6",
        text=totals, textposition="outside",
    )
    fig_vol.update_layout(
        title="Volume total par jour (ml)",
        xaxis_title="Date", yaxis_title="ml",
        xaxis=dict(tickformat="%d/%m"),
        height=350, margin=dict(t=50, b=30),
    )
    st.plotly_chart(fig_vol, use_container_width=True)

    # ── Graphique 2 : nombre de prises ────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        fig_count = go.Figure()
        fig_count.add_bar(
            x=days_range, y=counts, name="Nombre de prises",
            marker_color="#7BC67E",
            text=counts, textposition="outside",
        )
        fig_count.update_layout(
            title="Nombre de prises par jour",
            xaxis=dict(tickformat="%d/%m"),
            height=300, margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig_count, use_container_width=True)

    with col_b:
        # Répartition biberon vs allaitement
        type_counts = {"bottle": 0, "breastfeeding": 0}
        for f in feedings:
            type_counts[f["feeding_type"]] += 1
        fig_pie = px.pie(
            names=["🍼 Biberon", "🤱 Allaitement"],
            values=list(type_counts.values()),
            title="Répartition des types",
            color_discrete_sequence=["#4F86C6", "#F4A460"],
        )
        fig_pie.update_layout(height=300, margin=dict(t=50, b=30))
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Métriques globales ─────────────────────────────────────────────────
    st.divider()
    total_ml = sum(f["quantity_ml"] for f in feedings)
    avg_per_day = total_ml / nb_days if nb_days else 0
    avg_per_feeding = total_ml / len(feedings) if feedings else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total période", f"{total_ml} ml")
    m2.metric("Moyenne / jour", f"{avg_per_day:.0f} ml")
    m3.metric("Moyenne / prise", f"{avg_per_feeding:.0f} ml")
    m4.metric("Nombre de prises", len(feedings))

    # ── Timeline détaillée ─────────────────────────────────────────────────
    with st.expander("📋 Détail des prises"):
        for f in sorted(feedings, key=lambda x: x["fed_at"], reverse=True):
            dt = datetime.fromisoformat(f["fed_at"])
            icon = "🍼" if f["feeding_type"] == "bottle" else "🤱"
            note = f" — _{f['notes']}_" if f.get("notes") else ""
            st.markdown(
                f"`{dt.strftime('%d/%m %H:%M')}` {icon} **{f['quantity_ml']} ml**{note}"
            )

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3 — Analyse IA
# ─────────────────────────────────────────────────────────────────────────────

elif page == "🤖 Analyse IA":
    st.header(f"🤖 Analyse IA — {selected_baby['name']}")
    st.caption("Propulsé par Claude · Contexte médical OMS/SFP via RAG")

    col1, col2 = st.columns(2)
    with col1:
        period = st.radio("Période", ["day", "week"],
                          format_func=lambda p: "📅 Journée" if p == "day" else "📆 Semaine",
                          horizontal=True)
    with col2:
        ref_date = st.date_input("Date de référence", value=date.today())

    analyze_btn = st.button("🔍 Analyser", use_container_width=True, type="primary")

    if analyze_btn:
        with st.spinner("Claude analyse les données..."):
            try:
                result = api.get_analysis(
                    baby_id=selected_baby["id"],
                    period=period,
                    reference_date=ref_date,
                )
                st.success(f"Analyse générée pour : **{result['period_label']}**")
                st.divider()
                st.markdown(result["analysis"])
            except requests.HTTPError as e:
                detail = e.response.json().get("detail", str(e))
                if e.response.status_code == 404:
                    st.warning(f"⚠️ {detail}")
                else:
                    st.error(f"Erreur : {detail}")
            except Exception as e:
                st.error(f"Erreur inattendue : {e}")
