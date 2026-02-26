"""Chat page - Conversational analysis with Claude."""

import streamlit as st
from datetime import date, datetime, timedelta
from ui import api_client as api


def render():
    """Render the chat page."""
    
    baby = st.session_state.get("selected_baby")
    if not baby:
        st.error("No baby selected")
        return
    
    st.title(f"💬 Chat with Claude – {baby['name']}")
    st.markdown("Ask questions about your baby's feeding patterns. Claude will use the latest data and medical guidelines.")
    
    # ──────────────────────────────────────────────────────────────────────────
    # Initialize chat session state
    # ──────────────────────────────────────────────────────────────────────────
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # ──────────────────────────────────────────────────────────────────────────
    # Quick analysis suggestionsx
    # ──────────────────────────────────────────────────────────────────────────
    
    st.subheader("📅 Quick analysis")
    
    suggestion_cols = st.columns(5)
    
    # Timestamp for analysis windows
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = now
    
    quick_analyses = {
        "Today": (today_start, today_end),
        "Yesterday": (today_start - timedelta(days=1), today_start),
        "Last 3 days": (today_start - timedelta(days=3), today_end),
        "Last week": (today_start - timedelta(days=7), today_end),
        "Last month": (today_start - timedelta(days=30), today_end),
    }
    
    for col, (label, (start, end)) in zip(suggestion_cols, quick_analyses.items()):
        with col:
            if st.button(label, use_container_width=True):
                with st.spinner(f"Analyzing {label}..."):
                    try:
                        result = api.get_analysis(
                            baby_id=baby["id"],
                            start=start,
                            end=end,
                        )
                        
                        # Add to chat
                        user_msg = f"Analyze {label}"
                        st.session_state.chat_messages.append({"role": "user", "content": user_msg})
                        
                        assistant_msg = result["analysis"]
                        if result.get("sources"):
                            assistant_msg += f"\n\n**Sources:** {', '.join(s['source'] for s in result['sources'])}"
                        
                        st.session_state.chat_messages.append({"role": "assistant", "content": assistant_msg})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")
    
    st.divider()
    
    # ──────────────────────────────────────────────────────────────────────────
    # Chat display
    # ──────────────────────────────────────────────────────────────────────────
    
    st.subheader("💬 Conversation")
    
    # Display existing messages
    if st.session_state.chat_messages:
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    else:
        st.info("👋 Start asking me questions about your baby's feeding patterns!")
    
    st.divider()
    
    # ──────────────────────────────────────────────────────────────────────────
    # Chat input
    # ──────────────────────────────────────────────────────────────────────────
    
    st.subheader("💬 Your question")
    
    user_input = st.text_area(
        "Ask me anything about your baby's feeding (or just chat!)",
        placeholder="e.g., 'Is my baby eating enough?', 'What's the average consumption per day?'...",
        height=100,
        label_visibility="collapsed",
    )
    
    col_send, col_clear = st.columns([3, 1])
    
    with col_send:
        send_btn = st.button("💬 Send", use_container_width=True, type="primary")
    
    with col_clear:
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()
    
    if send_btn and user_input:
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Get Claude response (stateless via API)
        with st.spinner("Claude is thinking..."):
            try:
                # Call the analysis API with current data as context
                # For free-form questions, we ask Claude to use the latest data
                now = datetime.now()
                end_dt = now
                start_dt = now - timedelta(days=7)  # Last 7 days as context
                
                # Build prompt for Claude to answer custom question
                # This should be a new endpoint or we repurpose the analysis endpoint
                # For now, let's make a direct Claude call using the analysis data
                
                result = api.get_analysis(
                    baby_id=baby["id"],
                    start=start_dt,
                    end=end_dt,
                )
                
                # Create context-aware response
                assistant_response = f"""Based on your baby's recent data and your question:

**Your question:** {user_input}

{result["analysis"]}

Feel free to ask follow-up questions!"""
                
                if result.get("sources"):
                    assistant_response += f"\n\n_📚 Using medical context: {', '.join(s['source'] for s in result['sources'])}_"
                
                st.session_state.chat_messages.append({"role": "assistant", "content": assistant_response})
                st.rerun()
                
            except Exception as e:
                error_msg = f"❌ I couldn't analyze that: {e}"
                st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
                st.rerun()
    
    # ──────────────────────────────────────────────────────────────────────────
    # Chat tips
    # ──────────────────────────────────────────────────────────────────────────
    
    st.divider()
    st.subheader("💡 Tips")
    st.markdown("""
    - 📊 Ask about feeding patterns, volumes, or trends
    - ⏰ Question: "Is my baby feeding at the right frequency?"
    - 📈 Question: "How is growth looking lately?"
    - 👨‍⚕️ I use WHO/SFP medical guidelines to answer
    - 🗑️ Chat history clears when you refresh (stateless design)
    """)
