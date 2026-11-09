"""Experiment harness for the Chakra paper.

This script runs a fair, reproducible evaluation of the multi-agent recursive
learning loop and writes publication-quality figures + statistics to
``experiment_results/``.

Design (addressing the issues that previously blocked submission):

1. **Fair baselines.** We compare the multi-agent loop against BOTH a *weak*
   single-pass generator (the same small model the loop uses to draft) AND a
   *strong* single-pass model (the fair comparison target a reviewer expects).
   Previously only the weak baseline was measured, so the loop's real value
   was never quantified.

2. **Ablations.** The loop is run in several modes (``full``, ``agni_only``,
   ``sutra_only``) so we can attribute gains to the critique/improve stages.

3. **Decoupled evaluation.** Final solutions are scored by an INDEPENDENT
   judge (a separate model instance with a frozen rubric) and by OBJECTIVE,
   execution-based metrics. This removes the circularity of using the in-loop
   critic (Sutra) as the sole measure of success.

4. **Robustness.** JSON parsing is tolerant (control chars, prose wrapping) and
   every LLM call retries, so transient failures no longer abort runs.

5. **Variance.** Multiple seeds are supported for variance estimation.
"""
import asyncio
import json
import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

sys.path.insert(0, 'backend')


# =============================================================================
# CONFIGURATION
# =============================================================================

EXPERIMENT_CONFIG = {
    # A weaker generator creates headroom for the critique/improve loop to
    # demonstrate measurable gains; the critic/judge is a stronger model.
    # The judge is a *separate instance* with a frozen rubric (temp 0.2, fixed
    # seed) so steering (Sutra-in-loop) is decoupled from measurement (Judge).
    # Judge/critic family separation: set judge_model to a different family
    # than critic_model (e.g. "llava:latest" / "llama3.2:1b") for paper runs,
    # or pass --judge-model. Same-family is allowed but warned loudly.
    "model": "mistral:latest",            # default / critic fallback
    "generator_model": "qwen2.5:1.5b",    # weak drafter
    "critic_model": "mistral:latest",     # strong critic + improver
    "judge_model": "mistral:latest",      # independent evaluator (separate instance)
    "ollama_url": "http://localhost:11434",
    "max_iterations": 3,
    "min_improvement": 0.5,
    "fast_mode": False,                   # normal mode -> better quality (full run)
    "output_dir": "experiment_results",
    "seeds": [42, 7, 123],                # >=3 seeds for variance estimation
    "use_rag": False,                     # global RAG toggle (document_qa always on)
    "resume": True,
    "ablation_modes": ["full", "agni_only", "sutra_only"],
    # Memory policy (paper fairness): "disabled" = Smriti neither read nor
    # written, so baselines and loop see identical empty memory and seeds
    # cannot leak across tasks. "frozen" = read-only snapshot. "enabled" =
    # online learning (interactive use; do NOT use for paper numbers).
    "memory_policy": "disabled",
    "clear_memory_before_run": True,
    "archive_legacy_results": True,
    "seed_base": None,                    # None -> use per-task `seed` values
}

# Relative compute cost per model (params in B / 7B reference). Local models are
# "free" to call, but the weak model is far cheaper per token, so total cost =
# factor * tokens. This lets us compare a weak-model+loop against a strong
# single pass on a cost-equivalent footing.
MODEL_COST_FACTOR = {
    "mistral:latest": 1.0,        # ~7B
    "qwen2.5:1.5b": 1.5 / 7.0,    # ~1.5B
    "qwen2.5:0.5b": 0.5 / 7.0,
    "llava:latest": 7.0 / 7.0,    # LLaMA family ~7B (vision-capable judge opt)
    "llama3.2:1b": 1.0 / 7.0,     # LLaMA family ~1B (judge sensitivity opt)
    "llama3.2:3b": 3.0 / 7.0,
}


def warn_judge_family(config: Dict):
    """Warn if judge shares model family with critic (reviewer concern)."""
    judge = config.get("judge_model", "")
    critic = config.get("critic_model", "")
    if judge == critic:
        print(f"⚠️  WARNING: judge_model == critic_model ({judge!r}).",
              )
        print("    Independence is instance/prompt/temperature only, not family.",
              )
        print("    For paper runs prefer a different family via --judge-model",
              " (e.g. llava:latest / llama3.2:1b).",
              flush=True)
    print(f"    judge_model={judge!r}  critic_model={critic!r}  "
          f"generator_model={config.get('generator_model')!r}",
          flush=True)


def backup_and_clear_memory(config: Dict) -> Optional[str]:
    """Back up ``backend/data/memory.db`` and remove it for a clean paper run.

    Returns backup path or None. The DB is recreated empty by ``Smriti`` on
    first use. With ``memory_policy="disabled"`` the empty DB is not even
    consulted, but clearing it removes any stale learning from July runs and
    makes the record reproducible.
    """
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
    db_path = os.path.join(backend_dir, "data", "memory.db")
    if not os.path.exists(db_path):
        print(f"  [memory] no existing DB at {db_path}")
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(backend_dir, "data", f"memory_backup_{stamp}.db")
    try:
        with open(db_path, "rb") as src, open(backup, "wb") as dst:
            dst.write(src.read())
        os.remove(db_path)
        print(f"  [memory] backed up {db_path} -> {backup}")
        print("  [memory] cleared for clean (disabled-memory) paper run")
        return backup
    except Exception as e:
        print(f"  [memory] backup/clear failed ({e}); continuing with existing DB")
        return None


