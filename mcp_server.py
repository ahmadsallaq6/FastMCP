import httpx
from fastmcp import FastMCP

# 1. Configure the AsyncClient with a higher timeout as well (for actual API calls later)
# default is 5.0, we set it to 60.0 for cold starts
client = httpx.AsyncClient(
    base_url="https://customer-microservice-eu.proudsky-2219dea3.westeurope.azurecontainerapps.io",
    timeout=60.0 
)

# 2. FIX: Add the timeout parameter here
print("Fetching OpenAPI spec (this may take a moment if the server is waking up)...")
response = httpx.get(
    "https://customer-microservice-eu.proudsky-2219dea3.westeurope.azurecontainerapps.io/openapi.json",
    timeout=60.0 # Increased from default 5s to 60s
)
openapi_spec = response.json()

# Create the MCP server
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="My API Server"
)

if __name__ == "__main__":
    mcp.run()