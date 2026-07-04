"""Test script to demonstrate Sutra's structured scoring and improvement measurement."""
import asyncio
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, 'backend')
from agents.sutra import Sutra, compute_composite, smooth_score, SutraScores


# Sample outputs simulating Yantra's progression across iterations
# These are realistic code outputs of varying quality
SAMPLE_OUTPUTS = [
    # Iteration 1: Buggy, incomplete
    {
        "task": "Write a Python function to check if a number is prime",
        "output": "def is_prime(n):\n    if n > 1:\n        for i in range(2, n):\n            if n % i == 0:\n                return False\n        return True\n    else:\n        return False",
        "expected_issues": ["missing edge case n=2", "inefficient O(n) instead of O(sqrt(n)", "no input validation"]
    },
    # Iteration 2: Fixed edge case, still inefficient
    {
        "task": "Write a Python function to check if a number is prime",
        "output": "def is_prime(n):\n    if n <= 1:\n        return False\n    if n == 2:\n        return True\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True",
        "expected_issues": ["still O(n) complexity", "no docstring", "no type hints"]
    },
    # Iteration 3: Optimized, clean
    {
        "task": "Write a Python function to check if a number is prime",
        "output": "def is_prime(n: int) -> bool:\n    \"\"\"Check if a number is prime.\"\"\"\n    if n <= 1:\n        return False\n    if n <= 3:\n        return True\n    if n % 2 == 0 or n % 3 == 0:\n        return False\n    i = 5\n    while i * i <= n:\n        if n % i == 0 or n % (i + 2) == 0:\n            return False\n        i += 6\n    return True",
        "expected_issues": ["minor: could add more input validation"]
    },
]

# Simulated Sutra scores for each iteration (what the LLM would return)
# These represent realistic scoring progression
SIMULATED_SCORES = [
    SutraScores(
        correctness=4, accuracy=5, efficiency=3, clarity=6, edge_case_coverage=3, groundedness=None
    ),
    SutraScores(
        correctness=6, accuracy=6, efficiency=4, clarity=6, edge_case_coverage=5, groundedness=None
    ),
    SutraScores(
        correctness=8, accuracy=8, efficiency=8, clarity=8, edge_case_coverage=7, groundedness=None
    ),
]

# Simulated critiques for each iteration
SIMULATED_CRITIQUES = [
    "1. Missing edge case: n=2 returns None instead of True. "
    "2. Inefficient: loops up to n instead of sqrt(n). "
    "3. No input validation for non-integers.",

    "1. Still O(n) complexity - should use sqrt(n) optimization. "
    "2. No docstring or type hints. "
    "3. Logic is correct for n >= 2.",

    "1. Minor: could add explicit type checking for input. "
    "2. Otherwise solid implementation with good optimization.",
]


async def run_simulation():
    """Simulate the scoring pipeline without calling Ollama."""
    print("="*60)
    print("SUTRA SCORING SIMULATION")
    print("="*60)

    previous_composite = None
    results = []

    for i, (sample, scores, critique) in enumerate(zip(SAMPLE_OUTPUTS, SIMULATED_SCORES, SIMULATED_CRITIQUES), 1):
        raw_composite = compute_composite(scores)
        final_composite = smooth_score(previous_composite, raw_composite, critique)

        result = {
            "iteration": i,
            "raw_composite": raw_composite,
            "smoothed_composite": final_composite,
            "scores": scores.model_dump(),
            "critique": critique,
            "smoothed": final_composite != raw_composite,
        }
        results.append(result)

        print(f"\nIteration {i}:")
        print(f"  Raw composite:   {raw_composite:.2f}")
        print(f"  Smoothed score:  {final_composite:.2f}")
        print(f"  Clamped:         {result['smoothed']}")
        print(f"  Scores:          {scores.model_dump()}")

        previous_composite = final_composite

    return results


