"""FastAPI server for the agent system with SSE support."""
import sys
import os

# Disable Python bytecode caching to prevent stale cache issues
# This prevents .pyc files and __pycache__ directories from being created
# Benefits:
#   - No stale cache issues (like job_manager errors)
#   - Always uses fresh source code
#   - Cleaner file system
# Trade-off: Slightly slower startup (10-30%), but negligible for this app
sys.dont_write_bytecode = True

# Also set environment variable for subprocesses and imported modules
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, AsyncGenerator
import uvicorn
import json
import asyncio
from orchestrator import Orchestrator
from agents.sutra import SutraOutput
from analytics.tracker import AnalyticsTracker
from utils.background_tasks import run_background_task
from rag.document_parser import DocumentParser

app = FastAPI(title="Agent System API", version="1.0.0")

# CORS middleware - updated for SSE and specific ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize orchestrator with fast_mode enabled for low latency
orchestrator = Orchestrator(fast_mode=True)

# Initialize analytics tracker
analytics = AnalyticsTracker()


class TaskRequest(BaseModel):
    task: str
    context: Optional[str] = None
    use_rag: bool = False
    is_code: bool = True


class IterationResponse(BaseModel):
    iteration: int
    yantra_output: str
    sutra_critique: str
    agni_output: str
    score: float
    improvement: Optional[float]
    score_details: Dict[str, float]


class ProcessResponse(BaseModel):
    task: str
    final_solution: str
    final_score: float
    iterations: List[Dict[str, Any]]
    total_iterations: int
    used_rag: bool
    rag_chunks: Optional[List[str]]


@app.get("/")
async def root():
    return {"message": "Agent System API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/process", response_model=ProcessResponse)
async def process_task(request: TaskRequest):
    """Process a task through the agent system."""
    import time
    start_time = time.time()
    try:
        result = await orchestrator.process(
            task=request.task,
            context=request.context,
            use_rag=request.use_rag,
            is_code=request.is_code
        )

        # Record analytics (non-blocking) - using background task manager
        duration_ms = (time.time() - start_time) * 1000
        task_type = "code" if request.is_code else "document"

        run_background_task(
            analytics.record_task,
            request.task,
            result["final_score"],
            result["iterations"],
            duration_ms,
            task_type
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def generate_process_events(request: TaskRequest) -> AsyncGenerator[str, None]:
    """Generate SSE events by delegating to the orchestrator's single loop.

    The orchestrator's `process_stream` is the single source of truth for the
    agent loop (including the JSON-parsing fix, degradation stop, error
    recovery, and code-execution validation). This endpoint just forwards its
    events as Server-Sent Events and records analytics on completion.
    """
    start_time = asyncio.get_event_loop().time()
    try:
        async for event in orchestrator.process_stream(
            task=request.task,
            context=request.context,
            use_rag=request.use_rag,
            is_code=request.is_code
        ):
            # Forward every event from the orchestrator as SSE
            yield f"data: {json.dumps(event)}\n\n"

            # Record analytics when the run completes
            if event.get("type") == "end":
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                task_type = "code" if request.is_code else "document"
                run_background_task(
                    analytics.record_task,
                    request.task,
                    event["final_score"],
                    event["iterations"],
                    duration_ms,
                    task_type
                )
    except Exception as e:
        error_msg = str(e) if e else "Unknown error occurred"
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'error': error_msg})}\n\n"


@app.post("/process-stream")
async def process_task_stream(request: TaskRequest):
    """Process a task through the agent system with streaming updates using POST."""
    async def event_generator():
        """Wrapper to ensure proper async iteration and immediate flushing."""
        try:
            async for event in generate_process_events(request):
                # Yield immediately without buffering
                yield event
        except Exception as e:
            error_msg = str(e) if e else "Unknown error occurred"
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'error': error_msg})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        }
    )


@app.post("/process/stream")
async def process_task_stream_legacy(request: TaskRequest):
    """Legacy endpoint - redirects to /process-stream."""
    return StreamingResponse(
        generate_process_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# Analytics API Endpoints
@app.get("/analytics/metrics")
async def get_metrics():
    """Get overall analytics metrics."""
    metrics = await asyncio.to_thread(analytics.get_metrics)
    return metrics


@app.get("/analytics/quality-improvement")
async def get_quality_improvement(limit: int = 20):
    """Get quality improvement data for chart."""
    data = await asyncio.to_thread(analytics.get_quality_improvement_data, limit)
    return {"data": data}


@app.get("/analytics/performance-history")
async def get_performance_history(hours: int = 24):
    """Get performance history over time."""
    data = await asyncio.to_thread(analytics.get_performance_history, hours)
    return {"data": data}


@app.get("/analytics/recent-tasks")
async def get_recent_tasks(limit: int = 10):
    """Get recent tasks."""
    tasks = await asyncio.to_thread(analytics.get_recent_tasks, limit)
    return {"tasks": tasks}


# RAG Document Upload Endpoints
@app.post("/rag/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document to the RAG system."""
    try:
        # Read file content
        content = await file.read()

        # Parse the file
        parsed_content = DocumentParser.parse_uploaded_file(content, file.filename)

        if not parsed_content:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {file.filename}")

        # Add to vector database
        success = await asyncio.to_thread(
            orchestrator.rag.add_document,
            parsed_content,
            file.filename
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to add document to vector database")

        return {
            "success": True,
            "filename": file.filename,
            "chunks_added": len(parsed_content.split("\n\n")),
            "message": f"Document '{file.filename}' uploaded successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
