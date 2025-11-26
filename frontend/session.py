"""
Session state management for the Streamlit application.
Handles initialization and persistence of chat state.
"""

import streamlit as st
import uuid
from datetime import datetime
from openai import AzureOpenAI

from config import (
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_GPT_DEPLOYMENT_NAME,
)

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from database import get_conversations_collection, get_logs_collection, get_mongo_client


def init_session_state():
    """Initialize all session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

    if "previous_response_id" not in st.session_state:
        st.session_state.previous_response_id = None

    if "pending_approval" not in st.session_state:
        st.session_state.pending_approval = None

    if "client" not in st.session_state:
        try:
            st.session_state.client = AzureOpenAI(
                api_key=AZURE_OPENAI_KEY,
                api_version="2025-03-01-preview",
                azure_endpoint=AZURE_OPENAI_ENDPOINT
            )
        except Exception as e:
            st.error(f"Failed to initialize Azure OpenAI client: {e}")
            st.stop()


def _extract_response_text(response) -> str:
    """Pull plain text content out of a Responses API call."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        if isinstance(output_text, (list, tuple)):
            joined = " ".join(str(part) for part in output_text if part)
        else:
            joined = str(output_text)
        if joined.strip():
            return joined.strip()

    text_fragments = []
    for output in getattr(response, "output", []) or []:
        if getattr(output, "type", None) != "message":
            continue
        for content_item in getattr(output, "content", []) or []:
            if getattr(content_item, "type", None) == "text":
                text_fragments.append(getattr(content_item, "text", ""))

    if not text_fragments and hasattr(response, "choices"):
        for choice in getattr(response, "choices", []) or []:
            message = getattr(choice, "message", None)
            if not message:
                continue
            if isinstance(message, dict):
                text_fragments.append(message.get("content", ""))
            else:
                text_fragments.append(getattr(message, "content", ""))

    return "".join(text_fragments).strip()


def generate_conversation_title(seed_content: str) -> str:
    """Use Azure OpenAI to craft a short conversation title."""
    base = (seed_content or "New Conversation").strip()
    default_title = (base[:30] + "...") if len(base) > 30 else (base or "New Conversation")

    client = st.session_state.get("client")
    if client is None:
        return default_title

    prompt = (
        "You are a helpful assistant naming banking chat conversations. "
        "Return a concise title (max 6 words) in Title Case with no quotes or punctuation beyond spaces."
    )

    try:
        response = client.responses.create(
            model=AZURE_OPENAI_GPT_DEPLOYMENT_NAME,
            input=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Conversation context:\n{seed_content}",
                },
            ],
        )
        llm_title = _extract_response_text(response)
        if not llm_title:
            return default_title

        cleaned = " ".join(llm_title.replace("\n", " ").split())
        cleaned = cleaned.strip('"\'')
        if not cleaned:
            return default_title
        if len(cleaned) > 60:
            cleaned = cleaned[:57].rstrip() + "..."
        return cleaned
    except Exception as exc:
        print(f"Conversation title generation failed: {exc}")
        return default_title


def save_message(role: str, content: str, tool_calls=None):
    """Save a message to the conversation in MongoDB.
    
    Args:
        role: The message role ('user' or 'assistant')
        content: The message content
        tool_calls: Optional list of tool calls made
    """
    collection = get_conversations_collection()
    if collection is None:
        return

    # Create new conversation if needed
    if "conversation_id" not in st.session_state or not st.session_state.conversation_id:
        st.session_state.conversation_id = str(uuid.uuid4())
        title = generate_conversation_title(content)
        collection.insert_one({
            "conversation_id": st.session_state.conversation_id,
            "title": title,
            "created_at": datetime.now(),
            "messages": []
        })

    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(),
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    update_data = {"$push": {"messages": message}}
    
    # Save the current previous_response_id to the conversation
    if "previous_response_id" in st.session_state:
        update_data["$set"] = {"last_response_id": st.session_state.previous_response_id}

    collection.update_one(
        {"conversation_id": st.session_state.conversation_id},
        update_data
    )


def load_conversation(conversation_id: str):
    """Load a conversation from MongoDB into session state.
    
    Args:
        conversation_id: The ID of the conversation to load
    """
    collection = get_conversations_collection()
    if collection is not None:
        conv = collection.find_one({"conversation_id": conversation_id})
        if conv:
            st.session_state.messages = conv.get("messages", [])
            st.session_state.conversation_id = conversation_id
            st.session_state.previous_response_id = None
            st.session_state.pending_approval = None


def log_interaction(user_input: str, assistant_message: str, tool_calls):
    """Log an interaction to MongoDB for analytics.
    
    Args:
        user_input: The user's input message
        assistant_message: The assistant's response
        tool_calls: List of tool calls made during the interaction
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": st.session_state.get("session_id", "unknown"),
        "user_input": user_input,
        "assistant_message": assistant_message,
        "tool_calls": tool_calls
    }
    
    collection = get_logs_collection()
    if collection is not None:
        try:
            collection.insert_one(log_entry)
        except Exception as e:
            st.error(f"MongoDB logging failed: {e}")
    else:
        st.error("MongoDB connection not available for logging.")


def get_conversation_history():
    """Get all conversations from MongoDB sorted by creation date.
    
    Returns:
        List of conversation documents or empty list
    """
    collection = get_conversations_collection()
    if collection is not None:
        return list(collection.find().sort("created_at", -1))
    return []


def clear_conversation():
    """Clear the current conversation and start fresh."""
    st.session_state.messages = []
    st.session_state.conversation_id = None
    st.session_state.previous_response_id = None
    st.session_state.pending_approval = None