def archive_legacy_results(output_dir: str) -> List[str]:
    """Move legacy old-schema results out of the active output directory.

    Old files (pre-``baselines`` schema, missing ``baseline_comparison.pdf``)
    must never be copied into paper §5. They are moved to
    ``<output_dir>/archive_legacy_<stamp>/`` with a manifest.
    """
    if not os.path.isdir(output_dir):
        return []
    legacy = []
    for fname in sorted(os.listdir(output_dir)):
        if not fname.startswith("results_") or not fname.endswith(".json"):
            continue
        path = os.path.join(output_dir, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            recs = data.get("results", [])
            if recs and not _is_new_schema(recs[0]):
                legacy.append(path)
        except Exception:
            continue
    if not legacy:
        return []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(output_dir, f"archive_legacy_{stamp}")
    os.makedirs(archive_dir, exist_ok=True)
    for path in legacy:
        os.rename(path, os.path.join(archive_dir, os.path.basename(path)))
        print(f"  [archive] legacy -> {os.path.join(archive_dir, os.path.basename(path))}")
    with open(os.path.join(archive_dir, "_MANIFEST.txt"), "w") as f:
        f.write("Legacy old-schema experiment results archived before paper runs.\n")
        f.write("Do NOT copy these numbers into paper §5 (old 'baseline' schema, "
                "no independent judge).\n")
    return legacy


def relative_cost(model: str, total_tokens: int) -> float:
    """Relative compute cost = (model size factor) x tokens."""
    factor = MODEL_COST_FACTOR.get(model, 1.0)
    return factor * max(0, total_tokens)


# =============================================================================
# TASKS
# =============================================================================
# Each task: task text, category, use_rag, is_code. ``tests`` is an OPTIONAL
# reference test snippet appended after the generated code (objective check).
# Tasks are chosen to span difficulty so the loop has genuine headroom (the
# previous ceiling effect -- baseline already ~9.5/10 -- masked any gain).

TASK_CATEGORIES: Dict[str, List[Dict[str, Any]]] = {
    "code_algorithms": [
        {"task": "Write a Python function named is_prime(n) to check if a number is prime",
         "tests": "assert is_prime(2) is True\nassert is_prime(1) is False\nassert is_prime(17) is True\nassert is_prime(9) is False"},
        {"task": "Write a Python function named reverse_list(head) to reverse a singly linked list. Nodes have .val and .next attributes; use this Node class: class Node:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next",
         "tests": "class Node:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next\ndef _vals(h):\n    out=[]\n    while h:\n        out.append(h.val)\n        h=h.next\n    return out\nassert reverse_list(None) is None\nassert _vals(reverse_list(Node(1, Node(2, Node(3))))) == [3,2,1]\nassert _vals(reverse_list(Node(7))) == [7]"},
        {"task": "Write a Python function named max_subarray(nums) to find the maximum subarray sum (Kadane's algorithm) of a non-empty list of numbers",
         "tests": "assert max_subarray([-2,1,-3,4,-1,2,1,-5,4]) == 6\nassert max_subarray([-1]) == -1\nassert max_subarray([1,2,3]) == 6"},
        {"task": "Write a Python function named merge_sorted(a, b) to merge two sorted lists of numbers into one sorted list",
         "tests": "assert merge_sorted([1,3,5],[2,4,6]) == [1,2,3,4,5,6]\nassert merge_sorted([],[1,2]) == [1,2]"},
        {"task": "Write a Python function named has_cycle(head) to detect a cycle in a singly linked list. Nodes have .val and .next. Return True if cyclic, else False.",
         "tests": "class Node:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next\ndef _cyc():\n    a=Node(1)\n    b=Node(2, a)\n    a.next=b\n    return b\nassert has_cycle(None) is False\nassert has_cycle(Node(1)) is False\nassert has_cycle(_cyc()) is True"},
        {"task": "Write a Python function named is_valid_bst(root) to validate a binary search tree. Nodes have .val, .left, .right. Return True if valid.",
         "tests": "class TreeNode:\n    def __init__(self, val=0, left=None, right=None):\n        self.val=val\n        self.left=left\n        self.right=right\nassert is_valid_bst(None) is True\nassert is_valid_bst(TreeNode(2, TreeNode(1), TreeNode(3))) is True\nassert is_valid_bst(TreeNode(2, TreeNode(3), TreeNode(4))) is False\nassert is_valid_bst(TreeNode(5, TreeNode(1), TreeNode(4, TreeNode(3)))) is False"},
        {"task": "Write a Python function named binary_search(arr, target) to perform binary search on a sorted list. Return the index of target or -1 if not found",
         "tests": "assert binary_search([1,2,3,4,5],3) == 2\nassert binary_search([1,2,3,4,5],6) == -1\nassert binary_search([10],10) == 0"},
        {"task": "Write a Python function named permutations(s) to generate all permutations of a string as a list",
         "tests": "assert sorted(permutations('ab')) == ['ab','ba']\nassert len(permutations('abc')) == 6"},
        {"task": "Write a Python function named dfs(graph, start) to implement depth-first search on a graph. graph is a dict of node -> list of neighbors. Return the DFS order as a list starting from start",
         "tests": "assert dfs({'A':['B','C'],'B':['A','D'],'C':['A'],'D':['B']}, 'A')[0] == 'A'\nassert sorted(dfs({'A':['B','C'],'B':['A','D'],'C':['A'],'D':['B']}, 'A')) == ['A','B','C','D']\nassert dfs({'X':[]}, 'X') == ['X']"},
        {"task": "Write a Python function named lcs(a, b) to find the length of the longest common subsequence of two strings",
         "tests": "assert lcs('abcde','ace') == 3\nassert lcs('abc','def') == 0"},
        # Harder tasks -> real headroom for the loop
        {"task": "Write a thread-safe Python class named BoundedQueue implemented with threading.Condition. It must have __init__(self, capacity) storing a capacity, put(self, item) that blocks when the queue is full and get(self) that blocks when the queue is empty. FIFO order.",
         "tests": "import threading, time\n_q=BoundedQueue(2)\n_q.put(1)\n_q.put(2)\nassert _q.get()==1\nassert _q.get()==2\n_q2=BoundedQueue(1)\n_q2.put('a')\ndef _bg():\n    time.sleep(0.1)\n    _q2.get()\n_t=threading.Thread(target=_bg)\n_t.start()\n_q2.put('b')\n_t.join(timeout=2)\nassert not _t.is_alive()\nassert _q2.get()=='b'"},
        {"task": "Write a Python function named fib(n) to compute the nth Fibonacci number in O(log n) time using matrix exponentiation (fib(0)==0, fib(1)==1). Return an int and raise ValueError for negative n.",
         "tests": "assert fib(0)==0\nassert fib(1)==1\nassert fib(10)==55\nassert fib(20)==6765\ntry:\n    fib(-1)\n    assert False, 'expected ValueError'\nexcept ValueError:\n    pass"},
        {"task": "Write a Python class named RunningMedian with __init__(self) and methods add(self, x) and get_median(self) returning the median of all added numbers (average of two middle values for an even count). get_median() on an empty structure must raise ValueError.",
         "tests": "_m=RunningMedian()\n_m.add(5)\nassert _m.get_median()==5\n_m.add(1)\nassert _m.get_median()==3.0\n_m.add(3)\nassert _m.get_median()==3\ntry:\n    RunningMedian().get_median()\n    assert False, 'expected ValueError'\nexcept ValueError:\n    pass"},
    ],
    "code_optimization": [
        {"task": "Optimize this Python function for performance. Keep the function name find_duplicates(arr) which returns the list of duplicated values (each duplicate once, order of first appearance): def find_duplicates(arr): return [x for i, x in enumerate(arr) if x in arr[:i]]",
         "tests": "assert find_duplicates([1,2,2,3,3,3]) == [2,3]\nassert find_duplicates([1,2,3]) == []"},
        {"task": "Refactor this code to be more readable. Replace the one-line lambda with a named function abs_diff(a, b) that returns the absolute difference: x=lambda a,b: a+b if a>b else a-b",
         "tests": "assert abs_diff(5,2) == 3\nassert abs_diff(2,5) == 3"},
        {"task": "Improve the error handling in this function. Keep the name divide(a, b) but raise ValueError (not ZeroDivisionError) when b is zero, and raise TypeError for non-numeric inputs: def divide(a,b): return a/b",
         "tests": "assert divide(10,2) == 5.0\ntry:\n    divide(1,0)\n    assert False, 'expected ValueError'\nexcept ValueError:\n    pass"},
        {"task": "Rewrite this O(n^2) duplicate-removal to run in O(n) average time while preserving order. Use function name dedupe(arr) that returns the list with duplicates removed preserving first-occurrence order",
         "tests": "assert dedupe([1,2,2,3,1]) == [1,2,3]\nassert dedupe([]) == []\nassert dedupe([7,7,7]) == [7]"},
    ],
    "math_reasoning": [
        {"task": "Solve for x: 3x + 7 = 22"},
        {"task": "What is the derivative of x^3 + 2x^2 - 5x + 1?"},
        {"task": "Calculate the area of a circle with radius 5"},
        {"task": "If a train travels 120 km in 2 hours, what is its speed in m/s?"},
        {"task": "A portfolio loses 20% then gains 25%. What is the net percentage change?"},
    ],
    "text_generation": [
        {"task": "Explain the concept of recursion in programming"},
        {"task": "Write a brief summary of how neural networks learn"},
        {"task": "Describe the difference between TCP and UDP"},
        {"task": "Explain the trade-offs between consistency and availability in distributed systems (CAP theorem)"},
    ],
    "document_qa": [
        {"task": "What are the four specialized agents in Chakra and what does each do?"},
        {"task": "How does the recursive learning loop decide when to stop?"},
        {"task": "How does Chakra validate generated Python code, and what happens on failure?"},
        {"task": "What is the purpose of RAG in Chakra and how does it reduce hallucination?"},
    ],
}

# Flatten into a task list with metadata. document_qa enables RAG; others
# follow the global toggle. Only true code categories are flagged is_code
# (math/text answers are prose — running them as code would corrupt the
# objective execution rate).
CODE_CATEGORIES = {"code_algorithms", "code_optimization"}
ALL_TASKS: List[Dict[str, Any]] = []
for category, tasks in TASK_CATEGORIES.items():
    for t in tasks:
        use_rag = True if category == "document_qa" else EXPERIMENT_CONFIG["use_rag"]
        ALL_TASKS.append({
            "task": t["task"],
            "category": category,
            "use_rag": use_rag,
            "is_code": category in CODE_CATEGORIES,
            "tests": t.get("tests"),
        })


# =============================================================================
# RUNNERS
# =============================================================================

async def get_rag_chunks(task: str, use_rag: bool) -> Optional[List[str]]:
    """Retrieve RAG chunks once per task (used for baselines + judge fairness)."""
    if not use_rag:
        return None
    try:
        from rag.vector_retriever import VectorRAGRetriever
        retr = VectorRAGRetriever()
        return retr.retrieve(task, 3)
    except Exception as e:
        print(f"  [RAG] retrieval failed ({e}); continuing without context")
        return None


async def run_single_pass(task: str, config: Dict, model: str,
                          rag_chunks: Optional[List[str]] = None,
                          seed: Optional[int] = None) -> Dict[str, Any]:
    """Single-pass generation with a given model (used for both baselines).

    Baselines never use Smriti memory — parity with the loop's
    ``memory_policy="disabled"`` ensures no memory confound.
    """
    from agents.yantra import Yantra
    yantra = Yantra(ollama_url=config["ollama_url"], model=model,
                    fast_mode=config["fast_mode"])
    if seed is not None:
        yantra.set_seed(seed)
    yantra.reset_token_stats()

    start = time.time()
    result = await yantra.process(task=task, rag_chunks=rag_chunks)
    elapsed = time.time() - start

    return {
        "output": result["output"],
        "time": elapsed,
        "model": model,
        "seed": seed,
        "total_tokens": yantra.token_stats["total"],
        "cost": relative_cost(model, yantra.token_stats["total"]),
        "status": "success",
    }


async def run_multi_agent_loop(task: str, config: Dict, use_rag: bool = False,
                               is_code: bool = True, mode: str = "full",
                               rag_chunks: Optional[List[str]] = None,
                               seed: Optional[int] = None) -> Dict[str, Any]:
    """Run the multi-agent recursive learning loop (supports ablation modes)."""
    from orchestrator import Orchestrator
    from utils.code_executor import extract_code, execute_code

    gen_model = config.get("generator_model", config["model"])
    crit_model = config.get("critic_model", config["model"])

    orchestrator = Orchestrator(
        ollama_url=config["ollama_url"],
        model=config["model"],
        generator_model=gen_model,
        critic_model=crit_model,
        max_iterations=config["max_iterations"],
        min_improvement=config["min_improvement"],
        fast_mode=config["fast_mode"],
        memory_policy=config.get("memory_policy", "disabled"),
        seed=seed,
    )

    start = time.time()
    result = await orchestrator.process(
        task=task,
        use_rag=use_rag,
        is_code=is_code,
        mode=mode,
        shared_rag_chunks=rag_chunks,
    )
    elapsed = time.time() - start

    # Per-agent cost: weight each agent's tokens by its model's cost factor
    ts = result.get("token_stats", {})
    cost = (
        relative_cost(gen_model, ts.get("yantra", {}).get("total", 0))
        + relative_cost(crit_model, ts.get("sutra", {}).get("total", 0))
        + relative_cost(crit_model, ts.get("agni", {}).get("total", 0))
    )

    # Execution validation for code tasks (objective signal)
    execution_passed = None
    if is_code and result.get("final_solution"):
        code = extract_code(result["final_solution"])
        if code:
            execution_passed = execute_code(code)["success"]

    return {
        "task": task,
        "final_solution": result["final_solution"],
        "final_score": result["final_score"],
        "iterations": result["iterations"],
        "total_iterations": result["total_iterations"],
        "time": elapsed,
        "agent": "Multi-Agent Loop",
        "mode": mode,
        "total_tokens": result.get("total_tokens", 0),
        "cost": cost,
        "execution_passed": execution_passed,
        "status": "success" if result.get("final_solution") else "failed",
        "error": None if result.get("final_solution") else "no final solution produced",
    }


async def run_independent_judge(task: str, solution: str, config: Dict,
                                rag_chunks: Optional[List[str]] = None,
                                is_code: bool = True,
                                seed: Optional[int] = None) -> Dict[str, Any]:
    """Score a final solution with the independent judge (decoupled from loop).

    Judge temperature is fixed at 0.2 and the Ollama ``seed`` is fixed
    (``seed + 999``) for reproducibility.
    """
    from evaluation.judge import Judge
    judge_seed = (seed + 999) if seed is not None else None
    judge = Judge(ollama_url=config["ollama_url"], model=config["judge_model"],
                  fast_mode=config["fast_mode"], seed=judge_seed)
    return await judge.score(task, solution, rag_chunks=rag_chunks)


def run_objective_eval(solution: str, is_code: bool,
                       tests: Optional[str] = None,
                       rag_chunks: Optional[List[str]] = None) -> Dict[str, Any]:
    """Objective, execution-based evaluation (no LLM)."""
    from evaluation.objective import objective_eval
    return objective_eval(solution, is_code, tests, rag_chunks=rag_chunks)


async def evaluate_solution(task: str, solution: str, config: Dict,
                            rag_chunks: Optional[List[str]], is_code: bool,
                            tests: Optional[str], seed: Optional[int] = None) -> Dict[str, Any]:
    """Run both the independent judge and the objective metric on a solution."""
    judge = await run_independent_judge(task, solution, config,
                                        rag_chunks=rag_chunks, is_code=is_code,
                                        seed=seed)
    objective = run_objective_eval(solution, is_code, tests, rag_chunks=rag_chunks)
    return {"judge": judge, "objective": objective}


async def run_experiment_task(task_data: Dict[str, Any], config: Dict,
                              seed: int) -> Dict[str, Any]:
    """Run baselines + multi-agent ablations + decoupled evaluation on one task."""
    task = task_data["task"]
    category = task_data["category"]
    use_rag = task_data.get("use_rag", config.get("use_rag", False))
    is_code = task_data["is_code"]
    tests = task_data.get("tests")

    print(f"\n{'='*60}")
    print(f"Task: {task[:60]}... | cat={category} | rag={use_rag} | code={is_code} | seed={seed}")
    print(f"{'='*60}")

    rag_chunks = await get_rag_chunks(task, use_rag)

    # ---- Baselines ----
    baselines: Dict[str, Any] = {}
    for kind, model in (("weak", config.get("generator_model", config["model"])),
                        ("strong", config.get("critic_model", config["model"]))):
        print(f"  [baseline:{kind}] single-pass ({model}, seed={seed})...")
        try:
            base = await run_single_pass(task, config, model,
                                         rag_chunks=rag_chunks, seed=seed)
            base["evaluation"] = await evaluate_solution(
                task, base["output"], config, rag_chunks, is_code, tests, seed=seed)
            baselines[kind] = base
        except Exception as e:
            print(f"  baseline:{kind} FAILED: {e}")
            baselines[kind] = {"status": "failed", "error": str(e), "output": "", "evaluation": {}}

    # ---- Multi-agent ablations ----
    multi_agent: Dict[str, Any] = {}
    for mode in config.get("ablation_modes", ["full"]):
        print(f"  [multi:{mode}] recursive loop (seed={seed})...")
        try:
            ma = await run_multi_agent_loop(
                task, config, use_rag=use_rag, is_code=is_code, mode=mode,
                rag_chunks=rag_chunks, seed=seed)
            if ma["status"] == "success":
                ma["evaluation"] = await evaluate_solution(
                    task, ma["final_solution"], config, rag_chunks, is_code, tests,
                    seed=seed)
            else:
                ma["evaluation"] = {}
            multi_agent[mode] = ma
        except Exception as e:
            print(f"  multi:{mode} FAILED: {e}")
            multi_agent[mode] = {"status": "failed", "error": str(e), "evaluation": {}}

    return {
        "task": task,
        "category": category,
        "is_code": is_code,
        "use_rag": use_rag,
        "seed": seed,
        "baselines": baselines,
        "multi_agent": multi_agent,
        "timestamp": datetime.now().isoformat(),
    }


def _is_new_schema(record: Dict) -> bool:
    """True for records in the current (baselines + ablations) schema."""
    return "baselines" in record and "multi_agent" in record


def load_latest_results(config: Dict) -> List[Dict[str, Any]]:
    """Load the latest results file for resuming.

    Prefers ``latest.json`` (written on every save). Falls back to the
    newest timestamped file, keeping only new-schema records so legacy
    runs (old ``baseline`` key, no judge) never contaminate paired stats.
    """
    output_dir = config["output_dir"]
    if not os.path.exists(output_dir):
        return []
    candidates = []
    latest = os.path.join(output_dir, "latest.json")
    if os.path.exists(latest):
        candidates.append(latest)
    result_files = [f for f in os.listdir(output_dir)
                    if f.startswith("results_") and f.endswith(".json")]
    result_files.sort(reverse=True)
    candidates += [os.path.join(output_dir, f) for f in result_files]
    for path in candidates:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                records = [r for r in data.get("results", []) if _is_new_schema(r)]
                if records:
                    return records
        except Exception as e:
            print(f"Warning: could not load {os.path.basename(path)}: {e}")
            continue
    return []


async def run_full_experiment(config: Dict) -> List[Dict[str, Any]]:
    """Run the experiment across all tasks and seeds.

    Paper-ready guards (called once per run):
    - Archive legacy old-schema results so they cannot be mistaken for
      paper numbers.
    - Back up + clear the Smriti memory DB when ``clear_memory_before_run``.
    - Memory policy ``disabled`` ensures no cross-task/seed leakage.
    - Log versions + seeds for reproducibility.
    """
    results: List[Dict[str, Any]] = []
    completed_keys = set()

    if config.get("archive_legacy_results"):
        archive_legacy_results(config["output_dir"])
    if config.get("clear_memory_before_run"):
        backup_and_clear_memory(config)
    print(f"  [memory_policy={config.get('memory_policy', 'disabled')!r}] "
          f"fast_mode={config.get('fast_mode')}")
    try:
        import sys as _sys
        import numpy as _np, scipy as _sp, matplotlib as _mpl
        print(f"  [versions] python={_sys.version.split()[0]} numpy={_np.__version__} "
              f"scipy={_sp.__version__} matplotlib={_mpl.__version__}")
    except Exception:
        pass

    if config.get("resume", False):
        existing = load_latest_results(config)
        results = existing
        # A record counts as complete only if every condition produced a
        # judgeable solution (score not None). Records from the broken-judge
        # era (all judge scores None) are re-run, not skipped.
        def _record_complete(r: Dict) -> bool:
            if r.get("status") == "fatal_error":
                return False
            for entry in list(r.get("baselines", {}).values()):
                if not isinstance(entry, dict) or entry.get("status") != "success":
                    return False
                if _judge_score(entry) is None:
                    return False
            for entry in list(r.get("multi_agent", {}).values()):
                if not isinstance(entry, dict) or entry.get("status") != "success":
                    return False
                if _judge_score(entry) is None:
                    return False
            return True

        completed_keys = {(r["task"], r.get("seed")) for r in existing
                          if _record_complete(r)}
        print(f"Resuming from {len(completed_keys)} completed (task, seed) pairs")

    seeds = config.get("seeds", [42])
    tasks = config.get("_pilot_tasks", ALL_TASKS)
    total = len(tasks) * len(seeds)
    done = len(completed_keys)
    print(f"Total (task x seed): {total}  tasks={len(tasks)} seeds={seeds}")
    # Rough runtime estimate (mistral judge ~10s/call).
    est_calls = total * (2 + 5 + len(config.get("ablation_modes", ["full"])) * 9)
    print(f"  [estimate] ~{est_calls} LLM calls; at 5-12s/call this is "
          f"{est_calls*5/3600:.1f}-{est_calls*12/3600:.1f} hours. "
          f"Use --pilot for a 1-5 task smoke test.")

    for seed in seeds:
        np.random.seed(seed)
        os.environ["PYTHONHASHSEED"] = str(seed)
        # Vary task order per seed for variance in any order-dependent effects.
        ordered = list(tasks)
        np.random.shuffle(ordered)
        for task_data in ordered:
            key = (task_data["task"], seed)
            if key in completed_keys:
                continue
            done += 1
            print(f"\n[{done}/{total}] Processing...")
            try:
                result = await run_experiment_task(task_data, config, seed)
                results.append(result)
                save_results(results, config)
            except Exception as e:
                print(f"  FATAL ERROR on task {done}: {e}")
                results.append({
                    "task": task_data["task"],
                    "category": task_data["category"],
                    "seed": seed,
                    "status": "fatal_error",
                    "error": str(e),
                })

    return results


# =============================================================================
# DATA SAVING
# =============================================================================

def save_results(results: List[Dict], config: Dict):
    """Save results to a timestamped JSON file plus ``latest.json`` (resume)."""
    os.makedirs(config["output_dir"], exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(config["output_dir"], f"results_{timestamp}.json")
    try:
        import sys as _sys
        _versions = {
            "python": _sys.version.split()[0],
            "numpy": np.__version__,
        }
        try:
            import scipy as _sp
            _versions["scipy"] = _sp.__version__
        except Exception:
            pass
        try:
            import matplotlib as _mpl
            _versions["matplotlib"] = _mpl.__version__
        except Exception:
            pass
    except Exception:
        _versions = {}
    payload = {
        "config": config,
        "versions": _versions,
        "results": results,
        "summary": compute_summary(results),
    }
    with open(filename, 'w') as f:
        json.dump(payload, f, indent=2, default=str)
    with open(os.path.join(config["output_dir"], "latest.json"), 'w') as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"  Saved: {filename}")
    return filename


def _judge_score(entry: Dict) -> Optional[float]:
    ev = entry.get("evaluation", {})
    j = ev.get("judge", {})
    return j.get("score") if isinstance(j, dict) else None


def _obj_runs(entry: Dict) -> Optional[bool]:
    ev = entry.get("evaluation", {})
    o = ev.get("objective", {})
    return o.get("runs") if isinstance(o, dict) else None


def _obj_groundedness(entry: Dict) -> Optional[float]:
    ev = entry.get("evaluation", {})
    o = ev.get("objective", {})
    if not isinstance(o, dict):
        return None
    g = o.get("groundedness")
    return float(g) if isinstance(g, (int, float)) else None


def _judge_groundedness(entry: Dict) -> Optional[float]:
    ev = entry.get("evaluation", {})
    j = ev.get("judge", {})
    if not isinstance(j, dict):
        return None
    scores = j.get("scores", {})
    if isinstance(scores, dict) and isinstance(scores.get("groundedness"), (int, float)):
        return float(scores["groundedness"])
    return None


def compute_summary(results: List[Dict]) -> Dict[str, Any]:
    """Compute a fair, comparison-oriented summary.

    The headline numbers are now:
      * improvement over the WEAK baseline (does the loop beat its own drafter?)
      * improvement over the STRONG baseline (the fair comparison target)
      * within-loop improvement (iteration 1 -> best)
      * objective execution success rate (baseline vs loop)
      * cost (time + relative tokens)
    """
    valid = [r for r in results if r.get("status") != "fatal_error"]

    # Collect paired records where we have a successful full multi-agent run
    # and at least the strong baseline.
    pairs = []
    for r in valid:
        ma = r.get("multi_agent", {}).get("full")
        if not ma or ma.get("status") != "success":
            continue
        weak = r.get("baselines", {}).get("weak")
        strong = r.get("baselines", {}).get("strong")
        if not (weak and strong and weak.get("status") == "success"
                and strong.get("status") == "success"):
            continue
        pairs.append((r, weak, strong, ma))

    if not pairs:
        return {"error": "No complete (baseline + multi-agent) runs to summarize"}

    # Judge scores (decoupled evaluation)
    weak_j = [ _judge_score(w) for _, w, _, _ in pairs ]
    strong_j = [ _judge_score(s) for _, _, s, _ in pairs ]
    multi_j = [ _judge_score(m) for _, _, _, m in pairs ]
    weak_j = [x for x in weak_j if x is not None]
    strong_j = [x for x in strong_j if x is not None]
    multi_j = [x for x in multi_j if x is not None]

    # Within-loop improvement (in-loop Sutra composite)
    within = []
    for _, _, _, m in pairs:
        iters = m.get("iterations", [])
        if iters:
            within.append(m["final_score"] - iters[0]["score"])

    # Objective execution success (code tasks only)
    weak_runs = [ _obj_runs(w) for _, w, _, _ in pairs if w.get("evaluation", {}).get("objective", {}).get("runs") is not None ]
    strong_runs = [ _obj_runs(s) for _, _, s, _ in pairs if s.get("evaluation", {}).get("objective", {}).get("runs") is not None ]
    multi_runs = [ _obj_runs(m) for _, _, _, m in pairs if m.get("evaluation", {}).get("objective", {}).get("runs") is not None ]

    def rate(lst):
        lst = [x for x in lst if x is not None]
        return float(np.mean([1 if x else 0 for x in lst])) if lst else None

    # Cost (relative compute + latency)
    weak_times = [w["time"] for _, w, _, _ in pairs]
    strong_times = [s["time"] for _, _, s, _ in pairs]
    multi_times = [m["time"] for _, _, _, m in pairs]
    multi_tokens = [m.get("total_tokens", 0) for _, _, _, m in pairs]
    weak_costs = [w.get("cost", 0) for _, w, _, _ in pairs]
    strong_costs = [s.get("cost", 0) for _, _, s, _ in pairs]
    multi_costs = [m.get("cost", 0) for _, _, _, m in pairs]

    # Hallucination proxies (RAG tasks only; None otherwise)
    weak_ground = [x for x in (_obj_groundedness(w) for _, w, _, _ in pairs) if x is not None]
    strong_ground = [x for x in (_obj_groundedness(s) for _, _, s, _ in pairs) if x is not None]
    multi_ground = [x for x in (_obj_groundedness(m) for _, _, _, m in pairs) if x is not None]
    weak_jground = [x for x in (_judge_groundedness(w) for _, w, _, _ in pairs) if x is not None]
    strong_jground = [x for x in (_judge_groundedness(s) for _, _, s, _ in pairs) if x is not None]
    multi_jground = [x for x in (_judge_groundedness(m) for _, _, _, m in pairs) if x is not None]

    # Ablation means (judge)
    ablation_means = {}
    for mode in ("full", "agni_only", "sutra_only"):
        scores = []
        for r in valid:
            ma = r.get("multi_agent", {}).get(mode)
            if ma and ma.get("status") == "success":
                s = _judge_score(ma)
                if s is not None:
                    scores.append(s)
        if scores:
            ablation_means[mode] = float(np.mean(scores))

    summary: Dict[str, Any] = {
        "n_complete": len(pairs),
        "n_judged": min(len(weak_j), len(strong_j), len(multi_j)) if (weak_j and strong_j and multi_j) else 0,
        "weak_judge_mean": float(np.mean(weak_j)) if weak_j else None,
        "strong_judge_mean": float(np.mean(strong_j)) if strong_j else None,
        "multi_judge_mean": float(np.mean(multi_j)) if multi_j else None,
        "improvement_vs_weak": (float(np.mean(multi_j)) - float(np.mean(weak_j)))
            if (weak_j and multi_j) else None,
        "improvement_vs_strong": (float(np.mean(multi_j)) - float(np.mean(strong_j)))
            if (strong_j and multi_j) else None,
        "within_loop_improvement_mean": float(np.mean(within)) if within else None,
        "within_loop_improvement_std": float(np.std(within)) if within else None,
        "objective_exec_rate_weak": rate(weak_runs),
        "objective_exec_rate_strong": rate(strong_runs),
        "objective_exec_rate_multi": rate(multi_runs),
        "weak_time_mean": float(np.mean(weak_times)) if weak_times else None,
        "strong_time_mean": float(np.mean(strong_times)) if strong_times else None,
        "multi_time_mean": float(np.mean(multi_times)) if multi_times else None,
        "weak_cost_mean": float(np.mean(weak_costs)) if weak_costs else None,
        "strong_cost_mean": float(np.mean(strong_costs)) if strong_costs else None,
        "multi_cost_mean": float(np.mean(multi_costs)) if multi_costs else None,
        "multi_tokens_mean": float(np.mean(multi_tokens)) if multi_tokens else None,
        "objective_groundedness_weak": float(np.mean(weak_ground)) if weak_ground else None,
        "objective_groundedness_strong": float(np.mean(strong_ground)) if strong_ground else None,
        "objective_groundedness_multi": float(np.mean(multi_ground)) if multi_ground else None,
        "judge_groundedness_weak": float(np.mean(weak_jground)) if weak_jground else None,
        "judge_groundedness_strong": float(np.mean(strong_jground)) if strong_jground else None,
        "judge_groundedness_multi": float(np.mean(multi_jground)) if multi_jground else None,
        "ablation_judge_means": ablation_means,
    }
    return summary


# =============================================================================
# PUBLICATION-QUALITY PLOTTING
# =============================================================================

def _primary(r: Dict) -> Optional[Dict]:
    """Return the primary (full-mode) multi-agent result for a task record."""
    ma = r.get("multi_agent", {})
    if "full" in ma:
        return ma["full"]
    # fallback: first successful mode
    for v in ma.values():
        if isinstance(v, dict) and v.get("status") == "success":
            return v
    return None


def setup_publication_style():
    """Configure matplotlib for publication-quality figures."""
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
        'font.size': 12,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,
        'axes.linewidth': 1.2,
        'grid.linewidth': 0.8,
        'lines.linewidth': 2,
        'lines.markersize': 8,
    })


