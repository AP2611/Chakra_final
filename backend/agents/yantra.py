"""Yantra - Generation Agent that produces initial solutions."""
from typing import Optional, List, Dict, Any
from .base_agent import BaseAgent


class Yantra(BaseAgent):
    """Generation agent that creates initial solutions."""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:1.5b", fast_mode: bool = True):
        super().__init__("Yantra", ollama_url, model, fast_mode=fast_mode)
    
    async def process(
        self,
        task: str,
        context: Optional[str] = None,
        rag_chunks: Optional[List[str]] = None,
        past_examples: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate initial solution."""
        
        # Build system prompt
        system_prompt = (
            "You are Yantra, an expert problem solver. "
            "Produce clear, correct, and efficient solutions following best practices. "
            "Be precise and thorough in your responses."
        )
        
        # Build user prompt
        user_prompt_parts = [f"Task: {task}"]
        
        if rag_chunks:
            user_prompt_parts.append("\n--- Relevant Document Context ---")
            for i, chunk in enumerate(rag_chunks, 1):
                user_prompt_parts.append(f"\n[Chunk {i}]\n{chunk}")
            user_prompt_parts.append(
                "\nIMPORTANT: Base your answer ONLY on the provided document context above. "
                "Do not make unsupported claims."
            )
        
        if past_examples:
            user_prompt_parts.append("\n--- Successful Past Solutions for Similar Tasks ---")
            for i, example in enumerate(past_examples, 1):
                user_prompt_parts.append(f"\n[Example {i}]\n{example}")
            user_prompt_parts.append(
                "\nUse these examples as reference for best practices and patterns."
            )
        
        if context:
            user_prompt_parts.append(f"\n--- Additional Context ---\n{context}")
        
        user_prompt = "\n".join(user_prompt_parts)
        
        # Call Ollama
        response = await self._call_ollama(user_prompt, system_prompt)
        
        return {
            "agent": self.name,
            "output": response,
            "task": task,
            "used_rag": rag_chunks is not None and len(rag_chunks) > 0,
            "used_examples": past_examples is not None and len(past_examples) > 0
        }

