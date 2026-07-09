# Reproducing the Chakra Experiments

This document explains how to reproduce every number and figure in the
manuscript ([`manuscript.md`](manuscript.md)).

## 1. Environment

```bash
# Backend (agents, orchestrator, evaluation)
cd backend
pip install -r requirements.txt

# Experiment harness (root-level, needs plotting + stats)
pip install numpy scipy matplotlib
```

Models are served locally with [Ollama](https://ollama.com):

```bash
ollama pull qwen2.5:1.5b     # weak generator (drafter)
ollama pull mistral:latest   # critic + independent judge
ollama serve                 # ensure the daemon is running
```

## 2. Run the experiment

From the repository root:

```bash
python run_experiment.py
```

What it does (see [`run_experiment.py`](../run_experiment.py)):

1. Connects to Ollama and verifies the required models are present.
2. For each task × seed it runs:
   - **weak single-pass** baseline (qwen2.5:1.5b, one shot),
   - **strong single-pass** baseline (mistral:latest, one shot),
   - the multi-agent loop in `full`, `agni_only`, `sutra_only` modes.
3. Scores **every** final solution with the **independent judge**
   ([`backend/evaluation/judge.py`](../backend/evaluation/judge.py)) and the
   **objective execution metric**
   ([`backend/evaluation/objective.py`](../backend/evaluation/objective.py)).
4. Writes `experiment_results/results_<timestamp>.json` (raw data + `summary`)
   and five publication figures.

Configuration (models, seeds, iterations, ablation modes) lives in
`EXPERIMENT_CONFIG` at the top of `run_experiment.py`. To change seeds:

```python
EXPERIMENT_CONFIG = { ..., "seeds": [42, 7, 123], ... }
```

## 3. Outputs

- `experiment_results/results_<timestamp>.json` → `summary` block contains:
  - `weak_judge_mean`, `strong_judge_mean`, `multi_judge_mean`
  - `improvement_vs_weak`, `improvement_vs_strong` (the headline paired gains)
  - `within_loop_improvement_mean/std`
  - `objective_exec_rate_weak/strong/multi` (code execution success)
  - `weak_time_mean`, `strong_time_mean`, `multi_time_mean`, `multi_tokens_mean`
  - `ablation_judge_means` (full / agni_only / sutra_only)
- Figures: `score_progression`, `improvement_distribution`, `time_vs_quality`,
  `dimension_radar`, `baseline_comparison` (PDF + PNG).

Copy the `summary` values into the Results table in `manuscript.md`.

## 4. Statistical tests

`perform_statistical_analysis` (in `run_experiment.py`) prints, for the
multi-agent (full) run:

- a one-sample t-test on **within-loop** improvement vs 0,
- a **paired** t-test + Wilcoxon signed-rank on (multi-agent − strong
  baseline) judge scores, with Cohen's d and a 95% CI,
- the same paired test vs the weak baseline.

## 5. Validate without Ollama (CI-friendly)

`test_experiment_pipeline.py` exercises the JSON parser, `compute_summary`,
all plotting functions, and the statistical analysis on synthetic data — no
models required:

```bash
python test_experiment_pipeline.py
```

## 6. Threats / caveats to report

- The independent judge is still an LLM; objective execution rates are the
  primary non-circular signal.
- LLM sampling is not perfectly reproducible; multiple seeds + paired tests
  account for variance.
- Absolute numbers depend on the chosen local models.
