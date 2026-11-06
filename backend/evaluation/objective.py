"""Objective, execution-based evaluation metrics.

These metrics do not depend on an LLM judge and therefore provide an
independent signal of quality -- especially for code tasks: does the generated
code actually run, and (optionally) does it pass reference test cases?

Paper metrics reported from this module:
- **Execution success rate**: fraction of code solutions that run (and, when
  reference ``tests`` are provided, pass them). Primary non-circular signal
  that the loop fixes broken/hallucinated code.
- **Lexical groundedness** (RAG proxy): fraction of answer sentences sharing
  content words with retrieved chunks. A cheap, LLM-free hallucination
  proxy; the LLM judge's ``groundedness`` dimension is the richer signal.
"""
import os
import re
import sys
import json
import tempfile
import subprocess
from typing import Dict, Any, Optional

from utils.code_executor import extract_code, execute_code


def _count_test_lines(tests: Optional[str]) -> int:
    if not tests:
        return 0
    return sum(1 for line in tests.splitlines() if line.strip().startswith("assert"))


def run_tests(code: str, tests: Optional[str] = None,
              timeout: float = 10.0) -> Dict[str, Any]:
    """Execute generated code, optionally followed by a reference test snippet.

    Returns a dict with: runs (bool), tests_run (int), tests_passed (int),
    score (0-1), stdout, stderr, error.

    When ``tests`` is provided, ``tests_run`` is the number of ``assert``
    lines and ``tests_passed`` is all-or-nothing (all asserts pass iff the
    subprocess exits 0), because asserts abort on first failure.
    """
    if not code:
        return {"runs": False, "tests_run": 0, "tests_passed": 0, "score": 0.0,
                "stdout": "", "stderr": "", "error": "no_code"}

    n_tests = _count_test_lines(tests)

    fd, path = tempfile.mkstemp(suffix=".py", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)
            if tests:
                f.write("\n\n# --- Reference tests ---\n")
                f.write(tests)

        try:
            result = subprocess.run(
                [sys.executable, path], capture_output=True, text=True, timeout=timeout
            )
            runs = result.returncode == 0
            if tests:
                return {
                    "runs": runs,
                    "tests_run": n_tests,
                    "tests_passed": n_tests if runs else 0,
                    "score": 1.0 if runs else 0.0,
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:2000],
                    "error": None if runs else (result.stderr or "execution failed")[:500],
                }
            return {
                "runs": runs,
                "tests_run": 0,
                "tests_passed": 0,
                "score": 1.0 if runs else 0.0,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:2000],
                "error": None if runs else (result.stderr or "execution failed")[:500],
            }
        except subprocess.TimeoutExpired:
            return {"runs": False, "tests_run": n_tests, "tests_passed": 0, "score": 0.0,
                    "stdout": "", "stderr": "", "error": "timeout"}
        except Exception as e:  # pragma: no cover - defensive
            return {"runs": False, "tests_run": n_tests, "tests_passed": 0, "score": 0.0,
                    "stdout": "", "stderr": "", "error": str(e)[:500]}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def objective_code_score(solution: str, tests: Optional[str] = None) -> Dict[str, Any]:
    """Extract code from a solution and run objective checks.

    If no fenced code block is found, the whole solution is treated as code.
    """
    code = extract_code(solution)
    if not code:
        code = solution
    return run_tests(code, tests)


_STOPWORDS = {
    "a", "an", "the", "to", "of", "in", "for", "and", "or", "is", "are",
    "it", "on", "as", "be", "that", "this", "by", "with", "from", "not",
}


def lexical_groundedness(answer: str, rag_chunks: Optional[list] = None) -> Dict[str, Any]:
    """LLM-free hallucination proxy for RAG answers.

    Splits the answer into sentences and checks whether each shares at least
    one content word (≥4 chars, non-stopword) with the retrieved chunks.
    Returns ``groundedness`` in [0,1] (fraction of supported sentences) plus
    counts. Purely lexical — it complements, not replaces, the judge's
    ``groundedness`` dimension.
    """
    if not rag_chunks:
        return {"groundedness": None, "supported_sentences": 0,
                "total_sentences": 0, "error": "no_rag_chunks"}
    if not answer or not answer.strip():
        return {"groundedness": 0.0, "supported_sentences": 0,
                "total_sentences": 0, "error": "empty_answer"}
    chunk_text = " ".join(rag_chunks).lower()
    chunk_words = {w for w in re.findall(r"[a-z0-9]+", chunk_text)
                   if w not in _STOPWORDS and len(w) >= 4}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    if not sentences:
        sentences = [answer.strip()]
    supported = 0
    for sent in sentences:
        sent_words = {w for w in re.findall(r"[a-z0-9]+", sent.lower())
                      if w not in _STOPWORDS and len(w) >= 4}
        if sent_words & chunk_words:
            supported += 1
    return {
        "groundedness": supported / len(sentences) if sentences else 0.0,
        "supported_sentences": supported,
        "total_sentences": len(sentences),
        "error": None,
    }


def objective_eval(solution: str, is_code: bool,
                   tests: Optional[str] = None,
                   rag_chunks: Optional[list] = None) -> Dict[str, Any]:
    """Unified objective evaluation entry point used by the experiment harness.

    For code tasks this reports execution success (and test pass). For
    non-code RAG tasks it reports lexical groundedness as the objective
    hallucination proxy. For other non-code tasks it returns a neutral
    placeholder and the LLM judge is used instead.
    """
    if is_code:
        result = objective_code_score(solution, tests)
        # Attach groundedness too when context is available (code + RAG).
        if rag_chunks:
            result["groundedness_detail"] = lexical_groundedness(solution, rag_chunks)
            result["groundedness"] = result["groundedness_detail"]["groundedness"]
        return result
    # Non-code: provide groundedness proxy if we have chunks.
    if rag_chunks:
        g = lexical_groundedness(solution, rag_chunks)
        return {"runs": None, "tests_run": 0, "tests_passed": 0,
                "score": g["groundedness"], "groundedness": g["groundedness"],
                "groundedness_detail": g, "stdout": "", "stderr": "",
                "error": "non_code_task"}
    return {"runs": None, "tests_run": 0, "tests_passed": 0,
            "score": None, "stdout": "", "stderr": "", "error": "non_code_task"}
