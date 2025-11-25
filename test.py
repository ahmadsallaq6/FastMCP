from openai import AzureOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2025-03-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# We start with no history
previous_response_id = None
print("💬 Chat started! (Type 'quit' to exit)")

while True:
    # 1. Get user input
    user_input = input("\n> ")
    if user_input.lower() in ["quit", "exit"]:
        break

    # 2. Call Azure OpenAI (The "Cloud-to-Cloud" magic happens here)
    # We pass 'previous_response_id' so the model remembers what we just said.
    print("Thinking...", end="\r")
    
    try:
        response = client.responses.create(
            model=os.getenv("AZURE_OPENAI_GPT_DEPLOYMENT_NAME", "gpt-4.1"), 
            input=user_input,
            previous_response_id=previous_response_id, # <--- Maintains Memory
            tools=[
                {
                    "type": "mcp",
                    "server_label": "MCP-server",
                    "server_url": "https://dithionous-dania-unterminated.ngrok-free.dev/sse", 
                    "require_approval": "never",
                },
            ],
        )


        # 3. Update history tracking
        # The API returns an ID for this specific interaction. 
        # We save it to chain the NEXT message to this one.
        previous_response_id = response.id

        # 4. Print the result
        # Note: We use 'output_text' instead of 'choices[0].message.content'
        print(f"🤖 {response.output_text}")

    except Exception as e:
        print(f"❌ Error: {e}")