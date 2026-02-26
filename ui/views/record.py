"""Records — Unified table of all feedings and weights."""

import streamlit as st
import requests
from datetime import date, datetime
from ui import api_client as api


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    st.markdown("## 📋 Records")

    # ── Load data ────────────────────────────────────────────────────────────

    try:
        feedings = api.get_feedings(baby["id"])
    except Exception:
        feedings = []

    try:
        weights = api.get_weights(baby["id"])
    except Exception:
        weights = []

    try:
        diapers = api.get_diapers(baby["id"])
    except Exception:
        diapers = []

    # ── Build unified rows ───────────────────────────────────────────────────

    rows = []

    for f in feedings:
        icon = "🍼 Bottle" if f["feeding_type"] == "bottle" else "🤱 Breast"
        rows.append({
            "type": icon,
            "date": datetime.fromisoformat(f["fed_at"]).strftime("%Y-%m-%d %H:%M"),
            "value": f"{f['quantity_ml']} ml",
            "notes": f.get("notes") or "",
            "_sort": f["fed_at"],
            "_kind": "feeding",
            "_id": f["id"],
            "_raw": f,
        })

    for w in weights:
        rows.append({
            "type": "⚖️ Weight",
            "date": datetime.fromisoformat(w["measured_at"]).strftime("%Y-%m-%d %H:%M"),
            "value": f"{w['weight_g']} g",
            "notes": w.get("notes") or "",
            "_sort": w["measured_at"],
            "_kind": "weight",
            "_id": w["id"],
            "_raw": w,
        })

    for d in diapers:
        pee = "💧" if d.get("has_pee") else ""
        poop = "💩" if d.get("has_poop") else ""
        value = f"{pee}{poop}".strip() or "—"
        rows.append({
            "type": "🧷 Diaper",
            "date": datetime.fromisoformat(d["changed_at"]).strftime("%Y-%m-%d %H:%M"),
            "value": value,
            "notes": d.get("notes") or "",
            "_sort": d["changed_at"],
            "_kind": "diaper",
            "_id": d["id"],
            "_raw": d,
        })

    # Sort newest first
    rows.sort(key=lambda r: r["_sort"], reverse=True)

    if not rows:
        st.info("No records yet. Add a bottle or weight entry using the sidebar.")
        return

    # ── Filter ───────────────────────────────────────────────────────────────

    filter_options = ["All", "🍼 Bottle", "🤱 Breast", "⚖️ Weight", "🧷 Diaper"]
    selected_filter = st.selectbox(
        "Filter by type",
        filter_options,
        index=0,
        key="record_filter",
        label_visibility="collapsed",
    )

    if selected_filter != "All":
        rows = [r for r in rows if r["type"] == selected_filter]

    st.caption(f"{len(rows)} records")

    # ── Display rows with Edit / Remove buttons ─────────────────────────────

    # Session state for editing
    if "_editing_record" not in st.session_state:
        st.session_state._editing_record = None

    for i, r in enumerate(rows):
        col_type, col_date, col_val, col_notes, col_edit, col_del = st.columns(
            [1.2, 1.5, 1, 2, 0.6, 0.6]
        )
        with col_type:
            st.markdown(r["type"])
        with col_date:
            st.markdown(r["date"])
        with col_val:
            st.markdown(f"**{r['value']}**")
        with col_notes:
            st.markdown(r["notes"] if r["notes"] else "—")
        with col_edit:
            if st.button("✏️", key=f"edit_{i}", help="Edit"):
                st.session_state._editing_record = i if st.session_state._editing_record != i else None
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{i}", help="Remove"):
                try:
                    if r["_kind"] == "feeding":
                        api.delete_feeding(r["_id"])
                    elif r["_kind"] == "diaper":
                        api.delete_diaper(r["_id"])
                    else:
                        resp = requests.delete(
                            f"{api.API_BASE}/weights/{r['_id']}", timeout=api.TIMEOUT
                        )
                        resp.raise_for_status()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        # ── Inline edit form ─────────────────────────────────────────────────
        if st.session_state._editing_record == i:
            _render_edit_form(r, i, baby)

        # Subtle separator
        if i < len(rows) - 1:
            st.markdown(
                "<hr style='margin:0;border:none;border-top:1px solid #f1f5f9'>",
                unsafe_allow_html=True,
            )


