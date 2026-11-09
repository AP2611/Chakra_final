"""Consolidate all experiment_results_chunks/*/latest.json into one summary."""
import json, os, glob

base = "experiment_results_chunks"
rows = []
for path in sorted(glob.glob(os.path.join(base, "*", "latest.json"))):
    chunk = os.path.basename(os.path.dirname(path))
    try:
        d = json.load(open(path))
        s = d.get("summary", {})
        results = d.get("results", [])
        rows.append({
            "chunk": chunk,
            "n": s.get("n_complete", len(results)),
            "weak": s.get("weak_judge_mean"),
            "strong": s.get("strong_judge_mean"),
            "multi": s.get("multi_judge_mean"),
            "vs_strong": s.get("improvement_vs_strong"),
            "vs_weak": s.get("improvement_vs_weak"),
            "within": s.get("within_loop_improvement_mean"),
            "exec_w": s.get("objective_exec_rate_weak"),
            "exec_s": s.get("objective_exec_rate_strong"),
            "exec_m": s.get("objective_exec_rate_multi"),
            "time_m": s.get("multi_time_mean"),
            "tokens_m": s.get("multi_tokens_mean"),
            "tasks": "; ".join(r.get("task","")[:45] for r in results),
        })
    except Exception as e:
        rows.append({"chunk": chunk, "n": "ERROR", "tasks": str(e)})

os.makedirs(base, exist_ok=True)
md = ["# Chunk Summary (paper-ready test chunks)\n", "", "| chunk | n | weak | strong | multi | vs strong | vs weak | within | exec w/s/m | time_m | tasks |",
      "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    fmt = lambda v: f"{v:.2f}" if isinstance(v, (int,float)) else str(v)
    md.append(f"| {r['chunk']} | {r.get('n')} | {fmt(r.get('weak'))} | {fmt(r.get('strong'))} | {fmt(r.get('multi'))} | "
              f"{fmt(r.get('vs_strong'))} | {fmt(r.get('vs_weak'))} | {fmt(r.get('within'))} | "
              f"{r.get('exec_w')}/{r.get('exec_s')}/{r.get('exec_m')} | {r.get('time_m')} | "
              f"{r.get('tasks')} |")
open(f"{base}/SUMMARY.md","w").write("\n".join(md) + "\n\nRaw JSON per chunk: latest.json + results_*.json + 5 PDF/PNG figures each.\n")
print("\n".join(md))
