# Paper-Ready Test Plan — Chunked Runs

Goal: get usable paper numbers fast, never lose >1 task to a failure,
and make every failure diagnosable. Full run is 30 tasks × 3 seeds
≈ 3k LLM calls (hours) — we never launch that blind.

## Principles

- **One seed, one output dir per chunk** — a stuck chunk never blocks
  others (`--output-dir`, `resume=True` writes `latest.json` after
  every task).
- **Fast mode for pilots** (`--pilot` ⇒ 384-token fast, 2 iterations,
  full-only), **normal mode for the paper run** (640 tokens, 3 iterations,
  3 ablations).
- **Memory always `disabled`** — no Smriti read/write, no leakage.
  Old results are archived; `latest.json` is the only paper source.
- **Acceptance per chunk** (all must hold): every condition `status=success`,
  judge `ok=True` with numeric score, objective `runs` not `None` for code,
  all 5 figures exist (`baseline_comparison.pdf` included), no
  `[Sutra] parse fallback` spam beyond ~20% (if >20%, fix scorer first).

## Chunk table

| Chunk | Tasks | Command | What it proves | Est. time |
|-------|-------|---------|----------------|-----------|
| S0 smoke | 1 (`is_prime`, seed 42) | `python run_experiment.py --pilot --task-substring is_prime` | sutra-coercion works, within-loop ≠ 0, no 3× retry storm | ~1-2 min |
| P1 core | 3 (`is_prime, reverse_list, max_subarray`, seed 42) | `python run_experiment.py --pilot` (default 3) | linked-list + Kadane tests, partial credit | ~3-6 min |
| P2 hard code | 3 (`BoundedQueue, fib, RunningMedian`, seed 42) | `python run_experiment.py --pilot --max-tasks 5 --task-substring ""` then filter (use `--max-tasks` after `--pilot` with custom order file if needed) | stateful tests, thread queue, O(log n) fib | ~5-8 min |
| P3 categories | 5 (1 code, 1 code_opt, 1 math, 1 text, 1 doc_qa, seed 42, ablations full+agni_only+sutra_only) | `python run_experiment.py --pilot --ablations full,agni_only,sutra_only --task-substring ""` (trim with `--max-tasks 5`) | grounding, math/text judge-only, ablation stats | ~8-12 min |
| F-seed | 30 × 1 seed, normal mode, 3 ablations | `python run_experiment.py --seeds 42` → `... --seeds 7` → `... --seeds 123` (same `experiment_results/`, resume merges) | paper numbers per seed, variance | hours, per-seed resume |

For P2/P3 where `--task-substring` is coarse, the harness shuffles per
seed — run with `--seed 42` and rely on `latest.json` resume to keep
completed pairs. If a chunk is too big, split with `--max-tasks 2`
in the order printed by `--dry-run`.

## Failure playbook (best solution per symptom)

- **`[Sutra] parse fallback` >20%** or `within_loop == 0` flat: scorer
  is rejecting JSON. Check `experiment_results*/latest.json` raw
  `sutra_critique`. Fix `_coerce_scores` aliases / lower temp to 0.2,
  do NOT launch the full run.
- **Judge `score=None` / `ok=False`**: a record is marked incomplete
  for resume. Re-run that chunk with `--no-resume` on a fresh dir or
  delete the failed record from `latest.json` and resume — judge-only
  rerun is enough (solutions are stored).
- **Objective `runs=False` for code that looks fine**: inspect
  `objective.stderr` in JSON — usually the model emitted prose outside
  the ```` ```python ```` block or redefined `Node`/`TreeNode`
  incompatibly. Fix task/API name, not the test.
- **Timeout / Ollama disconnect (60s httpx)**: `ollama serve` + resume.
  The harness prints the resume count; completed (task, seed) pairs
  are skipped. Never restart from zero.
- **Multi `status=failed` / `no final solution`**: iteration error before
  Agni (see `iteration_error` in JSON). With the orchestrator recovery
  fix, this should now fall back to the Yantra candidate with score 5 —
  if you still see it, read `error` field and fix that agent.
- **Time > est. by 2×**: usually nested retries. Check
  `total_tokens` — >5k tokens/task means Sutra is retrying. Tighten
  `_coerce_scores` instead of adding more retry attempts.

## Paper gate

Only after S0 + P1 + P2 pass acceptance do we launch F-seed.
Paper §5 is filled *only* from `experiment_results/latest.json`
`summary` + console stats (t/Wilcoxon/Cohen’s d). Legacy
`archive_legacy_*/` numbers are never copied.