def _render_edit_form(row: dict, idx: int, baby: dict):
    """Render an inline edit form for a record."""
    raw = row["_raw"]
    kind = row["_kind"]

    with st.form(f"edit_form_{idx}", clear_on_submit=False):
        if kind == "feeding":
            dt = datetime.fromisoformat(raw["fed_at"])
            e_date = st.date_input("Date", value=dt.date(), key=f"edt_{idx}")
            e_time = st.time_input("Time", value=dt.time(), key=f"etm_{idx}")
            e_qty = st.number_input(
                "Amount (ml)", 1, 500, int(raw["quantity_ml"]), step=10, key=f"eqt_{idx}"
            )
            e_type = st.selectbox(
                "Type", ["bottle", "breastfeeding"],
                index=0 if raw["feeding_type"] == "bottle" else 1,
                format_func=lambda t: "🍼 Bottle" if t == "bottle" else "🤱 Breast",
                key=f"etp_{idx}",
            )
            e_notes = st.text_input("Notes", value=raw.get("notes") or "", key=f"ent_{idx}")
            submitted = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
            if submitted:
                new_at = datetime.combine(e_date, e_time).isoformat()
                try:
                    api.update_feeding(raw["id"], {
                        "fed_at": new_at,
                        "quantity_ml": int(e_qty),
                        "feeding_type": e_type,
                        "notes": e_notes or None,
                    })
                    st.session_state._editing_record = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        elif kind == "diaper":
            dt = datetime.fromisoformat(raw["changed_at"])
            e_date = st.date_input("Date", value=dt.date(), key=f"edt_{idx}")
            e_time = st.time_input("Time", value=dt.time(), key=f"etm_{idx}")
            e_pee = st.checkbox("💧 Pee", value=bool(raw.get("has_pee", True)), key=f"epee_{idx}")
            e_poop = st.checkbox("💩 Poop", value=bool(raw.get("has_poop", False)), key=f"epoop_{idx}")
            e_notes = st.text_input("Notes", value=raw.get("notes") or "", key=f"ent_{idx}")
            submitted = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
            if submitted:
                new_at = datetime.combine(e_date, e_time).isoformat()
                try:
                    api.update_diaper(raw["id"], {
                        "changed_at": new_at,
                        "has_pee": e_pee,
                        "has_poop": e_poop,
                        "notes": e_notes or None,
                    })
                    st.session_state._editing_record = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            dt = datetime.fromisoformat(raw["measured_at"])
            e_date = st.date_input("Date", value=dt.date(), key=f"edt_{idx}")
            e_time = st.time_input("Time", value=dt.time(), key=f"etm_{idx}")
            e_g = st.number_input(
                "Weight (g)", 500, 20000, int(raw["weight_g"]), step=50, key=f"ewg_{idx}"
            )
            e_notes = st.text_input("Notes", value=raw.get("notes") or "", key=f"ent_{idx}")
            submitted = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
            if submitted:
                new_at = datetime.combine(e_date, e_time).isoformat()
                try:
                    resp = requests.patch(
                        f"{api.API_BASE}/weights/{raw['id']}",
                        json={"measured_at": new_at, "weight_g": int(e_g), "notes": e_notes or None},
                        timeout=api.TIMEOUT,
                    )
                    resp.raise_for_status()
                    st.session_state._editing_record = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.button("Cancel", key=f"cancel_{idx}"):
        st.session_state._editing_record = None
        st.rerun()