def plot_score_progression(results: List[Dict], config: Dict):
    """Plot score progression over iterations for all tasks (full mode)."""
    setup_publication_style()

    valid = [r for r in results
             if r.get("status") != "fatal_error" and _primary(r)
             and _primary(r).get("iterations")]

    if not valid:
        print("No valid results for score progression plot")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax1 = axes[0]
    for r in valid:
        iters = _primary(r)["iterations"]
        axes[0].plot([i["iteration"] for i in iters],
                     [i["score"] for i in iters], marker='o', alpha=0.7, linewidth=1.5)
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Composite Score (1-10)")
    ax1.set_title("Score Progression Across Tasks")
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 10)
    ax1.set_xticks(range(1, config["max_iterations"] + 1))

    ax2 = axes[1]
    max_iter = config["max_iterations"]
    mean_scores, std_scores = [], []
    for i in range(1, max_iter + 1):
        scores_at_iter = []
        for r in valid:
            iters = _primary(r)["iterations"]
            if len(iters) >= i:
                scores_at_iter.append(iters[i-1]["score"])
        if scores_at_iter:
            mean_scores.append(np.mean(scores_at_iter))
            std_scores.append(np.std(scores_at_iter))
        else:
            mean_scores.append(np.nan)
            std_scores.append(np.nan)
    iterations = list(range(1, len(mean_scores) + 1))
    ax2.plot(iterations, mean_scores, marker='o', color='#0173B2', linewidth=2.5, label='Mean Score')
    ax2.fill_between(iterations,
                     np.array(mean_scores) - np.array(std_scores),
                     np.array(mean_scores) + np.array(std_scores),
                     alpha=0.2, color='#0173B2', label='±1 Std Dev')
    ax2.set_xlabel("Iteration")
    ax2.set_ylabel("Composite Score (1-10)")
    ax2.set_title("Mean Score Progression (n={})".format(len(valid)))
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 10)
    ax2.set_xticks(iterations)

    plt.tight_layout()
    plt.savefig(os.path.join(config["output_dir"], "score_progression.pdf"))
    plt.savefig(os.path.join(config["output_dir"], "score_progression.png"), dpi=300)
    plt.close()
    print("  Saved: score_progression.pdf")


