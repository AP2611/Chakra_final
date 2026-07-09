"""Independent judge for post-hoc evaluation of final solutions.

This module deliberately decouples *scoring* from the recursive loop. The
in-loop Sutra critic is used to *steer* improvement; this ``Judge`` provides a
separate, fixed-rubric assessment of the final artifacts so that the baseline
and the multi-agent system are compared on identical, externally-defined
criteria. Using a distinct model instance and a frozen prompt reduces the
LLM-as-judge circularity that would otherwise inflate the loop's apparent gain.
"""
import json
from typing import Dict, Any, Optional

from agents.base_agent import BaseAgent
from agents.sutra import _parse_json_safe, compute_composite, SutraScores


JUDGE_SYSTEM_PROMPT = (
    "You are an independent evaluator. You are NOT part of the solution "
    "pipeline. Your only job is to score a final solution against a fixed "
    "rubric, consistently and conservatively.\n\n"
    "Rubric (score each dimension 1-10):\n"
    "  correctness: does it actually solve the task and produce correct results?\n"
    "  accuracy: are the factual / technical claims correct?\n"
    "  efficiency: computational and resource efficiency.\n"
    "  clarity: readability, structure, and explanation quality.\n"
    "  edge_case_coverage: handling of boundary and edge inputs.\n"
    "  groundedness: (only if document context is provided) are claims supported?\n\n"
    "Anchor scale: 1-2 = critical failure, 3-4 = major issues, 5-6 = usable "
    "with caveats, 7-8 = solid with minor issues, 9-10 = excellent with no "
    "legitimate issue. Only give 9-10 if you truly cannot find a single issue.\n\n"
    "Respond with a single JSON object and nothing else:\n"
    '{"critique": "<brief justification>", '
    '"scores": {"correctness": <int>, "accuracy": <int>, "efficiency": <int>, '
    '"clarity": <int>, "edge_case_coverage": <int>, "groundedness": <int or null>}}'
)


class Judge(BaseAgent):
    """Separate, fixed-rubric evaluator applied identically to all systems."""

    def __init__(self, ollama_url: str = "http://localhost:11434",
                 model: str = "mistral:latest", fast_mode: bool = False):
        super().__init__("Judge", ollama_url, model, fast_mode=fast_mode)

    async def score(
        self,
        task: str,
        solution: str,
        rag_chunks: Optional[list] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Score a final solution. Returns a dict with ``score`` (1-10 composite)."""
        if not solution or not solution.strip():
            return {
                "score": 0.0, "raw_composite": 0.0, "scores": {},
                "critique": "empty solution", "ok": False,
            }

        parts = [f"Task: {task}", f"\n--- Final Solution ---\n{solution}"]
        if rag_chunks:
            parts.append("\n--- Document Context (for groundedness) ---")
            for i, chunk in enumerate(rag_chunks, 1):
                parts.append(f"\n[Chunk {i}]\n{chunk}")
        parts.append("\nScore this final solution against the rubric.")
        user_prompt = "\n".join(parts)

        last_err = None
        for _ in range(3):
            try:
                raw = await self._call_ollama(
                    user_prompt, JUDGE_SYSTEM_PROMPT, temperature=temperature
                )
                parsed = _parse_json_safe(raw)
                scores = SutraScores(**parsed["scores"])
                composite = compute_composite(scores)
                return {
                    "score": composite,
                    "raw_composite": composite,
                    "scores": scores.model_dump(),
                    "critique": parsed.get("critique", ""),
                    "ok": True,
                }
            except Exception as e:  # transient API / parse failure
                last_err = e
                continue
        return {
            "score": None, "raw_composite": None, "scores": {},
            "critique": f"judge failed: {last_err}", "ok": False,
        }
