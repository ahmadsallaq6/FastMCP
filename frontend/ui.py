"""UI helpers for the Streamlit frontend."""

from __future__ import annotations

import json
import os
import sys
from typing import Iterable, Tuple, Literal

import streamlit as st

from config import (
    PAGE_CONFIG,
    DEFAULT_SERVER_URL,
    AZURE_OPENAI_GPT_DEPLOYMENT_NAME,
    get_custom_css,
)
from session import (
    get_conversation_history,
    load_conversation,
    clear_conversation,
)

# Ensure backend package is importable for database connectivity checks
BACKEND_PATH = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

try:
    from database import get_mongo_client  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - defensive fallback
    get_mongo_client = None  # type: ignore


def setup_page() -> None:
    """Apply Streamlit page config and theme-specific CSS."""
    if not st.session_state.get("_page_configured"):
        layout_value = PAGE_CONFIG.get("layout", "centered")
        layout_literal: Literal["centered", "wide"] = "wide" if layout_value == "wide" else "centered"

        sidebar_value = PAGE_CONFIG.get("initial_sidebar_state", "expanded")
        sidebar_literal: Literal["auto", "collapsed", "expanded"]
        if sidebar_value == "auto":
            sidebar_literal = "auto"
        elif sidebar_value == "collapsed":
            sidebar_literal = "collapsed"
        else:
            sidebar_literal = "expanded"

        st.set_page_config(
            page_title=PAGE_CONFIG.get("page_title", "Loans Assistant"),
            page_icon=PAGE_CONFIG.get("page_icon", "💬"),
            layout=layout_literal,
            initial_sidebar_state=sidebar_literal,
        )
        st.session_state._page_configured = True

    if "theme" not in st.session_state:
        st.session_state.theme = "dark"

    st.markdown(get_custom_css(st.session_state.theme), unsafe_allow_html=True)


def initialize_connections() -> bool:
    """Prime external connections (MongoDB) and memoize the status."""
    if "mongo_available" in st.session_state:
        return bool(st.session_state.mongo_available)

    available = False
    if get_mongo_client is not None:
        try:
            available = get_mongo_client() is not None
        except Exception:
            available = False

    st.session_state.mongo_available = available
    return available


def render_sidebar() -> Tuple[str, str]:
    """Render sidebar controls and return server/model selections."""
    theme_index = 0 if st.session_state.get("theme", "dark") == "dark" else 1

    with st.sidebar:
        col_title, col_theme = st.columns([0.7, 0.3])
        with col_title:
            st.markdown("<p class='settings-title'>Control Center</p>", unsafe_allow_html=True)
        with col_theme:
            theme_choice = st.radio(
                "Theme",
                options=["dark", "light"],
                index=theme_index,
                label_visibility="collapsed",
                horizontal=True,
            )
            st.session_state.theme = theme_choice

        server_default = st.session_state.get("server_url", DEFAULT_SERVER_URL)
        server_url = st.text_input("MCP Server URL", value=server_default)
        st.session_state.server_url = server_url

        model_default = st.session_state.get("model_name", AZURE_OPENAI_GPT_DEPLOYMENT_NAME)
        model_name = st.text_input("Azure OpenAI deployment", value=model_default)
        st.session_state.model_name = model_name

        mongo_available = st.session_state.get("mongo_available", False)
        if mongo_available:
            st.success("MongoDB connected", icon="✅")
        else:
            st.info("MongoDB not available", icon="ℹ️")

        st.markdown("---")
        if st.button("+ New chat", use_container_width=True, type="primary"):
            clear_conversation()
            st.rerun()

        st.markdown("### History")
        conversations = _safe_get_conversations() if mongo_available else []
        if conversations:
            for conv in conversations:
                title = conv.get("title") or conv.get("conversation_id")
                if st.button(title, key=f"hist_{conv['conversation_id']}", use_container_width=True):
                    load_conversation(conv['conversation_id'])
                    st.rerun()
        else:
            st.caption("No stored conversations yet.")

    safe_server = (server_url or "").strip() or DEFAULT_SERVER_URL
    safe_model = (model_name or "").strip() or AZURE_OPENAI_GPT_DEPLOYMENT_NAME
    return safe_server, safe_model


def render_main_title() -> None:
    """Display the main page title and supporting subtitle."""
    st.title("Loans Assistant ChatBot")
    st.caption("Chat with your AI co-pilot and dispatch MCP tools when needed.")


def render_chat_messages(messages: Iterable[dict]) -> None:
    """Replay past chat messages using Streamlit's chat components."""
    for message in messages:
        role = message.get("role", "assistant")
        avatar = "👤" if role == "user" else "🤖"
        content = message.get("content", "")
        tool_calls = message.get("tool_calls") or []

        with st.chat_message(role, avatar=avatar):
            if content:
                st.markdown(content)
            if tool_calls:
                with st.expander("Tool calls", expanded=False):
                    for idx, call in enumerate(tool_calls, start=1):
                        st.markdown(f"**#{idx} {call.get('name', 'tool')}**")
                        if call.get("arguments"):
                            st.code(call["arguments"], language="json")
                        if call.get("result"):
                            st.code(call["result"], language="json")


def render_approval_dialog(*, on_approve, on_reject) -> None:
    """Show a confirmation UI for pending tool calls."""
    approval = st.session_state.get("pending_approval")
    if not approval:
        return

    st.markdown("""
        <div class="approval-banner">
            <div class="approval-banner__icon">⚠️</div>
            <div>
                <div class="approval-banner__title">Tool approval required</div>
                <div class="approval-banner__subtitle">Review the arguments below before continuing.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='approval-json__label'>Tool Name</div>", unsafe_allow_html=True)
    st.info(approval.get("tool_name", "unknown"))

    st.markdown("<div class='approval-json__label'>Arguments</div>", unsafe_allow_html=True)
    
    args = approval.get("arguments") or {}
    if args:
        for key, value in args.items():
            # Use text_area for long text, text_input for short
            val_str = str(value)
            if len(val_str) > 60 or "\n" in val_str:
                st.text_area(key, value=val_str, disabled=True, height=150)
            else:
                st.text_input(key, value=val_str, disabled=True)
    else:
        st.caption("No arguments provided.")

    col_left, col_right = st.columns(2)
    col_left.button("Approve", use_container_width=True, on_click=on_approve, type="primary")
    col_right.button("Reject", use_container_width=True, on_click=on_reject)


def render_chat_input(*, disabled: bool = False) -> str:
    """Render chat input element and return submitted text."""
    return st.chat_input("Ask Teller anything", disabled=disabled) or ""


def _safe_get_conversations():
    try:
        return get_conversation_history()
    except Exception:
        return []
