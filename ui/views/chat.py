"""Chat — Conversational interface with memory and persistence."""

import streamlit as st
from datetime import datetime, timedelta
from ui import api_client as api


def render():
    baby = st.session_state.get("selected_baby")
    if not baby:
        return

    name = baby["name"]

    # ── Init chat state ──────────────────────────────────────────────────────

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_conv_id" not in st.session_state:
        st.session_state.chat_conv_id = None

    # Reset history when baby changes
    if st.session_state.get("_chat_baby_id") != baby["id"]:
        st.session_state.chat_messages = []
        st.session_state.chat_conv_id = None
        st.session_state._chat_baby_id = baby["id"]

    # ── Sidebar: conversation history ────────────────────────────────────────

    with st.sidebar:
        st.markdown("---")
        st.markdown("**💬 Conversations**")

        if st.button("➕ Nouvelle conversation", use_container_width=True, key="new_chat_btn"):
            _save_current_if_needed(baby)
            st.session_state.chat_messages = []
            st.session_state.chat_conv_id = None
            st.rerun()

        try:
            conversations = api.list_conversations(baby["id"], limit=15)
        except Exception:
            conversations = []

        for conv in conversations:
            col_title, col_del = st.columns([5, 1])
            with col_title:
                label = conv["title"][:35]
                is_active = st.session_state.chat_conv_id == conv["id"]
                btn_type = "primary" if is_active else "secondary"
                if st.button(
                    f"{'▸ ' if is_active else ''}{label}",
                    key=f"conv_{conv['id']}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    _save_current_if_needed(baby)
                    _load_conversation(conv["id"])
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_conv_{conv['id']}", help="Supprimer"):
                    try:
                        api.delete_conversation(conv["id"])
                        if st.session_state.chat_conv_id == conv["id"]:
                            st.session_state.chat_messages = []
                            st.session_state.chat_conv_id = None
                        st.rerun()
                    except Exception:
                        pass

    # ── Prompt suggestions (when empty) ──────────────────────────────────────

    if not st.session_state.chat_messages:
        st.markdown("## 💬 Chat")
        st.caption(f"Posez vos questions sur l'alimentation, le poids, les couches ou la santé de {name}.")

        suggestions = [
            f"Comment {name} mange aujourd'hui ?",
            "Bilan complet d'hier",
            "Tendances de la semaine",
            f"Est-ce que {name} mange assez ?",
            f"Des préoccupations sur la croissance de {name} ?",
        ]

        # Spacer to push suggestions toward the bottom
        st.markdown("<div style='flex:1;min-height:200px'></div>", unsafe_allow_html=True)

        # Stack suggestions vertically, aligned right
        suggestion_clicked = None
        for idx, sug in enumerate(suggestions):
            col_spacer, col_btn = st.columns([3, 2])
            with col_btn:
                if st.button(sug, key=f"sug_{idx}", use_container_width=True):
                    suggestion_clicked = sug

        if suggestion_clicked:
            _handle_user_message(baby, suggestion_clicked)
            st.rerun()

    # ── Display conversation ─────────────────────────────────────────────────

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Chat input ───────────────────────────────────────────────────────────

    user_input = st.chat_input(f"Question sur {name}...")

    if user_input:
        _handle_user_message(baby, user_input)
        st.rerun()


def _handle_user_message(baby: dict, user_input: str):
    """Process a user message: add to history, call API, save conversation."""
    # Add user message
    st.session_state.chat_messages.append({"role": "user", "content": user_input})

    # Build time window from intent
    start_dt, end_dt = _parse_time_window(user_input)

    # Build history for API (exclude current msg)
    history_for_api = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_messages[:-1]
        if m["role"] in ("user", "assistant")
    ]

    # Call API
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

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )
    except Exception as e:
        error_msg = f"Désolé, une erreur est survenue : {e}"
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": error_msg}
        )

    # Auto-save conversation
    _auto_save(baby)


def _auto_save(baby: dict):
    """Save or update the current conversation."""
    messages = st.session_state.chat_messages
    if not messages:
        return

    # Generate title from first user message
    first_user = next(
        (m["content"] for m in messages if m["role"] == "user"), "Nouvelle conversation"
    )
    title = first_user[:60]

    conv_id = st.session_state.chat_conv_id
    try:
        if conv_id:
            api.update_conversation(conv_id, title=title, messages=messages)
        else:
            conv = api.save_conversation(baby["id"], title, messages)
            st.session_state.chat_conv_id = conv["id"]
    except Exception:
        pass  # Don't block chat on save failure


def _save_current_if_needed(baby: dict):
    """Save current conversation before switching."""
    if st.session_state.chat_messages:
        _auto_save(baby)


def _load_conversation(conversation_id: int):
    """Load a conversation from the API into session state."""
    try:
        conv = api.get_conversation(conversation_id)
        st.session_state.chat_messages = conv.get("messages", [])
        st.session_state.chat_conv_id = conv["id"]
    except Exception:
        st.session_state.chat_messages = []
        st.session_state.chat_conv_id = None


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
