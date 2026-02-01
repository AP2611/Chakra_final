"""Smriti - Memory Agent that stores and retrieves learning experiences."""
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import hashlib


class Smriti:
    """Memory agent for persistent learning."""
    
    def __init__(self, db_path: str = "backend/data/memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the memory database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_hash TEXT UNIQUE NOT NULL,
                task TEXT NOT NULL,
                task_embedding TEXT,
                solution TEXT NOT NULL,
                quality_score REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _hash_task(self, task: str) -> str:
        """Create a hash of the task for deduplication."""
        return hashlib.md5(task.encode()).hexdigest()
    
    def store(
        self,
        task: str,
        solution: str,
        quality_score: float,
        task_embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store a successful solution."""
        task_hash = self._hash_task(task)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if task already exists
        cursor.execute("SELECT quality_score FROM memories WHERE task_hash = ?", (task_hash,))
        existing = cursor.fetchone()
        
        if existing:
            # Only update if new score is better
            if quality_score > existing[0]:
                cursor.execute("""
                    UPDATE memories 
                    SET solution = ?, quality_score = ?, task_embedding = ?, metadata = ?
                    WHERE task_hash = ?
                """, (
                    solution,
                    quality_score,
                    json.dumps(task_embedding) if task_embedding else None,
                    json.dumps(metadata) if metadata else None,
                    task_hash
                ))
        else:
            # Insert new memory
            cursor.execute("""
                INSERT INTO memories (task_hash, task, task_embedding, solution, quality_score, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                task_hash,
                task,
                json.dumps(task_embedding) if task_embedding else None,
                solution,
                quality_score,
                json.dumps(metadata) if metadata else None
            ))
        
        conn.commit()
        conn.close()
    
    def retrieve_similar(
        self,
        task: str,
        limit: int = 3,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Retrieve similar past tasks and their solutions."""
        # Simple text-based similarity (can be enhanced with embeddings)
        task_lower = task.lower()
        task_words = set(task_lower.split())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT task, solution, quality_score, metadata
            FROM memories
            WHERE quality_score >= ?
            ORDER BY quality_score DESC
            LIMIT ?
        """, (min_score, limit * 2))  # Get more, then filter
        
        results = cursor.fetchall()
        conn.close()
        
        # Simple similarity scoring
        similar = []
        for stored_task, solution, score, metadata in results:
            stored_words = set(stored_task.lower().split())
            # Jaccard similarity
            intersection = len(task_words & stored_words)
            union = len(task_words | stored_words)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > 0.2:  # Threshold for similarity
                similar.append({
                    "task": stored_task,
                    "solution": solution,
                    "quality_score": score,
                    "similarity": similarity,
                    "metadata": json.loads(metadata) if metadata else {}
                })
        
        # Sort by similarity and score, return top results
        similar.sort(key=lambda x: (x["similarity"], x["quality_score"]), reverse=True)
        return similar[:limit]
    
    def get_best_examples(self, limit: int = 5) -> List[str]:
        """Get the best solutions regardless of similarity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT solution
            FROM memories
            ORDER BY quality_score DESC
            LIMIT ?
        """, (limit,))
        
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return results

