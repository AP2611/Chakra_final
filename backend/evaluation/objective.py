"""Objective, execution-based evaluation metrics.

These metrics do not depend on an LLM judge and therefore provide an
independent signal of quality -- especially for code tasks: does the generated
code actually run, and (optionally) does it pass reference test cases?

The primary objective metric used in the paper is the **execution success
rate**: the fraction of generated code solutions that run without error. This
is a fair, model-agnostic signal that the recursive loop should improve (the
in-loop execution validation steers Agni to fix failing code).
"""
import os
import sys
import json
import tempfile
import subprocess
from typing import Dict, Any, Optional

from utils.code_executor import extract_code, execute_code


def run_tests(code: str, tests: Optional[str] = None,
              timeout: float = 10.0) -> Dict[str, Any]:
    """Execute generated code, optionally followed by a reference test snippet.

    Returns a dict with: runs (bool), tests_run (int), tests_passed (int),
    score (0-1), stdout, stderr, error.
    """
    if not code:
        return {"runs": False, "tests_run": 0, "tests_passed": 0, "score": 0.0,
                "stdout": "", "stderr": "", "error": "no_code"}

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
                    "tests_run": 1,
                    "tests_passed": 1 if runs else 0,
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


def objective_code_score(solution: str, tests: Optional[str] = None) -> Dict[str, Any]:
    """Extract code from a solution and run objective checks.

    If no fenced code block is found, the whole solution is treated as code.
    """
    code = extract_code(solution)
    if not code:
        code = solution
    return run_tests(code, tests)


def objective_eval(solution: str, is_code: bool,
                   tests: Optional[str] = None) -> Dict[str, Any]:
    """Unified objective evaluation entry point used by the experiment harness.

    For code tasks this reports execution success; for non-code tasks it
    returns a neutral placeholder (objective metrics for free-form text are
    out of scope here and the LLM judge is used instead).
    """
    if not is_code:
        return {"runs": None, "tests_run": 0, "tests_passed": 0,
                "score": None, "stdout": "", "stderr": "", "error": "non_code_task"}
    return objective_code_score(solution, tests)
