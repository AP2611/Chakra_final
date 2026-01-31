# Chakra - Multi-Agent AI System

<div align="center">

![Chakra Logo](chakra_ui/public/bg_removed.png)

**An intelligent multi-agent system with real-time streaming, analytics, and recursive learning capabilities**

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API Documentation](#-api-documentation) • [Configuration](#-configuration)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Frontend Modules](#-frontend-modules)
- [Analytics](#-analytics)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

---

## 🎯 Overview

Chakra is a sophisticated multi-agent AI system that leverages a recursive learning loop to generate, critique, improve, and learn from solutions. The system consists of four specialized agents working together to produce high-quality outputs for code generation, document assistance, and conversational AI tasks.

### Key Capabilities

- **Code Generation**: Generate, refine, and optimize code solutions
- **Document Assistance**: Answer questions using RAG (Retrieval-Augmented Generation)
- **Conversational AI**: Intelligent chatbot with context awareness
- **Real-time Streaming**: Server-Sent Events (SSE) for live token streaming
- **Analytics Dashboard**: Track performance metrics and improvements
- **Learning System**: Stores and retrieves successful solutions

---

## ✨ Features

### Core Features

- 🤖 **Multi-Agent Architecture**: Four specialized agents (Yantra, Sutra, Agni, Smriti)
- ⚡ **Real-time Streaming**: Tokens appear as they're generated (SSE)
- 🔄 **Recursive Learning**: Iterative improvement with quality scoring
- 📊 **Analytics Dashboard**: Real-time performance metrics and charts
- 💾 **Memory System**: Stores and retrieves successful solutions
- 📚 **RAG Support**: Document-based question answering
- 🎨 **Modern UI**: Beautiful 3D interface with particle effects
- ⚙️ **Fast Mode**: Optimized for low latency (3-5x faster)

### Performance Optimizations

- **Token Limits**: Configurable limits for faster responses
- **Parallel Processing**: RAG and memory retrieval run concurrently
- **Background Tasks**: Non-blocking analytics recording
- **Streaming**: Immediate token delivery for better UX
- **Fast Mode**: Optimized inference parameters

---

## 🏗️ Architecture

### Multi-Agent System

The system uses four specialized agents in a recursive learning loop:

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Yantra  │ --> │  Sutra   │ --> │  Agni   │ --> │ Smriti  │
│ Generate│     │ Critique │     │ Improve │     │  Learn  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     │               │               │               │
     └───────────────┴───────────────┴───────────────┘
                      │
                 ┌─────────┐
                 │Evaluator│
                 └─────────┘
```

#### Agents

1. **Yantra** (Generation Agent)
   - Produces initial solutions
   - Supports RAG and past examples
   - Streams tokens in real-time

2. **Sutra** (Critique Agent)
   - Analyzes solutions for issues
   - Identifies bugs, inefficiencies, and improvements
   - Provides detailed feedback

3. **Agni** (Improvement Agent)
   - Rewrites solutions addressing critiques
   - Optimizes code and responses
   - Ensures best practices

4. **Smriti** (Memory Agent)
   - Stores successful solutions
   - Retrieves similar past examples
   - Enables learning from experience

### System Flow

1. **Task Input** → User submits task via frontend
2. **Yantra** → Generates initial solution (streaming)
3. **Sutra** → Critiques the solution
4. **Agni** → Improves based on critique (streaming)
5. **Evaluator** → Scores the solution
6. **Iteration** → Repeats if improvement threshold not met
7. **Smriti** → Stores successful solutions
8. **Analytics** → Records metrics in Redis

---

## 🛠️ Tech Stack

### Backend

- **Python 3.13+**
- **FastAPI**: Modern async web framework
- **Ollama**: Local LLM inference (qwen2.5:1.5b)
- **Redis**: Analytics data storage
- **SQLite**: Memory/learning database
- **Server-Sent Events (SSE)**: Real-time streaming

### Frontend

- **Next.js 14**: React framework
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Styling
- **Three.js**: 3D graphics and animations
- **Framer Motion**: Animations
- **Recharts**: Analytics charts

### Infrastructure

- **Docker**: Redis and MySQL containers
- **Docker Compose**: Service orchestration

---

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- Docker & Docker Compose
- Ollama installed and running

### 1. Install Ollama

```bash
# Install Ollama from https://ollama.com
# Then pull the model:
ollama pull qwen2.5:1.5b

# Start Ollama (if not running as service):
ollama serve
```

### 2. Start Infrastructure

```bash
# Start Redis and MySQL
docker-compose up -d

# Verify services are running
docker ps
```

### 3. Setup Backend

```bash
cd Chakra/backend

# Install Python dependencies
pip install -r requirements.txt

# Run the API server
python api.py
```

The backend will be available at `http://localhost:8000`

### 4. Setup Frontend

```bash
cd chakra_ui

# Install Node.js dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

### 5. Verify Installation

```bash
# Check backend health
curl http://localhost:8000/health

# Check analytics
curl http://localhost:8000/analytics/metrics
```

---

## 📦 Installation

### Backend Dependencies

```bash
cd Chakra/backend
pip install -r requirements.txt
```

**Key Dependencies:**
- `fastapi==0.115.0` - Web framework
- `uvicorn[standard]==0.32.0` - ASGI server
- `httpx==0.27.2` - HTTP client
- `redis==5.0.1` - Redis client
- `pydantic==2.9.2` - Data validation

### Frontend Dependencies

```bash
cd chakra_ui
npm install
```

**Key Dependencies:**
- `next@14` - React framework
- `react@18` - UI library
- `three@0.160` - 3D graphics
- `framer-motion` - Animations
- `recharts` - Charts

---

## ⚙️ Configuration

### Backend Configuration

#### Orchestrator Settings (`orchestrator.py`)

```python
orchestrator = Orchestrator(
    ollama_url="http://localhost:11434",
    model="qwen2.5:1.5b",
    max_iterations=3,          # Max improvement iterations
    min_improvement=0.05,       # Minimum score improvement (5%)
    fast_mode=True              # Enable fast mode (3-5x faster)
)
```

#### Fast Mode vs Normal Mode

**Fast Mode** (Default):
- Token limit: 384 (code), 512 (chatbot)
- Temperature: 0.5
- Context: 1024 tokens
- **3-5x faster** with slightly lower quality

**Normal Mode**:
- Token limit: 640 (code), 1024 (chatbot)
- Temperature: 0.6
- Context: 2048 tokens
- **Better quality** with slower response

#### Environment Variables

```bash
# Redis Configuration
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0

# Ollama Configuration
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=qwen2.5:1.5b
```

### Frontend Configuration

Edit `chakra_ui/utils/api.ts` to change API URL:

```typescript
const API_URL = 'http://localhost:8000'
```

---

## 📡 API Documentation

### Base URL

```
http://localhost:8000
```

### Endpoints

#### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

#### Process Task (Non-Streaming)

```http
POST /process
Content-Type: application/json
```

**Request:**
```json
{
  "task": "Implement a Python function to calculate factorial",
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
  "iterations": [
    {
      "iteration": 1,
      "yantra_output": "...",
      "sutra_critique": "...",
      "agni_output": "...",
      "score": 0.75,
      "improvement": 0.0
    }
  ],
  "total_iterations": 2,
  "used_rag": false
}
```

#### Process Task (Streaming)

```http
POST /process-stream
Content-Type: application/json
Accept: text/event-stream
```

**Request:** Same as `/process`

**Response:** Server-Sent Events (SSE) stream with events:

- `start` - Processing started
- `token` - Token from initial generation
- `first_response_complete` - Initial generation done
- `improving_started` - Improvement phase started
- `improved_token` - Token from improved output
- `improved` - Improved output complete
- `iteration_complete` - Iteration finished
- `end` - All iterations complete
- `error` - Error occurred

**Example Event:**
```
data: {"type":"token","token":"def","iteration":1}

data: {"type":"improved","improved_output":"...","iteration":1}

data: {"type":"end","final_solution":"...","final_score":0.85}
```

### Analytics Endpoints

#### Get Metrics

```http
GET /analytics/metrics
```

**Response:**
```json
{
  "avg_improvement": 181.3,
  "avg_latency": 17.9,
  "avg_accuracy": 49.3,
  "avg_iterations": 1.0,
  "total_tasks": 94
}
```

#### Get Quality Improvement Data

```http
GET /analytics/quality-improvement?limit=20
```

#### Get Performance History

```http
GET /analytics/performance-history?hours=24
```

#### Get Recent Tasks

```http
GET /analytics/recent-tasks?limit=10
```

---

## 🎨 Frontend Modules

### Code Assistant

- **Purpose**: Generate and refine code solutions
- **Features**:
  - Real-time code streaming
  - First generation + refined output
  - Code syntax highlighting
  - Iteration tracking

**Usage:**
1. Enter your coding task
2. Watch first generation stream in
3. See refined/improved version appear
4. Compare both outputs

### Chatbot

- **Purpose**: Conversational AI assistant
- **Features**:
  - Real-time message streaming
  - Context-aware responses
  - Iteration and token tracking
  - Error handling

**Usage:**
1. Type your question
2. Receive streaming response
3. Continue conversation

### Document Assistant

- **Purpose**: Answer questions using documents (RAG)
- **Features**:
  - Document-based Q&A
  - RAG retrieval
  - Context grounding
  - Answer history

**Usage:**
1. Enable RAG mode
2. Ask questions about documents
3. Get grounded answers

### Analytics Dashboard

- **Purpose**: View system performance metrics
- **Features**:
  - Real-time metrics (updates every 3s)
  - Quality improvement charts
  - Performance history
  - Recent tasks list

---

## 📊 Analytics

The system tracks comprehensive analytics in Redis:

### Metrics Tracked

- **Initial Score**: Yantra's output quality
- **Final Score**: Agni's improved output quality
- **Improvement**: Score difference and percentage
- **Latency**: Task completion time
- **Iterations**: Number of improvement cycles
- **Task Type**: Code vs Document

### Data Storage

- **Redis**: Fast analytics storage
- **SQLite**: Memory/learning database
- **Automatic Cleanup**: Keeps last 100 tasks

### Dashboard

Access at: `http://localhost:3000` (Analytics tab)

- Real-time metrics cards
- Quality improvement charts
- Performance history graphs
- Recent tasks table

---

## 💻 Development

### Project Structure

```
chakra_full/
├── Chakra/
│   └── backend/
│       ├── agents/          # Agent implementations
│       ├── analytics/        # Analytics tracker
│       ├── evaluation/       # Solution evaluator
│       ├── rag/             # RAG retriever
│       ├── utils/           # Utilities (background tasks)
│       ├── api.py           # FastAPI server
│       └── orchestrator.py  # Agent orchestrator
├── chakra_ui/              # Next.js frontend
│   ├── app/                # Next.js app router
│   ├── components/        # React components
│   ├── utils/              # Utilities (API client)
│   └── hooks/              # React hooks
├── docker-compose.yml      # Docker services
└── README.md              # This file
```

### Running Tests

```bash
# Backend agent tests
cd Chakra/backend
python test_agents_comprehensive.py

# Frontend-backend connection test
cd /Users/arjunpanse/Desktop/chakra_full
python test_frontend_backend_connection.py

# Simple diagnostic test
python test_simple_diagnostic.py
```

### Development Mode

**Backend:**
```bash
cd Chakra/backend
python api.py
# Or with auto-reload:
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd chakra_ui
npm run dev
```

### Code Style

- **Backend**: Follows PEP 8 Python style guide
- **Frontend**: TypeScript with ESLint
- **Formatting**: Prettier for frontend

---

## 🔧 Troubleshooting

### Common Issues

#### Backend Not Starting

**Issue**: Port 8000 already in use

**Solution:**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn api:app --port 8001
```

#### Ollama Connection Error

**Issue**: `Connection refused` to Ollama

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve
```

#### Redis Connection Error

**Issue**: Analytics not working, Redis connection failed

**Solution:**
```bash
# Check if Redis is running
docker ps | grep redis

# Start Redis
docker-compose up -d redis

# Verify connection
redis-cli ping
```

#### Frontend Not Connecting to Backend

**Issue**: CORS errors or connection refused

**Solution:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check CORS settings in `api.py`
3. Verify API URL in `chakra_ui/utils/api.ts`

#### Stale Cache Issues

**Issue**: Old code behavior, `job_manager` errors

**Solution:**
```bash
# Clear Python cache
find Chakra/backend -type d -name "__pycache__" -exec rm -rf {} +
find Chakra/backend -name "*.pyc" -delete

# Restart backend
```

**Note**: Bytecode caching is disabled by default in `api.py` to prevent stale cache issues.

### Debug Mode

Enable verbose logging:

```python
# In api.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Logs

**Backend:**
```bash
tail -f /tmp/backend_test.log
```

**Frontend:**
- Open browser DevTools → Console
- Check Network tab for API calls

---

## 🧪 Testing

### Test Files

- `test_simple_diagnostic.py` - Quick diagnostic test
- `test_capture_errors.py` - Error capture test
- `test_code_assistant_output_change.py` - Code assistant test
- `test_chatbot_token_limit.py` - Chatbot token limit test
- `test_frontend_backend_connection.py` - Integration test

### Running Tests

```bash
# Quick test
python3 test_simple_diagnostic.py

# All tests
for test in test_*.py; do
    python3 $test
done
```

---

## 📝 Configuration Details

### Token Limits

| Mode | Code Tasks | Chatbot Tasks |
|------|-----------|---------------|
| Fast | 384 tokens | 512 tokens |
| Normal | 640 tokens | 1024 tokens |

### Inference Parameters

**Fast Mode:**
- `num_predict`: 384
- `temperature`: 0.5
- `top_p`: 0.7
- `top_k`: 20
- `num_ctx`: 1024

**Normal Mode:**
- `num_predict`: 640
- `temperature`: 0.6
- `top_p`: 0.8
- `top_k`: 30
- `num_ctx`: 2048

### Iteration Settings

- **Max Iterations**: 3 (default)
- **Min Improvement**: 0.05 (5% default)
- **Stops early** if improvement threshold not met

---

## 🚀 Performance

### Expected Performance

**Fast Mode:**
- First token: 0.5-2 seconds
- Token streaming: 50+ tokens/sec
- Full response (384 tokens): 4-10 seconds

**Normal Mode:**
- First token: 1-3 seconds
- Token streaming: 40+ tokens/sec
- Full response (640 tokens): 8-15 seconds

### Optimization Features

- ✅ Parallel RAG and memory retrieval
- ✅ Background analytics (non-blocking)
- ✅ Real-time token streaming
- ✅ Optimized inference parameters
- ✅ Fast mode for low latency

---

## 🤝 Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

### Code Guidelines

- Follow existing code style
- Add tests for new features
- Update documentation
- Ensure all tests pass

---

## 📄 License

[Add your license here]

---

## 🙏 Acknowledgments

- **Ollama** - Local LLM inference
- **FastAPI** - Modern Python web framework
- **Next.js** - React framework
- **Three.js** - 3D graphics library

---

## 📞 Support

For issues, questions, or contributions:

- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section

---

## 🔄 Changelog

### Recent Updates

- ✅ Disabled Python bytecode caching (prevents stale cache issues)
- ✅ Implemented background task manager (replaces job_manager)
- ✅ Fixed token routing in frontend
- ✅ Improved error handling
- ✅ Enhanced analytics dashboard
- ✅ Optimized for low latency (fast mode)

---

<div align="center">

**Built with ❤️ using multi-agent AI**

[Back to Top](#-chakra---multi-agent-ai-system)

</div>

