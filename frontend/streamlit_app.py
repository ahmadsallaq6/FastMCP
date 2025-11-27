"""
Loans Assistant ChatBot - Streamlit Frontend

A clean, modular Streamlit application for the Loan Assistant.
Connects to a local MCP server for tool execution.

Run with: streamlit run frontend/streamlit_app.py
"""

import streamlit as st

from ui import (
    setup_page,
    render_sidebar,
    render_chat_messages,
    render_approval_dialog,
    render_chat_input,
    render_main_title,
    initialize_connections,
)
from session import init_session_state
from chat import process_chat, handle_approval, fetch_mcp_tools, process_pending_approval
from dashboard import render_dashboard


def render_chat_page(server_url: str, model: str) -> None:
    """Render the chat assistant page content."""
    # Render main content
    render_main_title()
    
    # Display existing chat messages
    render_chat_messages(st.session_state.messages)
    
    # Check if we are processing an approval
    if st.session_state.processing_approval:
        process_pending_approval(server_url, model)
    
    # Check if approval is pending
    approval_pending = st.session_state.pending_approval is not None
    
    # Render approval dialog if needed
    if approval_pending:
        render_approval_dialog(
            on_approve=lambda: handle_approval(True, server_url, model),
            on_reject=lambda: handle_approval(False, server_url, model)
        )
    
    # Render chat input
    user_input = render_chat_input(disabled=approval_pending)
    
    # Process user input
    if user_input:
        process_chat(user_input, server_url, model)


def main():
    """Main application entry point."""
    # Setup page configuration
    setup_page()
    
    # Initialize session state
    init_session_state()
    
    # Initialize current page in session state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "chat"
    
    # Initialize database connections
    initialize_connections()
    
    # Render sidebar and get settings
    server_url, model = render_sidebar()
    
    # Render the appropriate page based on selection
    if st.session_state.current_page == "dashboard":
        render_dashboard()
    else:
        render_chat_page(server_url, model)


if __name__ == "__main__":
    main()
