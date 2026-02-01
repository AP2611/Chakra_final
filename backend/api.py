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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, AsyncGenerator
import uvicorn
import json
import asyncio
from orchestrator import Orchestrator
from analytics.tracker import AnalyticsTracker
from utils.background_tasks import run_background_task

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
    """Generate SSE events for task processing with token streaming."""
    start_time = asyncio.get_event_loop().time()
    iterations = []
    best_score = 0.0
    best_solution = None
    
    try:
        # Send start event
        yield f"data: {json.dumps({'type': 'start', 'message': 'Starting task processing...'})}\n\n"
        
        # Retrieve RAG chunks if needed
        rag_chunks = None
        if request.use_rag:
            rag_chunks = orchestrator.rag.retrieve(request.task, top_k=3)
            yield f"data: {json.dumps({'type': 'rag_retrieved', 'chunks_count': len(rag_chunks)})}\n\n"
        
        # Retrieve similar past examples from memory
        similar_tasks = orchestrator.smriti.retrieve_similar(request.task, limit=3)
        if similar_tasks:
            yield f"data: {json.dumps({'type': 'memory_found', 'examples_count': len(similar_tasks)})}\n\n"
        
        past_examples = [ex["solution"] for ex in similar_tasks] if similar_tasks else []
        
        current_solution = None
        
        for iteration in range(orchestrator.max_iterations):
            iteration_data = {
                "iteration": iteration + 1,
                "yantra_output": None,
                "sutra_critique": None,
                "agni_output": None,
                "score": None,
                "improvement": None
            }
            
            yield f"data: {json.dumps({'type': 'iteration_start', 'iteration': iteration + 1})}\n\n"
            
            # Step 1: Yantra generates solution with token streaming
            yield f"data: {json.dumps({'type': 'first_response_started'})}\n\n"
            
            # Build prompt for Yantra
            system_prompt = (
                "You are Yantra, an expert problem solver. "
                "Produce clear, correct, and efficient solutions following best practices. "
                "Be precise and thorough in your responses."
            )
            
            user_prompt_parts = [f"Task: {request.task}"]
            if rag_chunks:
                user_prompt_parts.append("\n--- Relevant Document Context ---")
                for i, chunk in enumerate(rag_chunks, 1):
                    user_prompt_parts.append(f"\n[Chunk {i}]\n{chunk}")
            if past_examples and iteration == 0:
                user_prompt_parts.append("\n--- Successful Past Solutions for Similar Tasks ---")
                for i, example in enumerate(past_examples, 1):
                    user_prompt_parts.append(f"\n[Example {i}]\n{example}")
            if request.context:
                user_prompt_parts.append(f"\n--- Additional Context ---\n{request.context}")
            
            user_prompt = "\n".join(user_prompt_parts)
            
            # Stream tokens from Yantra with optimized parameters
            # Strategy 4: Streaming - tokens appear immediately (0.5-2s first token)
            # CRITICAL FIX: Higher token limits for non-code responses (chatbot)
            # Code: 384/640 tokens, Chatbot: 512/1024 tokens (more verbose responses needed)
            token_limit = 512 if orchestrator.fast_mode else 1024 if not request.is_code else (384 if orchestrator.fast_mode else 640)
            
            yantra_output = ""
            token_count = 0
            async for token in orchestrator.yantra._call_ollama_stream(
                user_prompt, 
                system_prompt,
                max_tokens=token_limit
            ):
                yantra_output += token
                token_count += 1
                # Stream tokens immediately for real-time updates
                yield f"data: {json.dumps({'type': 'token', 'token': token, 'token_count': token_count, 'iteration': iteration + 1})}\n\n"
            
            iteration_data["yantra_output"] = yantra_output.strip()
            current_solution = yantra_output.strip()
            
            # Evaluate Yantra's initial output for accurate analytics
            yantra_score_result = orchestrator.evaluator.evaluate(
                solution=current_solution,
                task=request.task,
                is_code=request.is_code,
                rag_chunks=rag_chunks
            )
            yantra_score = yantra_score_result["total"]
            iteration_data["yantra_score"] = yantra_score
            iteration_data["yantra_score_details"] = yantra_score_result
            
            yield f"data: {json.dumps({'type': 'first_response_complete', 'iteration': iteration + 1})}\n\n"
            
            # Step 2: Sutra critiques (optimized with token limits)
            yield f"data: {json.dumps({'type': 'sutra_started', 'iteration': iteration + 1})}\n\n"
            # Strategy 1: Token Limits - Use shorter critique (faster)
            sutra_result = await orchestrator.sutra.process(
                yantra_output=current_solution,
                original_task=request.task,
                rag_chunks=rag_chunks
            )
            iteration_data["sutra_critique"] = sutra_result["critique"]
            
            # Step 3: Agni improves - BYPASS STRATEGY: Skip streaming, send complete output
            # This ensures reliable delivery of refined output without streaming issues
            yield f"data: {json.dumps({'type': 'improving_started', 'iteration': iteration + 1})}\n\n"
            
            # Build prompt for Agni
            agni_system_prompt = (
                "You are Agni, an expert optimizer. "
                "Rewrite the solution fixing all issues and following best practices. "
                "Produce clean, correct, and efficient code or answers."
            )
            
            agni_user_prompt_parts = [
                f"Original Task: {request.task}",
                f"\n--- Original Output ---\n{current_solution}",
                f"\n--- Critique and Issues Found ---\n{sutra_result['critique']}",
            ]
            
            if rag_chunks:
                agni_user_prompt_parts.append("\n--- Document Context ---")
                for i, chunk in enumerate(rag_chunks, 1):
                    agni_user_prompt_parts.append(f"\n[Chunk {i}]\n{chunk}")
            
            agni_user_prompt_parts.append(
                "\n--- Your Task ---\n"
                "Rewrite the solution addressing ALL issues mentioned in the critique. "
                "Provide the improved solution in clean final form."
            )
            
            agni_user_prompt = "\n".join(agni_user_prompt_parts)
            
            # BYPASS: Direct non-streaming call - guaranteed to work
            # This skips all streaming complexity and ensures output is always delivered
            # CRITICAL FIX: Higher token limits for non-code responses (chatbot)
            token_limit = 512 if orchestrator.fast_mode else 1024 if not request.is_code else (384 if orchestrator.fast_mode else 640)
            
            try:
                agni_output = await orchestrator.agni._call_ollama(
                    agni_user_prompt,
                    agni_system_prompt,
                    max_tokens=token_limit
                )
                
                # Ensure we have output
                if not agni_output:
                    agni_output = "Unable to generate improved output"
                    
            except Exception as e:
                # Log error but still provide fallback
                error_msg = str(e)
                print(f"Agni generation error: {error_msg}")
                print(f"  Full error details: {type(e).__name__}: {error_msg}")
                agni_output = "Error generating improved output. Please try again."
            
            # Clean the output
            agni_output = agni_output.strip()
            iteration_data["agni_output"] = agni_output
            current_solution = agni_output
            
            # Calculate token count (approximate word count)
            improved_token_count = len(agni_output.split()) if agni_output else 0
            
            # CRITICAL: Send improved output events BEFORE any potential errors
            # This ensures frontend receives the refined code even if background errors occur
            try:
                # Send complete output as improved_token (frontend will display it immediately)
                yield f"data: {json.dumps({'type': 'improved_token', 'token': agni_output, 'iteration': iteration + 1, 'token_count': improved_token_count})}\n\n"
                
                # Send final improved event (with both fields for frontend compatibility)
                yield f"data: {json.dumps({'type': 'improved', 'iteration': iteration + 1, 'improved_output': current_solution, 'solution': current_solution, 'token_count': improved_token_count})}\n\n"
            except Exception as e:
                # If sending events fails, log but continue - we've already generated the output
                error_msg = str(e)
                print(f"Error sending improved events: {error_msg}")
            
            # Step 4: Evaluate Agni's improved output
            agni_score_result = orchestrator.evaluator.evaluate(
                solution=current_solution,
                task=request.task,
                is_code=request.is_code,
                rag_chunks=rag_chunks
            )
            agni_score = agni_score_result["total"]
            iteration_data["agni_score"] = agni_score
            iteration_data["score"] = agni_score  # Keep for backward compatibility
            iteration_data["score_details"] = agni_score_result
            
            # Calculate improvement (Agni vs Yantra for this iteration)
            improvement = agni_score - yantra_score
            iteration_data["improvement"] = improvement
            
            # Also calculate improvement from previous iteration's Agni score
            if iteration > 0:
                prev_agni_score = iterations[-1].get("agni_score", iterations[-1].get("score", 0.0))
                iteration_improvement = agni_score - prev_agni_score
                iteration_data["iteration_improvement"] = iteration_improvement
            else:
                iteration_data["iteration_improvement"] = improvement
            
            iterations.append(iteration_data)
            
            # Send iteration complete event with data
            yield f"data: {json.dumps({
                'type': 'iteration_complete',
                'iteration': iteration + 1,
                'data': iteration_data
            })}\n\n"
            
            # Update best solution
            if agni_score > best_score:
                best_score = agni_score
                best_solution = current_solution
            
            # Check if we should continue
            if iteration > 0:
                prev_agni_score = iterations[-1].get("agni_score", iterations[-1].get("score", 0.0))
                improvement = agni_score - prev_agni_score
                if improvement < orchestrator.min_improvement:
                    # Score plateaued, stop
                    yield f"data: {json.dumps({
                        'type': 'plateau_reached',
                        'message': f'Score improvement ({improvement:.2%}) below minimum threshold ({orchestrator.min_improvement:.2%})'
                    })}\n\n"
                    break
        
        # Store best solution in memory
        if best_score > 0.6:
            orchestrator.smriti.store(
                task=request.task,
                solution=best_solution,
                quality_score=best_score,
                metadata={
                    "is_code": request.is_code,
                    "used_rag": request.use_rag,
                    "iterations": len(iterations)
                }
            )
        
        # Send completion event
        yield f"data: {json.dumps({
            'type': 'end',
            'task': request.task,
            'final_solution': best_solution,
            'final_score': best_score,
            'iterations': iterations,
            'total_iterations': len(iterations),
            'used_rag': request.use_rag
        })}\n\n"
        
        # Record analytics (non-blocking) - using background task manager
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        task_type = "code" if request.is_code else "document"
        
        run_background_task(
            analytics.record_task,
            request.task,
            best_score,
            iterations,
            duration_ms,
            task_type
        )
        
    except Exception as e:
        error_msg = str(e) if e else "Unknown error occurred"
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg, 'error': error_msg})}\n\n"


@app.post("/process-stream")
async def process_task_stream(request: TaskRequest):
    """Process a task through the agent system with streaming updates using POST."""
    from fastapi.responses import StreamingResponse
    import asyncio
    
    async def event_generator():
        """Wrapper to ensure proper async iteration and immediate flushing."""
        try:
            async for event in generate_process_events(request):
                # Yield immediately without buffering
                yield event
                # Remove sleep(0) to reduce latency - events are already flushed
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

