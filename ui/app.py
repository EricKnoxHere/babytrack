"""
🍼 BabyTrack UI - Modern multi-page Streamlit app
Home | Dashboard | Chat with Claude

Run: streamlit run ui/app.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from datetime import date, datetime
from ui import api_client as api

# ──────────────────────────────────────────────────────────────────────────────
# Page configuration
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="🍼 BabyTrack",
    page_icon="🍼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
# Modern styling (dark-friendly)
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* System font stack */
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    }
    
    /* Main gradient background */
    .main {
        background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
        border-radius: 12px;
    }
    
    /* Sidebar cleanup */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 1px solid #e5e7eb;
    }
    
    /* Card containers */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-color: #3b82f6;
    }
    
    /* Typography */
    h1, h2, h3 {
        color: #111827;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 10px 20px;
        transition: all 0.2s ease;
        border: none;
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* input fields */
    .stTextInput input, .stNumberInput input, .stDateInput input {
        border-radius: 8px;
        border: 1px solid #e5e7eb !important;
        padding: 10px 12px !important;
    }
    
    /* Divider */
    hr {
        border: none;
        border-top: 1px solid #e5e7eb;
        margin: 20px 0;
    }
    
    /* Metrics */
    [data-testid="metric-container"] {
        background: white;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #f9fafb;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# Initialize session state
# ──────────────────────────────────────────────────────────────────────────────

if "selected_baby" not in st.session_state:
    st.session_state.selected_baby = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

# ──────────────────────────────────────────────────────────────────────────────
# API health check
# ──────────────────────────────────────────────────────────────────────────────

try:
    health = api.health()
    api_ok = health.get("status") == "ok"
except Exception as e:
    api_ok = False
    print(f"❌ API health check failed: {e}")

if not api_ok:
    st.error("❌ **API offline** - Cannot connect to backend service")
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar: Baby selection & navigation
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🍼 BabyTrack")
    st.markdown("Infant feeding tracker · Claude + RAG")
    st.divider()
    
    # Load babies
    try:
        babies = api.list_babies()
    except Exception as e:
        st.error(f"Could not load babies: {e}")
        st.stop()
    
    if not babies:
        st.info("📭 No babies yet.")
        if st.button("➕ Create first baby", use_container_width=True):
            st.session_state.current_page = "CreateBaby"
        st.stop()
    
    # Baby selector
    st.subheader("👶 Baby")
    baby_labels = {f"{b['name']} ({(date.today() - datetime.fromisoformat(b['created_at']).date()).days}d)": b for b in babies}
    
    selected_label = st.selectbox(
        "Select baby",
        list(baby_labels.keys()),
        label_visibility="collapsed",
        key="baby_selector",
    )
    
    st.session_state.selected_baby = baby_labels[selected_label]
    
    st.divider()
    
    # Navigation
    st.subheader("📍 Navigation")
    pages = ["🏠 Home", "📊 Dashboard", "💬 Chat"]
    selected_page = st.radio(
        "Go to",
        pages,
        label_visibility="collapsed",
        key="page_selector",
    )
    st.session_state.current_page = selected_page.split(" ", 1)[1]  # Remove emoji
    
    st.divider()
    
    # Baby actions
    st.subheader("⚙️ Actions")
    col_new, col_create = st.columns(2)
    
    with col_new:
        if st.button("➕ New baby", use_container_width=True):
            st.session_state.current_page = "CreateBaby"
            st.rerun()
    
    with col_create:
        if st.button("🗑️ Delete", use_container_width=True):
            if st.session_state.selected_baby:
                try:
                    # Would need to add delete endpoint
                    st.info("Delete via API coming soon")
                except Exception as e:
                    st.error(f"Delete failed: {e}")
    
    st.divider()
    st.caption("✨ Modern AI-powered infant tracking")

# ──────────────────────────────────────────────────────────────────────────────
# Page routing
# ──────────────────────────────────────────────────────────────────────────────

page = st.session_state.current_page

if page == "Home":
    from ui.pages import home
    home.render()

elif page == "Dashboard":
    from ui.pages import dashboard
    dashboard.render()

elif page == "Chat":
    from ui.pages import chat
    chat.render()

elif page == "CreateBaby":
    st.title("👶 Create new baby")
    
    with st.form("new_baby_form"):
        name = st.text_input("Baby's name", placeholder="e.g., Louise")
        dob = st.date_input("Date of birth", value=date.today())
        birth_weight = st.number_input("Birth weight (grams)", min_value=500, max_value=6000, value=3300)
        
        submitted = st.form_submit_button("✅ Create baby", use_container_width=True)
    
    if submitted:
        if not name:
            st.error("Please enter a baby name")
        else:
            try:
                baby = api.create_baby(name, dob, int(birth_weight))
                st.success(f"✅ {baby['name']} created!")
                st.session_state.selected_baby = baby
                st.session_state.current_page = "Home"
                st.rerun()
            except Exception as e:
                st.error(f"Creation failed: {e}")
