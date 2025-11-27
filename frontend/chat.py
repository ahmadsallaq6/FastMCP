"""
Chat processing logic for the Streamlit application.
Handles streaming responses, tool execution, and approval workflows.
"""

import streamlit as st
import json
import base64
from typing import List, Dict, Any, Tuple, Optional, Union

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from mcp_client import MCPClient, run_async
from config import tool_requires_approval, SYSTEM_PROMPT
from session import save_message, log_interaction


def display_tool_result(result: Any, result_str: str, container=None) -> None:
    """Display tool result, handling PDF downloads specially.
    
    Args:
        result: The parsed result dictionary
        result_str: The stringified result
        container: Streamlit container to display in (defaults to st)
    """
    if container is None:
        container = st
    
    # Check if result contains a PDF (base64 encoded)
    if isinstance(result, dict) and "pdf_base64" in result:
        container.success("✅ PDF contract generated successfully!")
        # Show download button for the PDF
        try:
            pdf_bytes = base64.b64decode(result['pdf_base64'])
            filename = result.get('filename', 'contract.pdf')
            container.download_button(
                label=f"📥 {filename}",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True,
                key=f"pdf_download_{result.get('loan_id', 'unknown')}"
            )
            # Show the rest of the result (without the large base64 string)
            display_result = {k: v for k, v in result.items() if k != 'pdf_base64'}
            if display_result:
                container.info("**Result Details:**")
                container.json(display_result)
        except Exception as e:
            container.error(f"Failed to decode PDF: {str(e)}")
            container.code(result_str)
    else:
        container.code(result_str)


@st.cache_data(ttl=300, show_spinner=False)  # Cache for 5 minutes
def fetch_mcp_tools(_server_url: str) -> Tuple[List, List[Dict]]:
    """Fetch tools from MCP server and cache them.
    
    The underscore prefix on _server_url tells Streamlit not to hash this parameter.
    
    Args:
        _server_url: URL of the MCP server
        
    Returns:
        Tuple of (raw MCP tools, OpenAI-formatted tools)
    """
    mcp_client = MCPClient(_server_url)
    tools = run_async(mcp_client.list_tools())
    return tools, mcp_client.get_openai_tools_config(tools)


def execute_tool_locally(
    tool_name: str,
    arguments: dict,
    mcp_client: MCPClient,
) -> Union[Dict[str, Any], List[Any]]:
    """Execute a tool on the local MCP server.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool
        mcp_client: MCPClient instance
        
    Returns:
        Tool execution result
    """
    return run_async(mcp_client.call_tool(tool_name, arguments))


def handle_stream_with_local_tools(
    stream,
    tools_container,
    text_placeholder,
    mcp_client: MCPClient,
    assistant_message: str = "",
    tool_calls_list: Optional[List] = None
) -> Tuple[str, List, List, bool]:
    """Handle streaming response from OpenAI with local tool execution.
    
    Args:
        stream: OpenAI streaming response
        tools_container: Streamlit container for tool status displays
        text_placeholder: Streamlit placeholder for text output
        mcp_client: MCPClient for tool execution
        assistant_message: Accumulated assistant message
        tool_calls_list: List to accumulate tool calls
        
    Returns:
        Tuple of (message, tool_calls, pending_calls, approval_needed)
    """
    if tool_calls_list is None:
        tool_calls_list = []
    
    tool_placeholders = {}
    pending_tool_calls = []
    approval_needed = False
    
    for event in stream:
        # Track response id
        if event.type == 'response.created':
            st.session_state.previous_response_id = event.response.id
        
        elif event.type == 'response.output_item.added':
            item = event.item
            item_type = getattr(item, 'type', None)
            
            if item_type == 'function_call':
                item_id = getattr(item, 'id', None)
                item_name = getattr(item, 'name', None)
                if not isinstance(item_name, str):
                    continue
                
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
                if not isinstance(item_name, str):
                    continue
                item_args = getattr(item, 'arguments', None)
                call_id = getattr(item, 'call_id', item_id)
                
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
                    continue
                
                # Execute tool locally
                ph = tool_placeholders.get(item_id)
                result = execute_tool_locally(item_name, args_dict, mcp_client)
                result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                
                if ph:
                    with ph.status(f"🛠️ Used tool: {item_name}", state="complete"):
                        st.write("Input:")
                        st.code(item_args)
                        st.write("Output:")
                        display_tool_result(result, result_str)
                
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


