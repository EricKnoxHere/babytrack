"""Home page - Baby summary + quick entry."""

import streamlit as st
from datetime import date, datetime, timedelta
from ui import api_client as api


def render():
    """Render the home page."""
    
    # Get selected baby from session
    baby = st.session_state.get("selected_baby")
    if not baby:
        st.error("No baby selected")
        return
    
    # ──────────────────────────────────────────────────────────────────────────
    # Header with baby info
    # ──────────────────────────────────────────────────────────────────────────
    
    col_title, col_actions = st.columns([3, 1])
    with col_title:
        age_days = (date.today() - datetime.fromisoformat(baby["created_at"]).date()).days
        st.title(f"🍼 {baby['name']}")
        st.markdown(f"**{age_days} days old** · Birth weight: {baby['birth_weight_grams']}g")
    
    with col_actions:
        st.write("")  # spacing
        if st.button("👶 Change baby", use_container_width=True):
            st.session_state.selected_baby = None
            st.rerun()
    
    st.divider()
    
    # ──────────────────────────────────────────────────────────────────────────
    # Quick metrics
    # ──────────────────────────────────────────────────────────────────────────
    
    try:
        today_feedings = api.get_feedings(baby["id"], day=date.today())
    except Exception:
        today_feedings = []
    
    today_ml = sum(f["quantity_ml"] for f in today_feedings)
    last_feeding = sorted(today_feedings, key=lambda x: x["fed_at"], reverse=True)[0] if today_feedings else None
    
    # Calculate expected feedings for this age
    age_days = (date.today() - datetime.fromisoformat(baby["created_at"]).date()).days
    if age_days <= 3:
        expected_per_day = 8
    elif age_days <= 7:
        expected_per_day = 8
    elif age_days <= 14:
        expected_per_day = 8
    elif age_days <= 30:
        expected_per_day = 7
    else:
        expected_per_day = 6
    
    # Metrics grid
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    
    with m_col1:
        st.metric(
            "Today's volume",
            f"{today_ml} ml",
            f"Target: {expected_per_day * 90}ml",
            delta_color="normal",
        )
        
    with m_col2:
        st.metric(
            "Feedings today",
            len(today_feedings),
            f"Expected: {expected_per_day}",
            delta_color="normal",
        )
    
    with m_col3:
        if last_feeding:
            now = datetime.now()
            last_time = datetime.fromisoformat(last_feeding["fed_at"])
            minutes_ago = int((now - last_time).total_seconds() / 60)
            delta_str = f"{minutes_ago}min ago"
            st.metric(
                "Time since last",
                last_time.strftime("%H:%M"),
                delta_str,
            )
        else:
            st.metric("Time since last", "—", "No feedings yet")
    
    with m_col4:
        st.metric(
            "Avg per feeding",
            f"{today_ml // len(today_feedings)}ml" if today_feedings else "—",
        )
    
    st.divider()
    
    # ──────────────────────────────────────────────────────────────────────────
    # Main action: New Entry
    # ──────────────────────────────────────────────────────────────────────────
    
    st.subheader("➕ Quick Entry")
    
    entry_type = st.radio(
        "What are you logging?",
        ["🍼 Feeding", "⚖️ Weight"],
        horizontal=True,
        label_visibility="collapsed",
    )
    
    if entry_type == "🍼 Feeding":
        col_feed1, col_feed2 = st.columns(2)
        
        with col_feed1:
            fed_date = st.date_input("Date", value=date.today(), key="home_feed_date")
            fed_time = st.time_input("Time", value=datetime.now().time(), key="home_feed_time")
        
        with col_feed2:
            quantity = st.number_input("ml", min_value=1, max_value=500, value=90, step=5, key="home_qty")
            feed_type = st.selectbox("Type", ["🍼 Bottle", "🤱 Breastfeeding"], key="home_type")
        
        notes = st.text_area("Notes", placeholder="e.g., baby seemed satisfied", height=80, key="home_notes")
        
        if st.button("✅ Save feeding", use_container_width=True, type="primary"):
            fed_at = datetime.combine(fed_date, fed_time).isoformat()
            type_val = "bottle" if "Bottle" in feed_type else "breastfeeding"
            try:
                api.add_feeding(
                    baby_id=baby["id"],
                    fed_at=fed_at,
                    quantity_ml=int(quantity),
                    feeding_type=type_val,
                    notes=notes or None,
                )
                st.success("✅ Saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    else:  # Weight
        col_weight1, col_weight2 = st.columns(2)
        
        with col_weight1:
            weight_date = st.date_input("Date", value=date.today(), key="home_weight_date")
            weight_time = st.time_input("Time", value=datetime.now().time(), key="home_weight_time")
        
        with col_weight2:
            weight_grams = st.number_input("grams", min_value=500, max_value=20000, value=3200, step=50, key="home_weight_g")
        
        weight_notes = st.text_area("Notes", placeholder="e.g., at pediatrician", height=80, key="home_weight_notes")
        
        if st.button("✅ Save weight", use_container_width=True, type="primary"):
            weight_at = datetime.combine(weight_date, weight_time).isoformat()
            try:
                api.add_weight(
                    baby_id=baby["id"],
                    measured_at=weight_at,
                    weight_g=int(weight_grams),
                    notes=weight_notes or None,
                )
                st.success("✅ Saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    
    # ──────────────────────────────────────────────────────────────────────────
    # Recent activity timeline
    # ──────────────────────────────────────────────────────────────────────────
    
    st.subheader("📋 Recent activity")
    
    if today_feedings:
        for feeding in sorted(today_feedings, key=lambda x: x["fed_at"], reverse=True)[:5]:
            col_f1, col_f2, col_f3 = st.columns([2, 3, 1])
            
            time_str = datetime.fromisoformat(feeding["fed_at"]).strftime("%H:%M")
            icon = "🍼" if feeding["feeding_type"] == "bottle" else "🤱"
            
            with col_f1:
                st.markdown(f"**{time_str}**")
            
            with col_f2:
                st.markdown(f"{icon} {feeding['quantity_ml']}ml · {feeding['feeding_type']}")
                if feeding.get("notes"):
                    st.caption(f"_{feeding['notes']}_")
            
            with col_f3:
                if st.button("🗑️", key=f"del_feed_{feeding['id']}", help="Delete"):
                    try:
                        api.delete_feeding(feeding["id"])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
    else:
        st.info("No feedings logged today yet.")
