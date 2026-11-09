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

Test scoring is **partial credit**: each ``assert``/``try`` block in ``tests``
is executed in its own subprocess (code + shared setup + one block), so
``tests_run`` is the number of blocks and ``tests_passed`` counts blocks
that exit 0. ``score = tests_passed / tests_run``. The old all-or-nothing
behaviour recorded 0 for a solution that passed 3/4 asserts; partial credit
discriminates between near-miss and totally broken code.
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
    return len(_split_test_blocks(tests)[1])


def _split_test_blocks(tests: Optional[str]):
    """Split a reference ``tests`` snippet into (setup, blocks).

    ``setup`` is the prelude before the first top-level ``assert``/``try``
    (e.g. ``class Node: ...`` for linked-list tasks) — it is prepended to
    every block execution so helper classes are available without being
    counted as a test. Each top-level ``assert`` or ``try:`` starts a new
    block; indented lines belong to the block they follow (e.g. the body of
    a ``try:/except:`` pair). Returns ([setup_lines], [block_str, ...]).
    """
    if not tests:
        return ([], [])
    lines = tests.splitlines()
    setup: list = []
    blocks: list = []
    current: list = []
    seen_test = False
    for line in lines:
        stripped = line.strip()
        is_top = (line == line.lstrip()) and (
            stripped.startswith("assert ") or stripped.startswith("assert(")
            or stripped.startswith("try:")
        )
        if is_top:
            if not seen_test:
                seen_test = True
                setup = current  # everything before first test is setup
                current = []
            elif current:
                blocks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        if not seen_test:
            # No assert/try at all: treat whole snippet as one block.
            return ([], ["\n".join(current).strip()])
        blocks.append("\n".join(current).strip())
    blocks = [b for b in blocks if b]
    return (setup, blocks)


def _run_one_block(code: str, setup_lines, blocks_prefix, timeout: float) -> Dict[str, Any]:
    """Execute code + setup + blocks_prefix (cumulative) in one subprocess."""
    fd, path = tempfile.mkstemp(suffix=".py", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)
            if setup_lines:
                f.write("\n\n# --- Test setup ---\n")
                f.write("\n".join(setup_lines))
            f.write("\n\n# --- Reference tests (prefix) ---\n")
            f.write("\n".join(blocks_prefix))
        try:
            result = subprocess.run(
                [sys.executable, path], capture_output=True, text=True, timeout=timeout
            )
            runs = result.returncode == 0
            return {
                "passed": runs,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:2000],
                "error": None if runs else (result.stderr or "execution failed")[:500],
            }
        except subprocess.TimeoutExpired:
            return {"passed": False, "stdout": "", "stderr": "", "error": "timeout"}
        except Exception as e:  # pragma: no cover - defensive
            return {"passed": False, "stdout": "", "stderr": "", "error": str(e)[:500]}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_tests(code: str, tests: Optional[str] = None,
              timeout: float = 10.0) -> Dict[str, Any]:
    """Execute generated code, optionally followed by a reference test snippet.

    Returns a dict with: runs (bool), tests_run (int), tests_passed (int),
    score (0-1), stdout, stderr, error.

    When ``tests`` is provided, each test block (one ``assert`` or one
    ``try:/except:``) runs in its own subprocess so partial credit is
    possible: ``tests_passed`` is the number of passing blocks and
    ``score = tests_passed / tests_run``. ``runs`` is True iff every block
    passes (backwards compatible with the old all-or-nothing flag).
    See :func:`_split_test_blocks` for how blocks are delimited.
    """
    if not code:
        return {"runs": False, "tests_run": 0, "tests_passed": 0, "score": 0.0,
                "stdout": "", "stderr": "", "error": "no_code"}

    if not tests:
        fd, path = tempfile.mkstemp(suffix=".py", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(code)
            try:
                result = subprocess.run(
                    [sys.executable, path], capture_output=True, text=True, timeout=timeout
                )
                runs = result.returncode == 0
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
                return {"runs": False, "tests_run": 0, "tests_passed": 0, "score": 0.0,
                        "stdout": "", "stderr": "", "error": "timeout"}
            except Exception as e:  # pragma: no cover - defensive
                return {"runs": False, "tests_run": 0, "tests_passed": 0, "score": 0.0,
                        "stdout": "", "stderr": "", "error": str(e)[:500]}
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    setup_lines, blocks = _split_test_blocks(tests)
    if not blocks:
        blocks = [tests]
    n_tests = len(blocks)
    # Prefix (cumulative) execution: run setup + blocks[0:i] for i=1..n.
    # This preserves sequential state (e.g. RunningMedian.add then
    # get_median, BoundedQueue.put then get) while still giving partial
    # credit: tests_passed = number of leading blocks that passed before
    # the first failure. score = tests_passed / tests_run.
    passed = 0
    stdouts, stderrs, first_error = [], [], None
    for i in range(n_tests):
        r = _run_one_block(code, setup_lines, blocks[: i + 1], timeout)
        if r["passed"]:
            passed += 1
            continue
        first_error = r["error"]
        break
    # One final full run for stdout/stderr reporting on success.
    if passed == n_tests:
        r = _run_one_block(code, setup_lines, blocks, timeout)
        stdouts.append(r["stdout"])
        stderrs.append(r["stderr"])
    runs = passed == n_tests
    return {
        "runs": runs,
        "tests_run": n_tests,
        "tests_passed": passed,
        "score": passed / n_tests if n_tests else 0.0,
        "stdout": "\n".join(stdouts)[:2000],
        "stderr": "\n".join(stderrs)[:2000],
        "error": None if runs else (first_error or "execution failed")[:500],
    }


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
