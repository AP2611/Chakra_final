# Chakra: A Recursive Multi-Agent Loop for Self-Improving Code and Document Generation

> **Status:** Submission-ready template. Method, protocol, and analysis code are
> complete; numbers are produced by `run_experiment.py` and must be pasted
> into §5 from `experiment_results/latest.json` → `summary` **before**
> submitting. Do not submit with placeholders.

## Abstract

We present **Chakra**, a multi-agent system that improves generated solutions
through a recursive critique–improve loop. A generator (Yantra) drafts a
solution; a critic (Sutra) scores it against a fixed rubric and identifies
defects; an improver (Agni) applies surgical fixes; and a memory agent (Smriti)
retains successful solutions for later retrieval. Iteration $N>0$ refines the
previous iteration's improved solution (it does not regenerate from scratch),
and each iteration is scored *after* improvement so scores pair with the
returned text. We evaluate Chakra against weak and strong single-pass
baselines on a diverse task suite (algorithms, optimization, math reasoning,
text generation, and RAG-based document QA), with ablations isolating each
stage. We decouple *steering* from *measurement*: in-loop Sutra scores steer
the loop, while final solutions are assessed by an **independent judge**
(separate instance, frozen rubric, low temperature) and by **objective,
execution-based metrics** plus a lexical groundedness hallucination proxy.
Results (to be inserted from the final run): judge-score improvement vs. the
strong baseline [paired test], execution success [vs. baselines], and
groundedness [vs. baselines].

## 1. Introduction

Large language models (LLMs) produce strong first-pass solutions, yet they
frequently contain subtle bugs, miss edge cases, or hallucinate unsupported
facts. Prior work shows that iterative self-refinement can improve quality,
but three problems limit its credibility as a scientific claim:

1. **Circular evaluation** — the same model that improves the solution also
   scores it, inflating apparent gains.
2. **Unfair baselines** — loops are compared only to a weak single pass, never
   to a strong single pass of equal or lower cost.
3. **Fragility** — real deployments drop runs due to malformed model outputs.

Chakra addresses all three. (1) We separate the in-loop critic (Sutra) used for
*steering* from an independent judge used for *measurement*. (2) We compare
against both weak and strong single-pass baselines and report relative-compute
cost accounting. (3) We make every LLM interaction tolerant — control-character
safe JSON parsing with balanced-brace recovery, three retries with backoff —
so runs are robust end-to-end (historical parse-failure rate ~21% → near-zero
on the synthetic pipeline test).

**Contributions.**
- A four-agent recursive architecture that is truly recursive (Yantra refines
  the prior Agni output on iterations $N>0$) and execution-aware, with
  post-improvement re-scoring.
- A non-circular evaluation protocol (independent judge + objective execution
  + lexical groundedness) applied identically to every system.
- A reproducible experiment harness with fair baselines, ablations, multi-seed
  statistics, and cost-equivalent comparison.

## 2. Related Work

- **Self-refinement / self-critique.** Iterative prompting where a model
  critiques and revises its own output (e.g., Self-Refine; Reflexion).
  Chakra differs by using *specialized* agents with distinct prompts and an
  *external* judge for measurement, plus execution feedback in the loop.
- **Multi-agent LLM systems.** Debate, role-play, and orchestration
  frameworks. Chakra's loop is recursive, execution-validated, and
  ablation-tested to attribute gains to critique vs. improvement stages.
- **LLM-as-judge.** Using LLMs to score generations. We adopt the critique
  but mitigate bias with a frozen rubric, a separate judge instance at low
  temperature, and objective cross-checks (execution + lexical groundedness).
- **Program synthesis & execution feedback.** Using test/execution signals to
  guide generation. Chakra embeds execution validation inside the critique
  loop and reports execution success as the primary non-circular metric.
- **RAG and hallucination mitigation.** Retrieval grounding reduces
  unsupported claims on document tasks. We measure this with judge
  `groundedness` (1–10) and an LLM-free lexical proxy (fraction of sentences
  sharing content words with retrieved chunks).
- *(Cite the above families with specific papers before submission.)*

## 3. Method

### 3.1 Architecture

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Yantra  │ → │  Sutra  │ → │  Agni   │ → ─┐
│ Generate│   │ Critique│   │ Improve │    │
│ /Refine │   │ (+score)│   │ (fix)   │    │
└─────────┘   └────┬────┘   └────┬────┘    │
                   │ execution validation │
        ┌──────────┴──────────┐           │
        │       Smriti        │◀─ best    │
        │      (Memory)       │  solution │
        └─────────────────────┘           │
                   └──────────────────────┘
                   (next iteration refines
                    prior improved output)
