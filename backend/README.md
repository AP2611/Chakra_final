# Agent System Backend

Multi-agent system with recursive learning capabilities using Ollama.

## Architecture

The system consists of four specialized agents:

- **Yantra** - Generation Agent: Produces initial solutions
- **Sutra** - Critique Agent: Analyzes and finds issues
- **Agni** - Improvement Agent: Rewrites solutions fixing issues
- **Smriti** - Memory Agent: Stores and retrieves learning experiences

## Setup

### Prerequisites

1. **Install Ollama**: https://ollama.com
2. **Pull the model**:
   ```bash
   ollama pull qwen2.5:1.5b
   ```
3. **Start Ollama** (if not running as a service):
   ```bash
   ollama serve
   ```

### Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Run the API Server

```bash
python api.py
```

Or using uvicorn directly:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### POST `/process`

Process a task through the agent system.

**Request Body:**
```json
{
  "task": "Create a React hook for managing paginated API data",
  "context": "Optional additional context",
  "use_rag": false,
  "is_code": true
}
```

**Response:**
```json
{
  "task": "...",
  "final_solution": "...",
  "final_score": 0.85,
  "iterations": [...],
  "total_iterations": 2,
  "used_rag": false,
  "rag_chunks": null
}
```

### GET `/health`

Health check endpoint.

## Configuration

Edit `orchestrator.py` to adjust:
- `max_iterations`: Maximum number of improvement iterations (default: 3)
- `min_improvement`: Minimum score improvement to continue (default: 0.05)

Edit agent classes to customize prompts or model settings.

## Data Storage

- **Memory**: SQLite database at `backend/data/memory.db`
- **Documents**: Text files in `backend/data/documents/` (for RAG)

## Development

The system uses async/await for all agent calls. Each agent is independent and can be tested separately.

To test an agent directly:

```python
from agents import Yantra

async def test():
    yantra = Yantra()
    result = await yantra.process(task="Your task here")
    print(result)

import asyncio
asyncio.run(test())
```