def plot_improvement_distribution(results: List[Dict], config: Dict):
    """Plot distribution of within-loop improvements."""
    setup_publication_style()

    valid = [r for r in results if r.get("status") != "fatal_error" and _primary(r)]
    improvements, categories = [], []
    for r in valid:
        p = _primary(r)
        iters = p.get("iterations", [])
        if iters:
            improvements.append(p["final_score"] - iters[0]["score"])
            categories.append(r["category"])
    if not improvements:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    ax1 = axes[0]
    ax1.hist(improvements, bins=15, color='#029E73', edgecolor='black', alpha=0.8)
    ax1.axvline(np.mean(improvements), color='red', linestyle='--', linewidth=2,
                label=f'Mean: {np.mean(improvements):.2f}')
    ax1.axvline(0, color='black', linestyle='-', linewidth=0.5)
    ax1.set_xlabel("Score Improvement (Final - Initial)")
    ax1.set_ylabel("Number of Tasks")
    ax1.set_title("Distribution of Within-Loop Improvements")
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')

    ax2 = axes[1]
    cat_data: Dict[str, List[float]] = {}
    for cat, imp in zip(categories, improvements):
        cat_data.setdefault(cat, []).append(imp)
    cat_names = list(cat_data.keys())
    cat_values = [cat_data[c] for c in cat_names]
    bp = ax2.boxplot(cat_values, labels=cat_names, patch_artist=True)
    for patch, color in zip(bp['boxes'], ['#0173B2', '#DE8F05', '#029E73', '#CC78BC', '#E6842A']):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_ylabel("Score Improvement")
    ax2.set_title("Improvement by Task Category")
    ax2.grid(True, alpha=0.3, axis='y')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig(os.path.join(config["output_dir"], "improvement_distribution.pdf"))
    plt.savefig(os.path.join(config["output_dir"], "improvement_distribution.png"), dpi=300)
    plt.close()
    print("  Saved: improvement_distribution.pdf")


