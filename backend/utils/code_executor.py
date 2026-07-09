"""Safely execute generated Python code for validation within the loop."""
import re
import os
import sys
import tempfile
import subprocess
from typing import Dict, Any, Optional


def extract_code(text: str) -> Optional[str]:
    """Extract python code blocks from agent output.

    Returns the concatenated code from all ```python ... ``` (or plain ```)
    blocks, or None if no code block is found.
    """
    if not text:
        return None
    matches = re.findall(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if matches:
        return "\n\n".join(m.strip() for m in matches if m.strip())
    return None


def execute_code(code: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Run code in an isolated subprocess and report the outcome.

    Returns a dict with: success (bool), stdout, stderr, returncode, error.
    Never raises — failures are captured and returned.
    """
    if not code:
        return {"success": False, "stdout": "", "stderr": "", "returncode": -1, "error": "no_code"}

    fd, path = tempfile.mkstemp(suffix=".py", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)

        try:
            result = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            success = result.returncode == 0
            return {
                "success": success,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
                "error": None if success else (result.stderr or "execution failed")[:500],
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "", "returncode": -1, "error": "timeout"}
        except Exception as e:  # pragma: no cover - defensive
            return {"success": False, "stdout": "", "stderr": "", "returncode": -1, "error": str(e)[:500]}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def format_for_prompt(exec_result: Dict[str, Any]) -> str:
    """Format an execution result into a short string for agent prompts."""
    if exec_result is None:
        return ""
    if exec_result["success"]:
        out = exec_result["stdout"].strip()
        preview = out[:400] + ("..." if len(out) > 400 else "")
        return f"[EXECUTION RESULT: PASSED]\nOutput:\n{preview}" if preview else "[EXECUTION RESULT: PASSED (no output)]"
    err = exec_result.get("error") or exec_result.get("stderr") or "unknown error"
    return f"[EXECUTION RESULT: FAILED]\nError:\n{err[:400]}"
