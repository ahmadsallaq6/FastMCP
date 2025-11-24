import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="MCP ChatBot",
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

if "previous_response_id" not in st.session_state:
    st.session_state.previous_response_id = None

if "client" not in st.session_state:
    try:
        st.session_state.client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
    except Exception as e:
        st.error(f"Failed to initialize OpenAI client: {e}")
        st.stop()

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Server URL configuration
    server_url = st.text_input(
        "MCP Server URL",
        value="https://stubbly-cathryn-broadish.ngrok-free.dev/sse",
        help="Enter your MCP server URL"
    )
    
    # Model selection
    model = st.selectbox(
        "Model",
        ["gpt-4.1", "gpt-4", "gpt-3.5-turbo"],
        index=0
    )
    
    st.divider()
    
    # Clear chat button
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.previous_response_id = None
        st.rerun()
    
    st.divider()
    
    st.caption("💬 MCP ChatBot")
    st.caption("Powered by OpenAI & FastMCP")

# Main chat interface
st.title("💬 MCP ChatBot")

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

# Chat input
if user_input := st.chat_input("Send a message..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)
    
    # Show thinking indicator
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            try:
                # Call OpenAI API with MCP tools
                stream = st.session_state.client.responses.create(
                    model=model,
                    input=user_input,
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
                            # Escape dollar signs for display
                            display_msg = assistant_message.replace("$", "\\$")
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
                display_message = assistant_message.replace("$", "\\$")
                text_placeholder.markdown(display_message)
                
                # Add assistant message to chat history (store original for consistency)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": assistant_message,
                    "tool_calls": tool_calls
                })
                
                # Rerun to update the UI
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
