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
        rag_chunks: Optional[List[str]] = None,
        exec_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Rewrite solution addressing all critiques (diff-based)."""
        
        system_prompt = (
            "You are Agni, an expert optimizer. "
            "You improve a solution by applying ONLY the specific fixes identified in the "
            "critique. Preserve everything that is already correct and good — do NOT rewrite "
            "the whole solution from scratch unless it is fundamentally broken. "
            "Produce clean, correct, and efficient code or answers."
        )
        
        user_prompt_parts = [
            f"Original Task: {task}",
            f"\n--- Original Output ---\n{original_output}",
            f"\n--- Critique and Issues Found ---\n{critique}",
        ]
        
        if exec_result is not None:
            from utils.code_executor import format_for_prompt
            user_prompt_parts.append("\n--- Execution Validation ---")
            user_prompt_parts.append(format_for_prompt(exec_result))
            user_prompt_parts.append(
                "\nIf execution FAILED, your TOP priority is to fix the exact error shown above. "
                "Make the minimal change required to make the code run successfully."
            )
        
        if rag_chunks:
            user_prompt_parts.append("\n--- Document Context ---")
            for i, chunk in enumerate(rag_chunks, 1):
                user_prompt_parts.append(f"\n[Chunk {i}]\n{chunk}")
            user_prompt_parts.append(
                "\nEnsure all claims are properly grounded in the document context."
            )
        
        user_prompt_parts.append(
            "\n--- Your Task ---\n"
            "Apply the fixes from the critique with minimal, surgical changes:\n"
            "1. Correctness - fix all bugs and errors (especially any execution failure)\n"
            "2. Performance - optimize only where the critique says to\n"
            "3. Clarity - keep logic clear; do not restructure working code unnecessarily\n"
            "4. Grounding - ensure all claims are supported (if RAG context provided)\n\n"
            "Return the COMPLETE improved solution (full code/answer), not just a diff."
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

