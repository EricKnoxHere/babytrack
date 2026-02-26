"""🍼 BabyTrack — Main Streamlit entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from datetime import date, datetime
from ui import api_client as api

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BabyTrack",
    page_icon="🍼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
}
.stButton > button[kind="primary"] {
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}
[data-testid="stSidebar"] { background: #fafbfc; }
.block-container { padding-top: 1.5rem; }
/* Hide Streamlit auto-detected page nav */
[data-testid="stSidebarNav"] { display: none !important; }
/* Prevent chat messages from overflowing */
[data-testid="stChatMessage"] {
    overflow-x: hidden;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
[data-testid="stChatMessage"] pre {
    white-space: pre-wrap;
    word-break: break-all;
}
</style>
""", unsafe_allow_html=True)

# ─── Session state defaults ──────────────────────────────────────────────────

if "selected_baby" not in st.session_state:
    st.session_state.selected_baby = None
if "_sidebar_form" not in st.session_state:
    st.session_state._sidebar_form = None
if "_nav_page" not in st.session_state:
    st.session_state._nav_page = "🏠 Home"

# ─── API check ───────────────────────────────────────────────────────────────

try:
    health = api.health()
    api_ok = health.get("status") == "ok"
except Exception:
    api_ok = False

if not api_ok:
    st.error("❌ API offline — cannot connect to backend")
    st.stop()


# ─── Sidebar form helpers (defined here, rendered inside sidebar) ────────────

def _sidebar_form_feeding(baby: dict):
    """Render a feeding form inside the sidebar."""
    st.markdown("**🍼 Log a bottle**")
    with st.form("sidebar_feeding_form", clear_on_submit=True):
        fed_date = st.date_input("Date", value=date.today(), key="sf_date")
        fed_time = st.time_input("Time", value=datetime.now().time(), key="sf_time")
        qty = st.number_input("Amount (ml)", 1, 500, 90, step=10, key="sf_qty")
        ftype = st.selectbox(
            "Type", ["bottle", "breastfeeding"],
            format_func=lambda t: "🍼 Bottle" if t == "bottle" else "🤱 Breast",
            key="sf_type",
        )
        notes = st.text_input("Notes", key="sf_notes", placeholder="optional")
        submitted = st.form_submit_button("✅ Save", type="primary", use_container_width=True)
        if submitted:
            fed_at = datetime.combine(fed_date, fed_time).isoformat()
            try:
                api.add_feeding(baby["id"], fed_at, int(qty), ftype, notes or None)
                st.session_state._sidebar_form = None
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


def _sidebar_form_weight(baby: dict):
    """Render a weight form inside the sidebar."""
    st.markdown("**⚖️ Log weight**")
    with st.form("sidebar_weight_form", clear_on_submit=True):
        w_date = st.date_input("Date", value=date.today(), key="sw_date")
        w_time = st.time_input("Time", value=datetime.now().time(), key="sw_time")
        w_g = st.number_input("Weight (g)", 500, 20000, 3200, step=50, key="sw_g")
        w_notes = st.text_input("Notes", key="sw_notes", placeholder="optional")
        submitted = st.form_submit_button("✅ Save", type="primary", use_container_width=True)
        if submitted:
            w_at = datetime.combine(w_date, w_time).isoformat()
            try:
                api.add_weight(baby["id"], w_at, int(w_g), w_notes or None)
                st.session_state._sidebar_form = None
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


def _sidebar_form_diaper(baby: dict):
    """Render a diaper form inside the sidebar."""
    st.markdown("**🧷 Log diaper**")
    with st.form("sidebar_diaper_form", clear_on_submit=True):
        d_date = st.date_input("Date", value=date.today(), key="sd_date")
        d_time = st.time_input("Time", value=datetime.now().time(), key="sd_time")
        d_pee = st.checkbox("💧 Pee", value=True, key="sd_pee")
        d_poop = st.checkbox("💩 Poop", value=False, key="sd_poop")
        d_notes = st.text_input("Notes", key="sd_notes", placeholder="optional")
        submitted = st.form_submit_button("✅ Save", type="primary", use_container_width=True)
        if submitted:
            d_at = datetime.combine(d_date, d_time).isoformat()
            try:
                api.add_diaper(baby["id"], d_at, d_pee, d_poop, d_notes or None)
                st.session_state._sidebar_form = None
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


