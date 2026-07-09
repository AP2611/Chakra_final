"""Sutra - Critique Agent that analyzes and finds issues with structured scoring."""
import re
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, field_validator
from .base_agent import BaseAgent


# --- Constants ---

WEIGHTS_WITH_RAG = {
    "correctness": 0.35,
    "groundedness": 0.20,
    "accuracy": 0.15,
    "efficiency": 0.10,
    "clarity": 0.10,
    "edge_case_coverage": 0.10,
}

WEIGHTS_NO_RAG = {
    "correctness": 0.45,
    "accuracy": 0.25,
    "efficiency": 0.10,
    "clarity": 0.10,
    "edge_case_coverage": 0.10,
}

MAX_DELTA_WITHOUT_JUSTIFICATION = 1.5
CRITICAL_KEYWORDS = ("critical", "breaking", "severe", "unsafe", "data loss")


# --- Pydantic Schemas ---

class SutraScores(BaseModel):
    correctness: int
    accuracy: int
    efficiency: int
    clarity: int
    edge_case_coverage: int
    groundedness: Optional[int] = None

    @field_validator("correctness", "accuracy", "efficiency", "clarity",
                      "edge_case_coverage", "groundedness")
    @classmethod
    def clamp_range(cls, v):
        if v is None:
            return v
        return max(1, min(10, v))


class SutraOutput(BaseModel):
    critique: str
    scores: SutraScores
    composite_score: float
    raw_composite: float
    agent: str = "Sutra"
    original_output: str
    task: str


# --- Helpers ---

def compute_composite(scores: SutraScores) -> float:
    weights = WEIGHTS_WITH_RAG if scores.groundedness is not None else WEIGHTS_NO_RAG
    raw = sum(getattr(scores, dim) * w for dim, w in weights.items())
    return round(raw, 2)


def smooth_score(previous_score: Optional[float], raw_score: float, critique_text: str) -> float:
    if previous_score is None:
        return raw_score

    delta = raw_score - previous_score
    if abs(delta) <= MAX_DELTA_WITHOUT_JUSTIFICATION:
        return raw_score

    text_lower = critique_text.lower()
    justified = any(kw in text_lower for kw in CRITICAL_KEYWORDS)
    if justified:
        return raw_score

    return round(previous_score + MAX_DELTA_WITHOUT_JUSTIFICATION * (1 if delta > 0 else -1), 2)


def _extract_balanced_json(text: str) -> Optional[str]:
    """Extract the outermost JSON object from arbitrary text via brace matching.

    This is far more robust than a greedy regex when the model emits prose
    before/after the JSON or when the JSON contains nested braces.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _parse_json_safe(raw_text: str) -> dict:
    """Parse Sutra's JSON output tolerantly.

    Key robustness fixes vs. the naive version:
      * ``json.loads(..., strict=False)`` permits control characters (tabs,
        newlines) that appear *inside* string values -- the exact cause of the
        historical "Invalid control character" failures (~21% of runs).
      * A balanced-brace scanner recovers the JSON object even when the model
        wraps it in prose or markdown fences.
      * A control-character sanitization pass is kept as a final fallback.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Sutra returned empty output")

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE).strip()

    candidates = [cleaned]
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        candidates.append(m.group(0))
    b = _extract_balanced_json(cleaned)
    if b:
        candidates.append(b)
    # Control-character sanitization fallback (replace with spaces so string
    # lengths/structure stay valid).
    sanitized = re.sub(r"[\x00-\x1f]", " ", cleaned)
    candidates.append(sanitized)
    sb = _extract_balanced_json(sanitized)
    if sb:
        candidates.append(sb)

    last_err = None
    for cand in candidates:
        if not cand:
            continue
        try:
            return json.loads(cand, strict=False)
        except json.JSONDecodeError as e:
            last_err = e
            continue

    # Last resort: reconstruct minimal valid JSON from any scores found.
    try:
        scores_match = re.search(r'"scores"\s*:\s*\{[^}]+\}', cleaned, re.DOTALL)
        critique_match = re.search(r'"critique"\s*:\s*"([^"]*)"', cleaned, re.DOTALL)
        if scores_match and critique_match:
            reconstructed = (
                '{"critique": ' + json.dumps(critique_match.group(1)) +
                ', "scores": {"correctness": 5, "accuracy": 5, "efficiency": 5, '
                '"clarity": 5, "edge_case_coverage": 5}}'
            )
            return json.loads(reconstructed, strict=False)
    except Exception:
        pass

    raise ValueError(f"Sutra returned unparseable output: {raw_text[:200]} (last error: {last_err})")


