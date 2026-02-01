"""Analytics tracker for recording and retrieving agent performance metrics."""
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
import redis
from functools import wraps


def async_to_thread(func):
    """Decorator to run async function in thread pool."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


class AnalyticsTracker:
    """Tracks agent performance metrics using Redis."""
    
    def __init__(
        self,
        redis_host: str = None,
        redis_port: int = None,
        redis_db: int = None,
        redis_password: str = None
    ):
        """Initialize analytics tracker with Redis connection."""
        # Get Redis config from environment or use defaults
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.redis_port = redis_port or int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = redis_db or int(os.getenv("REDIS_DB", "0"))
        self.redis_password = redis_password or os.getenv("REDIS_PASSWORD", None)
        
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            print(f"✓ Analytics: Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"⚠ Analytics: Redis connection failed: {e}")
            print("⚠ Analytics: Continuing without analytics storage")
            self.redis_client = None
    
    def record_task(
        self,
        task: str,
        final_score: float,
        iterations: List[Dict[str, Any]],
        duration_ms: float,
        task_type: str = "code"
    ):
        """Record a completed task and its metrics (non-blocking)."""
        if not self.redis_client:
            return
        
        try:
            # Calculate improvement metrics
            if iterations and len(iterations) > 0:
                # Get scores from first iteration
                first_iter = iterations[0]
                yantra_score = first_iter.get("yantra_score") or first_iter.get("score", final_score)
                agni_score = first_iter.get("agni_score") or first_iter.get("score", final_score)
                
                # Use final score if agni_score not available
                if not agni_score or agni_score == yantra_score:
                    agni_score = final_score
                
                improvement = agni_score - yantra_score
                
                # Calculate improvement percentage
                if yantra_score > 0.01:
                    improvement_percent = (improvement / yantra_score) * 100
                elif yantra_score <= 0.01 and agni_score > yantra_score:
                    # Special handling for very low initial scores
                    improvement_percent = min(500.0, max(10.0, ((agni_score - yantra_score) / 0.1) * 100))
                elif yantra_score > 0:
                    improvement_percent = (improvement / max(0.01, yantra_score)) * 100
                else:
                    if improvement > 0:
                        improvement_percent = min(200.0, (improvement / 0.1) * 100)
                    else:
                        improvement_percent = 0.0
                
                initial_score = yantra_score
                final_score_actual = agni_score
            else:
                initial_score = final_score
                final_score_actual = final_score
                improvement = 0.0
                improvement_percent = 0.0
            
            # Generate task ID
            task_id = self.redis_client.incr("analytics:task_counter")
            
            # Create timestamp
            timestamp = datetime.now().isoformat()
            
            # Store task record
            task_record = {
                "id": str(task_id),
                "task": task[:100],  # Truncate to 100 chars
                "initial_score": str(initial_score),
                "final_score": str(final_score_actual),
                "improvement": str(improvement),
                "improvement_percent": str(round(improvement_percent, 2)),
                "iterations": str(len(iterations)),
                "duration_ms": str(duration_ms),
                "task_type": task_type,
                "timestamp": timestamp
            }
            
            # Store in Redis hash
            self.redis_client.hset(
                f"analytics:task:{task_id}",
                mapping=task_record
            )
            
            # Add to sorted set for ordering by timestamp
            timestamp_float = datetime.fromisoformat(timestamp).timestamp()
            self.redis_client.zadd("analytics:task_ids", {str(task_id): timestamp_float})
            
            # Store iterations
            for i, iteration in enumerate(iterations):
                iter_num = i + 1
                iteration_record = {
                    "task_id": str(task_id),
                    "iteration_num": str(iter_num),
                    "score": str(iteration.get("score", 0.0)),
                    "improvement": str(iteration.get("improvement", 0.0)),
                    "timestamp": timestamp
                }
                self.redis_client.hset(
                    f"analytics:iteration:{task_id}:{iter_num}",
                    mapping=iteration_record
                )
                self.redis_client.sadd(f"analytics:task:{task_id}:iterations", str(iter_num))
            
            # Cleanup: Keep only last 100 tasks
            self._cleanup_old_tasks()
            
        except Exception as e:
            print(f"⚠ Analytics: Error recording task: {e}")
    
    def _cleanup_old_tasks(self, keep_count: int = 100):
        """Keep only the last N tasks."""
        if not self.redis_client:
            return
        
        try:
            task_ids = self._get_task_ids(limit=keep_count)
            if len(task_ids) > keep_count:
                # Get all task IDs
                all_task_ids = self._get_task_ids(limit=10000)
                old_task_ids = all_task_ids[keep_count:]
                
                for old_id in old_task_ids:
                    # Delete task hash
                    self.redis_client.delete(f"analytics:task:{old_id}")
                    # Remove from sorted set
                    self.redis_client.zrem("analytics:task_ids", old_id)
                    # Get iteration numbers
                    iter_nums = self.redis_client.smembers(f"analytics:task:{old_id}:iterations")
                    # Delete iterations
                    for iter_num in iter_nums:
                        self.redis_client.delete(f"analytics:iteration:{old_id}:{iter_num}")
                    # Delete iterations set
                    self.redis_client.delete(f"analytics:task:{old_id}:iterations")
        except Exception as e:
            print(f"⚠ Analytics: Error cleaning up tasks: {e}")
    
    def _get_task_ids(self, limit: int = 100) -> List[str]:
        """Get task IDs ordered by timestamp (newest first)."""
        if not self.redis_client:
            return []
        
        try:
            # Get last N task IDs from sorted set (reverse order)
            task_ids = self.redis_client.zrevrange("analytics:task_ids", 0, limit - 1)
            return [str(tid) for tid in task_ids]
        except Exception as e:
            print(f"⚠ Analytics: Error getting task IDs: {e}")
            return []
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        if not self.redis_client:
            return None
        
        try:
            task_data = self.redis_client.hgetall(f"analytics:task:{task_id}")
            if not task_data:
                return None
            
            return {
                "id": int(task_data["id"]),
                "task": task_data["task"],
                "initial_score": float(task_data["initial_score"]),
                "final_score": float(task_data["final_score"]),
                "improvement": float(task_data["improvement"]),
                "improvement_percent": float(task_data["improvement_percent"]),
                "iterations": int(task_data["iterations"]),
                "duration_ms": float(task_data["duration_ms"]),
                "task_type": task_data["task_type"],
                "timestamp": task_data["timestamp"]
            }
        except Exception as e:
            print(f"⚠ Analytics: Error getting task: {e}")
            return None
    
    def get_all_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all tasks."""
        task_ids = self._get_task_ids(limit=limit)
        tasks = []
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task:
                tasks.append(task)
        return tasks
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get overall metrics."""
        if not self.redis_client:
            return {
                "avg_improvement": 0.0,
                "avg_latency": 0.0,
                "avg_accuracy": 0.0,
                "avg_iterations": 0.0,
                "total_tasks": 0
            }
        
        tasks = self.get_all_tasks()
        if not tasks:
            return {
                "avg_improvement": 0.0,
                "avg_latency": 0.0,
                "avg_accuracy": 0.0,
                "avg_iterations": 0.0,
                "total_tasks": 0
            }
        
        improvements = [t["improvement_percent"] for t in tasks]
        latencies = [t["duration_ms"] / 1000 for t in tasks if t["duration_ms"] > 0]
        accuracies = [t["final_score"] * 100 for t in tasks]
        iterations = [t["iterations"] for t in tasks]
        
        return {
            "avg_improvement": round(sum(improvements) / len(improvements), 1) if improvements else 0.0,
            "avg_latency": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "avg_accuracy": round(sum(accuracies) / len(accuracies), 1) if accuracies else 0.0,
            "avg_iterations": round(sum(iterations) / len(iterations), 1) if iterations else 0.0,
            "total_tasks": len(tasks)
        }
    
    def get_quality_improvement_data(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get quality improvement data for chart."""
        if not self.redis_client:
            return []
        
        tasks = self.get_all_tasks(limit=10)
        chart_data = []
        
        for task in tasks:
            task_id = task["id"]
            # Get iterations
            iter_nums = self.redis_client.smembers(f"analytics:task:{task_id}:iterations")
            iterations = []
            for iter_num in sorted(iter_nums, key=int):
                iter_data = self.redis_client.hgetall(f"analytics:iteration:{task_id}:{iter_num}")
                if iter_data:
                    iterations.append({
                        "task_id": int(iter_data["task_id"]),
                        "iteration_num": int(iter_data["iteration_num"]),
                        "score": float(iter_data["score"]),
                        "improvement": float(iter_data.get("improvement", 0.0)),
                        "timestamp": iter_data["timestamp"]
                    })
            
            if iterations:
                initial_score = iterations[0]["score"] * 100
                final_score = iterations[-1]["score"] * 100
            else:
                initial_score = task["initial_score"] * 100
                final_score = task["final_score"] * 100
            
            improvement = final_score - initial_score
            
            chart_data.append({
                "iteration": f"T{task_id}",
                "before": round(initial_score, 1),
                "after": round(final_score, 1),
                "improvement": round(improvement, 1)
            })
        
        return chart_data[-limit:]
    
    def get_performance_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get performance history over time."""
        if not self.redis_client:
            return []
        
        tasks = self.get_all_tasks(limit=1000)
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Group by hour
        hourly_data = {}
        for task in tasks:
            try:
                task_time = datetime.fromisoformat(task["timestamp"])
                if task_time < cutoff_time:
                    continue
                
                hour_key = task_time.replace(minute=0, second=0, microsecond=0)
                hour_str = hour_key.strftime("%H:00")
                
                if hour_str not in hourly_data:
                    hourly_data[hour_str] = {"latencies": [], "accuracies": []}
                
                if task["duration_ms"] > 0:
                    hourly_data[hour_str]["latencies"].append(task["duration_ms"] / 1000)
                hourly_data[hour_str]["accuracies"].append(task["final_score"] * 100)
            except:
                continue
        
        # Calculate averages
        result = []
        for hour_str in sorted(hourly_data.keys()):
            data = hourly_data[hour_str]
            result.append({
                "time": hour_str,
                "latency": round(sum(data["latencies"]) / len(data["latencies"]), 0) if data["latencies"] else 0,
                "accuracy": round(sum(data["accuracies"]) / len(data["accuracies"]), 1) if data["accuracies"] else 0.0
            })
        
        return result
    
    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent tasks formatted for display."""
        if not self.redis_client:
            return []
        
        tasks = self.get_all_tasks(limit=limit)
        now = datetime.now()
        
        formatted_tasks = []
        for task in tasks:
            try:
                task_time = datetime.fromisoformat(task["timestamp"])
                time_diff = now - task_time
                
                if time_diff < timedelta(hours=1):
                    time_str = f"{int(time_diff.total_seconds() / 60)} minutes ago"
                elif time_diff < timedelta(hours=24):
                    time_str = f"Today, {task_time.strftime('%I:%M %p')}"
                elif time_diff < timedelta(hours=48):
                    time_str = f"Yesterday, {task_time.strftime('%I:%M %p')}"
                else:
                    time_str = task_time.strftime("%b %d, %I:%M %p")
                
                formatted_tasks.append({
                    "id": task["id"],
                    "task": task["task"],
                    "improvement": f"+{task['improvement_percent']:.1f}%",
                    "duration": f"{task['duration_ms'] / 1000:.1f}s" if task["duration_ms"] > 0 else "N/A",
                    "iterations": task["iterations"],
                    "date": time_str
                })
            except:
                continue
        
        return formatted_tasks

