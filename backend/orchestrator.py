"""Orchestrator that coordinates all agents in the recursive learning loop."""
from typing import Dict, Any, List, Optional
import asyncio
from agents import Yantra, Sutra, Agni, Smriti
from agents.sutra import SutraOutput


class Orchestrator:
    """Orchestrates the multi-agent system with recursive learning."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen2.5:1.5b",
        generator_model: Optional[str] = None,
        critic_model: Optional[str] = None,
        max_iterations: int = 3,
        min_improvement: float = 0.5,
        fast_mode: bool = True
    ):
        # Allow splitting models: a weaker generator (Yantra) creates headroom
        # for the critique/improve loop to demonstrate measurable gains.
        self.generator_model = generator_model or model
        self.critic_model = critic_model or model

        # Initialize agents with fast_mode for low latency
        self.yantra = Yantra(ollama_url, self.generator_model, fast_mode=fast_mode)
        self.sutra = Sutra(ollama_url, self.critic_model, fast_mode=fast_mode)
        self.agni = Agni(ollama_url, self.critic_model, fast_mode=fast_mode)
        self.smriti = Smriti()
        self._rag = None
        self.max_iterations = max_iterations
        self.min_improvement = min_improvement
        self.fast_mode = fast_mode

    @property
    def rag(self):
        """Lazy-load RAG retriever only when needed to avoid heavy imports at startup.

        Falls back to a lightweight TF-IDF retriever if the heavy vector
        dependencies (sentence-transformers / chromadb) are unavailable.
        """
        if self._rag is None:
            from rag.vector_retriever import VectorRAGRetriever
            self._rag = VectorRAGRetriever()
        return self._rag

    async def process(
        self,
        task: str,
        context: Optional[str] = None,
        use_rag: bool = False,
        is_code: bool = True,
        validate_code: bool = True
    ) -> Dict[str, Any]:
        """Process a task through the recursive learning loop (non-streaming).

        Delegates to :meth:`process_stream` and returns the final aggregated
        result, so streaming and non-streaming paths share identical logic.
        """
        final = None
        async for event in self.process_stream(
            task=task, context=context, use_rag=use_rag,
            is_code=is_code, validate_code=validate_code
        ):
            if event.get("type") == "end":
                final = event

        if final is None:
            return {
                "task": task, "final_solution": None, "final_score": 0.0,
                "iterations": [], "total_iterations": 0,
                "used_rag": use_rag, "rag_chunks": None
            }
        return {
            "task": final["task"],
            "final_solution": final["final_solution"],
            "final_score": final["final_score"],
            "iterations": final["iterations"],
            "total_iterations": final["total_iterations"],
            "used_rag": final["used_rag"],
            "rag_chunks": final.get("rag_chunks"),
        }

    async def process_stream(
        self,
        task: str,
        context: Optional[str] = None,
        use_rag: bool = False,
        is_code: bool = True,
        validate_code: bool = True
    ):
        """Stream the recursive learning loop as SSE-style events.

        This is the SINGLE SOURCE OF TRUTH for the agent loop. The REST API
        wraps this generator into Server-Sent Events, so streaming and
        non-streaming paths share identical logic (fixes, recovery, validation).
        """
        from utils.code_executor import extract_code, execute_code

        # Parallel RAG + memory retrieval
        rag_task = None
        if use_rag:
            rag_task = asyncio.create_task(
                asyncio.to_thread(self.rag.retrieve, task, 3)
            )
        memory_task = asyncio.create_task(
            asyncio.to_thread(self.smriti.retrieve_similar, task, 3)
        )

        rag_chunks = (await rag_task) if rag_task else None
        similar_tasks = await memory_task
        past_examples = [ex["solution"] for ex in similar_tasks] if similar_tasks else []

        yield {"type": "start", "message": "Starting task processing..."}
        if use_rag and rag_chunks:
            yield {"type": "rag_retrieved", "chunks_count": len(rag_chunks)}
        if similar_tasks:
            yield {"type": "memory_found", "examples_count": len(similar_tasks)}

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
                "improvement": None,
            }

            yield {"type": "iteration_start", "iteration": iteration + 1}
            yield {"type": "first_response_started"}

            try:
                # Step 1: Yantra generates solution (streamed tokens)
                system_prompt = (
                    "You are Yantra, an expert problem solver. "
                    "Produce clear, correct, and efficient solutions following best practices. "
                    "Be precise and thorough in your responses."
                )
                user_prompt_parts = [f"Task: {task}"]
                if rag_chunks:
                    user_prompt_parts.append("\n--- Relevant Document Context ---")
                    for i, chunk in enumerate(rag_chunks, 1):
                        user_prompt_parts.append(f"\n[Chunk {i}]\n{chunk}")
                if past_examples and iteration == 0:
                    user_prompt_parts.append("\n--- Successful Past Solutions for Similar Tasks ---")
                    for i, example in enumerate(past_examples, 1):
                        user_prompt_parts.append(f"\n[Example {i}]\n{example}")
                if context:
                    user_prompt_parts.append(f"\n--- Additional Context ---\n{context}")
                user_prompt = "\n".join(user_prompt_parts)

                token_limit = 512 if self.fast_mode else 1024
                if is_code:
                    token_limit = 384 if self.fast_mode else 640

                yantra_output = ""
                token_count = 0
                async for token in self.yantra._call_ollama_stream(
                    user_prompt, system_prompt, max_tokens=token_limit
                ):
                    yantra_output += token
                    token_count += 1
                    yield {"type": "token", "token": token, "token_count": token_count, "iteration": iteration + 1}

                yantra_output = yantra_output.strip()
                iteration_data["yantra_output"] = yantra_output
                current_solution = yantra_output

                # Optional execution validation for code tasks
                exec_result = None
                if is_code and validate_code:
                    code = extract_code(current_solution)
                    if code:
                        exec_result = execute_code(code)
                        status = "passed" if exec_result["success"] else "failed"
                        yield {"type": "validation", "iteration": iteration + 1,
                               "status": status, "detail": exec_result.get("error")}

                # Step 2: Sutra critiques with structured scoring
                yield {"type": "sutra_started", "iteration": iteration + 1}
                sutra_result: SutraOutput = await self.sutra.process(
                    yantra_output=current_solution,
                    original_task=task,
                    rag_chunks=rag_chunks,
                    previous_score=previous_composite,
                    exec_result=exec_result
                )
                iteration_data["sutra_critique"] = sutra_result.critique
                iteration_data["sutra_scores"] = sutra_result.scores.model_dump()
                iteration_data["raw_composite"] = sutra_result.raw_composite
                iteration_data["smoothed"] = sutra_result.composite_score != sutra_result.raw_composite

                yield {"type": "first_response_complete", "iteration": iteration + 1}

                # Step 3: Agni improves (diff-based, execution-aware)
                yield {"type": "improving_started", "iteration": iteration + 1}
                agni_result = await self.agni.process(
                    original_output=current_solution,
                    critique=sutra_result.critique,
                    task=task,
                    rag_chunks=rag_chunks,
                    exec_result=exec_result
                )
                agni_output = agni_result["improved_output"].strip()
                iteration_data["agni_output"] = agni_output
                current_solution = agni_output

                improved_token_count = len(agni_output.split())
                yield {"type": "improved_token", "token": agni_output,
                       "iteration": iteration + 1, "token_count": improved_token_count}
                yield {"type": "improved", "iteration": iteration + 1,
                       "improved_output": current_solution, "solution": current_solution,
                       "token_count": improved_token_count}

                # Step 4: Use Sutra's composite score (1-10 scale)
                score = sutra_result.composite_score
                iteration_data["score"] = score
                iteration_data["improvement"] = (
                    score - previous_composite if previous_composite is not None else 0.0
                )

                iterations.append(iteration_data)

                if score > best_score:
                    best_score = score
                    best_solution = current_solution
                previous_composite = score

                yield {"type": "iteration_complete", "iteration": iteration + 1, "data": iteration_data}

                # Stopping conditions
                if iteration > 0:
                    improvement = score - iterations[-2]["score"]
                    if improvement < -1.0:
                        yield {"type": "plateau_reached",
                               "message": f"Score degraded by {abs(improvement):.2f}, stopping early"}
                        break
                    if improvement < self.min_improvement:
                        yield {"type": "plateau_reached",
                               "message": f"Score improvement ({improvement:.2f}) below minimum threshold ({self.min_improvement:.2f})"}
                        break

            except Exception as e:
                yield {"type": "iteration_error", "iteration": iteration + 1, "message": str(e)}
                if current_solution is not None:
                    iterations.append(iteration_data)
                    score = previous_composite if previous_composite is not None else 5.0
                    iteration_data["score"] = score
                    iteration_data["improvement"] = 0.0
                    iteration_data["error"] = str(e)
                    previous_composite = score
                    yield {"type": "iteration_complete", "iteration": iteration + 1, "data": iteration_data}
                    continue
                else:
                    yield {"type": "error", "message": str(e)}
                    return

        # Store best solution in memory (threshold adjusted for 1-10 scale)
        if best_score > 6.0 and best_solution is not None:
            self.smriti.store(
                task=task,
                solution=best_solution,
                quality_score=best_score / 10.0,
                metadata={
                    "is_code": is_code,
                    "used_rag": use_rag,
                    "iterations": len(iterations)
                }
            )

        yield {
            "type": "end",
            "task": task,
            "final_solution": best_solution,
            "final_score": best_score,
            "iterations": iterations,
            "total_iterations": len(iterations),
            "used_rag": use_rag,
            "rag_chunks": rag_chunks if use_rag else None
        }
