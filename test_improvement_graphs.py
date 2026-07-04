"""Test script to measure and plot before/after improvement of the agent system."""
import asyncio
import json
import sys
import time
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, 'backend')
from orchestrator import Orchestrator


TEST_TASKS = [
    "Write a Python function to check if a number is prime",
    "Write a Python function to reverse a linked list",
    "Write a Python function to find the maximum subarray sum (Kadane's algorithm)",
    "Write a Python function to merge two sorted arrays",
    "Write a Python function to detect a cycle in a linked list",
    "Write a Python function to validate a binary search tree",
    "Write a Python function to perform binary search on a sorted array",
    "Write a Python function to generate all permutations of a string",
]


async def run_test():
    orchestrator = Orchestrator(fast_mode=True, max_iterations=3)
    results = []

    print(f"Running {len(TEST_TASKS)} tasks through the agent system...")
    print("This will take a few minutes as it calls Ollama for each iteration.\n")

    for i, task in enumerate(TEST_TASKS, 1):
        print(f"[{i}/{len(TEST_TASKS)}] Task: {task[:60]}...")
        start = time.time()

        try:
            result = await orchestrator.process(
                task=task,
                use_rag=False,
                is_code=True
            )
            elapsed = time.time() - start

            # Extract per-iteration scores
            iteration_scores = []
            raw_composites = []
            smoothed_flags = []

            for iter_data in result["iterations"]:
                iteration_scores.append(iter_data.get("score", 0.0))
                raw_composites.append(iter_data.get("raw_composite", iter_data.get("score", 0.0)))
                smoothed_flags.append(iter_data.get("smoothed", False))

            initial_score = iteration_scores[0] if iteration_scores else 0.0
            final_score = result["final_score"]
            improvement = final_score - initial_score
            improvement_pct = (improvement / initial_score * 100) if initial_score > 0 else 0

            results.append({
                "task": task,
                "initial_score": initial_score,
                "final_score": final_score,
                "raw_composite": raw_composites[0] if raw_composites else initial_score,
                "improvement": improvement,
                "improvement_pct": improvement_pct,
                "iterations": result["total_iterations"],
                "iteration_scores": iteration_scores,
                "raw_composites": raw_composites,
                "smoothed_flags": smoothed_flags,
                "elapsed": elapsed,
            })

            print(f"  Initial: {initial_score:.2f} → Final: {final_score:.2f} "
                  f"(+{improvement:.2f}, {improvement_pct:.1f}%) "
                  f"in {result['total_iterations']} iterations, {elapsed:.1f}s")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "task": task,
                "initial_score": 0.0,
                "final_score": 0.0,
                "raw_composite": 0.0,
                "improvement": 0.0,
                "improvement_pct": 0.0,
                "iterations": 0,
                "iteration_scores": [],
                "raw_composites": [],
                "smoothed_flags": [],
                "elapsed": 0.0,
                "error": str(e),
            })

    return results


def plot_results(results):
    """Generate before/after comparison graphs."""
    valid_results = [r for r in results if r["iterations"] > 0 and not r.get("error")]

    if not valid_results:
        print("No valid results to plot.")
        return

    # --- Figure 1: Score progression over iterations ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Agent System: Before vs After Improvement", fontsize=16, fontweight='bold')

    # Plot 1: Line chart - score progression per task
    ax1 = axes[0, 0]
    for r in valid_results:
        iterations = list(range(1, len(r["iteration_scores"]) + 1))
        ax1.plot(iterations, r["iteration_scores"], marker='o', label=r["task"][:40], alpha=0.8)
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Composite Score (1-10)")
    ax1.set_title("Score Progression Over Iterations")
    ax1.legend(fontsize=7, loc='lower right')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 10)

    # Plot 2: Bar chart - initial vs final score
    ax2 = axes[0, 1]
    tasks_short = [r["task"][:30] for r in valid_results]
    x = np.arange(len(tasks_short))
    width = 0.35
    initial_scores = [r["initial_score"] for r in valid_results]
    final_scores = [r["final_score"] for r in valid_results]

    bars1 = ax2.bar(x - width/2, initial_scores, width, label='Initial (Yantra)', color='#ff6b6b', alpha=0.8)
    bars2 = ax2.bar(x + width/2, final_scores, width, label='Final (After Loop)', color='#4ecdc4', alpha=0.8)

    ax2.set_ylabel("Composite Score (1-10)")
    ax2.set_title("Initial vs Final Score by Task")
    ax2.set_xticks(x)
    ax2.set_xticklabels(tasks_short, rotation=45, ha='right', fontsize=8)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_ylim(0, 10)

    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        ax2.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=7)
    for bar in bars2:
        height = bar.get_height()
        ax2.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=7)

    # Plot 3: Improvement distribution
    ax3 = axes[1, 0]
    improvements = [r["improvement"] for r in valid_results]
    colors = ['#4ecdc4' if imp > 0 else '#ff6b6b' for imp in improvements]
    ax3.bar(range(len(improvements)), improvements, color=colors, alpha=0.8)
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax3.axhline(y=np.mean(improvements), color='blue', linestyle='--', linewidth=1.5, label=f'Mean: {np.mean(improvements):.2f}')
    ax3.set_xlabel("Task Index")
    ax3.set_ylabel("Score Improvement (points)")
    ax3.set_title("Improvement per Task (Final - Initial)")
    ax3.set_xticks(range(len(improvements)))
    ax3.set_xticklabels([f"T{i+1}" for i in range(len(improvements))], fontsize=8)
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')

    # Plot 4: Raw vs Smoothed composite (convergence analysis)
    ax4 = axes[1, 1]
    for r in valid_results[:4]:  # Show first 4 tasks to avoid clutter
        iterations = list(range(1, len(r["raw_composites"]) + 1))
        ax4.plot(iterations, r["raw_composites"], marker='s', linestyle='--', alpha=0.6, label=f'{r["task"][:20]} (raw)')
        ax4.plot(iterations, r["iteration_scores"], marker='o', alpha=0.9, label=f'{r["task"][:20]} (smoothed)')
    ax4.set_xlabel("Iteration")
    ax4.set_ylabel("Composite Score (1-10)")
    ax4.set_title("Raw vs Smoothed Score (Convergence Analysis)")
    ax4.legend(fontsize=7, loc='lower right')
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim(0, 10)

    plt.tight_layout()
    plt.savefig("improvement_graphs.png", dpi=150, bbox_inches='tight')
    print("\nGraphs saved to: improvement_graphs.png")

    # --- Print summary statistics ---
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print(f"Tasks tested: {len(valid_results)}")
    print(f"Mean initial score: {np.mean(initial_scores):.2f} ± {np.std(initial_scores):.2f}")
    print(f"Mean final score:   {np.mean(final_scores):.2f} ± {np.std(final_scores):.2f}")
    print(f"Mean improvement:   {np.mean(improvements):.2f} ± {np.std(improvements):.2f}")
    print(f"Mean improvement %: {np.mean([r['improvement_pct'] for r in valid_results]):.1f}%")
    print(f"Tasks with improvement: {sum(1 for imp in improvements if imp > 0)}/{len(improvements)}")
    print(f"Mean iterations per task: {np.mean([r['iterations'] for r in valid_results]):.1f}")
    print(f"Mean time per task: {np.mean([r['elapsed'] for r in valid_results]):.1f}s")
    print("="*60)


if __name__ == "__main__":
    results = asyncio.run(run_test())
    plot_results(results)
