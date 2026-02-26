"""Chat — Real conversational interface with Claude."""

import streamlit as st
from datetime import datetime, timedelta
from ui import api_client as api


# ── Welcome message shown on first load ──────────────────────────────────────

def _welcome_message(baby_name: str) -> str:
    return (
        f"Hello! I'm here to help analyze **{baby_name}**'s feeding data. "
        f"I have access to medical guidelines (WHO/SFP) and all recorded data.\n\n"
        f"What would you like to know? Here are some suggestions:\n"
        f"- 📊 **Analyze today** — How is today going so far?\n"
        f"- 📅 **Analyze yesterday** — Full day review\n"
        f"- 📈 **Analyze this week** — 7-day trends\n"
        f"- ❓ Or ask me anything!"
    )


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    st.markdown(f"## 💬 Chat – {baby['name']}")

    # ── Init chat history ────────────────────────────────────────────────────

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Show welcome on first visit
    if not st.session_state.chat_messages:
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": _welcome_message(baby["name"]),
        })

    # ── Display messages ─────────────────────────────────────────────────────

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Chat input (pinned at bottom by Streamlit) ───────────────────────────

    user_input = st.chat_input("Ask about feedings, growth, or say 'analyze today'...")

    if user_input:
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Determine analysis window from user intent
        start_dt, end_dt, label = _parse_intent(user_input)

        # Call API
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    result = api.get_analysis(
                        baby_id=baby["id"],
                        start=start_dt,
                        end=end_dt,
                    )

                    response = result["analysis"]

                    # Add source references
                    if result.get("sources"):
                        response += "\n\n---\n_📚 Sources: " + ", ".join(
                            s["source"] for s in result["sources"]
                        ) + "_"

                    st.markdown(response)
                    st.session_state.chat_messages.append({"role": "assistant", "content": response})

                except Exception as e:
                    error_msg = f"❌ Analysis failed: {e}"
                    st.markdown(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})

    # ── Clear chat button (small, bottom) ────────────────────────────────────

    if len(st.session_state.chat_messages) > 1:
        st.markdown("")
        if st.button("🗑️ Clear conversation", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()


# ── Intent parser ────────────────────────────────────────────────────────────

def _parse_intent(text: str) -> tuple:
    """Parse user message to determine analysis time window.

    Returns (start_dt, end_dt, label).
    Defaults to last 7 days for free-form questions.
    """
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    t = text.lower().strip()

    # Today
    if any(w in t for w in ["today", "aujourd'hui", "ce jour", "journée"]):
        return today_start, now, "today"

    # Yesterday
    if any(w in t for w in ["yesterday", "hier"]):
        return today_start - timedelta(days=1), today_start, "yesterday"

    # Last 3 days
    if any(w in t for w in ["3 day", "3 jour", "trois jour", "three day"]):
        return now - timedelta(days=3), now, "3 days"

    # This week / last 7 days
    if any(w in t for w in ["week", "semaine", "7 day", "7 jour"]):
        return now - timedelta(days=7), now, "week"

    # This month / last 30 days
    if any(w in t for w in ["month", "mois", "30 day", "30 jour"]):
        return now - timedelta(days=30), now, "month"

    # Default: last 7 days (gives Claude enough context for any question)
    return now - timedelta(days=7), now, "default"
