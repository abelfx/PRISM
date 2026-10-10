#!/usr/bin/env bash
# Run from prism/: ./run.sh help, ./run.sh test, or ./run.sh bench-all.
# New logs and JSON go to artifacts/evaluator-runs, not curated references.
set -euo pipefail

PRISM_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd -- "$PRISM_DIR/.." && pwd)"
export PETTA_HOME="${PETTA_HOME:-$WORKSPACE_DIR/PeTTa}"
[[ "$PETTA_HOME" = /* ]] || PETTA_HOME="$PRISM_DIR/$PETTA_HOME"
PYTHON_BIN="${PRISM_PYTHON:-python3}"
[[ "$PYTHON_BIN" != */* || "$PYTHON_BIN" = /* ]] || PYTHON_BIN="$PRISM_DIR/$PYTHON_BIN"
RESULTS_DIR="${PRISM_RESULTS_DIR:-$PRISM_DIR/artifacts/evaluator-runs}"
[[ "$RESULTS_DIR" = /* ]] || RESULTS_DIR="$PRISM_DIR/$RESULTS_DIR"
# Legacy MeTTa microbenchmarks import scorer from this package subdirectory.
export PYTHONPATH="$PRISM_DIR/src:$PRISM_DIR:$PRISM_DIR/src/prism/core:$PETTA_HOME:$PETTA_HOME/repos/PLN${PYTHONPATH:+:$PYTHONPATH}"

usage() {
  cat <<'HELP'
Usage: ./run.sh COMMAND

Checks:
  doctor                Check Python, pytest, PeTTa and PLN paths.
  test                  Run Python, direct MeTTa and pinned PLN rule tests.
  test-python           Run the complete PRISM pytest suite.
  test-metta            Check PRISM's four direct MeTTa integration fixtures.
  test-pln              Run seven pinned PLN rule regression files.
  test-pln-examples     Run six working upstream PLN examples.

Benchmarks:
  bench-ffi             Measure cached and uncached PeTTa/Python calls.
  bench-chain           Compare unguided PLN and PRISM on chains.
  bench-diamond         Compare both modes on alternative-path graphs.
  bench-tree            Compare both modes on conjunction/tree graphs.
  bench-search          Compare unguided and guided explicit search.
  bench-ablation        Compare Stage 0, Tier 1 and their combination.
  bench-bidirectional   Compare forward and bidirectional proof search.
  bench-tier2           Test offline/mock stall recovery and subgoals.
  bench-kg              Evaluate the supplied kgadexp.metta KG pilot.
  bench-scaling         Test size scaling and cross-domain transfer.
  bench-external-kg     Test bounded slices of the supplied external KGs.
  bench-soundness       Replay PLN proofs and test failure containment.
  bench-all             Run every offline check above; can take many minutes.
  bench-tier2-live      Optional live OpenRouter run; needs OPENROUTER_API_KEY.

Only the PLN integration exists on this branch. OpenPsi and learned Tier 1 v2
belong to experimental branches and are not run by this launcher.
Set PETTA_HOME, PRISM_PYTHON or PRISM_RESULTS_DIR to override defaults.
HELP
}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
need_python() { command -v "$PYTHON_BIN" >/dev/null || fail "Python not found: $PYTHON_BIN"; }
need_python_312() {
  need_python
  "$PYTHON_BIN" -c 'import sys; sys.exit(sys.version_info < (3, 12))' ||
    fail "The bidirectional benchmark uses Python 3.12 f-string syntax."
}
need_petta() {
  command -v swipl >/dev/null || fail "SWI-Prolog (swipl) is required."
  [[ -f "$PETTA_HOME/run.sh" && -f "$PETTA_HOME/src/main.pl" ]] ||
    fail "PeTTa is missing at $PETTA_HOME"
  [[ -f "$PETTA_HOME/repos/PLN/lib_pln.metta" ]] ||
    fail "PLN is missing from $PETTA_HOME/repos/PLN"
}
prepare_results() { mkdir -p "$RESULTS_DIR"; }

doctor() {
  need_python
  need_petta
  "$PYTHON_BIN" -m pytest --version
  "$PYTHON_BIN" -c 'import sys; print("Python:", sys.version.split()[0])'
  printf 'PRISM: %s\nPeTTa: %s\nSWI-Prolog: %s\nResults: %s\n' \
    "$PRISM_DIR" "$PETTA_HOME" "$(command -v swipl)" "$RESULTS_DIR"
  if ! "$PYTHON_BIN" -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    printf 'Note: use Python 3.12 for bench-bidirectional and bench-all.\n'
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
  if ! grep -Eq "$expected" <(sed -E 's/\x1B\[[0-9;]*[[:alpha:]]//g' "$log"); then
    tail -n 35 "$log" >&2
    fail "$label did not emit its expected result; full log: $log"
  fi
  if grep -Eq '^is .*should .*❌|^\(.*"FAIL"\)$' \
    <(sed -E 's/\x1B\[[0-9;]*[[:alpha:]]//g' "$log"); then
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
  # Check fallback, depth discount, premise filtering and goal-aware ranking in PeTTa.
  local tests="$PRISM_DIR/tests/integration"
  run_metta_checked test-fallback "$tests/test_fallback.metta" '^\(EMPTY_ITEM_GUARD: .*"PASS"\)$'
  run_metta_checked test-depth "$tests/test_depth_penalty.metta" '^\(DEPTH_PENALTY_VERIFICATION: .*"PASS"\)$'
  run_metta_checked test-stage0 "$tests/test_stage0_metta.metta" '^\(STAGE0_TEST2_FILTERED: .*"PASS"\)$'
  run_metta_checked test-hook "$tests/test_prism_hook.metta" '^\(HOOK_VERIFICATION: .*prism_guided_pick_selected_overlap: \(Sentence \(\(Inheritance Alice Person\)'
}

test_pln() {
  # Confirm the seven PLN rule fixtures still emit successful assertions.
  local file
  for file in "$PETTA_HOME"/repos/PLN/ruletests/*.metta; do
    run_metta_checked "pln-$(basename "${file%.metta}")" "$file" '^is .*should .*✅'
  done
}

test_pln_examples() {
  # Run six working examples; the upstream Direct.metta father/3 error is excluded.
  local name
  for name in DeductionRevision FlyingRaven RavenInduction Robot Smokes Toothbrush; do
    run_metta_checked "pln-example-$name" "$PETTA_HOME/repos/PLN/examples/$name.metta" '^is .*should .*✅'
  done
}

bench_ffi() {
  # Time repeated cached and uncached calls through the real PeTTa bridge.
  run_metta_checked ffi-cached "$PRISM_DIR/benchmarks/metta/benchmark_pycall.metta" '^\(BENCHMARK_RESULTS:'
  run_metta_checked ffi-uncached "$PRISM_DIR/benchmarks/metta/benchmark_uncached.metta" '^\(UNCACHED_BENCHMARK_RESULTS:'
}

bench_pair() {
  local domain="$1" mode result
  shift
  need_petta
  # Apply identical budgets and domains to confidence-only PLN and guided PRISM.
  run_module "$domain-native" benchmarks.run_benchmark --domain "$domain" "$@" --output "$RESULTS_DIR/$domain-native.json"
  run_module "$domain-prism" benchmarks.run_benchmark --domain "$domain" --guided "$@" --output "$RESULTS_DIR/$domain-prism.json"
  # The sweep runner stores failed PeTTa exit codes in JSON without exiting itself.
  for mode in native prism; do
    result="$RESULTS_DIR/$domain-$mode.json"
    [[ -f "$result" ]] || fail "Sweep did not produce $result"
    grep -Fq '"exit_code":' "$result" || fail "No PeTTa exit codes in $result"
    if grep -Eq '"exit_code": -?[1-9][0-9]*' "$result"; then
      fail "A PeTTa run failed inside $result; inspect its exit_code entries."
    fi
  done
}

bench_all() {
  # Full offline PLN suite; the provider-dependent live run is excluded.
  need_python_312
  test_python
  test_metta
  test_pln
  test_pln_examples
  bench_ffi
  bench_pair chain --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80
  bench_pair diamond --diamond-depths 2:5 3:6 --distractors 0 10 25 --repeats 2 --max-steps 80
  bench_pair tree --tree-depths 2:2 3:3 --distractors 0 10 25 --repeats 2 --max-steps 80
  run_module search benchmarks.evaluate_search_comparison
  run_module ablation benchmarks.evaluate_ablation
  run_module bidirectional benchmarks.evaluate_bidirectional
  run_module tier2-offline benchmarks.evaluate_gap_rescue --output "$RESULTS_DIR/tier2-offline.json"
  run_module kgadexp benchmarks.evaluate_kg_similarity --kg "$WORKSPACE_DIR/kgadexp.metta" --sources 5 --targets 10 --queries 5 --max-steps 40 --queue-size 150 --beam-width 5 --timeout 30 --output "$RESULTS_DIR/kgadexp.json"
  run_module scaling benchmarks.evaluate_scaling_generalization --output "$RESULTS_DIR/scaling.json"
  run_module external-kg benchmarks.evaluate_external_kg_scaling --output "$RESULTS_DIR/external-kg.json"
  run_module soundness benchmarks.evaluate_soundness_robustness --output "$RESULTS_DIR/soundness.json"
}

[[ $# -le 1 ]] || fail "Use one command at a time; run './run.sh help' for the list."
case "${1:-help}" in
  help|-h|--help) usage ;;
  # Check that the local Python and real PeTTa/PLN runtimes are reachable.
  doctor) doctor ;;
  # Run Python, direct MeTTa and pinned PLN rule regressions.
  test) test_python; test_metta; test_pln ;;
  # Run all Python unit and integration tests in this branch.
  test-python) test_python ;;
  # Verify the four PRISM MeTTa hooks without OpenPsi.
  test-metta) test_metta ;;
  # Check the seven upstream PLN rule fixtures.
  test-pln) test_pln ;;
  # Check six upstream PLN examples beyond the rule fixtures.
  test-pln-examples) test_pln_examples ;;
  # Measure cached and uncached Python/MeTTa crossing costs.
  bench-ffi) bench_ffi ;;
  # Compare unguided and guided transitive chains at fixed budgets.
  bench-chain) bench_pair chain --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80 ;;
  # Compare both modes where long and short routes compete.
  bench-diamond) bench_pair diamond --diamond-depths 2:5 3:6 --distractors 0 10 25 --repeats 2 --max-steps 80 ;;
  # Compare both modes on conjunction/tree proof tasks.
  bench-tree) bench_pair tree --tree-depths 2:2 3:3 --distractors 0 10 25 --repeats 2 --max-steps 80 ;;
  # Compare unguided and guided explicit proof search.
  bench-search) need_petta; run_module search benchmarks.evaluate_search_comparison ;;
  # Isolate the effects of Stage 0, Tier 1 and full PRISM.
  bench-ablation) need_petta; run_module ablation benchmarks.evaluate_ablation ;;
  # Compare forward-only and bidirectional search on deep chains.
  bench-bidirectional) need_petta; need_python_312; run_module bidirectional benchmarks.evaluate_bidirectional ;;
  # Test mock Tier 2 subgoals, which PLN must still establish.
  bench-tier2) need_petta; run_module tier2-offline benchmarks.evaluate_gap_rescue --output "$RESULTS_DIR/tier2-offline.json" ;;
  # Run the small KG pilot supplied beside the PeTTa checkout.
  bench-kg) need_petta; run_module kgadexp benchmarks.evaluate_kg_similarity --kg "$WORKSPACE_DIR/kgadexp.metta" --sources 5 --targets 10 --queries 5 --max-steps 40 --queue-size 150 --beam-width 5 --timeout 30 --output "$RESULTS_DIR/kgadexp.json" ;;
  # Measure size scaling and transfer to other proof topologies.
  bench-scaling) need_petta; run_module scaling benchmarks.evaluate_scaling_generalization --output "$RESULTS_DIR/scaling.json" ;;
  # Test bounded inference over larger supplied KG slices.
  bench-external-kg) need_petta; run_module external-kg benchmarks.evaluate_external_kg_scaling --output "$RESULTS_DIR/external-kg.json" ;;
  # Replay proof arithmetic/evidence and exercise safe fallbacks.
  bench-soundness) need_petta; run_module soundness benchmarks.evaluate_soundness_robustness --output "$RESULTS_DIR/soundness.json" ;;
  # Run every offline test and benchmark on main; may take many minutes.
  bench-all) need_petta; bench_all ;;
  # Contact OpenRouter only when explicitly requested with a key.
  bench-tier2-live)
    need_petta
    [[ -n "${OPENROUTER_API_KEY:-}" ]] || fail "Set OPENROUTER_API_KEY before bench-tier2-live."
    run_module tier2-live benchmarks.evaluate_gap_rescue --live --runs 3 --output "$RESULTS_DIR/tier2-live.json" ;;
  *) usage >&2; fail "Unknown command: $1" ;;
esac
