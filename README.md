# Assignment 3: Customer 360 Operator Agent

## Objective
Build a **Model Context Protocol (MCP) Server** that wraps an existing Core Banking Microservice and an **MCP Client Chatbot** that interacts with it. This assignment focuses on standardizing tool exposure using the MCP specification.

## The Existing Service
You are provided with a simulated Core Banking Customer Microservice.

- **Base URL**: `https://customer-microservice-eu.proudsky-2219dea3.westeurope.azurecontainerapps.io`
- **Interactive Docs**: [Swagger UI](https://customer-microservice-eu.proudsky-2219dea3.westeurope.azurecontainerapps.io/docs)

### Capabilities
- **Get Customer Profile**: `GET /api/v1/customers/{id}`
- **List Accounts**: `GET /api/v1/customers/{id}/accounts`
- **Internal Transfer**: `POST /api/v1/transfers/internal`

### Test Data
The database is in-memory and resets on restart. Use these IDs:
- **Alice Johnson**: `CUST-001` (Has 2 accounts)
- **Bob Smith**: `CUST-002` (Has 1 account)

## Core Tasks

### 1. Build the MCP Server
- Create a new server using **FastMCP** 
- This server should expose the Core Banking Microservice's POST endpoints as **MCP Tools** and GET endpoints as **MCP Resources**
- The tools should handle the API calls to the provided FastAPI app.

### 2. Build the MCP Client Chatbot
- Build a chatbot application that acts as an MCP Client.
- It should connect to your MCP Server.
- Users should be able to ask natural language questions like:
  - "What is Alice's current balance?"
  - "Transfer $500 from Alice's checking to her savings."
- The chatbot uses the LLM to select the appropriate MCP tool and execute the action.

### 3. Frontend Reactivity
- The frontend must be **reactive to agent processing**.
- **Visibility**: When the agent calls a tool (e.g., `transfer_money`), the UI should display this action in real-time (e.g., "Agent is executing transfer...").
- **Technical Hint**: Use **Server-Sent Events (SSE)** to stream events from the backend to the frontend. The frontend should listen to these events and update the UI accordingly.

## Suggested Team Split
To complete this assignment effectively as a team of 3, we recommend the following division of labor:

- **Member 1: MCP Server Implementation**
  - Analyzing the upstream API.
  - Implementing the FastMCP server.
  - Defining the Tool (POST) and Resource (GET) definitions.
- **Member 2: Frontend (Streamlit)**
  - Building the Chatbot UI using Streamlit.
  - Implementing the event loop to render SSE updates.
  - Ensuring a smooth, reactive user experience.
- **Member 3: MCP Client & Backend**
  - Building the MCP Client logic to connect to the server.
  - Handling the LLM interaction loop.
  - Setting up the backend API to stream events to the frontend.
