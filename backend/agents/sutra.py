"""Sutra - Critique Agent that analyzes and finds issues."""
from typing import Optional, List, Dict, Any
from .base_agent import BaseAgent


class Sutra(BaseAgent):
    """Critique agent that identifies problems in solutions."""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:1.5b", fast_mode: bool = True):
        super().__init__("Sutra", ollama_url, model, fast_mode=fast_mode)
    
    async def process(
        self,
        yantra_output: str,
        original_task: str,
        rag_chunks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Analyze output and find issues."""
        
        system_prompt = (
            "You are Sutra, a strict expert reviewer. "
            "Identify all issues precisely and explain what must be improved. "
            "Be thorough and specific in your critique."
        )
        
        user_prompt_parts = [
            f"Original Task: {original_task}",
            f"\n--- Yantra's Output ---\n{yantra_output}",
        ]
        
        if rag_chunks:
            user_prompt_parts.append("\n--- Document Context (for verification) ---")
            for i, chunk in enumerate(rag_chunks, 1):
                user_prompt_parts.append(f"\n[Chunk {i}]\n{chunk}")
            user_prompt_parts.append(
                "\nCheck if all claims in the output are supported by the document context. "
                "Flag any hallucinations or unsupported statements."
            )
        
        user_prompt_parts.append(
            "\n--- Your Task ---\n"
            "Analyze the output and identify:\n"
            "1. Bugs or errors\n"
            "2. Inaccuracies\n"
            "3. Inefficiencies\n"
            "4. Unclear logic\n"
            "5. Missing edge cases\n"
            "6. Unsupported claims (if RAG context provided)\n\n"
            "Provide a bullet list of problems and suggested fixes."
        )
        
        user_prompt = "\n".join(user_prompt_parts)
        
        response = await self._call_ollama(user_prompt, system_prompt)
        
        return {
            "agent": self.name,
            "critique": response,
            "original_output": yantra_output,
            "task": original_task
        }