def plot_time_vs_quality(results: List[Dict], config: Dict):
    """Plot time vs quality trade-off (multi-agent full mode)."""
    setup_publication_style()

    valid = [r for r in results if r.get("status") != "fatal_error" and _primary(r)
             and _primary(r).get("status") == "success"]
    if not valid:
        return

    times, scores, iterations = [], [], []
    for r in valid:
        p = _primary(r)
        j = _judge_score(p)
        if j is None:
            continue
        times.append(p["time"])
        scores.append(j)
        iterations.append(p.get("total_iterations", 0))

    if not times:
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(times, scores, c=iterations, cmap='viridis',
                         s=100, alpha=0.8, edgecolors='black', linewidth=1)
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label("Iterations", rotation=270, labelpad=15)
    ax.set_xlabel("Total Time (seconds)")
    ax.set_ylabel("Judge Score (1-10)")
    ax.set_title("Time-Quality Trade-off (Multi-Agent)")
    ax.grid(True, alpha=0.3)
    if len(times) > 2:
        z = np.polyfit(times, scores, 1)
        p = np.poly1d(z)
        ax.plot(times, p(times), "r--", alpha=0.5, linewidth=1.5, label='Trend')
        ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(config["output_dir"], "time_vs_quality.pdf"))
    plt.savefig(os.path.join(config["output_dir"], "time_vs_quality.png"), dpi=300)
    plt.close()
    print("  Saved: time_vs_quality.pdf")