def plot_simulation_results(results):
    """Plot the simulation results."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Sutra Scoring: Before vs After Smoothing (Simulated)", fontsize=16, fontweight='bold')

    iterations = [r["iteration"] for r in results]
    raw_scores = [r["raw_composite"] for r in results]
    smoothed_scores = [r["smoothed_composite"] for r in results]

    # Plot 1: Raw vs Smoothed over iterations
    ax1 = axes[0, 0]
    ax1.plot(iterations, raw_scores, marker='s', linestyle='--', color='#ff6b6b', label='Raw Composite', linewidth=2)
    ax1.plot(iterations, smoothed_scores, marker='o', color='#4ecdc4', label='Smoothed Score', linewidth=2)
    ax1.fill_between(iterations, raw_scores, smoothed_scores, alpha=0.2, color='#4ecdc4')
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Score (1-10)")
    ax1.set_title("Raw vs Smoothed Composite Score")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 10)
    ax1.set_xticks(iterations)

    # Plot 2: Per-dimension scores heatmap-style
    ax2 = axes[0, 1]
    dimensions = ["correctness", "accuracy", "efficiency", "clarity", "edge_case_coverage"]
    dim_labels = ["Correctness", "Accuracy", "Efficiency", "Clarity", "Edge Cases"]
    scores_matrix = np.array([[r["scores"][d] for d in dimensions] for r in results])

    im = ax2.imshow(scores_matrix, cmap='RdYlGn', aspect='auto', vmin=1, vmax=10)
    ax2.set_xticks(range(len(dim_labels)))
    ax2.set_xticklabels(dim_labels, rotation=45, ha='right')
    ax2.set_yticks(iterations)
    ax2.set_yticklabels([f"Iter {i}" for i in iterations])
    ax2.set_title("Per-Dimension Scores (1-10)")
    plt.colorbar(im, ax=ax2, label='Score')

    # Add text annotations
    for i in range(len(iterations)):
        for j in range(len(dimensions)):
            text = ax2.text(j, i, scores_matrix[i, j], ha="center", va="center", color="black", fontsize=10)

    # Plot 3: Improvement delta
    ax3 = axes[1, 0]
    deltas = [smoothed_scores[i] - smoothed_scores[i-1] if i > 0 else 0 for i in range(len(smoothed_scores))]
    colors = ['#4ecdc4' if d > 0 else '#ff6b6b' for d in deltas]
    ax3.bar(iterations, deltas, color=colors, alpha=0.8)
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax3.axhline(y=1.5, color='red', linestyle='--', linewidth=1, label='Smoothing clamp (±1.5)')
    ax3.axhline(y=-1.5, color='red', linestyle='--', linewidth=1)
    ax3.set_xlabel("Iteration")
    ax3.set_ylabel("Score Delta")
    ax3.set_title("Iteration-to-Iteration Improvement")
    ax3.set_xticks(iterations)
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')

    # Plot 4: Dimension contribution to composite
    ax4 = axes[1, 1]
    weights = {"correctness": 0.45, "accuracy": 0.25, "efficiency": 0.10, "clarity": 0.10, "edge_case_coverage": 0.10}
    contributions = []
    for r in results:
        contrib = {d: r["scores"][d] * w for d, w in weights.items()}
        contributions.append(contrib)

    bottom = np.zeros(len(iterations))
    colors_dim = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    for idx, dim in enumerate(dimensions):
        values = [contributions[i][dim] for i in range(len(iterations))]
        ax4.bar(iterations, values, bottom=bottom, label=dim_labels[idx], color=colors_dim[idx], alpha=0.8)
        bottom += values

    ax4.set_xlabel("Iteration")
    ax4.set_ylabel("Weighted Contribution")
    ax4.set_title("Composite Score Breakdown by Dimension")
    ax4.set_xticks(iterations)
    ax4.legend(loc='upper left', fontsize=8)
    ax4.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig("sutra_scoring_simulation.png", dpi=150, bbox_inches='tight')
    print("\nSimulation graphs saved to: sutra_scoring_simulation.png")

    # Print summary
    print("\n" + "="*60)
    print("SIMULATION SUMMARY")
    print("="*60)
    print(f"Initial raw score:   {raw_scores[0]:.2f}")
    print(f"Final smoothed score: {smoothed_scores[-1]:.2f}")
    print(f"Total improvement:    {smoothed_scores[-1] - smoothed_scores[0]:.2f} points")
    print(f"Improvement %:        {(smoothed_scores[-1] - smoothed_scores[0]) / smoothed_scores[0] * 100:.1f}%")
    print(f"Times smoothing applied: {sum(1 for r in results if r['smoothed'])}/{len(results)}")
    print("="*60)


if __name__ == "__main__":
    results = asyncio.run(run_simulation())
    plot_simulation_results(results)
