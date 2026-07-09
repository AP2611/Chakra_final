"""Experiment script for collecting real data for arXiv paper.

This script runs the multi-agent system on real tasks and collects metrics
for publication-quality figures and statistical analysis.
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
# Lazy imports to avoid segfault from sentence_transformers at import time
# from orchestrator import Orchestrator
# from agents.yantra import Yantra
# from agents.sutra import compute_composite


# =============================================================================
# CONFIGURATION
# =============================================================================

EXPERIMENT_CONFIG = {
    "model": "mistral:latest",  # Default model (used when split not specified)
    "generator_model": "qwen2.5:1.5b",  # Weaker generator -> creates headroom for improvement
    "critic_model": "mistral:latest",   # Stronger critic evaluates & improves
    "ollama_url": "http://localhost:11434",
    "max_iterations": 5,
    "min_improvement": 0.5,
    "fast_mode": False,  # Use normal mode for better quality
    "output_dir": "experiment_results",
    "seed": 42,
    "use_rag": False,  # Global RAG toggle; document_qa tasks enable it per-task
    "resume": True,  # Resume from latest results file if available
    # NOTE: set "resume": False for a clean run when testing the new pipeline,
    # since the loop mechanics (validation, diff-based Agni, split models) changed.
}

# Task categories for diverse evaluation
TASK_CATEGORIES = {
    "code_algorithms": [
        "Write a Python function to check if a number is prime",
        "Write a Python function to reverse a linked list",
        "Write a Python function to find the maximum subarray sum (Kadane's algorithm)",
        "Write a Python function to merge two sorted arrays",
        "Write a Python function to detect a cycle in a linked list",
        "Write a Python function to validate a binary search tree",
        "Write a Python function to perform binary search on a sorted array",
        "Write a Python function to generate all permutations of a string",
        "Write a Python function to implement depth-first search on a graph",
        "Write a Python function to find the longest common subsequence of two strings",
    ],
    "code_optimization": [
        "Optimize this Python function for performance: def find_duplicates(arr): return [x for i, x in enumerate(arr) if x in arr[:i]]",
        "Refactor this code to be more readable: x=lambda a,b: a+b if a>b else a-b",
        "Improve the error handling in this function: def divide(a,b): return a/b",
    ],
    "math_reasoning": [
        "Solve for x: 3x + 7 = 22",
        "What is the derivative of x^3 + 2x^2 - 5x + 1?",
        "Calculate the area of a circle with radius 5",
        "If a train travels 120 km in 2 hours, what is its speed in m/s?",
    ],
    "text_generation": [
        "Explain the concept of recursion in programming",
        "Write a brief summary of how neural networks learn",
        "Describe the difference between TCP and UDP",
    ],
    "document_qa": [
        "What are the four specialized agents in Chakra and what does each do?",
        "How does the recursive learning loop decide when to stop?",
        "How does Chakra validate generated Python code, and what happens on failure?",
        "What is the purpose of RAG in Chakra and how does it reduce hallucination?",
    ],
}

# Combine all tasks. document_qa tasks enable RAG; others follow the global toggle.
ALL_TASKS = []
for category, tasks in TASK_CATEGORIES.items():
    for task in tasks:
        use_rag = True if category == "document_qa" else EXPERIMENT_CONFIG["use_rag"]
        ALL_TASKS.append({"task": task, "category": category, "use_rag": use_rag})


# =============================================================================
# EXPERIMENT RUNNERS
# =============================================================================

async def run_single_agent_baseline(task: str, config: Dict) -> Dict[str, Any]:
    """Run single-pass generation (Yantra only) as baseline."""
    from agents.yantra import Yantra
    yantra = Yantra(
        ollama_url=config["ollama_url"],
        model=config.get("generator_model", config["model"]),
        fast_mode=config["fast_mode"]
    )
    
    start_time = time.time()
    result = await yantra.process(task=task)
    elapsed = time.time() - start_time
    
    return {
        "task": task,
        "output": result["output"],
        "time": elapsed,
        "agent": "Yantra (baseline)",
    }


# Relative compute cost per model (params in B / 7B reference). Used to compare
# cost of a weak-model+loop vs a strong single pass. Local models are "free" to
# call, but the weak model is far cheaper per token, so total cost = factor * tokens.
MODEL_COST_FACTOR = {
    "mistral:latest": 1.0,       # ~7B
    "qwen2.5:1.5b": 1.5 / 7.0,   # ~1.5B
    "qwen2.5:0.5b": 0.5 / 7.0,
    "llava:latest": 7.0 / 7.0,
}


def relative_cost(model: str, total_tokens: int) -> float:
    """Relative compute cost = (model size factor) x tokens."""
    factor = MODEL_COST_FACTOR.get(model, 1.0)
    return factor * max(0, total_tokens)


async def run_strong_single_pass(task: str, config: Dict) -> Dict[str, Any]:
    """Strong-model single-pass baseline (the fair comparison target)."""
    from agents.yantra import Yantra
    yantra = Yantra(
        ollama_url=config["ollama_url"],
        model=config.get("critic_model", config["model"]),
        fast_mode=config["fast_mode"]
    )
    yantra.reset_token_stats()

    start_time = time.time()
    result = await yantra.process(task=task)
    elapsed = time.time() - start_time

    return {
        "task": task,
        "output": result["output"],
        "time": elapsed,
        "agent": "Yantra (strong single-pass)",
        "model": config.get("critic_model", config["model"]),
        "total_tokens": yantra.token_stats["total"],
        "cost": relative_cost(config.get("critic_model", config["model"]), yantra.token_stats["total"]),
    }


async def run_multi_agent_loop(task: str, config: Dict, use_rag: bool = False, is_code: bool = True, mode: str = "full") -> Dict[str, Any]:
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
        fast_mode=config["fast_mode"]
    )

    start_time = time.time()
    result = await orchestrator.process(
        task=task,
        use_rag=use_rag,
        is_code=is_code,
        mode=mode
    )
    elapsed = time.time() - start_time

    # Per-agent cost: weight each agent's tokens by its model's cost factor
    ts = result.get("token_stats", {})
    cost = (
        relative_cost(gen_model, ts.get("yantra", {}).get("total", 0))
        + relative_cost(crit_model, ts.get("sutra", {}).get("total", 0))
        + relative_cost(crit_model, ts.get("agni", {}).get("total", 0))
    )

    # Execution validation for code tasks (judge validation signal)
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
    }


async def run_experiment_task(task_data: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """Run both baseline and multi-agent on a single task."""
    task = task_data["task"]
    category = task_data["category"]
    use_rag = task_data.get("use_rag", config.get("use_rag", False))
    is_code = category != "document_qa"
    
    print(f"\n{'='*60}")
    print(f"Task: {task[:60]}...")
    print(f"Category: {category}  | RAG: {use_rag} | Code: {is_code}")
    print(f"{'='*60}")
    
    # Run baseline
    print("  [1/2] Running baseline (single-pass)...")
    try:
        baseline = await run_single_agent_baseline(task, config)
        baseline["status"] = "success"
    except Exception as e:
        print(f"  Baseline FAILED: {e}")
        baseline = {"task": task, "status": "failed", "error": str(e)}
    
    # Run multi-agent loop
    print("  [2/2] Running multi-agent loop...")
    try:
        multi = await run_multi_agent_loop(task, config, use_rag=use_rag, is_code=is_code)
        multi["status"] = "success"
    except Exception as e:
        print(f"  Multi-agent FAILED: {e}")
        multi = {"task": task, "status": "failed", "error": str(e)}
    
    return {
        "task": task,
        "category": category,
        "baseline": baseline,
        "multi_agent": multi,
        "timestamp": datetime.now().isoformat(),
    }


def load_latest_results(config: Dict) -> List[Dict[str, Any]]:
    """Load the latest results file for resuming."""
    output_dir = config["output_dir"]
    if not os.path.exists(output_dir):
        return []
    
    # Find all result files
    result_files = [f for f in os.listdir(output_dir) if f.startswith("results_") and f.endswith(".json")]
    if not result_files:
        return []
    
    # Sort by filename (which includes timestamp)
    result_files.sort(reverse=True)
    latest_file = os.path.join(output_dir, result_files[0])
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
            return data.get("results", [])
    except Exception as e:
        print(f"Warning: Could not load latest results file: {e}")
        return []


async def run_full_experiment(config: Dict) -> List[Dict[str, Any]]:
    """Run experiment on all tasks."""
    results = []
    completed_tasks = set()
    
    # Load existing results if resuming
    if config.get("resume", False):
        existing_results = load_latest_results(config)
        results = existing_results
        completed_tasks = {r["task"] for r in existing_results if r.get("status") != "fatal_error"}
        print(f"Resuming from {len(completed_tasks)} completed tasks")
    
    total = len(ALL_TASKS)
    remaining = [t for t in ALL_TASKS if t["task"] not in completed_tasks]
    
    print(f"Total tasks: {total}, Remaining: {len(remaining)}")
    
    for i, task_data in enumerate(remaining, 1):
        print(f"\n[{len(completed_tasks) + i}/{total}] Processing task...")
        try:
            result = await run_experiment_task(task_data, config)
            results.append(result)
            
            # Save intermediate results
            save_results(results, config)
            
        except Exception as e:
            print(f"  FATAL ERROR on task {len(completed_tasks) + i}: {e}")
            results.append({
                "task": task_data["task"],
                "category": task_data["category"],
                "status": "fatal_error",
                "error": str(e)
            })
    
    return results


# =============================================================================
# DATA SAVING
# =============================================================================

def save_results(results: List[Dict], config: Dict):
    """Save results to JSON file."""
    os.makedirs(config["output_dir"], exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(config["output_dir"], f"results_{timestamp}.json")
    
    with open(filename, 'w') as f:
        json.dump({
            "config": config,
            "results": results,
            "summary": compute_summary(results)
        }, f, indent=2, default=str)
    
    print(f"  Saved: {filename}")
    return filename


def compute_summary(results: List[Dict]) -> Dict[str, Any]:
    """Compute summary statistics from results."""
    valid_baseline = []
    valid_multi = []
    
    for r in results:
        if r.get("baseline", {}).get("status") == "success":
            valid_baseline.append(r["baseline"])
        if r.get("multi_agent", {}).get("status") == "success":
            valid_multi.append(r["multi_agent"])
    
    if not valid_multi:
        return {"error": "No successful multi-agent runs"}
    
    # Extract metrics
    baseline_times = [r["time"] for r in valid_baseline]
    multi_times = [r["time"] for r in valid_multi]
    multi_scores = [r["final_score"] for r in valid_multi]
    multi_iterations = [r["total_iterations"] for r in valid_multi]
    
    # Per-iteration scores
    all_iteration_scores = []
    for r in valid_multi:
        for iter_data in r["iterations"]:
            all_iteration_scores.append({
                "task": r["task"],
                "iteration": iter_data["iteration"],
                "score": iter_data["score"],
                "raw_composite": iter_data["raw_composite"],
                "smoothed": iter_data["smoothed"],
            })
    
    # Improvement per task
    improvements = []
    for r in valid_multi:
        if r["iterations"]:
            initial = r["iterations"][0]["score"]
            final = r["final_score"]
            improvements.append(final - initial)
    
    return {
        "total_tasks": len(results),
        "successful_baseline": len(valid_baseline),
        "successful_multi": len(valid_multi),
        "baseline_time_mean": float(np.mean(baseline_times)) if baseline_times else 0,
        "multi_time_mean": float(np.mean(multi_times)) if multi_times else 0,
        "final_score_mean": float(np.mean(multi_scores)) if multi_scores else 0,
        "final_score_std": float(np.std(multi_scores)) if multi_scores else 0,
        "iterations_mean": float(np.mean(multi_iterations)) if multi_iterations else 0,
        "improvement_mean": float(np.mean(improvements)) if improvements else 0,
        "improvement_std": float(np.std(improvements)) if improvements else 0,
        "num_tasks_improved": sum(1 for imp in improvements if imp > 0),
    }


# =============================================================================
# PUBLICATION-QUALITY PLOTTING
# =============================================================================

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
    """Plot score progression over iterations for all tasks."""
    setup_publication_style()
    
    valid_results = [r for r in results 
                     if r.get("multi_agent", {}).get("status") == "success"
                     and r["multi_agent"]["iterations"]]
    
    if not valid_results:
        print("No valid results for score progression plot")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Plot 1: All task trajectories
    ax1 = axes[0]
    for r in valid_results:
        iterations = [i["iteration"] for i in r["multi_agent"]["iterations"]]
        scores = [i["score"] for i in r["multi_agent"]["iterations"]]
        ax1.plot(iterations, scores, marker='o', alpha=0.7, linewidth=1.5)
    
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Composite Score (1-10)")
    ax1.set_title("Score Progression Across Tasks")
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 10)
    ax1.set_xticks(range(1, config["max_iterations"] + 1))
    
    # Plot 2: Mean trajectory with confidence interval
    ax2 = axes[1]
    max_iter = config["max_iterations"]
    mean_scores = []
    std_scores = []
    
    for i in range(1, max_iter + 1):
        scores_at_iter = []
        for r in valid_results:
            if len(r["multi_agent"]["iterations"]) >= i:
                scores_at_iter.append(r["multi_agent"]["iterations"][i-1]["score"])
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
    ax2.set_title("Mean Score Progression (n={})".format(len(valid_results)))
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 10)
    ax2.set_xticks(iterations)
    
    plt.tight_layout()
    os.makedirs(config["output_dir"], exist_ok=True)
    plt.savefig(os.path.join(config["output_dir"], "score_progression.pdf"))
    plt.savefig(os.path.join(config["output_dir"], "score_progression.png"), dpi=300)
    plt.close()
    print("  Saved: score_progression.pdf")


def plot_improvement_distribution(results: List[Dict], config: Dict):
    """Plot distribution of improvements."""
    setup_publication_style()
    
    valid_results = [r for r in results 
                     if r.get("multi_agent", {}).get("status") == "success"
                     and r["multi_agent"]["iterations"]]
    
    if not valid_results:
        return
    
    improvements = []
    categories = []
    for r in valid_results:
        if r["multi_agent"]["iterations"]:
            initial = r["multi_agent"]["iterations"][0]["score"]
            final = r["multi_agent"]["final_score"]
            improvements.append(final - initial)
            categories.append(r["category"])
    
    if not improvements:
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Plot 1: Histogram of improvements
    ax1 = axes[0]
    ax1.hist(improvements, bins=15, color='#029E73', edgecolor='black', alpha=0.8)
    ax1.axvline(np.mean(improvements), color='red', linestyle='--', linewidth=2,
                label=f'Mean: {np.mean(improvements):.2f}')
    ax1.axvline(0, color='black', linestyle='-', linewidth=0.5)
    ax1.set_xlabel("Score Improvement (Final - Initial)")
    ax1.set_ylabel("Number of Tasks")
    ax1.set_title("Distribution of Improvements")
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Plot 2: Box plot by category
    ax2 = axes[1]
    category_data = {}
    for cat, imp in zip(categories, improvements):
        if cat not in category_data:
            category_data[cat] = []
        category_data[cat].append(imp)
    
    cat_names = list(category_data.keys())
    cat_values = [category_data[cat] for cat in cat_names]
    
    bp = ax2.boxplot(cat_values, labels=cat_names, patch_artist=True)
    for patch, color in zip(bp['boxes'], ['#0173B2', '#DE8F05', '#029E73', '#CC78BC']):
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
    """Plot time vs quality trade-off."""
    setup_publication_style()
    
    valid_results = [r for r in results 
                     if r.get("multi_agent", {}).get("status") == "success"]
    
    if not valid_results:
        return
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    times = [r["multi_agent"]["time"] for r in valid_results]
    scores = [r["multi_agent"]["final_score"] for r in valid_results]
    iterations = [r["multi_agent"]["total_iterations"] for r in valid_results]
    
    scatter = ax.scatter(times, scores, c=iterations, cmap='viridis', 
                        s=100, alpha=0.8, edgecolors='black', linewidth=1)
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label("Iterations", rotation=270, labelpad=15)
    
    ax.set_xlabel("Total Time (seconds)")
    ax.set_ylabel("Final Score (1-10)")
    ax.set_title("Time-Quality Trade-off")
    ax.grid(True, alpha=0.3)
    
    # Add trend line
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
    """Plot radar chart of average dimension scores."""
    setup_publication_style()
    
    valid_results = [r for r in results 
                     if r.get("multi_agent", {}).get("status") == "success"
                     and r["multi_agent"]["iterations"]]
    
    if not valid_results:
        return
    
    # Collect all final scores
    dimensions = ["correctness", "accuracy", "efficiency", "clarity", "edge_case_coverage"]
    dim_scores = {dim: [] for dim in dimensions}
    
    for r in valid_results:
        final_iter = r["multi_agent"]["iterations"][-1]
        scores = final_iter.get("sutra_scores", {})
        for dim in dimensions:
            if dim in scores:
                dim_scores[dim].append(scores[dim])
    
    # Compute means
    means = [np.mean(dim_scores[dim]) if dim_scores[dim] else 0 for dim in dimensions]
    
    # Radar plot
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    
    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
    means_plot = means + means[:1]  # Close the polygon
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


def generate_all_plots(results: List[Dict], config: Dict):
    """Generate all publication-quality plots."""
    print("\n" + "="*60)
    print("GENERATING PUBLICATION-QUALITY FIGURES")
    print("="*60)
    
    plot_score_progression(results, config)
    plot_improvement_distribution(results, config)
    plot_time_vs_quality(results, config)
    plot_dimension_radar(results, config)
    
    print("="*60)


# =============================================================================
# STATISTICAL ANALYSIS
# =============================================================================

def perform_statistical_analysis(results: List[Dict], config: Dict):
    """Perform statistical tests on the results."""
    print("\n" + "="*60)
    print("STATISTICAL ANALYSIS")
    print("="*60)
    
    valid_results = [r for r in results 
                     if r.get("multi_agent", {}).get("status") == "success"
                     and r["multi_agent"]["iterations"]]
    
    if not valid_results:
        print("No valid results for statistical analysis")
        return
    
    # Extract improvements
    improvements = []
    for r in valid_results:
        if r["multi_agent"]["iterations"]:
            initial = r["multi_agent"]["iterations"][0]["score"]
            final = r["multi_agent"]["final_score"]
            improvements.append(final - initial)
    
    if not improvements:
        return
    
    # One-sample t-test: H0: mean improvement = 0
    t_stat, p_value = stats.ttest_1samp(improvements, 0)
    
    print(f"\n1. One-sample t-test (H0: mean improvement = 0)")
    print(f"   t-statistic: {t_stat:.4f}")
    print(f"   p-value: {p_value:.4f}")
    print(f"   Significant at α=0.05: {p_value < 0.05}")
    
    # Effect size (Cohen's d)
    cohens_d = np.mean(improvements) / np.std(improvements)
    print(f"\n2. Effect Size (Cohen's d): {cohens_d:.4f}")
    if abs(cohens_d) < 0.2:
        effect_size_interp = "negligible"
    elif abs(cohens_d) < 0.5:
        effect_size_interp = "small"
    elif abs(cohens_d) < 0.8:
        effect_size_interp = "medium"
    else:
        effect_size_interp = "large"
    print(f"   Interpretation: {effect_size_interp}")
    
    # Confidence interval
    ci = stats.t.interval(0.95, len(improvements)-1, 
                          loc=np.mean(improvements),
                          scale=stats.sem(improvements))
    print(f"\n3. 95% Confidence Interval: [{ci[0]:.4f}, {ci[1]:.4f}]")
    
    # Normality test
    shapiro_stat, shapiro_p = stats.shapiro(improvements)
    print(f"\n4. Shapiro-Wilk Normality Test:")
    print(f"   W-statistic: {shapiro_stat:.4f}")
    print(f"   p-value: {shapiro_p:.4f}")
    print(f"   Normally distributed: {shapiro_p > 0.05}")
    
    # Wilcoxon signed-rank test (non-parametric alternative)
    if len(improvements) >= 6:
        w_stat, w_p = stats.wilcoxon(improvements)
        print(f"\n5. Wilcoxon Signed-Rank Test (non-parametric):")
        print(f"   W-statistic: {w_stat:.4f}")
        print(f"   p-value: {w_p:.4f}")
    
    print("="*60)


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Main experiment runner."""
    print("="*60)
    print("CHAKRA MULTI-AGENT EXPERIMENT")
    print("="*60)
    print(f"Model: {EXPERIMENT_CONFIG['model']}")
    print(f"Max iterations: {EXPERIMENT_CONFIG['max_iterations']}")
    print(f"Fast mode: {EXPERIMENT_CONFIG['fast_mode']}")
    print(f"Total tasks: {len(ALL_TASKS)}")
    print("="*60)
    
    # Check Ollama connection
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{EXPERIMENT_CONFIG['ollama_url']}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]
                if EXPERIMENT_CONFIG["model"] in model_names:
                    print(f"✓ Model {EXPERIMENT_CONFIG['model']} is available")
                else:
                    print(f"✗ Model {EXPERIMENT_CONFIG['model']} NOT found!")
                    print(f"  Available models: {model_names}")
                    return
            else:
                print(f"✗ Ollama returned status {response.status_code}")
                return
    except Exception as e:
        print(f"✗ Cannot connect to Ollama: {e}")
        print("  Make sure Ollama is running: ollama serve")
        return
    
    # Run experiment
    start_time = time.time()
    results = await run_full_experiment(EXPERIMENT_CONFIG)
    total_time = time.time() - start_time
    
    # Save final results
    filename = save_results(results, EXPERIMENT_CONFIG)
    
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
    generate_all_plots(results, EXPERIMENT_CONFIG)
    
    # Statistical analysis
    perform_statistical_analysis(results, EXPERIMENT_CONFIG)
    
    print(f"\n✓ Experiment complete! Results saved to: {EXPERIMENT_CONFIG['output_dir']}/")


if __name__ == "__main__":
    asyncio.run(main())
