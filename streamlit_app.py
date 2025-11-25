import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid
import pymongo

# Load environment variables
load_dotenv()

@st.cache_resource(show_spinner=False)
def get_mongo_client():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    try:
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        # Check connection
        client.server_info()
        return client
    except Exception as e:
        return None

def get_mongo_collection():
    client = get_mongo_client()
    if client:
        db = client["loan_assistant_db"]
        return db["logs"]
    return None

def get_conversations_collection():
    client = get_mongo_client()
    if client:
        db = client["loan_assistant_db"]
        return db["conversations"]
    return None

def save_message(role, content, tool_calls=None):
    collection = get_conversations_collection()
    if collection is None:
        return

    if "conversation_id" not in st.session_state or not st.session_state.conversation_id:
        st.session_state.conversation_id = str(uuid.uuid4())
        # Create new conversation document
        title = content[:30] + "..." if len(content) > 30 else content
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

def load_conversation(conversation_id):
    collection = get_conversations_collection()
    if collection is not None:
        conv = collection.find_one({"conversation_id": conversation_id})
        if conv:
            st.session_state.messages = conv.get("messages", [])
            st.session_state.conversation_id = conversation_id
            st.session_state.previous_response_id = conv.get("last_response_id")
            # We don't rerun here, we let the main loop handle it or rerun from the caller

def log_interaction(user_input, assistant_message, tool_calls):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": st.session_state.get("session_id", "unknown"),
        "user_input": user_input,
        "assistant_message": assistant_message,
        "tool_calls": tool_calls
    }
    
    # Try MongoDB first
    collection = get_mongo_collection()
    if collection is not None:
        try:
            collection.insert_one(log_entry)
            return
        except Exception as e:
            st.error(f"MongoDB logging failed: {e}")
    else:
        st.error("MongoDB connection not available for logging.")

