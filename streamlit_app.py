import streamlit as st
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid
import pymongo

# Load environment variables
load_dotenv()

AZURE_GPT_DEPLOYMENT = os.getenv("AZURE_OPENAI_GPT_DEPLOYMENT_NAME", "gpt-4.1")

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

def _extract_response_text(response) -> str:
    """Pull plain text segments out of a Responses API output."""
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
    """Use Azure OpenAI to craft a short descriptive title."""
    base = (seed_content or "New Conversation").strip()
    default_title = (base[:30] + "...") if len(base) > 30 else (base or "New Conversation")

    client = st.session_state.get("client")
    if client is None:
        return default_title

    prompt = (
        "You name banking chat conversations. "
        "Respond with a title under 6 words, Title Case, no surrounding quotes."
    )

    try:
        response = client.responses.create(
            model=AZURE_GPT_DEPLOYMENT,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Conversation context:\n{seed_content}"},
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


def save_message(role, content, tool_calls=None):
    collection = get_conversations_collection()
    if collection is None:
        return

    if "conversation_id" not in st.session_state or not st.session_state.conversation_id:
        st.session_state.conversation_id = str(uuid.uuid4())
        # Create new conversation document
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

def load_conversation(conversation_id):
    collection = get_conversations_collection()
    if collection is not None:
        conv = collection.find_one({"conversation_id": conversation_id})
        if conv:
            st.session_state.messages = conv.get("messages", [])
            st.session_state.conversation_id = conversation_id
            # Don't restore previous_response_id - these IDs expire quickly on OpenAI's side
            # Treating loaded history as context for a fresh request avoids 400 errors
            st.session_state.previous_response_id = None
            st.session_state.pending_approval = None
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

if "pending_approval" not in st.session_state:
    # { response_id, tool_call_id, tool_name }
    st.session_state.pending_approval = None


if "client" not in st.session_state:
    try:
        st.session_state.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2025-03-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    except Exception as e:
        st.error(f"Failed to initialize Azure OpenAI client: {e}")
        st.stop()

# Helper function to get MCP tools configuration
def get_mcp_tools_config(mcp_server_url):
    return [
        {
            "type": "mcp",
            "server_label": "MCP-server",
            "server_url": mcp_server_url,
            "require_approval": {
                "always": {"tool_names": ["apply_for_loan"]},
                "never": {
                    "tool_names": [
                        "list_customers_basic_customers_basic_get",
                        "get_customer_customers",
                        "get_accounts_customers",
                        "get_customer_loans_loans",
                        "calculate_dti_customers",
                        "get_employment_score_customers",
                        "linkup_web_search_search_web_get"
                    ]
                }
            }
        }
    ]

# Initialize MongoDB connection
get_mongo_client()

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Server URL configuration
    server_url = st.text_input(
        "MCP Server URL",
        value="https://stubbly-cathryn-broadish.ngrok-free.dev/sse",
        help="Enter your MCP server URL"
    )
    
    # Model selection - uses Azure OpenAI deployment name
    model = st.selectbox(
        "Model",
        [AZURE_GPT_DEPLOYMENT],
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
    st.caption("Powered by Azure OpenAI & FastMCP")

# Main chat interface
st.title("💬 Loans Assistant ChatBot")

def handle_stream(stream, tools_container, text_placeholder, assistant_message="", tool_calls=None):
    if tool_calls is None:
        tool_calls = []
    
    tool_placeholders = {}
    approval_needed = False  # Track if approval is needed, but don't return early
    
    for event in stream:
        # Debug: uncomment to see all events
        # st.write(f"DEBUG Event: {event.type}")
        # if hasattr(event, 'item'):
        #     item = event.item
        #     st.write(f"DEBUG Item type attr: {getattr(item, 'type', 'N/A')}")
        #     st.write(f"DEBUG Item vars: {vars(item) if hasattr(item, '__dict__') else item}")
        
        # Track response id for possible follow-up approvals
        if event.type == 'response.created':
            st.session_state.previous_response_id = event.response.id
        
        elif event.type == 'response.output_item.added':
            item = event.item
            item_type = getattr(item, 'type', None)
            
            # MCP approval request - this is when a tool requires user approval
            if item_type == 'mcp_approval_request':
                # Get the approval request ID from the item
                approval_id = getattr(item, 'id', None)
                tool_name = getattr(item, 'name', None)
                arguments = getattr(item, 'arguments', None)
                server_label = getattr(item, 'server_label', None)
                
                st.session_state.pending_approval = {
                    "response_id": st.session_state.previous_response_id,
                    "approval_request_id": approval_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "server_label": server_label,
                }
                # Mark that approval is needed, but DON'T return early
                # We need to let the stream complete so the response is stored
                approval_needed = True
            
            # Normal tool / MCP execution (no approval required)
            if item_type in ['mcp_call', 'tool_call', 'function_call', 'function']:
                ph = tools_container.empty()
                item_id = getattr(item, 'id', None) if not isinstance(item, dict) else item.get('id')
                item_name = getattr(item, 'name', None) if not isinstance(item, dict) else item.get('name')
                item_args = getattr(item, 'arguments', None) if not isinstance(item, dict) else item.get('arguments')

                tool_placeholders[item_id] = ph
                with ph.status(f"🛠️ Calling tool: {item_name}...", state="running"):
                    st.write("Input:")
                    st.code(item_args)
            
        elif event.type == 'response.output_text.delta':
            if event.delta:
                assistant_message += event.delta
                # Escape dollar signs for display
                display_msg = assistant_message.replace("$", "\\$")
                text_placeholder.markdown(display_msg + "▌")

        elif event.type == 'response.output_item.done':
            item = event.item
            item_type = getattr(item, 'type', None)
            if isinstance(item, dict):
                item_type = item.get('type')

            if item_type in [
                'mcp_call',
                'tool_call',
                'function_call',
                'function',
            ]:
                item_id = getattr(item, 'id', None)
                ph = tool_placeholders.get(item_id)
                if ph:
                    item_name = getattr(item, 'name', None)
                    item_args = getattr(item, 'arguments', None)
                    item_output = getattr(item, 'output', None)

                    with ph.status(f"🛠️ Used tool: {item_name}", state="complete"):
                        st.write("Input:")
                        st.code(item_args)
                        st.write("Output:")
                        st.code(item_output)

                tool_calls.append(
                    {
                        "name": getattr(item, 'name', None),
                        "arguments": getattr(item, 'arguments', None),
                        "result": getattr(item, 'output', None),
                    }
                )
                
    return assistant_message, tool_calls, approval_needed

def handle_approval(approved):
    approval_data = st.session_state.pending_approval
    # If there is no pending approval recorded, do nothing.
    if not approval_data:
        return

    # Clear pending approval immediately so UI buttons disappear
    st.session_state.pending_approval = None

    # If there's no approval request ID or response ID, show a message
    if not approval_data.get("approval_request_id") or not approval_data.get("response_id"):
        msg = "Tool action rejected by user." if not approved else "Unable to continue tool call (missing identifiers)."
        st.session_state.messages.append({"role": "assistant", "content": msg})
        save_message("assistant", msg)
        return

    # Get the last assistant message so we can append to it
    last_msg_index = None
    for i in range(len(st.session_state.messages) - 1, -1, -1):
        if st.session_state.messages[i]["role"] == "assistant":
            last_msg_index = i
            break

    if last_msg_index is None:
        base_content = ""
        base_tools = []
    else:
        last_msg = st.session_state.messages[last_msg_index]
        base_content = last_msg.get("content", "")
        base_tools = last_msg.get("tool_calls", [])

    with st.chat_message("assistant", avatar="🤖"):
        tools_container = st.container()
        text_placeholder = st.empty()

        try:
            approval_request_id = approval_data["approval_request_id"]
            
            # Build the MCP approval response input item
            mcp_approval_response = {
                "type": "mcp_approval_response",
                "approval_request_id": approval_request_id,
                "approve": approved,
            }
            if not approved:
                mcp_approval_response["reason"] = "User rejected the tool call"
            
            # Continue with previous_response_id - now valid since we let stream complete
            stream = st.session_state.client.responses.create(
                model=model,
                previous_response_id=approval_data["response_id"],
                input=[mcp_approval_response],
                store=True,
                tools=get_mcp_tools_config(server_url),
                stream=True,
            )

            new_message, new_tool_calls, approval_needed = handle_stream(
                stream, tools_container, text_placeholder, base_content, base_tools
            )

            # Final display update
            display_message = new_message.replace("$", "\\$")
            text_placeholder.markdown(display_message)

            # Update or append the assistant message in session state
            if last_msg_index is None:
                st.session_state.messages.append(
                    {"role": "assistant", "content": new_message, "tool_calls": new_tool_calls}
                )
            else:
                st.session_state.messages[last_msg_index] = {
                    "role": "assistant",
                    "content": new_message,
                    "tool_calls": new_tool_calls,
                }
            
            # Save to MongoDB and log the interaction
            save_message("assistant", new_message, new_tool_calls)
            log_interaction(f"[Approval: {'approved' if approved else 'rejected'}] {approval_data.get('tool_name', 'unknown')}", new_message, new_tool_calls)

            # Always rerun to refresh UI (hide approval buttons, enable input)
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error: {e}")
            # Reset state on error to prevent getting stuck
            st.session_state.previous_response_id = None
            st.rerun()

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
                            "When the user asks a question requesting information or knowledge, use the 'search' tool to find relevant information and provide accurate answers. "
                            "Loan approvals and rejections are ultimately decided by the human user: if the user explicitly approves a loan request you must treat it as approved and may not overturn it, and if the user rejects a request you must treat it as rejected with no reversals. "
                            "IMPORTANT: You must ONLY answer questions related to loans, banking services, and customer account information. "
                            "If the user asks about any other topic (e.g., general knowledge, coding, cooking, weather, etc.), "
                            "you must politely decline to answer and remind them that you are a specialized loan assistant."
                            "\n\nUser: " + user_input
                        )

                # Call OpenAI API with MCP tools
                stream = st.session_state.client.responses.create(
                    model=model,
                    input=api_input,
                    previous_response_id=st.session_state.previous_response_id,
                    store=True,  # Required for previous_response_id to work with approvals
                    tools=get_mcp_tools_config(server_url),
                    stream=True,
                )
                
                tools_container = st.container()
                text_placeholder = st.empty()
                
                assistant_message, tool_calls, approval_needed = handle_stream(
                    stream, tools_container, text_placeholder
                )
                
                # Final display update
                display_message = assistant_message.replace("$", "\\$")
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

                # Rerun if approval needed
                if approval_needed:
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
        display_content = content.replace("$", "\\$")
        st.markdown(display_content)

# Check for approval request
approval_pending = st.session_state.pending_approval is not None

if approval_pending:
    # Show explanation text above the buttons
    tool_name = st.session_state.pending_approval.get("tool_name", "a tool")
    st.info(f"🔐 **Action Required:** The assistant wants to use **{tool_name}**. Please review and approve or reject this action.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            handle_approval(True)
    with col2:
        if st.button("❌ Reject", type="secondary", use_container_width=True):
            handle_approval(False)

# Chat input
input_placeholder = "Send a message..."
if approval_pending:
    input_placeholder = "Please approve or reject the loan request above."

if user_input := st.chat_input(input_placeholder, disabled=approval_pending):
    process_chat(user_input)
