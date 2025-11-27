import streamlit as st
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid
import pymongo
import json
import asyncio

# FastMCP Client - handles transport inference automatically
from fastmcp import Client

# Load environment variables
load_dotenv()

# ================
# MCP Client - Connect to local MCP server via FastMCP Client
# ================
class MCPClient:
    """MCP client that connects to a local MCP server using FastMCP Client.
    
    Dynamically fetches tools from the server - no hardcoded tool definitions needed.
    """
    
    def __init__(self, server_url: str):
        # Ensure URL ends with /sse for SSE transport
        self.server_url = server_url.rstrip('/')
        if not self.server_url.endswith('/sse'):
            self.server_url = self.server_url + '/sse'
        self._tools_cache = None
    
    async def list_tools(self):
        """Fetch available tools from the MCP server dynamically."""
        if self._tools_cache is not None:
            return self._tools_cache
        
        try:
            client = Client(self.server_url)
            async with client:
                tools_result = await client.list_tools()
                
                # Store raw MCP tools for later use
                self._tools_cache = tools_result
                return self._tools_cache
        except Exception as e:
            print(f"Error fetching tools from MCP server: {e}")
            self._tools_cache = []
            return self._tools_cache
    
    def get_openai_tools_config(self, tools):
        """Convert MCP tools to OpenAI function calling format.
        
        Args:
            tools: List of MCP Tool objects from list_tools()
            
        Returns:
            List of tool definitions in OpenAI format
        """
        openai_tools = []
        for tool in tools:
            tool_def = {
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') and tool.inputSchema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            openai_tools.append(tool_def)
        return openai_tools
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """Execute a tool on the MCP server via FastMCP Client.
        
        Args:
            tool_name: The exact tool name as returned by the MCP server
            arguments: Dictionary of arguments to pass to the tool
        """
        try:
            client = Client(self.server_url)
            async with client:
                # Call the tool via FastMCP Client - use tool name directly (no mapping)
                result = await client.call_tool(tool_name, arguments)
                
                # FastMCP Client returns a CallToolResult with .data property
                if hasattr(result, 'data'):
                    data = result.data
                    # If it's already a dict/list, return directly
                    if isinstance(data, (dict, list)):
                        return data
                    # Try to parse as JSON if it's a string
                    if isinstance(data, str):
                        try:
                            return json.loads(data)
                        except json.JSONDecodeError:
                            return {"result": data}
                    return {"result": str(data)}
                else:
                    # Fallback: handle raw result
                    if isinstance(result, (dict, list)):
                        return result
                    return {"result": str(result)}
                        
        except Exception as e:
            return {"error": f"MCP tool execution failed: {str(e)}"}


# Helper to run async functions in Streamlit
def run_async(coro):
    """Run an async coroutine in Streamlit"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


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
            st.session_state.previous_response_id = None
            st.session_state.pending_approval = None

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
    # { tool_call_id, tool_name, arguments }
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

# Tools that require approval - match by substring in tool name
# This way you don't need to know the exact MCP tool name
TOOLS_REQUIRING_APPROVAL_PATTERNS = ["apply_for_loan_loans_apply_post"]


def tool_requires_approval(tool_name: str) -> bool:
    """Check if a tool requires user approval before execution."""
    tool_name_lower = tool_name.lower()
    return any(pattern in tool_name_lower for pattern in TOOLS_REQUIRING_APPROVAL_PATTERNS)


# Cache for dynamically fetched tools
@st.cache_data(ttl=300, show_spinner=False)  # Cache for 5 minutes
def fetch_mcp_tools(_server_url: str):
    """Fetch tools from MCP server and cache them.
    
    The underscore prefix on _server_url tells Streamlit not to hash this parameter.
    """
    mcp_client = MCPClient(_server_url)
    tools = run_async(mcp_client.list_tools())
    return tools, mcp_client.get_openai_tools_config(tools)


# Initialize MongoDB connection
get_mongo_client()

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Local FastAPI Server URL configuration
    server_url = st.text_input(
        "Local API Server URL",
        value="http://localhost:8000",
        help="Enter your local FastAPI server URL (no ngrok needed!)"
    )
    
    # Model selection - uses Azure OpenAI deployment name
    model = st.selectbox(
        "Model",
        [os.getenv("AZURE_OPENAI_GPT_DEPLOYMENT_NAME", "gpt-4.1")],
        index=0
    )
    
    st.divider()
    
    # Status indicator
    st.markdown("🔒 **Local Mode Active**")
    st.caption("Tools execute locally - no external exposure")
    
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
    st.caption("Powered by Azure OpenAI & Local MCP")

# Main chat interface
st.title("💬 Loans Assistant ChatBot")

def execute_tool_locally(tool_name: str, arguments: dict, mcp_client: MCPClient):
    """Execute a tool on the local MCP server"""
    return run_async(mcp_client.call_tool(tool_name, arguments))

def handle_stream_with_local_tools(stream, tools_container, text_placeholder, mcp_client, assistant_message="", tool_calls_list=None):
    """
    Handle streaming response from OpenAI.
    When function calls are detected, execute them locally and continue the conversation.
    """
    if tool_calls_list is None:
        tool_calls_list = []
    
    tool_placeholders = {}
    pending_tool_calls = []  # Collect function calls to execute
    approval_needed = False
    
    for event in stream:
        # Track response id
        if event.type == 'response.created':
            st.session_state.previous_response_id = event.response.id
        
        elif event.type == 'response.output_item.added':
            item = event.item
            item_type = getattr(item, 'type', None)
            
            # Function call detected - just track it, don't process yet
            if item_type == 'function_call':
                item_id = getattr(item, 'id', None)
                item_name = getattr(item, 'name', None)
                
                # For non-approval tools, show status
                if not tool_requires_approval(item_name):
                    ph = tools_container.empty()
                    tool_placeholders[item_id] = ph
                    with ph.status(f"🛠️ Calling tool: {item_name}...", state="running"):
                        st.write("Waiting for arguments...")
            
        elif event.type == 'response.output_text.delta':
            if event.delta:
                assistant_message += event.delta
                display_msg = assistant_message.replace("$", "\\$")
                text_placeholder.markdown(display_msg + "▌")

        elif event.type == 'response.output_item.done':
            item = event.item
            item_type = getattr(item, 'type', None)

            if item_type == 'function_call':
                item_id = getattr(item, 'id', None)
                item_name = getattr(item, 'name', None)
                item_args = getattr(item, 'arguments', None)
                call_id = getattr(item, 'call_id', item_id)  # call_id for function_call_output
                
                # Parse arguments - NOW they are complete
                try:
                    args_dict = json.loads(item_args) if isinstance(item_args, str) else (item_args or {})
                except:
                    args_dict = {}
                
                # Check if this tool requires approval
                if tool_requires_approval(item_name):
                    st.session_state.pending_approval = {
                        "response_id": st.session_state.previous_response_id,
                        "tool_call_id": call_id,
                        "tool_name": item_name,
                        "arguments": args_dict,
                    }
                    approval_needed = True
                    continue  # Skip execution, wait for approval
                
                # Execute tool locally
                ph = tool_placeholders.get(item_id)
                result = execute_tool_locally(item_name, args_dict, mcp_client)
                result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                
                # Update status
                if ph:
                    with ph.status(f"🛠️ Used tool: {item_name}", state="complete"):
                        st.write("Input:")
                        st.code(item_args)
                        st.write("Output:")
                        st.code(result_str)
                
                # Collect for continuation
                pending_tool_calls.append({
                    "call_id": call_id,
                    "name": item_name,
                    "arguments": args_dict,
                    "result": result_str,
                })
                
                tool_calls_list.append({
                    "name": item_name,
                    "arguments": item_args,
                    "result": result_str,
                })
    
    return assistant_message, tool_calls_list, pending_tool_calls, approval_needed

def continue_with_tool_results(pending_tool_calls, tools_container, text_placeholder, mcp_client, openai_tools, assistant_message="", tool_calls_list=None):
    """Continue the conversation by sending tool results back to OpenAI"""
    if tool_calls_list is None:
        tool_calls_list = []
    
    # Build function call output items
    function_outputs = []
    for tc in pending_tool_calls:
        function_outputs.append({
            "type": "function_call_output",
            "call_id": tc["call_id"],
            "output": tc["result"],
        })
    
    # Continue the response with tool outputs
    stream = st.session_state.client.responses.create(
        model=model,
        previous_response_id=st.session_state.previous_response_id,
        input=function_outputs,
        tools=openai_tools,
        stream=True,
    )
    
    # Handle the continuation stream (may trigger more tool calls)
    new_message, new_tool_calls, more_pending, approval_needed = handle_stream_with_local_tools(
        stream, tools_container, text_placeholder, mcp_client, assistant_message, tool_calls_list
    )
    
    # If there are more tool calls, continue recursively
    if more_pending and not approval_needed:
        return continue_with_tool_results(
            more_pending, tools_container, text_placeholder, mcp_client, openai_tools, new_message, new_tool_calls
        )
    
    return new_message, new_tool_calls, approval_needed

def handle_approval(approved):
    """Handle user approval/rejection of a tool call"""
    approval_data = st.session_state.pending_approval
    if not approval_data:
        return

    st.session_state.pending_approval = None
    
    mcp_client = MCPClient(server_url)
    
    # Fetch tools dynamically from MCP server
    _, openai_tools = fetch_mcp_tools(server_url)

    # Get the last assistant message
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
            tool_name = approval_data["tool_name"]
            arguments = approval_data["arguments"]
            call_id = approval_data["tool_call_id"]
            
            if approved:
                # Execute the tool locally
                ph = tools_container.empty()
                with ph.status(f"🛠️ Calling tool: {tool_name}...", state="running"):
                    st.write("Input:")
                    st.code(json.dumps(arguments, indent=2))
                
                result = execute_tool_locally(tool_name, arguments, mcp_client)
                result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                
                with ph.status(f"🛠️ Used tool: {tool_name}", state="complete"):
                    st.write("Input:")
                    st.code(json.dumps(arguments, indent=2))
                    st.write("Output:")
                    st.code(result_str)
                
                base_tools.append({
                    "name": tool_name,
                    "arguments": json.dumps(arguments),
                    "result": result_str,
                })
                
                # Continue with tool result
                function_output = {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result_str,
                }
                
                stream = st.session_state.client.responses.create(
                    model=model,
                    previous_response_id=approval_data["response_id"],
                    input=[function_output],
                    tools=openai_tools,
                    stream=True,
                )
                
                new_message, new_tool_calls, pending_calls, approval_needed = handle_stream_with_local_tools(
                    stream, tools_container, text_placeholder, mcp_client, base_content, base_tools
                )
                
                # Continue if there are more tool calls
                if pending_calls and not approval_needed:
                    new_message, new_tool_calls, approval_needed = continue_with_tool_results(
                        pending_calls, tools_container, text_placeholder, mcp_client, openai_tools, new_message, new_tool_calls
                    )
                
            else:
                # User rejected - for loan applications, still call backend with force_reject=True
                if tool_name == "apply_for_loan_loans_apply_post":
                    reject_arguments = dict(arguments)
                    reject_arguments["force_reject"] = True
                    
                    ph = tools_container.empty()
                    with ph.status(f"🛠️ Recording rejected loan...", state="running"):
                        st.write("Input:")
                        st.code(json.dumps(reject_arguments, indent=2))
                    
                    result = execute_tool_locally(tool_name, reject_arguments, mcp_client)
                    result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                    
                    with ph.status(f"🛠️ Loan rejected and recorded", state="complete"):
                        st.write("Input:")
                        st.code(json.dumps(reject_arguments, indent=2))
                        st.write("Output:")
                        st.code(result_str)
                    
                    rejection_result = result_str
                    base_tools.append({
                        "name": tool_name,
                        "arguments": json.dumps(reject_arguments),
                        "result": rejection_result,
                    })
                else:
                    rejection_result = json.dumps({"error": "User rejected the tool call", "status": "rejected"})
                    base_tools.append({
                        "name": tool_name,
                        "arguments": json.dumps(arguments),
                        "result": rejection_result,
                    })
                
                function_output = {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": rejection_result,
                }
                
                stream = st.session_state.client.responses.create(
                    model=model,
                    previous_response_id=approval_data["response_id"],
                    input=[function_output],
                    tools=openai_tools,
                    stream=True,
                )
                
                new_message, new_tool_calls, pending_calls, approval_needed = handle_stream_with_local_tools(
                    stream, tools_container, text_placeholder, mcp_client, base_content, base_tools
                )
                
                # Continue if there are more tool calls
                if pending_calls and not approval_needed:
                    new_message, new_tool_calls, approval_needed = continue_with_tool_results(
                        pending_calls, tools_container, text_placeholder, mcp_client, openai_tools, new_message, new_tool_calls
                    )

            # Final display update
            display_message = new_message.replace("$", "\\$")
            text_placeholder.markdown(display_message)

            # Update or append the assistant message
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
            
            save_message("assistant", new_message, new_tool_calls)
            log_interaction(f"[Approval: {'approved' if approved else 'rejected'}] {tool_name}", new_message, new_tool_calls)

            # Rerun if more approval needed, otherwise just refresh
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.session_state.previous_response_id = None
            st.rerun()

def process_chat(user_input):
    """Process user input and generate response with local tool execution"""
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_message("user", user_input)
    
    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)
    
    # Create MCP client for local tool execution
    mcp_client = MCPClient(server_url)
    
    # Fetch tools dynamically from MCP server
    _, openai_tools = fetch_mcp_tools(server_url)
    
    # Show thinking indicator
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            try:
                # Include system instructions with every message
                api_input = (
                    "System Instructions: You are a helpful loan assistant. "
                    "You have access to various tools to help customers. "
                    "When the user asks a question requesting information or knowledge, use the appropriate search tool to find relevant information and provide accurate answers. "
                    "Loan approvals and rejections are ultimately decided by the human user: if the user explicitly approves a loan request you must treat it as approved and may not overturn it, and if the user rejects a request you must treat it as rejected with no reversals. "
                    "IMPORTANT: You must ONLY answer questions related to loans, banking services, and customer account information. "
                    "If the user asks about any other topic (e.g., general knowledge, coding, cooking, weather, etc.), "
                    "you must politely decline to answer and remind them that you are a specialized loan assistant."
                    "\n\nUser: " + user_input
                )

                # Call OpenAI API with dynamically fetched tools
                stream = st.session_state.client.responses.create(
                    model=model,
                    input=api_input,
                    previous_response_id=st.session_state.previous_response_id,
                    tools=openai_tools,
                    stream=True,
                )
                
                tools_container = st.container()
                text_placeholder = st.empty()
                
                assistant_message, tool_calls, pending_calls, approval_needed = handle_stream_with_local_tools(
                    stream, tools_container, text_placeholder, mcp_client
                )
                
                # If there are pending tool calls (not requiring approval), continue
                if pending_calls and not approval_needed:
                    assistant_message, tool_calls, approval_needed = continue_with_tool_results(
                        pending_calls, tools_container, text_placeholder, mcp_client, openai_tools, assistant_message, tool_calls
                    )
                
                # Final display update
                display_message = assistant_message.replace("$", "\\$")
                text_placeholder.markdown(display_message)
                
                # Add assistant message to chat history
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
    arguments = st.session_state.pending_approval.get("arguments", {})
    
    st.info(f"🔐 **Action Required:** The assistant wants to use **{tool_name}**.")
    st.json(arguments)
    st.caption("Please review and approve or reject this action.")
    
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
