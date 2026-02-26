"""🍼 BabyTrack — Main Streamlit entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from datetime import date
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
</style>
""", unsafe_allow_html=True)

# ─── Session state defaults ──────────────────────────────────────────────────

if "selected_baby" not in st.session_state:
    st.session_state.selected_baby = None
if "_home_widget" not in st.session_state:
    st.session_state._home_widget = None
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

# ─── Sidebar (minimal) ──────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🍼 BabyTrack")

    # Baby selector
    try:
        babies = api.list_babies()
    except Exception:
        babies = []

    if not babies:
        st.info("No babies registered yet.")
        if st.button("➕ Create a baby", use_container_width=True, type="primary"):
            st.session_state._page_override = "CreateBaby"
            st.rerun()
        st.stop()

    labels = {b["name"]: b for b in babies}
    selected_name = st.selectbox(
        "Baby", list(labels.keys()), label_visibility="collapsed", key="sidebar_baby_select"
    )
    st.session_state.selected_baby = labels[selected_name]

    st.markdown("---")

    # Navigation — 2 options only
    nav = st.radio(
        "nav",
        ["🏠 Home", "💬 Chat"],
        label_visibility="collapsed",
        index=0 if st.session_state._nav_page == "🏠 Home" else 1,
        key="sidebar_nav",
    )
    st.session_state._nav_page = nav

    st.markdown("---")
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

elif "Chat" in nav:
    from ui.views.chat import render
    render()
