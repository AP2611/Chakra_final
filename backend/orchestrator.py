"""Orchestrator that coordinates all agents in the recursive learning loop.

Paper-ready loop semantics (fixed):
- Iteration 0 produces a fresh Yantra draft. Iteration N>0 *refines* the
  previous iteration's Agni output (Yantra receives the previous solution +
  critique) instead of regenerating from scratch.
- Each full iteration is: candidate generation -> Sutra critique ->
  Agni improvement -> Sutra re-scoring of the improved output. The
  iteration ``score`` is the *post-improvement* score, so the stored score
  and ``final_solution`` are correctly paired (previously the pre-improvement
  score was paired with the post-improvement text).
- ``shared_rag_chunks`` lets the experiment harness inject pre-retrieved
  chunks so baselines and loop see identical context (fairness).

Memory / reproducibility policy (paper-ready):
- ``memory_policy="disabled"`` (experiment default): Smriti is neither
  retrieved nor written, so every condition sees identical (empty) memory
  and seeds cannot contaminate each other. Baselines never use Smriti, so
  the baseline-vs-loop comparison is not confounded by memory leakage.
- ``memory_policy="frozen"``: retrieve from an existing snapshot but never
  write (demonstrates retrieval without online learning).
- ``memory_policy="enabled"``: full online learning (retrieve + store);
  for interactive use, not for paper numbers.
The experiment harness additionally backs up and clears ``memory.db``
before a final run (see ``run_experiment.backup_and_clear_memory``).
LLM seeds are propagated via :meth:`set_seed` (Ollama ``seed`` option) so
``EXPERIMENT_CONFIG["seeds"]`` controls sampling, not just task order.
"""
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
        fast_mode: bool = True,
        memory_policy: str = "enabled",
        seed: Optional[int] = None,
    ):
        # Allow splitting models: a weaker generator (Yantra) creates headroom
        # for the critique/improve loop to demonstrate measurable gains.
        self.generator_model = generator_model or model
        self.critic_model = critic_model or model

        # Initialize agents with fast_mode for low latency
        self.yantra = Yantra(ollama_url, self.generator_model, fast_mode=fast_mode)
        self.sutra = Sutra(ollama_url, self.critic_model, fast_mode=fast_mode)
        self.agni = Agni(ollama_url, self.critic_model, fast_mode=fast_mode)
        if memory_policy not in ("enabled", "frozen", "disabled"):
            raise ValueError(f"unknown memory_policy {memory_policy!r}")
        self.memory_policy = memory_policy
        self.smriti = Smriti()
        self._rag = None
        self.max_iterations = max_iterations
        self.min_improvement = min_improvement
        self.fast_mode = fast_mode
        self.base_seed = seed
        self.set_seed(seed)

    @property
    def memory_enabled(self) -> bool:
        """True unless memory retrieval/storage is disabled (fairness)."""
        return self.memory_policy != "disabled"

    @property
    def memory_writable(self) -> bool:
        """True only for online learning (``enabled``)."""
        return self.memory_policy == "enabled"

    def set_seed(self, seed: Optional[int]):
        """Propagate a base seed to every agent (Ollama ``seed`` option).

        Each agent gets a distinct offset so sampling patterns differ per
        role while remaining deterministic for a given base seed.
        Iteration-level variation is handled in :meth:`process_stream`
        by re-seeding Yantra with ``base + iteration``.
        """
        self.base_seed = seed
        if seed is None:
            for agent in (self.yantra, self.sutra, self.agni):
                agent.set_seed(None)
            return
        self.yantra.set_seed(seed)
        self.sutra.set_seed(seed + 1)
        self.agni.set_seed(seed + 2)

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
        validate_code: bool = True,
        mode: str = "full",
        shared_rag_chunks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Process a task through the recursive learning loop (non-streaming).

        Delegates to :meth:`process_stream` and returns the final aggregated
        result, so streaming and non-streaming paths share identical logic.

        mode: "full" (Yantra->Sutra->Agni, recursively refined), "agni_only"
        (Yantra->Agni with generic prompt; Sutra used for measurement only),
        "sutra_only" (Yantra->Sutra, no Agni; single pass).
        """
        final = None
        async for event in self.process_stream(
            task=task, context=context, use_rag=use_rag,
            is_code=is_code, validate_code=validate_code, mode=mode,
            shared_rag_chunks=shared_rag_chunks,
        ):
            if event.get("type") == "end":
                final = event

        if final is None:
            return {
                "task": task, "final_solution": None, "final_score": 0.0,
                "iterations": [], "total_iterations": 0,
                "used_rag": use_rag, "rag_chunks": None, "mode": mode
            }
        final["mode"] = mode
        return final

    async def process_stream(
        self,
        task: str,
        context: Optional[str] = None,
        use_rag: bool = False,
        is_code: bool = True,
        validate_code: bool = True,
        mode: str = "full",
        shared_rag_chunks: Optional[List[str]] = None,
    ):
        """Stream the recursive learning loop as SSE-style events.

        This is the SINGLE SOURCE OF TRUTH for the agent loop. The REST API
        wraps this generator into Server-Sent Events, so streaming and
        non-streaming paths share identical logic (fixes, recovery, validation).

        mode: "full" (Yantra->Sutra->Agni, recursively refined, post-improvement
        re-scored), "agni_only" (Yantra->Agni with a generic prompt; Sutra
        still scores pre/post for measurement), "sutra_only"
        (Yantra->Sutra, no Agni; single pass).
        """
        from utils.code_executor import extract_code, execute_code

        # Reset per-run token accounting
        self.yantra.reset_token_stats()
        self.sutra.reset_token_stats()
        self.agni.reset_token_stats()

        # Parallel RAG + memory retrieval.
        # If the harness supplies shared chunks, use them verbatim so every
        # condition (baselines + loop) is evaluated against identical context.
        if shared_rag_chunks is not None:
            rag_chunks = list(shared_rag_chunks) if shared_rag_chunks else None
            rag_task = None
        elif use_rag:
            rag_task = asyncio.create_task(
                asyncio.to_thread(self.rag.retrieve, task, 3)
            )
        else:
            rag_task = None
        memory_task = None
        if self.memory_enabled:
            memory_task = asyncio.create_task(
                asyncio.to_thread(self.smriti.retrieve_similar, task, 3)
            )

        if shared_rag_chunks is not None:
            pass  # rag_chunks already set
        elif rag_task is not None:
            rag_chunks = await rag_task
        else:
            rag_chunks = None
        similar_tasks = []
        past_examples = []
        if self.memory_enabled:
            similar_tasks = await memory_task
            past_examples = [ex["solution"] for ex in similar_tasks] if similar_tasks else []
        elif memory_task is not None:
            # Drain retrieval result without using it (disabled policy).
            try:
                await memory_task
            except Exception:
                pass

        yield {"type": "start", "message": "Starting task processing..."}
        if use_rag and rag_chunks:
            yield {"type": "rag_retrieved", "chunks_count": len(rag_chunks)}
        if similar_tasks:
            yield {"type": "memory_found", "examples_count": len(similar_tasks)}

        iterations = []
        best_score = 0.0
        best_solution = None
        current_solution = None
        previous_improved: Optional[str] = None
        previous_critique: Optional[str] = None
        previous_composite: Optional[float] = None  # last *post-improvement* score

        for iteration in range(self.max_iterations):
            iteration_data = {
                "iteration": iteration + 1,
                "yantra_output": None,
                "sutra_critique": None,
                "sutra_scores": None,
                "pre_critique": None,
                "pre_scores": None,
                "pre_score": None,
                "post_critique": None,
                "post_scores": None,
                "agni_output": None,
                "score": None,
                "raw_composite": None,
                "smoothed": None,
                "improvement": None,
            }

            yield {"type": "iteration_start", "iteration": iteration + 1}
            yield {"type": "first_response_started"}

            try:
                # Deterministic per-iteration seed variation for reproducibility.
                if self.base_seed is not None:
                    self.yantra.set_seed(self.base_seed + iteration * 10)
                    self.sutra.set_seed(self.base_seed + iteration * 10 + 1)
                    self.agni.set_seed(self.base_seed + iteration * 10 + 2)

                # Step 1: Yantra generates candidate.
                # Iteration 0: fresh draft. Iteration N>0: refine the previous
                # Agni output using the previous critique (true recursion).
                is_refine = iteration > 0 and previous_improved is not None
                if is_refine:
                    system_prompt = (
                        "You are Yantra, an expert problem solver. "
                        "You are refining a previous attempt: preserve everything that "
                        "is already correct, apply the critique, and fix every "
                        "identified defect. Produce clear, correct, and efficient "
                        "solutions following best practices."
                    )
                else:
                    system_prompt = (
                        "You are Yantra, an expert problem solver. "
                        "Produce clear, correct, and efficient solutions following best practices. "
                        "Be precise and thorough in your responses."
                    )
                user_prompt_parts = [f"Task: {task}"]
                if is_refine:
                    user_prompt_parts.append(
                        f"\n--- Previous Attempt (prior improved solution) ---\n{previous_improved}"
                    )
                    if previous_critique:
                        user_prompt_parts.append(
                            f"\n--- Critique to Address ---\n{previous_critique}"
                        )
                    user_prompt_parts.append(
                        "\nRefine this attempt: keep correct parts, fix every "
                        "issue from the critique. Do not start from scratch."
                    )
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
                candidate = yantra_output

                # Optional execution validation for code tasks (on the candidate)
                exec_result = None
                if is_code and validate_code:
                    code = extract_code(candidate)
                    if code:
                        exec_result = execute_code(code)
                        status = "passed" if exec_result["success"] else "failed"
                        yield {"type": "validation", "iteration": iteration + 1,
                               "status": status, "detail": exec_result.get("error")}

                # Step 2: Sutra critiques the candidate (steering signal)
                yield {"type": "sutra_started", "iteration": iteration + 1}
                sutra_result: SutraOutput = await self.sutra.process(
                    yantra_output=candidate,
                    original_task=task,
                    rag_chunks=rag_chunks,
                    previous_score=previous_composite,
                    exec_result=exec_result
                )
                iteration_data["pre_critique"] = sutra_result.critique
                iteration_data["pre_scores"] = sutra_result.scores.model_dump()
                iteration_data["pre_score"] = sutra_result.composite_score

                yield {"type": "first_response_complete", "iteration": iteration + 1}

                # Step 3: Agni improves (diff-based, execution-aware) — mode-dependent
                if mode == "sutra_only":
                    # Critique is computed but never applied; return candidate as-is.
                    iteration_data["agni_output"] = None
                    iteration_data["sutra_critique"] = sutra_result.critique
                    iteration_data["sutra_scores"] = sutra_result.scores.model_dump()
                    iteration_data["raw_composite"] = sutra_result.raw_composite
                    iteration_data["smoothed"] = sutra_result.composite_score != sutra_result.raw_composite
                    current_solution = candidate
                    yield {"type": "improved", "iteration": iteration + 1,
                           "improved_output": current_solution, "solution": current_solution,
                           "token_count": 0}
                    score = sutra_result.composite_score
                else:
                    yield {"type": "improving_started", "iteration": iteration + 1}
                    # In agni_only mode, Agni gets a generic prompt (critique not used to steer)
                    agni_critique = sutra_result.critique if mode == "full" else \
                        "Please improve this solution for correctness, efficiency, and clarity."
                    agni_result = await self.agni.process(
                        original_output=candidate,
                        critique=agni_critique,
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

                    # Step 4: Re-score the *improved* output so the iteration
                    # score correctly pairs with final_solution. Falls back to
                    # the pre-score if re-scoring fails.
                    yield {"type": "rescoring_started", "iteration": iteration + 1}
                    post_exec = None
                    if is_code and validate_code:
                        code2 = extract_code(current_solution)
                        if code2:
                            post_exec = execute_code(code2)
                    try:
                        post_result: SutraOutput = await self.sutra.process(
                            yantra_output=current_solution,
                            original_task=task,
                            rag_chunks=rag_chunks,
                            previous_score=sutra_result.composite_score,
                            exec_result=post_exec,
                        )
                        iteration_data["post_critique"] = post_result.critique
                        iteration_data["post_scores"] = post_result.scores.model_dump()
                        iteration_data["sutra_critique"] = post_result.critique
                        iteration_data["sutra_scores"] = post_result.scores.model_dump()
                        iteration_data["raw_composite"] = post_result.raw_composite
                        iteration_data["smoothed"] = post_result.composite_score != post_result.raw_composite
                        score = post_result.composite_score
                    except Exception as rescore_err:
                        iteration_data["sutra_critique"] = sutra_result.critique
                        iteration_data["sutra_scores"] = sutra_result.scores.model_dump()
                        iteration_data["raw_composite"] = sutra_result.raw_composite
                        iteration_data["smoothed"] = sutra_result.composite_score != sutra_result.raw_composite
                        iteration_data["post_critique"] = f"[rescore failed: {rescore_err}]"
                        score = sutra_result.composite_score

                iteration_data["score"] = score
                iteration_data["improvement"] = (
                    score - previous_composite if previous_composite is not None else 0.0
                )

                iterations.append(iteration_data)

                if score > best_score:
                    best_score = score
                    best_solution = current_solution
                previous_improved = current_solution
                previous_critique = iteration_data.get("sutra_critique")
                previous_composite = score

                # sutra_only is a single pass (critique computed but not applied)
                if mode == "sutra_only":
                    yield {"type": "iteration_complete", "iteration": iteration + 1, "data": iteration_data}
                    break

                yield {"type": "iteration_complete", "iteration": iteration + 1, "data": iteration_data}

                # Stopping conditions (on post-improvement scores)
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
                # Recover: if this iteration produced a Yantra candidate
                # (even before Agni ran), keep it as the current solution so
                # the run still returns a scoreable artifact instead of
                # losing the whole record.
                if current_solution is None and iteration_data.get("yantra_output"):
                    current_solution = iteration_data["yantra_output"]
                if current_solution is not None:
                    iterations.append(iteration_data)
                    score = previous_composite if previous_composite is not None else 5.0
                    # Only fill a score if the iteration actually produced one.
                    if iteration_data.get("score") is None:
                        iteration_data["score"] = score
                    else:
                        score = iteration_data["score"]
                    iteration_data["improvement"] = 0.0
                    iteration_data["error"] = str(e)
                    previous_composite = score
                    if best_solution is None:
                        best_solution = current_solution
                        best_score = score
                    yield {"type": "iteration_complete", "iteration": iteration + 1, "data": iteration_data}
                    continue
                else:
                    yield {"type": "error", "message": str(e)}
                    return

        # If best_solution was never set (all scores lost), fall back to the
        # last current_solution so we still return something scoreable.
        if best_solution is None and current_solution is not None:
            best_solution = current_solution
            best_score = previous_composite if previous_composite is not None else best_score

        # Store best solution in memory — only under online-learning policy.
        if self.memory_writable and best_score > 6.0 and best_solution is not None:
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

        # Aggregate token usage across agents for this run
        total_tokens = (
            self.yantra.token_stats["total"]
            + self.sutra.token_stats["total"]
            + self.agni.token_stats["total"]
        )

        yield {
            "type": "end",
            "task": task,
            "final_solution": best_solution,
            "final_score": best_score,
            "iterations": iterations,
            "total_iterations": len(iterations),
            "used_rag": use_rag,
            "rag_chunks": rag_chunks if use_rag else None,
            "mode": mode,
            "total_tokens": total_tokens,
            "token_stats": {
                "yantra": dict(self.yantra.token_stats),
                "sutra": dict(self.sutra.token_stats),
                "agni": dict(self.agni.token_stats),
            }
        }
