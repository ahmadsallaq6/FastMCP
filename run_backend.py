"""
Backend server runner script.

Starts the MCP server that wraps the FastAPI banking backend.

Usage:
    python run_backend.py
    
Or with FastMCP CLI:
    fastmcp run backend/mcp_server.py --transport sse --port 8000
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.mcp_server import mcp

if __name__ == "__main__":
    print("Starting MCP Server on http://localhost:8000")
    print("Press Ctrl+C to stop")
    mcp.run()