def plot_dimension_radar(results: List[Dict], config: Dict):
    """Plot radar chart of average dimension scores (final iteration, full mode)."""
    setup_publication_style()

    valid = [r for r in results if r.get("status") != "fatal_error" and _primary(r)]
    if not valid:
        return

    dimensions = ["correctness", "accuracy", "efficiency", "clarity",
                  "edge_case_coverage", "groundedness"]
    dim_scores = {dim: [] for dim in dimensions}
    for r in valid:
        p = _primary(r)
        final_iter = p.get("iterations", [{}])[-1] if p.get("iterations") else {}
        scores = final_iter.get("sutra_scores") or {}
        if not isinstance(scores, dict):
            continue
        for dim in dimensions:
            if isinstance(scores.get(dim), (int, float)):
                dim_scores[dim].append(scores[dim])
    # Groundedness only exists on RAG tasks; drop it if no data so the radar
    # stays on comparable dimensions.
    dimensions = [d for d in dimensions if dim_scores[d]]
    if not dimensions:
        return
    means = [np.mean(dim_scores[dim]) for dim in dimensions]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
    means_plot = means + means[:1]
    angles += angles[:1]
    ax.plot(angles, means_plot, 'o-', linewidth=2, color='#0173B2')
    ax.fill(angles, means_plot, alpha=0.25, color='#0173B2')
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([dim.replace('_', ' ').title() for dim in dimensions])
    ax.set_ylim(0, 10)
    ax.set_title("Average Dimension Scores (Final Iteration)", pad=20)
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(config["output_dir"], "dimension_radar.pdf"))
    plt.savefig(os.path.join(config["output_dir"], "dimension_radar.png"), dpi=300)
    plt.close()
    print("  Saved: dimension_radar.pdf")


