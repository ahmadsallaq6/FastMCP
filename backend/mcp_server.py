"""
MCP Server that wraps the FastAPI app.
Converts FastAPI endpoints into MCP tools using FastMCP.

Run with: fastmcp run backend/mcp_server.py --transport sse --port 8000
"""

from fastmcp import FastMCP
from app import app

# Convert FastAPI app to MCP server
mcp = FastMCP.from_fastapi(app=app)

if __name__ == "__main__":
    mcp.run()
