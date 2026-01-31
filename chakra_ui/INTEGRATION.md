# Chakra - Backend + Frontend Integration

This document describes the integration between the Chakra backend (Python/FastAPI) and the chakra_ui frontend (Next.js) using Server-Sent Events (SSE) for real-time communication.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      chakra_ui (Frontend)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ CodeAssistant│  │DocAssistant │  │   useSSE Hook       │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                     │            │
│         └────────────────┼─────────────────────┘            │
│                          │                                  │
│                          ▼                                  │
│                 SSE Connection                              │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Chakra (Backend)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    FastAPI Server                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │   │
│  │  │ Yantra  │  │ Sutra   │  │ Agni    │  │ Smriti │ │   │
│  │  │ Agent   │  │ Agent   │  │ Agent   │  │ Memory │ │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬───┘ │   │
│  └───────┼────────────┼────────────┼────────────┼─────┘   │
│          │            │            │            │          │
│          └────────────┴─────┬──────┴────────────┘          │
│                             ▼                               │
│                    SSE Streaming Endpoint                    │
│                    /process/stream                          │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Real-time Progress Updates**: See agent iterations as they happen
- **SSE Streaming**: No polling needed - push-based updates
- **Fallback Mode**: Graceful degradation when backend is unavailable
- **CORS Enabled**: Cross-origin requests from frontend to backend

## Quick Start

### 1. Set up the Backend

```bash
cd Chakra/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python api.py
```

The backend will start at `http://localhost:8000`

### 2. Set up the Frontend

```bash
cd chakra_ui

# Copy environment file
cp .env.example .env.local

# Install dependencies
npm install

# Start development server (defaults to port 3000, or next available port)
npm run dev
```

**Note**: If port 3000 is already in use, Next.js will automatically use another port (e.g., 3001). Check the terminal output for the correct URL.

The frontend will start at `http://localhost:3000` (or the port shown in terminal)

## API Endpoints

### POST /process/stream
Stream task processing results using SSE.

**Query Parameters:**
- `task` (required): The task to process
- `context` (optional): Additional context
- `use_rag` (optional): Enable RAG retrieval (default: false)
- `is_code` (optional): Task is code-related (default: true)

**SSE Events:**

| Event Type | Description |
|------------|-------------|
| `start` | Processing started |
| `rag_retrieved` | RAG chunks retrieved |
| `memory_found` | Similar tasks found in memory |
| `iteration_start` | New iteration began |
| `yantra_complete` | Yantra agent finished |
| `sutra_complete` | Sutra agent finished |
| `agni_complete` | Agni agent finished |
| `iteration_complete` | Iteration finished with data |
| `plateau_reached` | Convergence detected |
| `complete` | Processing complete with final results |
| `error` | Error occurred |

## Environment Variables

### Frontend (.env.local)
```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## File Structure

```
chakra_full/
├── Chakra/
│   └── backend/
│       ├── api.py           # FastAPI server with SSE endpoints
│       ├── orchestrator.py  # Multi-agent orchestration
│       ├── agents/          # Agent implementations
│       └── requirements.txt # Python dependencies
│
└── chakra_ui/
    ├── hooks/
    │   └── useSSE.ts        # SSE client hook
    ├── components/
    │   ├── CodeAssistant.tsx    # Code optimization UI
    │   └── DocumentAssistant.tsx # Document Q&A UI
    ├── .env.example         # Environment template
    └── package.json         # Node.js dependencies
```

## Troubleshooting

### CORS Errors
Ensure the backend CORS configuration allows requests from your frontend origin:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Backend Not Connecting
1. Check the backend is running: `curl http://localhost:8000/health`
2. Verify the frontend URL matches `.env.local`
3. Check browser console for connection errors

### SSE Not Working
1. Verify the `/process/stream` endpoint is accessible
2. Check network tab for SSE events
3. Ensure no proxy is blocking the connection

## Performance

- SSE provides low-latency updates (~100ms)
- Connection stays open during processing
- Automatic reconnection on connection loss
- Fallback to simulated responses if backend unavailable