# ─── Load babies ─────────────────────────────────────────────────────────────

try:
    babies = api.list_babies()
except Exception:
    babies = []

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🍼 BabyTrack")

    if not babies:
        st.info("No babies registered yet.")
        if st.button("➕ Create a baby", use_container_width=True, type="primary"):
            st.session_state._page_override = "CreateBaby"
            st.rerun()
        st.stop()

    # ── Navigation ───────────────────────────────────────────────────────────
    _nav_options = ["🏠 Home", "📋 Records", "💬 Chat"]
    _current_idx = next(
        (i for i, o in enumerate(_nav_options) if o == st.session_state._nav_page), 0
    )
    nav = st.radio(
        "nav",
        _nav_options,
        label_visibility="collapsed",
        index=_current_idx,
        key="sidebar_nav",
    )
    st.session_state._nav_page = nav

    st.markdown("---")

    # ── Baby selector (radio buttons) + entry buttons ────────────────────────
    st.markdown("**Baby**")
    baby_names = [b["name"] for b in babies]
    baby_map = {b["name"]: b for b in babies}

    # Determine current baby index
    current_baby_name = (st.session_state.selected_baby or {}).get("name", baby_names[0])
    if current_baby_name not in baby_names:
        current_baby_name = baby_names[0]
    _baby_idx = baby_names.index(current_baby_name)

    selected_name = st.radio(
        "baby",
        baby_names,
        label_visibility="collapsed",
        index=_baby_idx,
        key="sidebar_baby_radio",
    )
    st.session_state.selected_baby = baby_map[selected_name]

    # Entry buttons (stacked vertically, inside Baby section)
    active_form = st.session_state._sidebar_form
    if st.button(
        "✕ Close" if active_form == "feeding" else "➕ Bottle 🍼",
        use_container_width=True,
        type="primary" if active_form == "feeding" else "secondary",
        key="sb_btn_feeding",
    ):
        st.session_state._sidebar_form = None if active_form == "feeding" else "feeding"
        st.rerun()

    if st.button(
        "✕ Close" if active_form == "weight" else "➕ Weight ⚖️",
        use_container_width=True,
        type="primary" if active_form == "weight" else "secondary",
        key="sb_btn_weight",
    ):
        st.session_state._sidebar_form = None if active_form == "weight" else "weight"
        st.rerun()

    if st.button(
        "✕ Close" if active_form == "diaper" else "➕ Diaper 🧷",
        use_container_width=True,
        type="primary" if active_form == "diaper" else "secondary",
        key="sb_btn_diaper",
    ):
        st.session_state._sidebar_form = None if active_form == "diaper" else "diaper"
        st.rerun()

    # Inline sidebar form
    if active_form == "feeding":
        _sidebar_form_feeding(st.session_state.selected_baby)
    elif active_form == "weight":
        _sidebar_form_weight(st.session_state.selected_baby)
    elif active_form == "diaper":
        _sidebar_form_diaper(st.session_state.selected_baby)

    if st.button("➕ New baby", use_container_width=True, key="sidebar_new_baby"):
        st.session_state._page_override = "CreateBaby"
        st.rerun()

# ─── Page routing ────────────────────────────────────────────────────────────

if st.session_state.get("_page_override") == "CreateBaby":
    st.title("👶 New baby")
    with st.form("create_baby"):
        name = st.text_input("Name")
        dob = st.date_input("Date of birth", value=date.today())
        weight = st.number_input("Birth weight (g)", 500, 6000, 3300)
        if st.form_submit_button("✅ Create", use_container_width=True, type="primary"):
            if name:
                try:
                    baby = api.create_baby(name, dob, int(weight))
                    st.session_state.selected_baby = baby
                    st.session_state._page_override = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Enter a name")
    if st.button("← Back"):
        st.session_state._page_override = None
        st.rerun()

elif "Home" in nav:
    from ui.views.home import render
    render()

elif "Records" in nav:
    from ui.views.record import render
    render()

elif "Chat" in nav:
    from ui.views.chat import render
    render()
