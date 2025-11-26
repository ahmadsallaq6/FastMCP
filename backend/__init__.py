# Backend package
# Contains FastAPI app, MCP server, and supporting modules

from backend.database import get_mongo_client, get_db
from backend.mcp_client import MCPClient

__all__ = ["get_mongo_client", "get_db", "MCPClient"]
