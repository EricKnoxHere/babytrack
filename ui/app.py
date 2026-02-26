"""🍼 BabyTrack — Clean multi-page Streamlit app."""

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

# ─── Minimal CSS ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* System fonts */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Metric card backgrounds */
[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
}

/* Primary buttons */
.stButton > button[kind="primary"] {
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}

/* Sidebar cleanup */
[data-testid="stSidebar"] {
    background: #fafbfc;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.85rem;
}

/* Less visual noise */
.block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ─── Session state ───────────────────────────────────────────────────────────

if "selected_baby" not in st.session_state:
    st.session_state.selected_baby = None

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
        st.info("No babies yet.")
        if st.button("➕ Create baby", use_container_width=True, type="primary"):
            st.session_state._page_override = "CreateBaby"
            st.rerun()
        st.stop()

    labels = {b["name"]: b for b in babies}
    selected_name = st.selectbox("Baby", list(labels.keys()), label_visibility="collapsed")
    st.session_state.selected_baby = labels[selected_name]

    st.markdown("---")

    # Navigation — just 3 clean options
    page = st.radio(
        "nav",
        ["🏠 Home", "📊 Dashboard", "💬 Chat"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    if st.button("➕ New baby", use_container_width=True):
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
                    st.error(f"Failed: {e}")
            else:
                st.warning("Enter a name")
    if st.button("← Back"):
        st.session_state._page_override = None
        st.rerun()

elif "Home" in page:
    from ui.pages.home import render
    render()

elif "Dashboard" in page:
    from ui.pages.dashboard import render
    render()

elif "Chat" in page:
    from ui.pages.chat import render
    render()
