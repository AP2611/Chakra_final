"""Evaluation engine for scoring solutions."""
import re
from typing import Dict, Any, Optional, List


class Evaluator:
    """Evaluates solution quality."""
    
    def __init__(self):
        self.code_patterns = {
            "has_comments": r"#.*|//.*|/\*.*?\*/",
            "has_docstrings": r'""".*?"""|\'\'\'.*?\'\'\'',
            "has_error_handling": r"try:|except:|catch\s*\(",
            "has_type_hints": r"def\s+\w+\s*\([^)]*:\s*\w+",
        }
    
    def evaluate_code(
        self,
        code: str,
        task: str,
        rag_chunks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Evaluate code solution."""
        scores = {
            "correctness": 0.5,  # Base score
            "quality": 0.5,
            "completeness": 0.5,
            "total": 0.5
        }
        
        # Check for code structure
        if "def " in code or "function " in code or "class " in code:
            scores["completeness"] += 0.2
        
        # Check for best practices
        for pattern_name, pattern in self.code_patterns.items():
            if re.search(pattern, code, re.DOTALL):
                scores["quality"] += 0.1
        
        # Check for imports
        if re.search(r"^import\s+|^from\s+", code, re.MULTILINE):
            scores["quality"] += 0.1
        
        # Normalize scores
        scores["correctness"] = min(1.0, scores["correctness"])
        scores["quality"] = min(1.0, scores["quality"])
        scores["completeness"] = min(1.0, scores["completeness"])
        
        # Calculate total (weighted average)
        scores["total"] = (
            scores["correctness"] * 0.4 +
            scores["quality"] * 0.3 +
            scores["completeness"] * 0.3
        )
        
        return scores
    
    def evaluate_rag_answer(
        self,
        answer: str,
        rag_chunks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Evaluate RAG-based answer."""
        scores = {
            "grounding": 0.5,
            "clarity": 0.5,
            "completeness": 0.5,
            "total": 0.5
        }
        
        if not rag_chunks:
            return scores
        
        # Check grounding - simple keyword matching
        answer_lower = answer.lower()
        chunk_text = " ".join(rag_chunks).lower()
        
        answer_words = set(answer_lower.split())
        chunk_words = set(chunk_text.split())
        
        # Calculate overlap
        overlap = len(answer_words & chunk_words)
        total_unique = len(answer_words | chunk_words)
        
        if total_unique > 0:
            grounding_score = overlap / total_unique
            scores["grounding"] = min(1.0, grounding_score * 2)  # Scale up
        
        # Check for citations or references
        if re.search(r"\[.*?\]|\(.*?\)|source|document|according", answer_lower):
            scores["grounding"] += 0.2
        
        # Clarity - check for structure
        if len(answer.split("\n")) > 3:
            scores["clarity"] += 0.2
        
        if re.search(r"\*\*.*?\*\*|#+\s+", answer):  # Markdown formatting
            scores["clarity"] += 0.1
        
        # Normalize
        scores["grounding"] = min(1.0, scores["grounding"])
        scores["clarity"] = min(1.0, scores["clarity"])
        scores["completeness"] = min(1.0, scores["completeness"])
        
        # Total score
        scores["total"] = (
            scores["grounding"] * 0.5 +
            scores["clarity"] * 0.3 +
            scores["completeness"] * 0.2
        )
        
        return scores
    
    def evaluate(
        self,
        solution: str,
        task: str,
        is_code: bool = True,
        rag_chunks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Main evaluation method."""
        if is_code:
            return self.evaluate_code(solution, task, rag_chunks)
        else:
            return self.evaluate_rag_answer(solution, rag_chunks)

