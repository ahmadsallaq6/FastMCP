import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# This tells the test script how to launch your server
server_params = StdioServerParameters(
    command=sys.executable,  # Uses the same python you are running now
    args=["mcp_server.py"],  # The file you just saved
    env=None                 # Inherit environment variables
)

async def main():
    print("🔌 Attempting to connect to mcp_server.py...")
    
    # Launch the server process
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Handshake
            await session.initialize()
            
            # Ask the server what tools it has
            print("✅ Connection established! Asking for tools...")
            result = await session.list_tools()
            
            # Print the results
            print(f"\n🎉 SUCCESS! Your server is working.")
            print(f"Found {len(result.tools)} tools from Azure:\n")
            for tool in result.tools:
                print(f"  🔹 {tool.name}: {tool.description}...")

if __name__ == "__main__":
    # If this fails, you need to install 'mcp': pip install mcp
    try:
        asyncio.run(main())
    except ImportError:
        print("Error: Please run 'pip install mcp' first.")
    except Exception as e:
        print(f"Error: {e}")