def plot_baseline_comparison(results: List[Dict], config: Dict):
    """Plot multi-agent vs weak/strong baseline judge scores (paired)."""
    setup_publication_style()

    valid = [r for r in results if r.get("status") != "fatal_error"]
    weak, strong, multi = [], [], []
    for r in valid:
        p = _primary(r)
        if not p or p.get("status") != "success":
            continue
        w = r.get("baselines", {}).get("weak")
        s = r.get("baselines", {}).get("strong")
        if not (w and s and w.get("status") == "success" and s.get("status") == "success"):
            continue
        wj, sj, mj = _judge_score(w), _judge_score(s), _judge_score(p)
        if None in (wj, sj, mj):
            continue
        weak.append(wj); strong.append(sj); multi.append(mj)

    if not multi:
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    x = np.arange(len(multi))
    w = 0.27
    ax.bar(x - w, weak, w, label='Weak single-pass', color='#DE8F05')
    ax.bar(x, strong, w, label='Strong single-pass', color='#CC78BC')
    ax.bar(x + w, multi, w, label='Multi-agent (full)', color='#0173B2')
    ax.set_xlabel("Task")
    ax.set_ylabel("Judge Score (1-10)")
    ax.set_title("Baseline Comparison (Independent Judge)")
    ax.set_xticks(x)
    ax.set_xticklabels([str(i+1) for i in x])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(config["output_dir"], "baseline_comparison.pdf"))
    plt.savefig(os.path.join(config["output_dir"], "baseline_comparison.png"), dpi=300)
    plt.close()
    print("  Saved: baseline_comparison.pdf")


def generate_all_plots(results: List[Dict], config: Dict):
    """Generate all publication-quality plots."""
    print("\n" + "="*60)
    print("GENERATING PUBLICATION-QUALITY FIGURES")
    print("="*60)
    plot_score_progression(results, config)
    plot_improvement_distribution(results, config)
    plot_time_vs_quality(results, config)
    plot_dimension_radar(results, config)
    plot_baseline_comparison(results, config)
    print("="*60)


# =============================================================================
# STATISTICAL ANALYSIS
# =============================================================================

def _paired_diffs(results: List[Dict], baseline_kind: str) -> List[float]:
    """Return multi-agent(full) judge score minus baseline judge score, per task."""
    diffs = []
    for r in results:
        if r.get("status") == "fatal_error":
            continue
        p = _primary(r)
        if not p or p.get("status") != "success":
            continue
        b = r.get("baselines", {}).get(baseline_kind)
        if not b or b.get("status") != "success":
            continue
        mj, bj = _judge_score(p), _judge_score(b)
        if None in (mj, bj):
            continue
        diffs.append(mj - bj)
    return diffs


