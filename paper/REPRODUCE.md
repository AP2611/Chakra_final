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

Pinned to the versions exercised in this repo: `numpy==2.2.6`,
`scipy==1.15.3`, `matplotlib==3.10.0` (see `backend/requirements.txt`).
Every `latest.json` logs the versions actually used, so a future
environment mismatch is visible in the output itself.

Models are served locally with [Ollama](https://ollama.com):

```bash
ollama pull qwen2.5:1.5b     # weak generator (drafter)
ollama pull mistral:latest   # critic + independent judge (default)
ollama serve                 # ensure the daemon is running
```

For a different judge family (recommended sensitivity check): `ollama
pull llava:latest` (LLaMA ~7B) or `ollama pull llama3.2:1b` (LLaMA ~1B)
and re-run with `--judge-model`. Same-family judge is allowed but the
harness warns loudly when `judge_model == critic_model`.

## 2. Run the experiment

From the repository root:

```bash
# Quick smoke test first (3 tasks x 1 seed, fast, full-only, pilot dir):
python run_experiment.py --pilot
# or print the resolved config without calling Ollama:
python run_experiment.py --pilot --dry-run

# Full paper run (30 tasks x 3 seeds, normal mode, ~3k calls = hours):
python run_experiment.py

# Full run with a different judge family (sensitivity check):
python run_experiment.py --judge-model llava:latest
```

What it does (see [`run_experiment.py`](../run_experiment.py)):

1. Archives legacy old-schema results to `experiment_results/archive_legacy_*/`
   and backs up + clears `backend/data/memory.db` (memory policy is
   `disabled` for paper runs, so Smriti neither reads nor writes).
2. Connects to Ollama and verifies the required models are present.
3. Seeds `np.random`, `PYTHONHASHSEED`, and every LLM call via Ollama's
   `seed` option (per task/seed/agent/iteration; judge `seed+999`).
4. For each task × seed it runs:
   - **weak single-pass** baseline (qwen2.5:1.5b, one shot),
   - **strong single-pass** baseline (mistral:latest, one shot),
   - the multi-agent loop in `full`, `agni_only`, `sutra_only` modes.
5. Scores **every** final solution with the **independent judge**
   ([`backend/evaluation/judge.py`](../backend/evaluation/judge.py)) and the
   **objective execution metric** (all 17 code tasks now have reference
   tests, scored with partial-credit prefix execution).
6. Writes `experiment_results/results_<timestamp>.json` (raw data + `summary`)
   plus `latest.json` and five publication figures.

Configuration (models, seeds, iterations, ablation modes, memory policy)
lives in `EXPERIMENT_CONFIG` at the top of `run_experiment.py` and can be
overridden on the CLI (`--seeds`, `--max-tasks`, `--task-substring`,
`--only-full`, `--ablations`, `--max-iterations`, `--fast`, `--judge-model`,
`--output-dir`, `--no-resume`, `--no-clear-memory`, `--memory-policy`).
To change seeds:

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
- By default the judge shares the critic's model family (`mistral:latest`);
  run the sensitivity check with `--judge-model llava:latest` (or similar)
  and report the correlation — do not claim family-level independence
  without it.
- Smriti is disabled during paper evaluation (`memory_policy="disabled"`);
  any memory benefit needs its own online-learning protocol.
- LLM sampling is seeded via Ollama's `seed` option but is not bit-identical
  across versions/hardware; multiple seeds + paired tests account for variance.
- Absolute numbers depend on the chosen local models; versions are logged
  in `latest.json`.
