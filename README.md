# Loans Assistant ChatBot

A modular loan assistant application built with FastMCP, Streamlit, and Azure OpenAI.

## Project Structure

```
FastMCP/
├── backend/                    # Backend modules
│   ├── __init__.py
│   ├── app.py                 # FastAPI banking endpoints
│   ├── database.py            # MongoDB connection utilities
│   ├── mcp_client.py          # MCP client for tool execution
│   ├── mcp_server.py          # MCP server wrapping FastAPI
│   └── models.py              # Pydantic data models
│
├── frontend/                   # Frontend modules
│   ├── __init__.py
│   ├── chat.py                # Chat processing & tool execution
│   ├── config.py              # Configuration settings
│   ├── session.py             # Session state management
│   ├── streamlit_app.py       # Main Streamlit application
│   └── ui.py                  # UI components
│
├── data/                       # Data files (JSON)
├── local-mongo/               # Local MongoDB setup
│
├── run_backend.py             # Backend runner script
├── run_frontend.py            # Frontend runner script
├── requirements.txt           # Python dependencies
└── README.md
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file with:

```env
AZURE_OPENAI_KEY=your_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_GPT_DEPLOYMENT_NAME=gpt-4.1
MONGO_URI=mongodb://localhost:27017/
LINKUP_API_KEY=your_linkup_key  # Optional, for web search
```

### 3. Start MongoDB (if using local)

```bash
cd local-mongo
docker-compose up -d
```

### 4. Start the Backend (MCP Server)

**Option A - Using FastMCP CLI (recommended):**
```bash
fastmcp run backend/mcp_server.py --transport sse --port 8000
```

**Option B - Using Python:**
```bash
python run_backend.py
```

### 5. Start the Frontend (Streamlit)

**Option A - Using Streamlit CLI (recommended):**
```bash
streamlit run frontend/streamlit_app.py
```

**Option B - Using Python:**
```bash
python run_frontend.py
```

## Architecture

### Backend

- **`app.py`**: FastAPI application with banking endpoints:
  - Customer lookup (basic list, full details)
  - Account management
  - Loan applications and status
  - DTI calculation
  - Employment scoring
  - Web search integration

- **`mcp_server.py`**: Wraps FastAPI app as an MCP server using FastMCP

- **`mcp_client.py`**: Client for connecting to MCP servers with SSE transport

- **`database.py`**: MongoDB utilities for both sync (PyMongo) and async (Motor) connections

- **`models.py`**: Pydantic models for data validation

### Frontend

- **`streamlit_app.py`**: Main entry point that orchestrates all components

- **`chat.py`**: Handles chat processing, streaming responses, and tool execution

- **`session.py`**: Manages Streamlit session state and conversation persistence

- **`ui.py`**: Reusable UI components (sidebar, chat display, approval dialog)

- **`config.py`**: Centralized configuration (API keys, prompts, styling)

## Features

- **Dynamic Tool Discovery**: Tools are fetched from MCP server at runtime
- **Streaming Responses**: Real-time display of LLM responses
- **Tool Approval**: Sensitive operations (like loan applications) require user approval
- **Conversation History**: Persisted to MongoDB
- **Local Execution**: All tools execute locally - no external exposure needed

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers/basic` | GET | List all customers (ID + name) |
| `/customers/{id}` | GET | Full customer details |
| `/customers/{id}/accounts` | GET | Customer accounts |
| `/customers/{id}/dti` | GET | Debt-to-income ratio |
| `/customers/{id}/employment_score` | GET | Employment stability score |
| `/loans/apply` | POST | Apply for a loan |
| `/loans/{customer_id}` | GET | Customer's existing loans |
| `/search/web` | GET | Web search via Linkup API |

## Legacy Files

The original monolithic files are still present for reference:
- `streamlit_app_local.py` - Original combined frontend
- `streamlit_app.py` - Cloud version
- `mcp_2.py` - Original MCP server
- `mcp_server.py` - Original MCP server variant

These can be safely removed after verifying the new structure works correctly.
