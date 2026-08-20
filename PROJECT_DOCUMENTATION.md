# Chakra: Multi-Agent AI System — Complete Project Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Backend Implementation](#3-backend-implementation)
4. [Agent Deep Dive](#4-agent-deep-dive)
5. [RAG System](#5-rag-system)
6. [Evaluation Framework](#6-evaluation-framework)
7. [Analytics & Observability](#7-analytics--observability)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Experiment Harness](#9-experiment-harness)
10. [Data Flow & Control Flow](#10-data-flow--control-flow)
11. [Configuration & Deployment](#11-configuration--deployment)
12. [Key Design Decisions & Trade-offs](#12-key-design-decisions--trade-offs)

---

## 1. Project Overview

**Chakra** is a sophisticated multi-agent AI system that leverages a recursive learning loop to generate, critique, improve, and learn from solutions. The system is designed for three primary use cases:

- **Code Generation**: Generate, refine, and optimize code solutions with real-time streaming
- **Document Assistance**: Answer questions using RAG (Retrieval-Augmented Generation)
- **Conversational AI**: Intelligent chatbot with context awareness and iterative improvement

### Core Innovation

The system's key innovation is its **recursive critique-improve loop** with **decoupled evaluation**:

1. A generator agent produces an initial solution
2. A critic agent analyzes the solution and provides structured scoring
3. An improver agent applies surgical fixes based on the critique
4. The loop repeats until convergence or a maximum iteration count
5. An **independent judge** (separate from the loop) scores the final solution to avoid circular evaluation
6. A memory agent stores successful solutions for future retrieval

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.13+, FastAPI, Uvicorn |
| **LLM Inference** | Ollama (local LLM serving) |
| **Models** | `qwen2.5:1.5b` (generator), `mistral:latest` (critic/judge) |
| **Analytics** | Redis (time-series metrics storage) |
| **Memory** | SQLite (persistent solution storage) |
| **RAG** | TF-IDF (default) or ChromaDB + sentence-transformers (optional) |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS |
| **3D/Animation** | Three.js, Framer Motion |
| **Charts** | Recharts |
| **Infrastructure** | Docker Compose (Redis, MySQL) |

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐ │
│  │ CodeAssistant│ │ Chatbot      │ │ Document     │ │ Analytics │ │
│  │              │ │              │ │ Assistant    │ │ Dashboard │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────┬─────┘ │
│         │                │                │                │       │
│         └────────────────┴────────────────┴────────────────┘       │
│                              │                                      │
│                    SSE Streaming (text/event-stream)                │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                    Backend (FastAPI)                                │
│  ┌───────────────────────────▼───────────────────────────────────┐ │
│  │                      API Layer (api.py)                        │ │
│  │  • /process (non-streaming)                                    │ │
│  │  • /process-stream (SSE streaming)                             │ │
│  │  • /analytics/* (metrics endpoints)                            │ │
│  │  • /rag/upload (document ingestion)                            │ │
│  └───────────────────────────┬───────────────────────────────────┘ │
│                              │                                      │
│  ┌───────────────────────────▼───────────────────────────────────┐ │
│  │                   Orchestrator (orchestrator.py)                │ │
│  │  • Manages recursive learning loop                             │ │
│  │  • Coordinates agents                                          │ │
│  │  • Handles RAG + memory retrieval in parallel                  │ │
│  │  • Controls stopping conditions                                │ │
│  └───────────────────────────┬───────────────────────────────────┘ │
│                              │                                      │
│  ┌─────────────┐  ┌──────────┴──────────┐  ┌───────────────────┐  │
│  │   Yantra    │  │       Sutra        │  │       Agni        │  │
│  │ (Generator) │  │     (Critic)       │  │    (Improver)     │  │
│  └─────────────┘  └────────────────────┘  └───────────────────┘  │
│                                                                     │
│  ┌─────────────┐  ┌────────────────────┐  ┌─────────────────────┐ │
│  │   Smriti    │  │   RAG Retriever    │  │   Code Executor     │ │
│  │  (Memory)   │  │  (Vector/TF-IDF)   │  │  (Validation)       │ │
│  └─────────────┘  └────────────────────┘  └─────────────────────┘ │
│                                                                     │
│  ┌────────────────────┐  ┌───────────────────────────────────────┐ │
│  │ Analytics Tracker  │  │        Evaluation Layer              │ │
│  │     (Redis)        │  │  ┌─────────────┐ ┌─────────────────┐ │ │
│  └────────────────────┘  │  │   Judge     │ │   Objective     │ │ │
│                           │  │ (LLM-based) │ │ (Execution)     │ │ │
│                           │  └─────────────┘ └─────────────────┘ │ │
│                           └───────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │   Ollama Server  │
                    │  (Local LLMs)    │
                    └──────────────────┘
```

### Agent Pipeline Flow

```
User Task
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PARALLEL RETRIEVAL PHASE                          │
│  ┌─────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ RAG Retriever   │  │ Smriti (Memory)                          │  │
│  │ (if use_rag)    │  │ Retrieve similar past solutions          │  │
│  └────────┬────────┘  └────────────────┬─────────────────────────┘  │
└───────────┼─────────────────────────────┼───────────────────────────┘
            │                             │
            ▼                             ▼
   rag_chunks[]                  past_examples[]
            │                             │
            └─────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ITERATION LOOP (max_iterations)                   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Step 1: YANTRA (Generation)                                  │  │
│  │ • Build prompt with task + RAG chunks + past examples        │  │
│  │ • Stream tokens via Ollama                                    │  │
│  │ • Yield SSE events: token, first_response_complete           │  │
│  │ • Optional: execute code for validation                       │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │ current_solution                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Step 2: SUTRA (Critique)                                     │  │
│  │ • Analyze solution against rubric                             │  │
│  │ • Return structured scores (1-10 per dimension)               │  │
│  │ • Compute composite score with weights                         │  │
│  │ • Apply score smoothing to prevent jitter                      │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │ composite_score                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Step 3: AGNI (Improvement)                                   │  │
│  │ • Apply surgical fixes from critique                          │  │
│  │ • Prioritize execution failures                                │  │
│  │ • Return improved solution                                     │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │ improved_solution                       │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Step 4: STOPPING CONDITIONS                                   │  │
│  │ • Check improvement vs min_improvement threshold               │  │
│  │ • Check for score degradation                                   │  │
│  │ • Break if converged, else continue to next iteration           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    POST-LOOP PHASE                                   │
│  • Store best solution in Smriti (if score > 6.0)                   │
│  • Record analytics in Redis (non-blocking)                          │
│  • Return final result with all iterations                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Implementation

### 3.1 API Layer (`backend/api.py`)

The FastAPI application serves as the entry point for all frontend requests.

**Key Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/process` | POST | Non-streaming task processing |
| `/process-stream` | POST | SSE streaming task processing |
| `/process/stream` | POST | Legacy streaming endpoint |
| `/analytics/metrics` | GET | Overall performance metrics |
| `/analytics/quality-improvement` | GET | Quality improvement chart data |
| `/analytics/performance-history` | GET | Time-series performance data |
| `/analytics/recent-tasks` | GET | Recent task history |
| `/rag/upload` | POST | Document upload for RAG |

**SSE Streaming Implementation:**

The streaming endpoint (`/process-stream`) wraps the orchestrator's `process_stream` generator into Server-Sent Events. Key implementation details:

- Uses `StreamingResponse` with `text/event-stream` media type
- Sets `Cache-Control: no-cache` and `Connection: keep-alive` headers
- Each event is formatted as `data: {json}\n\n`
- Analytics recording happens asynchronously when the `end` event is received
- Error events are yielded for any exceptions during processing

**CORS Configuration:**

The API allows connections from multiple local development ports (3000, 5173, 8080, 8081) to support different frontend development setups.

### 3.2 Orchestrator (`backend/orchestrator.py`)

The `Orchestrator` class is the central coordinator that manages the entire multi-agent pipeline.

**Initialization Parameters:**

```python
Orchestrator(
    ollama_url="http://localhost:11434",
    model="qwen2.5:1.5b",           # Default model
    generator_model=None,            # Optional separate model for Yantra
    critic_model=None,               # Optional separate model for Sutra/Agni
    max_iterations=3,                # Maximum improvement iterations
    min_improvement=0.5,             # Minimum score improvement (1-10 scale)
    fast_mode=True                   # Enable low-latency mode
)
```

**Key Design Decisions:**

1. **Model Splitting**: The orchestrator supports using different models for generation vs. critique/improvement. This creates "headroom" for the critique loop to demonstrate measurable gains — a weaker generator produces solutions that a stronger critic can meaningfully improve.

2. **Lazy RAG Loading**: The RAG retriever is loaded lazily (only when `use_rag=True`) to avoid heavy imports at startup. If vector dependencies are unavailable, it falls back to a lightweight TF-IDF retriever.

3. **Single Source of Truth**: Both streaming and non-streaming paths delegate to `process_stream()`, ensuring identical logic for fixes, recovery, and validation.

4. **Parallel Retrieval**: RAG and memory retrieval run concurrently using `asyncio.create_task()` and `asyncio.to_thread()` to minimize latency.

**Processing Modes:**

| Mode | Pipeline | Purpose |
|------|----------|---------|
| `full` | Yantra → Sutra → Agni | Complete recursive loop |
| `agni_only` | Yantra → Agni (generic prompt) | Measure Agni's contribution without Sutra's critique |
| `sutra_only` | Yantra → Sutra (no Agni) | Measure Sutra's scoring without improvement |

### 3.3 Base Agent (`backend/agents/base_agent.py`)

The `BaseAgent` abstract class provides common functionality for all agents.

**Ollama Communication:**

Two methods for calling Ollama:
- `_call_ollama()`: Non-streaming, returns complete response
- `_call_ollama_stream()`: Streaming, yields tokens as they arrive

Both methods include:
- Retry logic (3 attempts with exponential backoff)
- Token accounting (prompt_tokens, completion_tokens, total)
- Configurable inference parameters
- Error handling for Ollama API failures

**Fast Mode vs Normal Mode:**

| Parameter | Fast Mode | Normal Mode |
|-----------|-----------|-------------|
| `num_predict` | 384 (code) / 512 (chat) | 640 (code) / 1024 (chat) |
| `temperature` | 0.5 | 0.6 |
| `top_p` | 0.7 | 0.8 |
| `top_k` | 20 | 30 |
| `num_ctx` | 1024 | 2048 |

Fast mode achieves 3-5x faster response times with slightly lower quality.

**Streaming Implementation Details:**

The `_call_ollama_stream()` method handles both SSE format (`data: {...}`) and NDJSON format (direct JSON lines) from Ollama. It:
- Buffers incoming bytes and processes complete lines
- Yields tokens immediately for low latency
- Accounts for tokens on the final `done` chunk
- Handles `GeneratorExit` cleanly for client disconnections

---

## 4. Agent Deep Dive

### 4.1 Yantra — Generation Agent

**File:** `backend/agents/yantra.py`

**Role:** Produces initial solutions to user tasks.

**System Prompt:**
```
You are Yantra, an expert problem solver. Produce clear, correct, and efficient
solutions following best practices. Be precise and thorough in your responses.
```

**Input Assembly:**
The user prompt is constructed from multiple optional components:
1. **Task**: The core user request
2. **RAG Chunks**: Relevant document context (if `use_rag=True`)
3. **Past Examples**: Successful solutions from Smriti (if available)
4. **Additional Context**: User-provided context

**Output:** Returns a dictionary with:
- `agent`: "Yantra"
- `output`: The generated solution text
- `task`: Original task
- `used_rag`: Whether RAG was used
- `used_examples`: Whether past examples were used

**Special Behavior:**
- When RAG is enabled, Yantra is instructed to base answers ONLY on provided document context
- Past examples are included only on the first iteration to avoid biasing subsequent improvements

### 4.2 Sutra — Critique Agent

**File:** `backend/agents/sutra.py`

**Role:** Analyzes solutions for issues and provides structured scoring.

**Scoring Rubric:**

Sutra evaluates solutions across multiple dimensions on a 1-10 scale:

| Dimension | Weight (with RAG) | Weight (no RAG) | Description |
|-----------|-------------------|-----------------|-------------|
| correctness | 0.35 | 0.45 | Does it solve the task correctly? |
| groundedness | 0.20 | N/A | Are claims supported by documents? |
| accuracy | 0.15 | 0.25 | Are factual/technical claims correct? |
| efficiency | 0.10 | 0.10 | Computational and resource efficiency |
| clarity | 0.10 | 0.10 | Readability and structure |
| edge_case_coverage | 0.10 | 0.10 | Handling of boundary inputs |

**Anchor Scale:**
- 1-2: Critical failure
- 3-4: Major issues
- 5-6: Usable with caveats
- 7-8: Solid with minor issues
- 9-10: Excellent, no meaningful issues

**Composite Score Calculation:**

```python
raw_composite = sum(score_dimension * weight_dimension)
```

**Score Smoothing:**

To prevent score jitter between iterations, Sutra applies smoothing:
- If the score delta is ≤ 1.5, the raw score is used
- If the delta > 1.5 and the critique contains critical keywords ("critical", "breaking", "severe", "unsafe", "data loss"), the raw score is used
- Otherwise, the score is clamped to ±1.5 from the previous score

**JSON Parsing Robustness:**

Sutra's output parsing is highly robust to handle LLM formatting issues:
1. Strip markdown code fences
2. Try greedy regex extraction
3. Try balanced-brace scanner
4. Sanitize control characters
5. Reconstruct minimal JSON from any found scores

This robustness reduced parsing failures from ~21% to near-zero.

**Retry Logic:**

All Sutra calls retry up to 3 times on API or parsing failures, using a lower temperature (0.3) for more deterministic scoring.

### 4.3 Agni — Improvement Agent

**File:** `backend/agents/agni.py`

**Role:** Rewrites solutions addressing all identified issues with minimal, surgical changes.

**System Prompt:**
```
You are Agni, an expert optimizer. You improve a solution by applying ONLY the
specific fixes identified in the critique. Preserve everything that is already
correct and good — do NOT rewrite the whole solution from scratch unless it is
fundamentally broken. Produce clean, correct, and efficient code or answers.
```

**Input Assembly:**
1. **Original Task**: The user's request
2. **Original Output**: The solution to improve
3. **Critique**: Sutra's identified issues
4. **Execution Validation**: If code execution failed, the error is prominently displayed
5. **Document Context**: RAG chunks (if available)

**Priority Order for Fixes:**
1. **Correctness**: Fix all bugs and errors (especially execution failures)
2. **Performance**: Optimize only where critique indicates
3. **Clarity**: Keep logic clear; don't restructure working code
4. **Grounding**: Ensure claims are supported by documents

**Mode-Dependent Behavior:**
- In `full` mode: Uses Sutra's critique to steer improvement
- In `agni_only` mode: Uses a generic improvement prompt (critique not used for steering, but Sutra still scores for measurement)

**Output:** Returns a dictionary with:
- `agent`: "Agni"
- `improved_output`: The refined solution
- `original_output`: The input solution
- `critique`: The critique applied
- `task`: Original task

### 4.4 Smriti — Memory Agent

**File:** `backend/agents/smriti.py`

**Role:** Stores and retrieves successful solutions for learning from experience.

**Storage:** SQLite database at `backend/data/memory.db`

**Schema:**
```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_hash TEXT UNIQUE NOT NULL,      -- MD5 hash for deduplication
    task TEXT NOT NULL,                   -- Original task text
    task_embedding TEXT,                  -- Optional embedding (JSON)
    solution TEXT NOT NULL,               -- The solution
    quality_score REAL NOT NULL,          -- 0.0-1.0 quality score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT                         -- JSON metadata
)
```

**Key Operations:**

1. **Store**: Stores a solution with quality score. Only updates if the new score is better than the existing one.

2. **Retrieve Similar**: Finds past solutions using Jaccard similarity on word sets:
   - Tokenizes both the query and stored tasks
   - Computes Jaccard similarity (intersection / union)
   - Filters by minimum similarity threshold (0.2)
   - Returns top results sorted by similarity and quality score

3. **Get Best Examples**: Returns the highest-quality solutions regardless of similarity.

**Deduplication:** Uses MD5 hash of the task text to prevent duplicate entries.

### 4.5 Agent Interaction Summary

| Agent | Input | Output | Purpose |
|-------|-------|--------|---------|
| Yantra | task, context, rag_chunks, past_examples | solution_text | Generate initial solution |
| Sutra | yantra_output, original_task, rag_chunks, previous_score, exec_result | SutraOutput(critique, scores, composite_score) | Critique and score |
| Agni | original_output, critique, task, rag_chunks, exec_result | improved_output | Apply fixes |
| Smriti | task, solution, quality_score | None (storage) | Persist learning |

---

## 5. RAG System

### 5.1 Architecture

The RAG system has two implementations with automatic fallback:

```
VectorRAGRetriever
    │
    ├─── If CHAKRA_USE_VECTOR_RAG=1 and deps available
    │         │
    │         ▼
    │   ┌─────────────────────────────────────┐
    │   │  sentence-transformers (embeddings) │
    │   │  ChromaDB (vector storage)          │
    │   │  all-MiniLM-L6-v2 model            │
    │   └─────────────────────────────────────┘
    │
    └─── Otherwise (default)
              │
              ▼
        ┌─────────────────────┐
        │ SimpleTfidfRetriever │
        │ (pure numpy TF-IDF)  │
        └─────────────────────┘
```

### 5.2 VectorRAGRetriever (`backend/rag/vector_retriever.py`)

**Lazy Dependency Loading:**

Heavy dependencies (`sentence-transformers`, `chromadb`) are imported lazily inside `__init__`. If they fail to load (including segfaults), the system falls back to TF-IDF. The vector path is opt-in via `CHAKRA_USE_VECTOR_RAG=1`.

**Document Chunking:**

Text is split into chunks with overlap:
- Default chunk size: 500 words
- Overlap: 50 words
- Splits on paragraph boundaries first, then on word boundaries for oversized paragraphs

**Vector Path:**
- Embedding model: `all-MiniLM-L6-v2`
- Vector database: ChromaDB with cosine similarity
- Persistent storage in `backend/data/documents/chroma_db/`

**TF-IDF Fallback (`SimpleTfidfRetriever`):**

A pure-numpy implementation that:
- Builds a vocabulary from all document chunks
- Computes TF-IDF vectors for each chunk
- Uses cosine similarity for retrieval
- Never requires external dependencies beyond numpy

### 5.3 Document Parser (`backend/rag/document_parser.py`)

Supports parsing:
- **Plain text** (.txt): Direct UTF-8 decoding
- **PDF** (.pdf): Uses PyPDF2 for text extraction

### 5.4 Document Upload Flow

1. Frontend sends file via multipart upload to `/rag/upload`
2. Backend parses file content using `DocumentParser`
3. Content is added to the RAG retriever (vector or TF-IDF)
4. Success response includes chunk count

---

## 6. Evaluation Framework

### 6.1 In-Loop Scoring (Sutra)

Sutra provides scores during the loop to **steer** improvement. These scores are:
- Used for stopping conditions
- Tracked for within-loop improvement analysis
- NOT used as the final measurement (to avoid circularity)

### 6.2 Independent Judge (`backend/evaluation/judge.py`)

**Purpose:** Provides a decoupled, fixed-rubric assessment of final solutions.

**Design Principles:**
- Separate model instance from the loop
- Frozen rubric with anchor scale
- Applied identically to all systems (baselines and loop)
- Lower temperature (0.2) for deterministic scoring

**Scoring Dimensions:** Same as Sutra (correctness, accuracy, efficiency, clarity, edge_case_coverage, groundedness)

**Retry Logic:** 3 attempts on API/parse failures.

### 6.3 Objective Metrics (`backend/evaluation/objective.py`)

**Purpose:** Provides model-agnostic, execution-based quality signals.

**Primary Metric:** Execution success rate — does the generated code run without error?

**Implementation:**
- Extracts code from solution (fenced code blocks)
- Writes to temporary file
- Executes in isolated subprocess with timeout
- Returns success/failure with stdout/stderr

**Optional:** Reference test cases can be appended to verify correctness beyond just running without error.

### 6.4 Evaluator (`backend/evaluation/evaluator.py`)

A simpler heuristic-based evaluator used for quick assessments:
- Checks for code structure (functions, classes)
- Checks for best practices (comments, docstrings, error handling, type hints)
- Checks for imports
- Computes weighted quality scores

---

## 7. Analytics & Observability

### 7.1 Analytics Tracker (`backend/analytics/tracker.py`)

**Storage:** Redis with the following key structure:

| Key Pattern | Type | Purpose |
|-------------|------|---------|
| `analytics:task_counter` | Counter | Auto-incrementing task ID |
| `analytics:task:{id}` | Hash | Task record (score, time, iterations, etc.) |
| `analytics:task_ids` | Sorted Set | Task IDs ordered by timestamp |
| `analytics:iteration:{task_id}:{n}` | Hash | Per-iteration metrics |
| `analytics:task:{id}:iterations` | Set | Iteration numbers for a task |

**Recorded Metrics:**

Per task:
- `initial_score`: Yantra's first output score
- `final_score`: Agni's final output score
- `improvement`: Score difference
- `improvement_percent`: Percentage improvement
- `iterations`: Number of iterations run
- `duration_ms`: Total processing time
- `task_type`: "code" or "document"
- `timestamp`: ISO format timestamp

Per iteration:
- `score`: Composite score at this iteration
- `improvement`: Score change from previous iteration

**Cleanup:** Automatically keeps only the last 100 tasks to prevent unbounded growth.

**Background Recording:**

Analytics recording is non-blocking. The API uses `run_background_task()` to record metrics after response delivery, ensuring the streaming response isn't delayed.

### 7.2 Metrics Endpoints

| Endpoint | Returns |
|----------|---------|
| `/analytics/metrics` | Average improvement, latency, accuracy, iterations, total tasks |
| `/analytics/quality-improvement` | Before/after scores for charting |
| `/analytics/performance-history` | Time-series latency and accuracy |
| `/analytics/recent-tasks` | Recent task list with relative timestamps |

---

## 8. Frontend Architecture

### 8.1 Application Structure

```
chakra_ui/
├── app/
│   ├── layout.tsx          # Root layout with theme provider
│   ├── page.tsx            # Main page with navigation
│   └── globals.css         # Global styles with CSS variables
├── components/
│   ├── Chakra3DScene.tsx   # Three.js 3D background
│   ├── ParticleSystem.tsx  # Animated particle effects
│   ├── CodeAssistant.tsx   # Code generation interface
│   ├── Chatbot.tsx         # Conversational AI interface
│   ├── DocumentAssistant.tsx # RAG-based document Q&A
│   ├── Analytics.tsx       # Performance dashboard
│   └── Settings.tsx        # Configuration panel
├── context/
│   └── ThemeContext.tsx     # Dark/light theme management
├── hooks/
│   └── useSSE.ts           # Custom SSE hook (legacy)
├── utils/
│   └── api.ts              # API client with SSE streaming
└── public/                 # Static assets
```

### 8.2 SSE Streaming Client (`chakra_ui/utils/api.ts`)

The `streamSSE()` function handles real-time communication with the backend:

**Key Features:**
- Health check before streaming
- Token batching for smooth UI updates (configurable batch size and interval)
- Phase-aware token routing (prevents improvement tokens from mixing with initial generation)
- Event dispatching for state changes
- Error handling with user-friendly messages

**Token Routing Logic:**

```typescript
if (data.type === 'token') {
    // Initial generation tokens → onToken callback
    tokenBuffer += data.token
} else if (data.type === 'improved_token') {
    // Improvement tokens → onEvent callback only (NOT onToken)
    // This prevents improved tokens from going to firstGeneratedCode
    callbacks.onEvent?.(data)
}
```

### 8.3 Code Assistant Component

**State Management:**
- `firstGeneratedCode`: Yantra's initial output (streamed via `token` events)
- `refinedCode`: Agni's improved output (streamed via `improved_token` events)
- `iterations`: Array of iteration data with scores
- `progress`: Visual progress indicator
- `currentStep`: Human-readable status message

**Phase Tracking:**
Uses `isInImprovementPhase` flag to route tokens correctly:
- Before `improving_started` event: tokens go to `firstGeneratedCode`
- After `improving_started` event: tokens go to `refinedCode`

### 8.4 Chatbot Component

Similar streaming architecture but for conversational AI:
- Maintains message history
- Streams assistant responses token-by-token
- Tracks iterations and token counts per message
- Supports aborting in-progress requests

### 8.5 Document Assistant Component

**Features:**
- Drag-and-drop file upload
- Document list management (load, delete)
- RAG-enabled Q&A with streaming answers
- Answer history with original/refined outputs
- Source citation display

### 8.6 Analytics Dashboard

**Real-time Updates:**
- Fetches metrics every 3 seconds
- Displays metric cards with trend indicators
- Renders charts using Recharts:
  - Quality improvement bar chart
  - Performance history line chart
  - Recent tasks table

---

## 9. Experiment Harness

### 9.1 Purpose

`run_experiment.py` is a comprehensive evaluation framework designed for academic publication. It addresses three key methodological issues:

1. **Fair Baselines**: Compares against both weak and strong single-pass baselines
2. **Decoupled Evaluation**: Uses independent judge + objective metrics
3. **Robustness**: Tolerant parsing and retry logic

### 9.2 Configuration

```python
EXPERIMENT_CONFIG = {
    "model": "mistral:latest",            # Default/critic fallback
    "generator_model": "qwen2.5:1.5b",    # Weak drafter
    "critic_model": "mistral:latest",     # Strong critic + improver
    "judge_model": "mistral:latest",      # Independent evaluator
    "ollama_url": "http://localhost:11434",
    "max_iterations": 3,
    "min_improvement": 0.5,
    "fast_mode": False,                   # Normal mode for quality
    "output_dir": "experiment_results",
    "seeds": [42],
    "use_rag": False,
    "resume": True,
    "ablation_modes": ["full", "agni_only", "sutra_only"],
}
```

### 9.3 Task Suite

Tasks span five categories:

| Category | Count | Description |
|----------|-------|-------------|
| `code_algorithms` | 13 | Prime checking, linked lists, Kadane's, binary search, DFS, etc. |
| `code_optimization` | 4 | Performance optimization, refactoring, error handling |
| `math_reasoning` | 5 | Algebra, calculus, physics, finance |
| `text_generation` | 4 | Explanations, summaries, comparisons |
| `document_qa` | 4 | Questions about Chakra's own documentation (RAG) |

Harder tasks (thread-safe queue, O(log n) Fibonacci, running median) are included to provide genuine headroom for the loop.

### 9.4 Evaluation Protocol

For each task and seed:

1. **Retrieve RAG chunks** (if enabled) — shared across all conditions for fairness
2. **Run weak baseline**: Single-pass with small model
3. **Run strong baseline**: Single-pass with strong model
4. **Run multi-agent ablations**: `full`, `agni_only`, `sutra_only`
5. **Score all solutions** with independent judge
6. **Run objective evaluation** (execution test) for code tasks

### 9.5 Statistical Analysis

Performs:
- One-sample t-test for within-loop improvement (H₀: mean = 0)
- Paired t-test for multi-agent vs. strong baseline
- Wilcoxon signed-rank test (for n ≥ 6)
- Cohen's d effect size
- 95% confidence intervals

### 9.6 Publication-Quality Plots

| Plot | File | Description |
|------|------|-------------|
| Score Progression | `score_progression.pdf/png` | Per-task and mean score over iterations |
| Improvement Distribution | `improvement_distribution.pdf/png` | Histogram and box plot by category |
| Time vs Quality | `time_vs_quality.pdf/png` | Scatter plot with iteration coloring |
| Dimension Radar | `dimension_radar.pdf/png` | Polar chart of average dimension scores |
| Baseline Comparison | `baseline_comparison.pdf/png` | Grouped bar chart of judge scores |

---

## 10. Data Flow & Control Flow

### 10.1 Complete Request Flow

```
1. Frontend sends POST /process-stream with task JSON
   │
2. API creates async generator from orchestrator.process_stream()
   │
3. Orchestrator begins parallel retrieval:
   │   ├── asyncio.create_task(rag.retrieve(task, 3))  [if use_rag]
   │   └── asyncio.create_task(smriti.retrieve_similar(task, 3))
   │
4. Orchestrator yields "start" event
   │
5. For each iteration (up to max_iterations):
   │   │
   │   ├── Yantra generates solution (streaming tokens)
   │   │   └── Yields: token, first_response_complete
   │   │
   │   ├── Optional: Execute code for validation
   │   │   └── Yields: validation (passed/failed)
   │   │
   │   ├── Sutra critiques and scores
   │   │   └── Yields: sutra_started, first_response_complete
   │   │
   │   ├── Agni improves solution
   │   │   └── Yields: improving_started, improved_token, improved
   │   │
   │   ├── Check stopping conditions
   │   │   └── Yields: iteration_complete or plateau_reached
   │   │
   │   └── Break if converged, else continue
   │
6. Store best solution in Smriti (if score > 6.0)
   │
7. Record analytics in Redis (background task)
   │
8. Yield "end" event with final result
   │
9. API forwards all events as SSE to frontend
   │
10. Frontend updates UI based on event types
```

### 10.2 Error Handling

**Agent-Level:**
- Each Ollama call retries 3 times with backoff
- Sutra has additional JSON parsing robustness
- Graceful degradation if RAG fails

**Orchestrator-Level:**
- Catches exceptions per iteration
- Records partial results if an iteration fails
- Can continue to next iteration or abort entirely

**API-Level:**
- Wraps all endpoints in try/except
- Returns HTTP 500 with error details
- SSE endpoint yields error events instead of crashing

**Frontend-Level:**
- AbortController for canceling requests
- Health check before streaming
- Error display with retry option

---

## 11. Configuration & Deployment

### 11.1 Environment Variables

```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=null

# Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b

# RAG (optional)
CHAKRA_USE_VECTOR_RAG=1  # Enable ChromaDB + embeddings
```

### 11.2 Docker Compose

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    
  mysql:
    image: mysql:8.0
    ports: ["3306:3306"]
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: chakra_db
```

### 11.3 Startup Sequence

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Start Ollama
ollama serve

# 3. Pull models
ollama pull qwen2.5:1.5b
ollama pull mistral:latest

# 4. Start backend
cd backend
pip install -r requirements.txt
python api.py

# 5. Start frontend
cd chakra_ui
npm install
npm run dev
```

---

## 12. Key Design Decisions & Trade-offs

### 12.1 Why Local LLMs?

**Decision:** Use Ollama with local models instead of cloud APIs.

**Benefits:**
- No API costs
- No rate limits
- Full control over inference parameters
- Privacy (data stays local)

**Trade-offs:**
- Requires GPU for reasonable performance
- Model quality limited by available hardware
- Setup complexity

### 12.2 Why Decoupled Evaluation?

**Decision:** Use an independent judge for final scoring instead of Sutra's in-loop scores.

**Benefits:**
- Eliminates circular evaluation (model scoring its own improvements)
- Provides fair comparison across baselines and loop
- Enables statistical significance testing

**Trade-offs:**
- Additional LLM calls increase cost and time
- Judge is still an LLM (potential bias, though mitigated)

### 12.3 Why Model Splitting?

**Decision:** Use a weaker generator (qwen2.5:1.5b) and stronger critic (mistral:latest).

**Benefits:**
- Creates measurable headroom for improvement
- Stronger critic can identify more issues
- Cost-equivalent comparison to strong single-pass baseline

**Trade-offs:**
- More complex configuration
- Requires multiple model downloads

### 12.4 Why TF-IDF Default?

**Decision:** Use TF-IDF as the default RAG retriever, with vector search as opt-in.

**Benefits:**
- No external dependencies (no segfault risk)
- Fast startup
- Predictable behavior
- Zero configuration

**Trade-offs:**
- Lower retrieval quality than semantic search
- No concept of synonymy or paraphrasing

### 12.5 Why SQLite for Memory?

**Decision:** Use SQLite instead of Redis or PostgreSQL for Smriti.

**Benefits:**
- Zero configuration
- File-based (easy backup)
- Sufficient for solution storage scale
- No separate service required

**Trade-offs:**
- Not suitable for high-concurrency writes
- No built-in vector search

### 12.6 Streaming Architecture

**Decision:** Use SSE with a single generator function as the source of truth.

**Benefits:**
- Streaming and non-streaming share identical logic
- Real-time UX with token-by-token updates
- Simple error propagation

**Trade-offs:**
- SSE is less flexible than WebSockets
- No bidirectional communication

---

## Appendix: File Reference

| File | Purpose | Lines |
|------|---------|-------|
| `backend/api.py` | FastAPI server, SSE endpoints | 267 |
| `backend/orchestrator.py` | Agent coordination, loop control | 328 |
| `backend/agents/base_agent.py` | Base agent, Ollama communication | 233 |
| `backend/agents/yantra.py` | Generation agent | 63 |
| `backend/agents/sutra.py` | Critique agent with scoring | 302 |
| `backend/agents/agni.py` | Improvement agent | 74 |
| `backend/agents/smriti.py` | Memory agent (SQLite) | 165 |
| `backend/rag/vector_retriever.py` | RAG with vector/TF-IDF fallback | 319 |
| `backend/rag/retriever.py` | Simple RAG retriever | 90 |
| `backend/rag/document_parser.py` | Document parsing (txt, pdf) | 89 |
| `backend/evaluation/judge.py` | Independent LLM judge | 89 |
| `backend/evaluation/objective.py` | Execution-based metrics | 100 |
| `backend/evaluation/evaluator.py` | Heuristic evaluator | 126 |
| `backend/analytics/tracker.py` | Redis analytics storage | 408 |
| `backend/utils/code_executor.py` | Code extraction and execution | 73 |
| `backend/utils/background_tasks.py` | Async background task wrapper | 44 |
| `run_experiment.py` | Experiment harness, plotting, stats | ~1100 |
| `chakra_ui/utils/api.ts` | Frontend API client, SSE handler | ~250 |
| `chakra_ui/components/CodeAssistant.tsx` | Code generation UI | ~400 |
| `chakra_ui/components/Chatbot.tsx` | Chat interface | ~300 |
| `chakra_ui/components/DocumentAssistant.tsx` | RAG Q&A UI | ~500 |
| `chakra_ui/components/Analytics.tsx` | Analytics dashboard | ~300 |
| `chakra_ui/app/page.tsx` | Main app with navigation | ~300 |
