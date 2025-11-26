"""
UI components for the Streamlit application.
Handles sidebar, chat display, and approval dialogs.
"""

import streamlit as st
import json
import html
from typing import List, Dict, Callable

from config import (
    PAGE_CONFIG,
    CUSTOM_CSS,
    DEFAULT_SERVER_URL,
    AZURE_OPENAI_GPT_DEPLOYMENT_NAME,
    get_custom_css,
)
from session import (
    get_conversation_history,
    load_conversation,
    clear_conversation,
)

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from database import get_mongo_client


def setup_page():
    """Configure the Streamlit page settings and apply custom CSS."""
    st.set_page_config(**PAGE_CONFIG)
    
    # Initialize theme in session state
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    
    # Apply theme-specific CSS
    current_css = get_custom_css(st.session_state.theme)
    st.markdown(current_css, unsafe_allow_html=True)


def render_sidebar() -> tuple[str, str]:
    """Render the sidebar with settings and conversation history.
    
    Returns:
        Tuple of (server_url, model)
    """
    with st.sidebar:
        # Theme toggle at the top
        col1, col2 = st.columns([4, 0.8], vertical_alignment="center")
        with col1:
            st.markdown(
                '<div class="settings-title">⚙️ Settings</div>',
                unsafe_allow_html=True,
            )
        with col2:
            # Theme toggle button
            theme_icon = "🌙" if st.session_state.theme == "dark" else "☀️"
            if st.button(theme_icon, key="theme_toggle", help="Toggle light/dark mode", use_container_width=False):
                st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
                st.rerun()
        
        st.divider()
        
        # Local FastAPI Server URL configuration
        st.text_input(
            "🔗 Local API Server URL",
            value=DEFAULT_SERVER_URL,
            help="Enter your local FastAPI server URL (no ngrok needed!)",
            key="server_url_input"
        )
        server_url = st.session_state.get("server_url_input", DEFAULT_SERVER_URL)
        
        # Model selection
        model = st.selectbox(
            "🤖 Model",
            [AZURE_OPENAI_GPT_DEPLOYMENT_NAME],
            index=0,
            key="model_select"
        )
        
        st.divider()
        
        # Status indicator with styling
        if st.session_state.theme == "dark":
            st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(124, 58, 237, 0.15) 0%, rgba(124, 58, 237, 0.05) 100%); 
                            padding: 1rem; border-radius: 12px; text-align: center;
                            border: 1px solid rgba(124, 58, 237, 0.3);">
                    <span style="font-size: 1.2rem; margin-right: 0.5rem;">🔒</span> 
                    <span style="color: #a78bfa; font-weight: 600; font-size: 0.95rem;">Local Mode Active</span>
                    <p style="margin-top: 0.5rem; font-size: 0.8rem; color: #7c3aed; margin-bottom: 0;">
                        Tools execute locally • No external exposure
                    </p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(124, 58, 237, 0.1) 0%, rgba(124, 58, 237, 0.05) 100%); 
                            padding: 1rem; border-radius: 12px; text-align: center;
                            border: 1px solid rgba(124, 58, 237, 0.2);">
                    <span style="font-size: 1.2rem; margin-right: 0.5rem;">🔒</span> 
                    <span style="color: #7c3aed; font-weight: 600; font-size: 0.95rem;">Local Mode Active</span>
                    <p style="margin-top: 0.5rem; font-size: 0.8rem; color: #8b5cf6; margin-bottom: 0;">
                        Tools execute locally • No external exposure
                    </p>
                </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # New Chat button
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            clear_conversation()
            st.rerun()
            
        st.markdown("#### 📜 Conversation History")
        
        # Fetch and display conversations
        conversations = get_conversation_history()
        if conversations:
            for conv in conversations:
                title = conv.get("title", "Untitled")
                # Truncate long titles
                display_title = title[:28] + "..." if len(title) > 28 else title
                if st.button(
                    f"💬 {display_title}", 
                    key=conv["conversation_id"], 
                    use_container_width=True
                ):
                    load_conversation(conv["conversation_id"])
                    st.rerun()
        else:
            st.markdown("""
                <div style="text-align: center; opacity: 0.6; padding: 1rem; font-size: 0.9rem;">
                    No conversation history yet
                </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Footer
        st.markdown("""
            <div style="text-align: center; opacity: 0.6; font-size: 0.8rem; line-height: 1.5;">
                <p style="margin: 0; font-weight: 600;">💬 Loans Assistant</p>
                <p style="margin: 0; font-size: 0.75rem;">Powered by Azure OpenAI & Local MCP</p>
            </div>
        """, unsafe_allow_html=True)
    
    return server_url, model


def render_chat_messages(messages: List[Dict]):
    """Render all chat messages in the conversation.
    
    Args:
        messages: List of message dictionaries with role, content, and tool_calls
    """
    for message in messages:
        role = message["role"]
        content = message["content"]
        tool_calls = message.get("tool_calls", [])
        
        with st.chat_message(role, avatar="👤" if role == "user" else "🤖"):
            # Display tool calls if any
            if tool_calls:
                for tool_call in tool_calls:
                    with st.status(
                        f"🛠️ Used tool: {tool_call.get('name', 'Unknown')}", 
                        state="complete"
                    ):
                        st.write("Input:")
                        st.code(str(tool_call.get('arguments', '')))
                        st.write("Output:")
                        st.code(str(tool_call.get('result', '')))

            # Escape dollar signs for display
            display_content = content.replace("$", "\\$")
            st.markdown(display_content)


def render_approval_dialog(on_approve: Callable, on_reject: Callable):
    """Render the approval dialog for sensitive tool calls.
    
    Args:
        on_approve: Callback function when user approves
        on_reject: Callback function when user rejects
    """
    if st.session_state.pending_approval is None:
        return
    
    tool_name = st.session_state.pending_approval.get("tool_name", "a tool")
    arguments = st.session_state.pending_approval.get("arguments", {})
    
    # Styled approval card
    st.markdown(
        """
        <div class="approval-banner">
            <div class="approval-banner__icon">🔐</div>
            <div>
                <div class="approval-banner__title">Action required</div>
                <div class="approval-banner__subtitle">Review the loan application details below</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown(f"**Tool:** `{tool_name}`")
    st.markdown("**Details:**")
    formatted_json = html.escape(json.dumps(arguments, indent=2))
    st.markdown(
        f"""
        <div class="approval-json">
            <pre>{formatted_json}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2 = st.columns(2, gap="small")
    with col1:
        if st.button("✅ Approve Request", type="primary", use_container_width=True):
            on_approve()
    with col2:
        if st.button("❌ Reject Request", use_container_width=True):
            on_reject()


def render_chat_input(disabled: bool = False) -> str:
    """Render the chat input box.
    
    Args:
        disabled: Whether the input should be disabled
        
    Returns:
        User input string or None
    """
    placeholder = "Send a message..."
    if disabled:
        placeholder = "Please approve or reject the loan request above."
    
    return st.chat_input(placeholder, disabled=disabled)


def render_main_title():
    """Render the main page title."""
    st.markdown("""
        <div class="hero-header">
            <div class="hero-chip">🛡️ Local MCP Ready</div>
            <h1>💬 Loans Assistant</h1>
            <p>Your AI-powered loan consultation partner</p>
        </div>
    """, unsafe_allow_html=True)


def initialize_connections():
    """Initialize database connections."""
    get_mongo_client()
