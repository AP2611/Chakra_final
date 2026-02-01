"""Simple background task wrapper without job_manager dependency."""
import asyncio
from typing import Callable, Any


def run_background_task(func: Callable, *args, **kwargs):
    """
    Run a function in the background with error handling.
    
    This replaces the need for job_manager by providing a simple,
    robust way to execute background tasks without blocking the main process.
    
    Args:
        func: The function to run (can be async or sync)
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
    
    Example:
        run_background_task(
            analytics.record_task,
            task="...",
            final_score=0.85,
            iterations=[],
            duration_ms=1000,
            task_type="code"
        )
    """
    async def safe_wrapper():
        try:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                # Run sync functions in thread pool to avoid blocking
                await asyncio.to_thread(func, *args, **kwargs)
        except Exception as e:
            # Log error but don't raise - background tasks shouldn't stop main process
            func_name = getattr(func, '__name__', str(func))
            error_msg = str(e)
            print(f"⚠️ Background task error ({func_name}): {error_msg}")
            # Don't re-raise - background tasks are fire-and-forget
    
    # Create and start the background task
    asyncio.create_task(safe_wrapper())