```

- **Yantra** (generator): drafts on iteration 0; on iterations $N>0$ it
  *refines* the previous Agni output using the previous critique. Supports
  RAG grounding and retrieved past examples (iteration 0 only, to avoid bias).
- **Sutra** (critic): returns a qualitative critique **and** a structured
  per-dimension score (correctness, accuracy, efficiency, clarity,
  edge-case coverage, and groundedness on RAG tasks) on a 1–10 scale with
  fixed weights and conservative anchors. Score smoothing clamps jumps >1.5
  unless the critique contains critical keywords.
- **Agni** (improver): applies *minimal, surgical* fixes from the critique,
  prioritizing execution failures. In `agni_only` ablation it receives a
  generic prompt (critique not used to steer).
- **Smriti** (memory): stored only under ``memory_policy="enabled"`` for
  interactive use. During paper evaluation Smriti is **disabled** (neither
  retrieved nor written) so baselines and loop see identical empty memory
  and seeds cannot leak across tasks. Pre-run the harness backs up and
  clears ``backend/data/memory.db`` (see REPRODUCE). A ``frozen``
  read-only mode is also available for demonstrating retrieval without
  online learning. Retrieval (when enabled) uses content-word Jaccard
  ($\geq 0.15$) with quality $\geq 0.6$ (store/retrieve thresholds aligned).

The loop runs up to `max_iterations=3`, stopping early when post-improvement
improvement falls below `min_improvement=0.5` or the score degrades by $>1.0$.
Each iteration's reported score is the **post-improvement** Sutra score
(Sutra re-scores the Agni output), so score and solution are paired. RAG
chunks are retrieved once per task and **shared** across all conditions
(`shared_rag_chunks`) for fairness.

### 3.2 Decoupled evaluation (key methodological choice)

To avoid LLM-as-judge circularity, the in-loop Sutra score is used only to
*steer* the loop. For *measurement*, each final solution is scored by:

- an **independent judge** (`backend/evaluation/judge.py`) — a separate model
  instance with a frozen rubric, low temperature (0.2), applied identically
  to every system (baselines and loop alike); and
- **objective metrics** (`backend/evaluation/objective.py`) —
  - code: does the generated code execute, and (where reference `tests`
    exist) pass them? Primary metric: execution success rate. **All 17
    code tasks** now have reference tests (partial-credit prefix scoring:
    each ``assert``/``try`` block deepens a cumulative prefix run, so
    stateful tests such as ``RunningMedian``/``BoundedQueue`` still work
    and near-misses get fractional credit instead of 0/1).
  - RAG text: lexical groundedness = fraction of sentences sharing a content
    word ($\geq$4 chars, non-stopword) with retrieved chunks ("supported
    sentences"). Complement to the judge's groundedness dimension.

Note: the judge currently shares the critic's model family
(`mistral:latest`) unless ``--judge-model`` overrides it (e.g.
`llava:latest` / `llama3.2:1b`, different LLaMA family, ~7B/1B). The
harness warns loudly when judge == critic. Independence is at
instance/prompt/temperature/seed level, not family level — a known
limitation (see §6); the sensitivity check (rerun judging with a different
family and report Spearman correlation) is the direct robustness test.
LLM sampling is seeded via Ollama's ``seed`` option
(``BaseAgent.set_seed``): per (task, seed) the generator/critic/improver
receive deterministic offsets ``seed``, ``seed+1``, ``seed+2`` (plus
``iteration*10``) and the judge ``seed+999`` at temperature 0.2, so
``seeds=[42,7,123]`` controls sampling, not only task-order shuffling.

### 3.3 Baselines and ablations

- **Weak single-pass**: Yantra with the small generator model
  (`qwen2.5:1.5b`, one shot).
- **Strong single-pass**: Yantra with the strong critic model
  (`mistral:latest`, one shot) — the fair comparison target.
- **Ablations**: `full` (Yantra→Sutra→Agni, recursive),
  `agni_only` (Yantra→Agni with generic prompt, Sutra for measurement),
  `sutra_only` (Yantra→Sutra, no improvement, single pass).

### 3.4 Cost accounting

We report relative compute cost = model-size-factor × tokens (1.5B vs 7B
reference), so weak+loop can be compared on a cost-equivalent footing to a
strong single pass, alongside wall-clock latency.

## 4. Experiments

### 4.1 Tasks

A curated suite of **30 tasks** across five categories: `code_algorithms`
(13, incl. harder thread-safe bounded queue, O(log n) Fibonacci, running
median — now specified as `BoundedQueue`/`fib`/`RunningMedian` with exact
APIs; testable tasks name their function, e.g. `is_prime`, `max_subarray`,
`binary_search`), `code_optimization` (4), `math_reasoning` (5),
`text_generation` (4), and `document_qa` (4, RAG). **All 17 code tasks**
carry reference tests (9 previously had them; reverse-list, cycle, BST,
DFS, bounded queue, Fibonacci, running median, and dedupe were added in
the paper-ready fix), scored with partial-credit prefix execution
(§3.2). Only true code categories are executed objectively; math/text
are judge-scored (prose is not runnable code). Tasks span difficulty so
the loop has genuine headroom.

### 4.2 Protocol

For each task and seed (default `seeds=[42,7,123]`) we retrieve RAG chunks
once, run both baselines and all three loop modes, then score every final
solution with the independent judge and the objective metric. Prior to a
paper run the harness **disables Smriti** (`memory_policy="disabled"`),
**archives legacy old-schema results** (`experiment_results/archive_legacy_*/`),
and **backs up + clears** the memory DB, so reported numbers never derive
from July-era runs or online learning. We report means
with standard deviations across seeds and paired statistical tests
(one-sample t-test on within-loop gain; paired t-test + Wilcoxon on
loop-minus-baseline judge differences, with Cohen's $d$ and 95% CIs).
LLM calls are seeded via Ollama's ``seed`` option per (task, seed, agent,
iteration) plus a fixed judge seed at temperature 0.2, so variance is
accounted for rather than left to sampling noise. Dependency versions
(numpy/scipy/matplotlib) and models are logged into every `latest.json`.

Runtime note: the full 90-record run is ~3k LLM calls (hours). A pilot
smoke test (`python run_experiment.py --pilot` → 3 tasks × 1 seed,
`fast_mode`, full-only, `experiment_results_pilot/`) validates the
pipeline in minutes; `--dry-run` prints the resolved config without any
Ollama calls.

### 4.3 Implementation

Local models via Ollama (`qwen2.5:1.5b` generator, `mistral:latest`
critic; judge `mistral:latest` by default, overridable to a different
family via `--judge-model`). Backend FastAPI/Python; frontend Next.js.
All prompts, weights, and thresholds are fixed and released.
`test_experiment_pipeline.py` validates the harness on synthetic data
without Ollama (parser, summary, plots, stats).

## 5. Results

> **Fill from `experiment_results/latest.json` → `summary` + console stats
> before submission. The template below is intentionally empty.**

| Metric | Value |
|---|---|
| Tasks (N) × seeds (S) | … |
| Judge score — weak / strong / multi-agent (full) | … / … / … |
| Improvement vs strong (paired) | … (t=…, p=…, d=…, 95% CI […]) |
| Improvement vs weak (paired) | … (t=…, p=…, d=…) |
| Within-loop improvement (mean ± sd) | … |
| Code execution success — weak / strong / multi | …% / …% / …% |
| Objective groundedness — weak / strong / multi (RAG) | … / … / … |
| Judge groundedness — weak / strong / multi (RAG) | … / … / … |
| Mean latency — weak / strong / multi | …s / …s / …s |
| Mean relative cost — weak / strong / multi | … / … / … |
| Ablation judge means (full / agni_only / sutra_only) | … / … / … |

**Findings (to be written from the numbers above, not pre-claimed):**
- Whether the recursive loop improves over the *strong* baseline (the fair
  target) and by how much.
- Whether the gain survives objective cross-checks (execution, groundedness)
  and is not judge-only.
- Which stage contributes (ablations: full vs agni_only vs sutra_only).

Figures (in `experiment_results/`): `score_progression`,
`improvement_distribution`, `time_vs_quality`, `dimension_radar` (includes
groundedness when present), `baseline_comparison`.

## 6. Threats to Validity

- **Judge bias.** Even an independent judge is an LLM, by default in the same
  model family as the critic unless `--judge-model` overrides it to a
  different family (e.g. `llava:latest`). Mitigations: frozen rubric, separate
  instance, low temperature (0.2), fixed judge seed, and objective
  execution/groundedness cross-checks. Human evaluation on a sample remains
  desirable; the judge-family rerun (report Spearman correlation vs the
  primary judge) is the required sensitivity check.
- **Lexical groundedness is a proxy.** Word overlap is cheap and LLM-free but
  misses paraphrase and claim-level support. The judge dimension is richer
  but model-dependent. Both are reported; neither alone is sufficient.
- **Task selection.** Results may not transfer outside our suite; we include
  five categories to bound this, but domain coverage is limited.
- **Model-specificity.** Gains are measured on the stated local models;
  absolute numbers will vary with model choice/hardware.
- **Determinism.** Ollama sampling is seeded per (task, seed, agent,
  iteration) but is not bit-identical across Ollama versions/hardware;
  multiple seeds and paired tests (with CIs) account for variance. Report
  seed count, versions (logged in `latest.json`), and CIs.
- **Memory.** Paper numbers use `memory_policy="disabled"` (no Smriti read
  or write) to isolate the loop; any memory benefit must be demonstrated
  separately under an explicit online-learning protocol, not conflated with
  the loop gain.
- **Cost/latency.** The loop uses more tokens and time than single passes.
  Relative-cost reporting makes the trade-off explicit; claims must be read
  alongside cost.

## 7. Conclusion

Chakra provides a recursive, execution-aware multi-agent loop with
non-circular, partly-objective evaluation and fair baselines/ablations. The
codebase is complete and reproducible; the empirical claim (quality and
hallucination improvement over a strong baseline at stated cost) must be
established by the filled §5 results and the judge-family sensitivity check.
Future work includes human validation at scale, tool-use and multi-modal
tasks, and semantic (embedding-based) memory retrieval.

## References

<!-- TODO: add citations for self-refinement, LLM-as-judge, RAG faithfulness,
     program synthesis. Do not submit with this comment. -->
