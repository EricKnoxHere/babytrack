"""Chat — Conversational interface with memory."""

import streamlit as st
from datetime import datetime, timedelta
from ui import api_client as api


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    # ── Init chat state ──────────────────────────────────────────────────────

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Reset history when baby changes
    if st.session_state.get("_chat_baby_id") != baby["id"]:
        st.session_state.chat_messages = []
        st.session_state._chat_baby_id = baby["id"]

    # ── Display conversation ─────────────────────────────────────────────────

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Chat input ───────────────────────────────────────────────────────────

    user_input = st.chat_input(f"Ask about {baby['name']}...")

    if user_input:
        # Show user message immediately
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Build time window from intent
        start_dt, end_dt = _parse_time_window(user_input)

        # Build history for API (only user/assistant, exclude current msg)
        history_for_api = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.chat_messages[:-1]
            if m["role"] in ("user", "assistant")
        ]

        # Call API with history
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = api.chat(
                        baby_id=baby["id"],
                        question=user_input,
                        start=start_dt,
                        end=end_dt,
                        chat_history=history_for_api,
                    )

                    response = result["analysis"]

                    # Append source footer
                    sources = result.get("sources", [])
                    if sources:
                        source_names = sorted(set(s["source"] for s in sources))
                        response += "\n\n---\n_📚 Sources: " + ", ".join(source_names) + "_"

                    st.markdown(response)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": response}
                    )

                except Exception as e:
                    error_msg = f"Sorry, something went wrong: {e}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": error_msg}
                    )

    # ── Clear chat ───────────────────────────────────────────────────────────

    if st.session_state.chat_messages:
        if st.button("📝 Clear conversation", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()


# ── Time window parser ───────────────────────────────────────────────────────

def _parse_time_window(text: str) -> tuple[datetime, datetime]:
    """Extract a time window from user text. Returns (start, end)."""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    t = text.lower().strip()

    if any(w in t for w in ["today", "aujourd'hui", "ce jour", "journée"]):
        return today_start, now

    if any(w in t for w in ["yesterday", "hier"]):
        return today_start - timedelta(days=1), today_start

    if any(w in t for w in ["3 day", "3 jour", "trois jour", "three day"]):
        return now - timedelta(days=3), now

    if any(w in t for w in ["week", "semaine", "7 day", "7 jour"]):
        return now - timedelta(days=7), now

    if any(w in t for w in ["month", "mois", "30 day", "30 jour"]):
        return now - timedelta(days=30), now

    # Default: last 7 days
    return now - timedelta(days=7), now