def continue_with_tool_results(
    pending_tool_calls: List[Dict],
    tools_container,
    text_placeholder,
    mcp_client: MCPClient,
    openai_tools: List[Dict],
    model: str,
    assistant_message: str = "",
    tool_calls_list: Optional[List] = None
) -> Tuple[str, List, bool]:
    """Continue the conversation by sending tool results back to OpenAI.
    
    Args:
        pending_tool_calls: List of tool calls that need results sent
        tools_container: Streamlit container for tool status
        text_placeholder: Streamlit placeholder for text
        mcp_client: MCPClient instance
        openai_tools: Tool definitions for OpenAI
        model: Model name to use
        assistant_message: Accumulated message
        tool_calls_list: Accumulated tool calls
        
    Returns:
        Tuple of (message, tool_calls, approval_needed)
    """
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
    
    # Handle the continuation stream
    new_message, new_tool_calls, more_pending, approval_needed = handle_stream_with_local_tools(
        stream, tools_container, text_placeholder, mcp_client, assistant_message, tool_calls_list
    )
    
    # If there are more tool calls, continue recursively
    if more_pending and not approval_needed:
        return continue_with_tool_results(
            more_pending, tools_container, text_placeholder, mcp_client, 
            openai_tools, model, new_message, new_tool_calls
        )
    
    return new_message, new_tool_calls, approval_needed


def process_chat(user_input: str, server_url: str, model: str):
    """Process user input and generate response with local tool execution.
    
    Args:
        user_input: The user's message
        server_url: URL of the MCP server
        model: Model name to use
    """
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
                api_input = SYSTEM_PROMPT + "\n\nUser: " + user_input

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
                        pending_calls, tools_container, text_placeholder, 
                        mcp_client, openai_tools, model, assistant_message, tool_calls
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


def handle_approval(approved: bool, server_url: str, model: str):
    """Handle user approval/rejection of a tool call.
    
    Args:
        approved: Whether the user approved the tool call
        server_url: URL of the MCP server
        model: Model name to use
    """
    if st.session_state.pending_approval:
        st.session_state.processing_approval = {
            "approved": approved,
            "data": st.session_state.pending_approval
        }
        st.session_state.pending_approval = None


def process_pending_approval(server_url: str, model: str):
    """Process a pending approval action.
    
    Args:
        server_url: URL of the MCP server
        model: Model name to use
    """
    approval_action = st.session_state.processing_approval
    if not approval_action:
        return

    approved = approval_action["approved"]
    approval_data = approval_action["data"]
    
    mcp_client = MCPClient(server_url)
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
            arguments = approval_data["arguments"] or {}
            exec_arguments = dict(arguments)
            if approved and tool_name == "apply_for_loan_loans_apply_post":
                # Flag tells backend the human advisor explicitly approved the loan
                exec_arguments["force_approve"] = True
            call_id = approval_data["tool_call_id"]
            
            if approved:
                # Execute the tool locally
                ph = tools_container.empty()
                with ph.status(f"🛠️ Calling tool: {tool_name}...", state="running"):
                    st.write("Input:")
                    st.code(json.dumps(exec_arguments, indent=2))
                
                result = execute_tool_locally(tool_name, exec_arguments, mcp_client)
                result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                
                with ph.status(f"🛠️ Used tool: {tool_name}", state="complete"):
                    st.write("Input:")
                    st.code(json.dumps(exec_arguments, indent=2))
                    st.write("Output:")
                    display_tool_result(result, result_str)
                
                base_tools.append({
                    "name": tool_name,
                    "arguments": json.dumps(exec_arguments),
                    "result": result_str,
                })
                
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
                
                if pending_calls and not approval_needed:
                    new_message, new_tool_calls, approval_needed = continue_with_tool_results(
                        pending_calls, tools_container, text_placeholder, 
                        mcp_client, openai_tools, model, new_message, new_tool_calls
                    )
                
            else:
                # User rejected
                # For loan applications, still call the backend with force_reject=True to record the denial
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
                
                if pending_calls and not approval_needed:
                    new_message, new_tool_calls, approval_needed = continue_with_tool_results(
                        pending_calls, tools_container, text_placeholder, 
                        mcp_client, openai_tools, model, new_message, new_tool_calls
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
            log_interaction(
                f"[Approval: {'approved' if approved else 'rejected'}] {tool_name}", 
                new_message, 
                new_tool_calls
            )

            st.session_state.processing_approval = None
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.session_state.previous_response_id = None
            st.session_state.processing_approval = None
            st.rerun()
