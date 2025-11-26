"""
MCP Client for connecting to a local MCP server.
Uses FastMCP Client for SSE transport communication.
"""

import json
import asyncio
from typing import Optional, List, Dict, Any
from fastmcp import Client


class MCPClient:
    """MCP client that connects to a local MCP server using FastMCP Client.
    
    Dynamically fetches tools from the server - no hardcoded tool definitions needed.
    
    Attributes:
        server_url: The URL of the MCP server (with /sse endpoint)
    """
    
    def __init__(self, server_url: str):
        """Initialize the MCP client.
        
        Args:
            server_url: Base URL of the MCP server (e.g., http://localhost:8000)
        """
        # Ensure URL ends with /sse for SSE transport
        self.server_url = server_url.rstrip('/')
        if not self.server_url.endswith('/sse'):
            self.server_url = self.server_url + '/sse'
        self._tools_cache: Optional[List] = None
    
    async def list_tools(self) -> List:
        """Fetch available tools from the MCP server dynamically.
        
        Returns:
            List of MCP Tool objects available on the server
        """
        if self._tools_cache is not None:
            return self._tools_cache
        
        try:
            client = Client(self.server_url)
            async with client:
                tools_result = await client.list_tools()
                self._tools_cache = tools_result
                return self._tools_cache
        except Exception as e:
            print(f"Error fetching tools from MCP server: {e}")
            self._tools_cache = []
            return self._tools_cache
    
    def clear_tools_cache(self):
        """Clear the cached tools to force a refresh on next list_tools call."""
        self._tools_cache = None
    
    def get_openai_tools_config(self, tools: List) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format.
        
        Args:
            tools: List of MCP Tool objects from list_tools()
            
        Returns:
            List of tool definitions in OpenAI function calling format
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
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on the MCP server via FastMCP Client.
        
        Args:
            tool_name: The exact tool name as returned by the MCP server
            arguments: Dictionary of arguments to pass to the tool
            
        Returns:
            Tool execution result as a dictionary
        """
        try:
            client = Client(self.server_url)
            async with client:
                # Call the tool via FastMCP Client
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


def run_async(coro):
    """Helper to run an async coroutine in synchronous context (e.g., Streamlit).
    
    Args:
        coro: An awaitable coroutine
        
    Returns:
        The result of the coroutine
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