# Page configuration
st.set_page_config(
    page_title="Loans Assistant ChatBot 💬",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for ChatGPT-like styling
st.markdown("""
    <style>
    /* Remove default padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
    }
    
    /* Style the sidebar */
    [data-testid="stSidebar"] {
        background-color: #202123;
        border-right: 1px solid #444654;
    }
    
    /* Style chat input */
    .stChatInputContainer {
        padding-bottom: 1rem;
    }
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #343541; 
    }
    ::-webkit-scrollbar-thumb {
        background: #565869; 
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #676980; 
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "previous_response_id" not in st.session_state:
    st.session_state.previous_response_id = None

if "client" not in st.session_state:
    try:
        st.session_state.client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
    except Exception as e:
        st.error(f"Failed to initialize OpenAI client: {e}")
        st.stop()

# Initialize MongoDB connection
get_mongo_client()

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Server URL configuration
    server_url = st.text_input(
        "MCP Server URL",
        value="https://loan-assistant.fastmcp.app/mcp",
        help="Enter your MCP server URL"
    )
    
    # Model selection
    model = st.selectbox(
        "Model",
        ["gpt-4.1", "gpt-4", "gpt-3.5-turbo"],
        index=0
    )
    
    st.divider()
    
    # New Chat button
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.session_state.previous_response_id = None
        st.rerun()
        
    st.subheader("History")
    
    # Fetch conversations
    conv_collection = get_conversations_collection()
    if conv_collection is not None:
        conversations = list(conv_collection.find().sort("created_at", -1))
        for conv in conversations:
            # Use a unique key for each button
            if st.button(conv.get("title", "Untitled"), key=conv["conversation_id"], use_container_width=True):
                load_conversation(conv["conversation_id"])
                st.rerun()
    
    st.divider()
    
    st.caption("💬 Loans Assistant ChatBot")
    st.caption("Powered by OpenAI & FastMCP")

# Main chat interface
st.title("💬 Loans Assistant ChatBot")

def process_chat(user_input):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_message("user", user_input)
    
    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)
    
    # Show thinking indicator
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            try:
                # Inject instructions if first message
                api_input = user_input
                # Check if this is the first user message (messages list has 1 item which is the user message we just added)
                if len(st.session_state.messages) == 1:
                     api_input = (
                        "System Instructions: You are a helpful loan assistant. "
                        "You have access to tools including 'apply_for_loan' and 'search'. "
                        "CRITICAL SAFETY RULE: You must NEVER call the 'apply_for_loan' tool without explicit user approval. "
                        "When the user wants a loan and you have gathered necessary info, you must STOP and ask for approval. "
                        "To ask for approval, output the exact text 'REQ_APPROVAL' followed by a summary of the loan details. "
                        "Do NOT call the tool yet. "
                        "I will show the user 'Approve' and 'Reject' buttons. "
                        "Wait for the user to click one (which will send 'Approved' or 'Rejected' to you). "
                        "If 'Approved', ONLY THEN call the 'apply_for_loan' tool. "
                        "If 'Rejected', do not call the tool. "
                        "When the user asks a question requesting information or knowledge, use the 'search' tool to find relevant information and provide accurate answers. "
                        "\n\nUser: " + user_input
                     )

                # Call OpenAI API with MCP tools
                stream = st.session_state.client.responses.create(
                    model=model,
                    input=api_input,
                    previous_response_id=st.session_state.previous_response_id,
                    tools=[
                        {
                            "type": "mcp",
                            "server_label": "MCP-server",
                            "server_url": server_url,
                            "require_approval": "never",
                        },
                    ],
                    stream=True,
                )
                
                assistant_message = ""
                tool_calls = []
                tool_placeholders = {}
                
                # Container for tools (appears before text)
                tools_container = st.container()
                # Placeholder for text
                text_placeholder = st.empty()
                
                for event in stream: 
                    if event.type == 'response.created':
                        st.session_state.previous_response_id = event.response.id
                        
                    elif event.type == 'response.output_text.delta':
                        if event.delta:
                            assistant_message += event.delta
                            # Escape dollar signs for display and hide REQ_APPROVAL
                            display_msg = assistant_message.replace("$", "\\$").replace("REQ_APPROVAL", "")
                            text_placeholder.markdown(display_msg + "▌")
                            
                    elif event.type == 'response.output_item.added':
                        item = event.item
                        if item.type == 'mcp_call':
                            ph = tools_container.empty()
                            tool_placeholders[item.id] = ph
                            with ph.status(f"🛠️ Calling tool: {item.name}...", state="running"):
                                st.write("Input:")
                                st.code(item.arguments)
                                
                    elif event.type == 'response.output_item.done':
                        item = event.item
                        if item.type == 'mcp_call':
                            ph = tool_placeholders.get(item.id)
                            if ph:
                                with ph.status(f"🛠️ Used tool: {item.name}", state="complete"):
                                    st.write("Input:")
                                    st.code(item.arguments)
                                    st.write("Output:")
                                    st.code(item.output)
                            
                            tool_calls.append({
                                "name": item.name,
                                "arguments": item.arguments,
                                "result": item.output
                            })
                
                # Final display update
                display_message = assistant_message.replace("$", "\\$").replace("REQ_APPROVAL", "")
                text_placeholder.markdown(display_message)
                
                # Add assistant message to chat history (store original for consistency)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": assistant_message,
                    "tool_calls": tool_calls
                })
                save_message("assistant", assistant_message, tool_calls)
                
                # Log the interaction
                log_interaction(user_input, assistant_message, tool_calls)

                # Rerun to update the UI
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")

# Display chat messages
for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]
    tool_calls = message.get("tool_calls", [])
    
    with st.chat_message(role, avatar="👤" if role == "user" else "🤖"):
        # Display tool calls if any
        if tool_calls:
            for tool_call in tool_calls:
                with st.status(f"🛠️ Used tool: {tool_call.get('name', 'Unknown')}", state="complete"):
                    st.write("Input:")
                    st.code(str(tool_call.get('arguments', '')))
                    st.write("Output:")
                    st.code(str(tool_call.get('result', '')))

        # Escape dollar signs for display to prevent LaTeX rendering issues
        display_content = content.replace("$", "\\$").replace("REQ_APPROVAL", "")
        st.markdown(display_content)

# Check for approval request
last_msg = st.session_state.messages[-1] if st.session_state.messages else None
approval_pending = False

if last_msg and last_msg["role"] == "assistant" and "REQ_APPROVAL" in last_msg["content"]:
    approval_pending = True
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            process_chat("Approved")
    with col2:
        if st.button("❌ Reject", type="secondary", use_container_width=True):
            process_chat("Rejected")

# Chat input
input_placeholder = "Send a message..."
if approval_pending:
    input_placeholder = "Please approve or reject the loan request above."

if user_input := st.chat_input(input_placeholder, disabled=approval_pending):
    process_chat(user_input)
