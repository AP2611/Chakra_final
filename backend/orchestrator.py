"""Orchestrator that coordinates all agents in the recursive learning loop."""
from typing import Dict, Any, List, Optional
import asyncio
from agents import Yantra, Sutra, Agni, Smriti
from agents.sutra import SutraOutput
from rag.vector_retriever import VectorRAGRetriever


class Orchestrator:
    """Orchestrates the multi-agent system with recursive learning."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen2.5:1.5b",
        max_iterations: int = 3,
        min_improvement: float = 0.5,
        fast_mode: bool = True
    ):
        # Initialize agents with fast_mode for low latency
        self.yantra = Yantra(ollama_url, model, fast_mode=fast_mode)
        self.sutra = Sutra(ollama_url, model, fast_mode=fast_mode)
        self.agni = Agni(ollama_url, model, fast_mode=fast_mode)
        self.smriti = Smriti()
        self.rag = VectorRAGRetriever()
        self.max_iterations = max_iterations
        self.min_improvement = min_improvement
        self.fast_mode = fast_mode

    async def process(
        self,
        task: str,
        context: Optional[str] = None,
        use_rag: bool = False,
        is_code: bool = True
    ) -> Dict[str, Any]:
        """Process a task through the recursive learning loop."""

        # Strategy 5: Parallel Processing - Run RAG and memory retrieval in parallel
        rag_task = None
        memory_task = None

        if use_rag:
            rag_task = asyncio.create_task(
                asyncio.to_thread(self.rag.retrieve, task, 3)
            )

        memory_task = asyncio.create_task(
            asyncio.to_thread(self.smriti.retrieve_similar, task, 3)
        )

        # Wait for parallel tasks to complete
        rag_chunks = None
        if rag_task:
            rag_chunks = await rag_task

        similar_tasks = await memory_task
        past_examples = []
        if similar_tasks:
            past_examples = [ex["solution"] for ex in similar_tasks]

        iterations = []
        best_score = 0.0
        best_solution = None
        current_solution = None
        previous_composite = None

        for iteration in range(self.max_iterations):
            iteration_data = {
                "iteration": iteration + 1,
                "yantra_output": None,
                "sutra_critique": None,
                "sutra_scores": None,
                "agni_output": None,
                "score": None,
                "raw_composite": None,
                "smoothed": None,
                "improvement": None
            }

            # Step 1: Yantra generates solution
            yantra_result = await self.yantra.process(
                task=task,
                context=context,
                rag_chunks=rag_chunks,
                past_examples=past_examples if iteration == 0 else None  # Only use examples in first iteration
            )
            iteration_data["yantra_output"] = yantra_result["output"]
            current_solution = yantra_result["output"]

            # Step 2: Sutra critiques with structured scoring
            sutra_result: SutraOutput = await self.sutra.process(
                yantra_output=current_solution,
                original_task=task,
                rag_chunks=rag_chunks,
                previous_score=previous_composite
            )
            iteration_data["sutra_critique"] = sutra_result.critique
            iteration_data["sutra_scores"] = sutra_result.scores.model_dump()
            iteration_data["raw_composite"] = sutra_result.raw_composite
            iteration_data["smoothed"] = sutra_result.composite_score != sutra_result.raw_composite

            # Step 3: Agni improves
            agni_result = await self.agni.process(
                original_output=current_solution,
                critique=sutra_result.critique,
                task=task,
                rag_chunks=rag_chunks
            )
            iteration_data["agni_output"] = agni_result["improved_output"]
            current_solution = agni_result["improved_output"]

            # Step 4: Use Sutra's composite score (1-10 scale)
            score = sutra_result.composite_score
            iteration_data["score"] = score

            # Calculate improvement
            if previous_composite is not None:
                improvement = score - previous_composite
                iteration_data["improvement"] = improvement
            else:
                iteration_data["improvement"] = 0.0

            iterations.append(iteration_data)

            # Update best solution
            if score > best_score:
                best_score = score
                best_solution = current_solution

            previous_composite = score

            # Check if we should continue
            if iteration > 0:
                prev_score = iterations[-2]["score"]
                improvement = score - prev_score
                if improvement < self.min_improvement:
                    # Score plateaued, stop
                    break

        # Store best solution in memory (threshold adjusted for 1-10 scale)
        if best_score > 6.0:  # Only store if score is decent
            self.smriti.store(
                task=task,
                solution=best_solution,
                quality_score=best_score / 10.0,  # Normalize to 0-1 for storage compatibility
                metadata={
                    "is_code": is_code,
                    "used_rag": use_rag,
                    "iterations": len(iterations)
                }
            )

        return {
            "task": task,
            "final_solution": best_solution,
            "final_score": best_score,
            "iterations": iterations,
            "total_iterations": len(iterations),
            "used_rag": use_rag,
            "rag_chunks": rag_chunks if use_rag else None
        }
