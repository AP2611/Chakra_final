"""Synthetic end-to-end test of the experiment pipeline (no Ollama required).

Validates:
  1. The hardened JSON parser now tolerates control characters inside strings
     (the historical cause of ~21% run failures).
  2. compute_summary / plotting / statistical analysis run on a realistic
     result structure and produce sensible numbers.
"""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, 'backend')

from agents.sutra import _parse_json_safe
import run_experiment as rexp


def test_json_parser_control_chars():
    # Raw newline + tab inside a JSON string value -- previously raised
    # "Invalid control character".
    raw = (
        '```json\n'
        '{"critique": "Line1\n\tLine2 with tab", '
        '"scores": {"correctness": 7, "accuracy": 8, "efficiency": 6, '
        '"clarity": 9, "edge_case_coverage": 7}}\n'
        '```'
    )
    parsed = _parse_json_safe(raw)
    assert parsed["scores"]["correctness"] == 7, parsed
    assert "\n" in parsed["critique"] and "\t" in parsed["critique"], parsed
    print("[OK] JSON parser tolerates control characters inside strings")

    # Prose wrapping + trailing text
    raw2 = 'Here is the evaluation:\n{"critique":"ok","scores":' \
           '{"correctness":5,"accuracy":5,"efficiency":5,"clarity":5,"edge_case_coverage":5}}' \
           '\nHope that helps!'
    parsed2 = _parse_json_safe(raw2)
    assert parsed2["scores"]["correctness"] == 5
    print("[OK] JSON parser recovers object from prose-wrapped output")


def make_synthetic_results(n=8):
    cats = ["code_algorithms", "math_reasoning", "text_generation", "document_qa"]
    results = []
    for i in range(n):
        cat = cats[i % len(cats)]
        is_code = cat != "document_qa"
        # Simulate: weak baseline ~6.5, strong ~8.5, multi-agent ~9.0
        weak_j = 6.0 + (i % 3) * 0.5
        strong_j = 8.0 + (i % 4) * 0.3
        multi_j = min(10.0, strong_j + 0.4 + (i % 2) * 0.3)
        first_score = multi_j - (0.3 + (i % 3) * 0.2)  # loop improved it
        results.append({
            "task": f"Synthetic task {i}",
            "category": cat,
            "is_code": is_code,
            "use_rag": cat == "document_qa",
            "seed": 42,
            "baselines": {
                "weak": {
                    "output": "x", "time": 12.0 + i, "model": "qwen2.5:1.5b",
                    "total_tokens": 500, "cost": 100, "status": "success",
                    "evaluation": {
                        "judge": {"score": weak_j, "ok": True},
                        "objective": {"runs": i % 4 != 0, "score": 1.0 if i % 4 != 0 else 0.0},
                    },
                },
                "strong": {
                    "output": "x", "time": 20.0 + i, "model": "mistral:latest",
                    "total_tokens": 900, "cost": 900, "status": "success",
                    "evaluation": {
                        "judge": {"score": strong_j, "ok": True},
                        "objective": {"runs": True, "score": 1.0},
                    },
                },
            },
            "multi_agent": {
                "full": {
                    "final_solution": "x", "final_score": multi_j,
                    "total_iterations": 2, "time": 60.0 + i * 3,
                    "total_tokens": 2000, "cost": 2500, "status": "success",
                    "iterations": [
                        {"iteration": 1, "score": first_score,
                         "sutra_scores": {"correctness": 8, "accuracy": 8,
                                          "efficiency": 7, "clarity": 8, "edge_case_coverage": 7}},
                        {"iteration": 2, "score": multi_j,
                         "sutra_scores": {"correctness": 9, "accuracy": 9,
                                          "efficiency": 8, "clarity": 9, "edge_case_coverage": 8}},
                    ],
                    "evaluation": {
                        "judge": {"score": multi_j, "ok": True},
                        "objective": {"runs": True, "score": 1.0},
                    },
                },
                "agni_only": {
                    "final_solution": "x", "final_score": multi_j - 0.2,
                    "total_iterations": 2, "time": 55.0, "status": "success",
                    "iterations": [{"iteration": 1, "score": multi_j - 0.2,
                                    "sutra_scores": {"correctness": 8, "accuracy": 8,
                                                     "efficiency": 7, "clarity": 8, "edge_case_coverage": 7}}],
                    "evaluation": {"judge": {"score": multi_j - 0.2, "ok": True},
                                   "objective": {"runs": True, "score": 1.0}},
                },
                "sutra_only": {
                    "final_solution": "x", "final_score": first_score,
                    "total_iterations": 1, "time": 30.0, "status": "success",
                    "iterations": [{"iteration": 1, "score": first_score,
                                    "sutra_scores": {"correctness": 7, "accuracy": 7,
                                                     "efficiency": 6, "clarity": 7, "edge_case_coverage": 6}}],
                    "evaluation": {"judge": {"score": first_score, "ok": True},
                                   "objective": {"runs": i % 2 == 0, "score": 1.0}},
                },
            },
            "timestamp": "2026-01-01T00:00:00",
        })
    return results


def test_pipeline():
    tmp = tempfile.mkdtemp(prefix="chakra_synth_")
    try:
        cfg = dict(rexp.EXPERIMENT_CONFIG)
        cfg["output_dir"] = tmp
        cfg["max_iterations"] = 3

        results = make_synthetic_results(8)
        summary = rexp.compute_summary(results)
        print("\n--- SUMMARY ---")
        for k, v in summary.items():
            print(f"  {k}: {v}")

        assert summary["n_complete"] == 8
        assert summary["improvement_vs_strong"] is not None
        assert summary["improvement_vs_weak"] is not None
        assert summary["within_loop_improvement_mean"] > 0
        assert summary["objective_exec_rate_multi"] == 1.0
        print("[OK] compute_summary produced a fair comparison")

        rexp.generate_all_plots(results, cfg)
        print("[OK] all plots generated")
        for f in ("score_progression.pdf", "improvement_distribution.pdf",
                  "time_vs_quality.pdf", "dimension_radar.pdf", "baseline_comparison.pdf"):
            assert os.path.exists(os.path.join(tmp, f)), f
        print("[OK] all 5 figure files exist")

        rexp.perform_statistical_analysis(results, cfg)
        print("[OK] statistical analysis ran")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_json_parser_control_chars()
    test_pipeline()
    print("\nALL SYNTHETIC TESTS PASSED")
