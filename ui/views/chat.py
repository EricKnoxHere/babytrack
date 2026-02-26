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

    # ── Load past conversations ──────────────────────────────────────────────

    try:
        conversations = api.list_conversations(baby["id"], limit=20)
    except Exception:
        conversations = []

    # ── Dropdown to reopen past conversations ────────────────────────────

    def _conv_label(idx: int) -> str:
        """Format dropdown label: date — title."""
        if idx == 0:
            return "— Conversations précédentes —"
        c = conversations[idx - 1]
        title = c["title"][:40]
        ts = c.get("updated_at") or c.get("created_at", "")
        try:
            dt = datetime.fromisoformat(ts)
            date_str = dt.strftime("%d/%m %H:%M:%S")
        except Exception:
            date_str = ""
        return f"{date_str}  —  {title}" if date_str else title

    selected_idx = st.selectbox(
        "Conversations",
        range(len(conversations) + 1),
        format_func=_conv_label,
        index=0,
        key="chat_conv_picker",
        label_visibility="collapsed",
    )
    if selected_idx > 0:
        target = conversations[selected_idx - 1]
        if st.session_state.chat_conv_id != target["id"]:
            _save_current_if_needed(baby)
            _load_conversation(target["id"])
            st.rerun()

    # ── Empty state: centered welcome + suggestion chips ─────────────────────

    if not st.session_state.chat_messages:
        st.markdown(
            "<div style='text-align:center;padding:60px 0 20px'>"
            "<span style='font-size:2.5rem'>✨</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<h2 style='text-align:center;margin:0 0 8px'>"
            f"Posez vos questions sur {name}</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#94a3b8;margin-bottom:40px'>"
            "Alimentation, poids, couches, santé…</p>",
            unsafe_allow_html=True,
        )

        suggestions = [
            f"Comment {name} mange aujourd'hui ?",
            "Bilan complet d'hier",
            f"Est-ce que {name} mange assez ?",
            "Tendances de la semaine",
        ]

        # Spacer
        st.markdown("<div style='min-height:120px'></div>", unsafe_allow_html=True)

        st.caption("Suggestions")
        suggestion_clicked = None
        cols = st.columns(2)
        for idx, sug in enumerate(suggestions):
            with cols[idx % 2]:
                if st.button(sug, key=f"sug_{idx}", use_container_width=True):
                    suggestion_clicked = sug

        if suggestion_clicked:
            st.session_state.chat_messages.append(
                {"role": "user", "content": suggestion_clicked}
            )
            st.rerun()

    # ── Display conversation ─────────────────────────────────────────────────

    else:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # If last message is from user, generate assistant response with spinner
        if (
            st.session_state.chat_messages
            and st.session_state.chat_messages[-1]["role"] == "user"
        ):
            with st.chat_message("assistant"):
                with st.spinner("Réflexion en cours…"):
                    _generate_response(baby)
            st.rerun()

    # ── Chat input ───────────────────────────────────────────────────────────

    user_input = st.chat_input(f"Question sur {name}...")

    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        st.rerun()


def _generate_response(baby: dict):
    """Call the API and append the assistant response. User message is already in state."""
    messages = st.session_state.chat_messages
    user_input = messages[-1]["content"]

    # Build time window from intent
    start_dt, end_dt = _parse_time_window(user_input)

    # Build history for API (exclude current msg)
    history_for_api = [
        {"role": m["role"], "content": m["content"]}
        for m in messages[:-1]
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

        messages.append({"role": "assistant", "content": response})
    except Exception as e:
        error_msg = f"Désolé, une erreur est survenue : {e}"
        messages.append({"role": "assistant", "content": error_msg})

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
