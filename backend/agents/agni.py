"""Agni - Improvement Agent that rewrites solutions fixing issues."""
from typing import Optional, List, Dict, Any
from .base_agent import BaseAgent


class Agni(BaseAgent):
    """Improvement agent that fixes issues and optimizes solutions."""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:1.5b", fast_mode: bool = True):
        super().__init__("Agni", ollama_url, model, fast_mode=fast_mode)
    
    async def process(
        self,
        original_output: str,
        critique: str,
        task: str,
        rag_chunks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Rewrite solution addressing all critiques."""
        
        system_prompt = (
            "You are Agni, an expert optimizer. "
            "Rewrite the solution fixing all issues and following best practices. "
            "Produce clean, correct, and efficient code or answers."
        )
        
        user_prompt_parts = [
            f"Original Task: {task}",
            f"\n--- Original Output ---\n{original_output}",
            f"\n--- Critique and Issues Found ---\n{critique}",
        ]
        
        if rag_chunks:
            user_prompt_parts.append("\n--- Document Context ---")
            for i, chunk in enumerate(rag_chunks, 1):
                user_prompt_parts.append(f"\n[Chunk {i}]\n{chunk}")
            user_prompt_parts.append(
                "\nEnsure all claims are properly grounded in the document context."
            )
        
        user_prompt_parts.append(
            "\n--- Your Task ---\n"
            "Rewrite the solution addressing ALL issues mentioned in the critique. "
            "Improve:\n"
            "1. Correctness - fix all bugs and errors\n"
            "2. Performance - optimize where possible\n"
            "3. Clarity - make logic clear and well-structured\n"
            "4. Grounding - ensure all claims are supported (if RAG context provided)\n\n"
            "Provide the improved solution in clean final form."
        )
        
        user_prompt = "\n".join(user_prompt_parts)
        
        response = await self._call_ollama(user_prompt, system_prompt)
        
        return {
            "agent": self.name,
            "improved_output": response,
            "original_output": original_output,
            "critique": critique,
            "task": task
        }

