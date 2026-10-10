#!/usr/bin/env bash
# Run from anywhere: ./run.sh help, ./run.sh test, or ./run.sh bench-all.
# Fresh logs and JSON go to artifacts/evaluator-runs, not curated references.
set -euo pipefail

PRISM_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$PRISM_DIR/.." && pwd)"
export PETTA_HOME="${PETTA_HOME:-$ROOT_DIR/PeTTa}"
PYTHON_BIN="${PRISM_PYTHON:-python3}"
RESULTS_DIR="${PRISM_RESULTS_DIR:-$PRISM_DIR/artifacts/evaluator-runs}"
[[ "$RESULTS_DIR" = /* ]] || RESULTS_DIR="$PRISM_DIR/$RESULTS_DIR"
# The old FFI microbenchmarks import `scorer` directly from prism.core.
export PYTHONPATH="$PRISM_DIR/src:$PRISM_DIR:$PRISM_DIR/src/prism/core:$PETTA_HOME:$PETTA_HOME/repos/PLN${PYTHONPATH:+:$PYTHONPATH}"

usage() {
  cat <<'HELP'
Usage: ./run.sh COMMAND

Checks:
  doctor                Check local runtime, dependencies, and data paths.
  test                  Run Python, PRISM MeTTa, and pinned PLN rule tests.
  test-python           Run the complete PRISM pytest suite (including OpenPsi).
  test-metta            Run PRISM's direct MeTTa integration checks.
  test-pln              Run the seven pinned PLN rule regression tests.
  test-pln-examples     Run six standard PLN examples; excludes broken Direct.metta.

PLN benchmarks:
  bench-ffi             Measure cached and uncached Python/MeTTa call latency.
  bench-chain           Compare native PLN and guided PRISM on transitive chains.
  bench-diamond         Compare both modes on alternative-path diamond graphs.
  bench-tree            Compare both modes on conjunction/tree graphs.
  bench-search          Compare unguided and guided explicit search.
  bench-ablation        Compare unguided, Stage 0, Tier 1, and full PRISM.
  bench-bidirectional   Test forward versus bidirectional proof search.
  bench-tier2           Test offline/mock stall recovery and verified subgoals.
  bench-kg              Run the supplied kgadexp.metta similarity pilot.
  bench-scaling         Test scaling and cross-domain transfer.
  bench-external-kg     Test the supplied external-KG edge slices.
  bench-soundness       Replay PLN proofs and test failure containment.

OpenPsi benchmarks:
  bench-openpsi         Compare native selector with PRISM on repository goals.
  bench-openpsi-fresh   Compare OpenPsi v1, v2, PRISM in fresh PeTTa processes.
  bench-openpsi-sim     Simulate stochastic action failures on fresh plans.
  bench-openpsi-cycle   Compare path-valid feedback/demand updates (two cases).
  bench-openpsi-action  Compare effectful ping-pong action execution.

Suites and optional runs:
  bench-all             Run all offline benchmarks above (can take a long time).
  bench-tier2-live      Optional live OpenRouter test; needs OPENROUTER_API_KEY.
  bench-v2              Explain missing Week 11 evaluator in this checkout.

Set PRISM_RESULTS_DIR to choose another output folder or PETTA_HOME for PeTTa.
Set PRISM_PYTHON to choose a Python executable. No command installs packages.
HELP
}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
need_python() { command -v "$PYTHON_BIN" >/dev/null || fail "Python not found: $PYTHON_BIN"; }
need_petta() {
  command -v swipl >/dev/null || fail "SWI-Prolog (swipl) is required."
  [[ -f "$PETTA_HOME/run.sh" && -f "$PETTA_HOME/src/main.pl" ]] || fail "PeTTa not found at $PETTA_HOME"
  [[ -f "$PETTA_HOME/repos/PLN/lib_pln.metta" ]] || fail "PLN is missing from $PETTA_HOME/repos/PLN"
}
need_openpsi() {
  [[ -d "$ROOT_DIR/other_hyperon/PeTTa-OpenPSI/main" ]] || fail "PeTTa-OpenPSI is missing from other_hyperon/"
}
prepare_results() { mkdir -p "$RESULTS_DIR"; }

doctor() {
  need_python
  need_petta
  "$PYTHON_BIN" -m pytest --version
  printf 'PRISM: %s\nPeTTa: %s\nSWI-Prolog: %s\nResults: %s\n' \
    "$PRISM_DIR" "$PETTA_HOME" "$(command -v swipl)" "$RESULTS_DIR"
  if [[ -d "$ROOT_DIR/other_hyperon/PeTTa-OpenPSI/main" ]]; then
    printf 'OpenPsi: present\n'
  else
    printf 'OpenPsi: missing (OpenPsi commands unavailable)\n'
  fi
  if [[ ! -f "$PRISM_DIR/benchmarks/evaluate_tier1_v2.py" ]]; then
    printf 'Tier 1 v2: historical results only; runnable evaluator absent\n'
  fi
}

run_metta_checked() {
  local label="$1" file="$2" expected="$3" log
  need_petta
  [[ -f "$file" ]] || fail "Missing MeTTa file: $file"
  prepare_results
  log="$RESULTS_DIR/$label.log"
  printf 'Running %s ...\n' "$label"
  if ! (cd "$PETTA_HOME" && sh run.sh "$file") >"$log" 2>&1; then
    tail -n 35 "$log" >&2
    fail "$label failed; full log: $log"
  fi
  if ! sed -E 's/\x1B\[[0-9;]*[[:alpha:]]//g' "$log" | grep -Eq "$expected"; then
    tail -n 35 "$log" >&2
    fail "$label did not emit its expected success result; full log: $log"
  fi
  if sed -E 's/\x1B\[[0-9;]*[[:alpha:]]//g' "$log" | grep -Eq '^is .*should .*❌|^\(.*"FAIL"\)$|^PRISM_OPENPSI_.*FAIL$'; then
    tail -n 35 "$log" >&2
    fail "$label emitted a failed assertion; full log: $log"
  fi
  printf 'PASS %s (log: %s)\n' "$label" "$log"
}

run_module() {
  local label="$1" module="$2" log
  shift 2
  need_python
  prepare_results
  log="$RESULTS_DIR/$label.log"
  printf 'Running %s ...\n' "$label"
  if ! (cd "$PRISM_DIR" && "$PYTHON_BIN" -m "$module" "$@") >"$log" 2>&1; then
    tail -n 40 "$log" >&2
    fail "$label failed; full log: $log"
  fi
  printf 'DONE %s (log: %s)\n' "$label" "$log"
  tail -n 5 "$log"
}

test_python() {
  need_python
  (cd "$PRISM_DIR" && "$PYTHON_BIN" -m pytest -q)
}

test_metta() {
  # Verify fallback, depth penalty, Stage 0 filtering, and goal-directed ranking in real PeTTa.
  local tests="$PRISM_DIR/tests/integration"
  run_metta_checked test-fallback "$tests/test_fallback.metta" '^\(EMPTY_ITEM_GUARD: .*"PASS"\)$'
  run_metta_checked test-depth "$tests/test_depth_penalty.metta" '^\(DEPTH_PENALTY_VERIFICATION: .*"PASS"\)$'
  run_metta_checked test-stage0 "$tests/test_stage0_metta.metta" '^\(STAGE0_TEST2_FILTERED: .*"PASS"\)$'
  run_metta_checked test-hook "$tests/test_prism_hook.metta" '^\(HOOK_VERIFICATION: .*prism_guided_pick_selected_overlap: \(Sentence \(\(Inheritance Alice Person\)'
  need_openpsi
  run_metta_checked test-openpsi "$tests/test_openpsi_planner.metta" '^PRISM_OPENPSI_BUDGET_PASS$'
}

test_pln() {
  # Run PLN's pinned rule assertions; PeTTa must print an actual successful “should” result.
  local file
  for file in "$PETTA_HOME"/repos/PLN/ruletests/*.metta; do
    run_metta_checked "pln-$(basename "${file%.metta}")" "$file" '^is .*should .*✅'
  done
}

test_pln_examples() {
  # Exercise six working repository examples; Direct.metta has an upstream father/3 error.
  local name
  for name in DeductionRevision FlyingRaven RavenInduction Robot Smokes Toothbrush; do
    run_metta_checked "pln-example-$name" "$PETTA_HOME/repos/PLN/examples/$name.metta" '^is .*should .*✅'
  done
}

bench_ffi() {
  # Measure Python/MeTTa bridge cost with and without score caching.
  run_metta_checked ffi-cached "$PRISM_DIR/benchmarks/metta/benchmark_pycall.metta" '^\(BENCHMARK_RESULTS:'
  run_metta_checked ffi-uncached "$PRISM_DIR/benchmarks/metta/benchmark_uncached.metta" '^\(UNCACHED_BENCHMARK_RESULTS:'
}

bench_pair() {
  local domain="$1"; shift
  need_petta
  # Use identical domain parameters for native PLN and PRISM; write separate JSON files.
  run_module "$domain-native" benchmarks.run_benchmark --domain "$domain" "$@" --output "$RESULTS_DIR/$domain-native.json"
  run_module "$domain-prism" benchmarks.run_benchmark --domain "$domain" --guided "$@" --output "$RESULTS_DIR/$domain-prism.json"
  # The sweep runner records PeTTa exit codes in JSON instead of failing itself.
  local mode result
  for mode in native prism; do
    result="$RESULTS_DIR/$domain-$mode.json"
    [[ -f "$result" ]] || fail "Sweep did not produce $result"
    grep -Fq '"exit_code":' "$result" || fail "Sweep has no process exit codes: $result"
    if grep -Eq '"exit_code": -?[1-9][0-9]*' "$result"; then
      fail "A PeTTa run failed inside $result; inspect its exit_code entries."
    fi
  done
}

bench_openpsi_fresh() {
  # Generate fresh, paired v1/v2/PRISM plans for the same repository goal set.
  need_petta; need_openpsi
  run_module openpsi-fresh benchmarks.evaluate_openpsi_fresh --output "$RESULTS_DIR/openpsi-fresh.json"
}

bench_openpsi_sim() {
  # Replay only validated fresh plans in a seeded hypothetical action-failure simulator.
  bench_openpsi_fresh
  run_module openpsi-sim benchmarks.evaluate_openpsi_stochastic \
    --input "$RESULTS_DIR/openpsi-fresh.json" --output "$RESULTS_DIR/openpsi-sim.json"
}

bench_all() {
  # Long offline suite; live API calls and the unavailable Tier 1 v2 evaluator are excluded.
  test_python; test_metta; test_pln; test_pln_examples
  bench_ffi
  bench_pair chain --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80
  bench_pair diamond --diamond-depths 2:5 3:6 --distractors 0 10 25 --repeats 2 --max-steps 80
  bench_pair tree --tree-depths 2:2 3:3 --distractors 0 10 25 --repeats 2 --max-steps 80
  run_module search benchmarks.evaluate_search_comparison
  run_module ablation benchmarks.evaluate_ablation
  run_module bidirectional benchmarks.evaluate_bidirectional
  run_module tier2-offline benchmarks.evaluate_gap_rescue --output "$RESULTS_DIR/tier2-offline.json"
  run_module kgadexp benchmarks.evaluate_kg_similarity --kg "$ROOT_DIR/kgadexp.metta" --sources 5 --targets 10 --queries 5 --max-steps 40 --queue-size 150 --beam-width 5 --timeout 30 --output "$RESULTS_DIR/kgadexp.json"
  run_module scaling benchmarks.evaluate_scaling_generalization --output "$RESULTS_DIR/scaling.json"
  run_module external-kg benchmarks.evaluate_external_kg_scaling --output "$RESULTS_DIR/external-kg.json"
  run_module soundness benchmarks.evaluate_soundness_robustness --output "$RESULTS_DIR/soundness.json"
  run_module openpsi benchmarks.evaluate_openpsi --output "$RESULTS_DIR/openpsi.json"
  bench_openpsi_sim
  run_module openpsi-cycle-full benchmarks.evaluate_openpsi_full_cycle --scenario full --output "$RESULTS_DIR/openpsi-cycle-full.json"
  run_module openpsi-cycle-conversation benchmarks.evaluate_openpsi_full_cycle --scenario conversation --output "$RESULTS_DIR/openpsi-cycle-conversation.json"
  run_module openpsi-action benchmarks.evaluate_openpsi_action_execution --output "$RESULTS_DIR/openpsi-action.json"
}

[[ $# -le 1 ]] || fail "Use one command at a time; run './run.sh help' for the list."
case "${1:-help}" in
  help|-h|--help) usage ;;
  # Check that Python, pytest, PeTTa, PLN, and the optional OpenPsi tree are reachable.
  doctor) doctor ;;
  # Run the core Python and real-MeTTa regression suites together.
  test) test_python; test_metta; test_pln ;;
  # Run all PRISM unit and Python integration tests.
  test-python) test_python ;;
  # Check the PRISM hooks and OpenPsi planner inside PeTTa.
  test-metta) test_metta ;;
  # Confirm unchanged behavior on seven PLN rule tests.
  test-pln) test_pln ;;
  # Check six standard PLN examples in addition to the rule tests.
  test-pln-examples) test_pln_examples ;;
  # Time cached and uncached Python calls across the PeTTa bridge.
  bench-ffi) bench_ffi ;;
  # Compare native PLN with PRISM on equal chain depths and distractors.
  bench-chain) bench_pair chain --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80 ;;
  # Compare native PLN with PRISM where short and long proof paths compete.
  bench-diamond) bench_pair diamond --diamond-depths 2:5 3:6 --distractors 0 10 25 --repeats 2 --max-steps 80 ;;
  # Compare native PLN with PRISM on two-branch conjunction tasks.
  bench-tree) bench_pair tree --tree-depths 2:2 3:3 --distractors 0 10 25 --repeats 2 --max-steps 80 ;;
  # Compare unguided and guided explicit search on several synthetic domains.
  bench-search) need_petta; run_module search benchmarks.evaluate_search_comparison ;;
  # Isolate Stage 0, Tier 1, and their combination against unguided search.
  bench-ablation) need_petta; run_module ablation benchmarks.evaluate_ablation ;;
  # Test forward and bidirectional search on deeper chains.
  bench-bidirectional) need_petta; run_module bidirectional benchmarks.evaluate_bidirectional ;;
  # Test stall recovery with a mock LLM; all accepted steps still use PLN.
  bench-tier2) need_petta; run_module tier2-offline benchmarks.evaluate_gap_rescue --output "$RESULTS_DIR/tier2-offline.json" ;;
  # Evaluate the supplied small KG using matched PLN/PRISM queries.
  bench-kg) need_petta; run_module kgadexp benchmarks.evaluate_kg_similarity --kg "$ROOT_DIR/kgadexp.metta" --sources 5 --targets 10 --queries 5 --max-steps 40 --queue-size 150 --beam-width 5 --timeout 30 --output "$RESULTS_DIR/kgadexp.json" ;;
  # Measure growing graph sizes and transfer to other task shapes.
  bench-scaling) need_petta; run_module scaling benchmarks.evaluate_scaling_generalization --output "$RESULTS_DIR/scaling.json" ;;
  # Repeat inference tests on larger slices of the supplied external KGs.
  bench-external-kg) need_petta; run_module external-kg benchmarks.evaluate_external_kg_scaling --output "$RESULTS_DIR/external-kg.json" ;;
  # Recheck PLN proof arithmetic/evidence and injected failure handling.
  bench-soundness) need_petta; run_module soundness benchmarks.evaluate_soundness_robustness --output "$RESULTS_DIR/soundness.json" ;;
  # Compare native and PRISM selectors on repository OpenPsi goals.
  bench-openpsi) need_petta; need_openpsi; run_module openpsi benchmarks.evaluate_openpsi --output "$RESULTS_DIR/openpsi.json" ;;
  # Recreate v1, v2, and PRISM plans in independently started PeTTa processes.
  bench-openpsi-fresh) bench_openpsi_fresh ;;
  # Simulate seeded action failures on newly generated, valid plans.
  bench-openpsi-sim) bench_openpsi_sim ;;
  # Compare native and PRISM planning within two demand-feedback cases.
  bench-openpsi-cycle)
    need_petta; need_openpsi
    run_module openpsi-cycle-full benchmarks.evaluate_openpsi_full_cycle --scenario full --output "$RESULTS_DIR/openpsi-cycle-full.json"
    run_module openpsi-cycle-conversation benchmarks.evaluate_openpsi_full_cycle --scenario conversation --output "$RESULTS_DIR/openpsi-cycle-conversation.json" ;;
  # Compare actual one-turn ping-pong action effects; no outcome gain is assumed.
  bench-openpsi-action) need_petta; need_openpsi; run_module openpsi-action benchmarks.evaluate_openpsi_action_execution --output "$RESULTS_DIR/openpsi-action.json" ;;
  # Run every offline test/benchmark above; this may take many minutes.
  bench-all) need_petta; need_openpsi; bench_all ;;
  # Contact OpenRouter only when explicitly requested and a key is supplied.
  bench-tier2-live)
    # Live provider use is opt-in only; no API key is needed by offline benchmarks.
    need_petta
    [[ -n "${OPENROUTER_API_KEY:-}" ]] || fail "Set OPENROUTER_API_KEY before bench-tier2-live."
    run_module tier2-live benchmarks.evaluate_gap_rescue --live --runs 3 --output "$RESULTS_DIR/tier2-live.json" ;;
  # Report honestly that historical Tier 1 v2 results cannot be regenerated here.
  bench-v2)
    # Historical Week 11 numbers are present, but this checkout lacks the source/checkpoint.
    fail "Tier 1 v2 evaluator/training code is missing here; see prism/benchmarks/results/reference/week11_tier1_v2_manual_probes.json" ;;
  *) usage >&2; fail "Unknown command: $1" ;;
esac
