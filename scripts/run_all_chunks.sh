#!/usr/bin/env bash
set -u
cd /Users/arjunpanse/Documents/Chakra_final
BASE="experiment_results_chunks"
mkdir -p "$BASE" "$BASE/logs"

run_chunk() {
  chunk="$1"; shift
  out="$BASE/$chunk"
  log="$BASE/logs/$chunk.log"
  mkdir -p "$out"
  echo "======================================================================"
  echo " CHUNK: $chunk  @ $(date -u +%H:%M:%S)  -> $out"
  echo " CMD: python run_experiment.py $*"
  echo "======================================================================" | tee -a "$log"
  python3 run_experiment.py "$@" --output-dir "$out" 2>&1 | tee -a "$log"
  code=${PIPESTATUS[0]}
  echo "CHUNK $chunk exit=$code" | tee -a "$log"
}

echo "S0 smoke (is_prime)"
run_chunk "S0_is_prime" --pilot --task-substring "is_prime"

echo "P1 core (3 tasks)"
run_chunk "P1_core_3tasks" --pilot

echo "P2 hard-code (3 x 1 task)"
run_chunk "P2_BoundedQueue" --pilot --task-substring "BoundedQueue"
run_chunk "P2_fib" --pilot --task-substring "fib(n)"
run_chunk "P2_RunningMedian" --pilot --task-substring "RunningMedian"

echo "P3 categories + ablations (5 x 1 task)"
run_chunk "P3_code_is_prime" --pilot --ablations full,agni_only,sutra_only --task-substring "is_prime"
run_chunk "P3_codeopt" --pilot --ablations full,agni_only,sutra_only --task-substring "find_duplicates"
run_chunk "P3_math" --pilot --ablations full,agni_only,sutra_only --task-substring "Solve for x"
run_chunk "P3_text" --pilot --ablations full,agni_only,sutra_only --task-substring "recursion"
run_chunk "P3_doc" --pilot --ablations full,agni_only,sutra_only --task-substring "four specialized agents"

python3 scripts/consolidate_chunks.py