def perform_statistical_analysis(results: List[Dict], config: Dict):
    """Perform statistical tests, including the fair paired comparison."""
    print("\n" + "="*60)
    print("STATISTICAL ANALYSIS")
    print("="*60)

    # 1) Within-loop improvement vs 0
    within = []
    for r in results:
        if r.get("status") == "fatal_error":
            continue
        p = _primary(r)
        if not p or not p.get("iterations"):
            continue
        within.append(p["final_score"] - p["iterations"][0]["score"])

    if within:
        t_stat, p_value = stats.ttest_1samp(within, 0)
        print(f"\n1. Within-loop improvement (H0: mean = 0)")
        print(f"   n={len(within)}  mean={np.mean(within):.4f}  std={np.std(within):.4f}")
        print(f"   t={t_stat:.4f}  p={p_value:.4f}  significant={p_value < 0.05}")

    # 2) Multi-agent vs STRONG baseline (the fair comparison)
    diffs_strong = _paired_diffs(results, "strong")
    if len(diffs_strong) >= 2:
        print(f"\n2. Multi-agent vs STRONG single-pass (paired, H0: mean diff = 0)")
        print(f"   n={len(diffs_strong)}  mean_diff={np.mean(diffs_strong):.4f}")
        t_stat, p_value = stats.ttest_1samp(diffs_strong, 0)
        cohens_d = np.mean(diffs_strong) / (np.std(diffs_strong) or 1)
        ci = stats.t.interval(0.95, len(diffs_strong)-1, loc=np.mean(diffs_strong),
                              scale=stats.sem(diffs_strong))
        print(f"   t={t_stat:.4f}  p={p_value:.4f}  significant={p_value < 0.05}")
        print(f"   Cohen's d={cohens_d:.4f}  95% CI=[{ci[0]:.4f}, {ci[1]:.4f}]")
        if len(diffs_strong) >= 6:
            w_stat, w_p = stats.wilcoxon(diffs_strong)
            print(f"   Wilcoxon W={w_stat:.4f}  p={w_p:.4f}")

    # 3) Multi-agent vs WEAK baseline
    diffs_weak = _paired_diffs(results, "weak")
    if len(diffs_weak) >= 2:
        print(f"\n3. Multi-agent vs WEAK single-pass (paired, H0: mean diff = 0)")
        print(f"   n={len(diffs_weak)}  mean_diff={np.mean(diffs_weak):.4f}")
        t_stat, p_value = stats.ttest_1samp(diffs_weak, 0)
        print(f"   t={t_stat:.4f}  p={p_value:.4f}  significant={p_value < 0.05}")

    print("="*60)


# =============================================================================
# MAIN
# =============================================================================

def build_config_from_args() -> Dict:
    """Parse CLI overrides (pilot, seeds, judge, etc.) into a fresh config."""
    import argparse
    p = argparse.ArgumentParser(description="Chakra paper experiment harness")
    p.add_argument("--pilot", action="store_true",
                   help="Quick smoke test: 3 tasks x 1 seed, full-only, fast_mode, "
                        "separate output dir.")
    p.add_argument("--fast", action="store_true", help="Use fast_mode (fewer tokens).")
    p.add_argument("--seeds", type=str, default=None,
                   help="Comma-separated seeds, e.g. '42' or '42,7,123'.")
    p.add_argument("--max-tasks", type=int, default=None,
                   help="Limit to first N tasks (deterministic order).")
    p.add_argument("--task-substring", type=str, default=None,
                   help="Only tasks containing this substring (case-insensitive).")
    p.add_argument("--only-full", action="store_true",
                   help="Run only the 'full' ablation (faster).")
    p.add_argument("--ablations", type=str, default=None,
                   help="Comma-separated modes, e.g. 'full' or 'full,agni_only'.")
    p.add_argument("--max-iterations", type=int, default=None)
    p.add_argument("--judge-model", type=str, default=None,
                   help="Judge model override (different family recommended).")
    p.add_argument("--output-dir", type=str, default=None)
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--no-clear-memory", action="store_true")
    p.add_argument("--memory-policy", type=str, default=None,
                   choices=["disabled", "frozen", "enabled"])
    p.add_argument("--dry-run", action="store_true",
                   help="Print resolved config and exit without running Ollama.")
    args = p.parse_args()

    config = dict(EXPERIMENT_CONFIG)
    pilot_tasks = None
    if args.pilot:
        config.update({
            "seeds": [42],
            "fast_mode": True,
            "max_iterations": 2,
            "ablation_modes": ["full"],
            "output_dir": "experiment_results_pilot",
            "memory_policy": "disabled",
            "clear_memory_before_run": False,
            "archive_legacy_results": False,
            "resume": True,
        })
        pilot_tasks = list(ALL_TASKS)[:3]
    if args.fast:
        config["fast_mode"] = True
    if args.seeds:
        config["seeds"] = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    if args.only_full:
        config["ablation_modes"] = ["full"]
    if args.ablations:
        config["ablation_modes"] = [s.strip() for s in args.ablations.split(",") if s.strip()]
    if args.max_iterations is not None:
        config["max_iterations"] = args.max_iterations
    if args.judge_model:
        config["judge_model"] = args.judge_model
    if args.output_dir:
        config["output_dir"] = args.output_dir
    if args.no_resume:
        config["resume"] = False
    if args.no_clear_memory:
        config["clear_memory_before_run"] = False
    if args.memory_policy:
        config["memory_policy"] = args.memory_policy
    if args.task_substring:
        needle = args.task_substring.lower()
        pilot_tasks = [t for t in ALL_TASKS if needle in t["task"].lower()]
    if args.max_tasks is not None:
        base_tasks = pilot_tasks if pilot_tasks is not None else list(ALL_TASKS)
        pilot_tasks = base_tasks[: args.max_tasks]
    if pilot_tasks is not None:
        config["_pilot_tasks"] = pilot_tasks
    return config, args


async def main():
    """Main experiment runner."""
    config, args = build_config_from_args()
    print("="*60)
    print("CHAKRA MULTI-AGENT EXPERIMENT")
    print("="*60)
    print(f"Generator: {config['generator_model']}  "
          f"Critic: {config['critic_model']}  "
          f"Judge: {config['judge_model']}")
    print(f"Max iterations: {config['max_iterations']}  "
          f"Seeds: {config['seeds']}")
    tasks_for_count = config.get("_pilot_tasks", ALL_TASKS)
    print(f"Total tasks: {len(tasks_for_count)}  (suite total {len(ALL_TASKS)})  "
          f"memory_policy={config.get('memory_policy')}")
    print(f"Output: {config['output_dir']}  pilot={bool(getattr(args, 'pilot', False))}")
    warn_judge_family(config)
    print("="*60)

    if args.dry_run:
        print(f"[dry-run] resolved config: {config}")
        print(f"[dry-run] tasks in scope: {len(tasks_for_count)}")
        print("[dry-run] no Ollama calls made.")
        return

    # Check Ollama connection
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config['ollama_url']}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]
                needed = {config["generator_model"],
                          config["critic_model"],
                          config["judge_model"]}
                missing = needed - set(model_names)
                if missing:
                    print(f"✗ Missing models: {missing}")
                    print(f"  Available: {model_names}")
                    print(f"  Pull them, e.g.: ollama pull {config['generator_model']}")
                    return
                print(f"✓ Required models available: {sorted(needed)}")
            else:
                print(f"✗ Ollama returned status {response.status_code}")
                return
    except Exception as e:
        print(f"✗ Cannot connect to Ollama: {e}")
        print("  Make sure Ollama is running: ollama serve")
        return

    # Run experiment
    start_time = time.time()
    results = await run_full_experiment(config)
    total_time = time.time() - start_time

    # Save final results
    filename = save_results(results, config)

    # Print summary
    summary = compute_summary(results)
    print("\n" + "="*60)
    print("EXPERIMENT SUMMARY")
    print("="*60)
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"\nTotal experiment time: {total_time:.1f}s")
    print("="*60)

    # Generate plots
    generate_all_plots(results, config)

    # Statistical analysis
    perform_statistical_analysis(results, config)

    print(f"\n✓ Experiment complete! Results saved to: {config['output_dir']}/")


if __name__ == "__main__":
    asyncio.run(main())