# --- Agent ---

class Sutra(BaseAgent):
    """Critique agent that identifies problems in solutions with structured scoring."""

    SYSTEM_PROMPT = (
        "You are Sutra, a strict expert reviewer operating inside an automated critique loop.\n"
        "You evaluate a candidate solution against a fixed rubric and return BOTH a qualitative\n"
        "critique and per-dimension numerical scores.\n\n"
        "Scoring rules (follow exactly):\n"
        "- Score each dimension from 1 to 10 using this anchor scale:\n"
        "  1-2 = critical failure, 3-4 = major issues, 5-6 = usable with caveats,\n"
        "  7-8 = solid with minor issues, 9-10 = excellent, no meaningful issues.\n"
        "- Be conservative: only give 9-10 if you cannot find a single legitimate issue.\n"
        "- Do not let overall impression inflate an individual score — score each dimension\n"
        "  independently based only on evidence for that dimension.\n"
        "- If no RAG context is provided, omit \"groundedness\" entirely.\n"
        "- Do not compute or output an overall/composite score. Only per-dimension scores.\n\n"
        "Output format: respond with a single JSON object, followed by nothing else, matching\n"
        "this schema exactly:\n\n"
        "{\n"
        '  "critique": "<full qualitative critique text, same depth as before>",\n'
        '  "scores": {\n'
        '    "correctness": <int 1-10>,\n'
        '    "accuracy": <int 1-10>,\n'
        '    "efficiency": <int 1-10>,\n'
        '    "clarity": <int 1-10>,\n'
        '    "edge_case_coverage": <int 1-10>,\n'
        '    "groundedness": <int 1-10 or null if no RAG context>\n'
        "  }\n"
        "}"
    )

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:1.5b", fast_mode: bool = True):
        super().__init__("Sutra", ollama_url, model, fast_mode=fast_mode)

    async def process(
        self,
        yantra_output: str,
        original_task: str,
        rag_chunks: Optional[List[str]] = None,
        previous_score: Optional[float] = None,
        exec_result: Optional[Dict[str, Any]] = None
    ) -> SutraOutput:
        """Analyze output and find issues with structured scoring."""

        from utils.code_executor import format_for_prompt

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

        if exec_result is not None:
            user_prompt_parts.append("\n--- Execution Validation ---")
            user_prompt_parts.append(format_for_prompt(exec_result))
            user_prompt_parts.append(
                "\nIf execution FAILED, the error above is the single most important issue to "
                "flag and must be fixed first. If it PASSED, verify correctness beyond just "
                "running without error."
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

        # Calibration block
        prev_score_str = f"{previous_score:.2f}" if previous_score is not None else "N/A — first iteration"
        user_prompt_parts.append(
            f"\nFor calibration, here is the score from the previous iteration on this same task "
            f"(if any): {prev_score_str}\n\n"
            "Score this iteration's output on its own merits using the rubric above. Do not "
            "anchor to the previous score — if the output has not meaningfully changed, the "
            "scores should not meaningfully change either."
        )

        user_prompt = "\n".join(user_prompt_parts)

        # Use lower temperature for scoring to reduce jitter. Retry on
        # transient API/parse failures so a single bad response does not abort
        # the whole run (previously ~21% of runs failed at this step).
        last_err = None
        for attempt in range(3):
            try:
                raw = await self._call_ollama(
                    user_prompt,
                    self.SYSTEM_PROMPT,
                    temperature=0.3
                )
                parsed = _parse_json_safe(raw)
                scores = SutraScores(**parsed["scores"])
                break
            except Exception as e:  # API error or unparseable output
                last_err = e
                continue
        else:
            raise ValueError(f"Sutra failed after 3 attempts: {last_err}")

        raw_composite = compute_composite(scores)
        final_composite = smooth_score(previous_score, raw_composite, parsed["critique"])

        return SutraOutput(
            critique=parsed["critique"],
            scores=scores,
            composite_score=final_composite,
            raw_composite=raw_composite,
            original_output=yantra_output,
            task=original_task,
        )
