# PRISM — Week 1 Milestone Specification & Execution Plan

**Milestone:** Week 1 — FFI Foundation, Goal Threading & Hook De-risking  
**Project:** PRISM (Programmable Reduction & Inference Search Manager)  
**Host Environment:** PeTTa (SWI-Prolog + Janus Python FFI) & `trueagi-io/PLN` (`lib_pln.metta`)  
**Timeline:** Week 1 of 12  
**Status:** Complete (All 4 Gates Passed)

---

## 1. Objectives & Scope

Week 1 transitions PRISM from specification to live code. The primary goal is **de-risking the foundation**: verifying the Python-MeTTa FFI performance, threading the optional `$Goal` parameter through the derivation loop, and implementing the `PriorityRankGoal` / `PriorityRankNegGoal` drop-in replacement hooks in `lib_pln.metta`.

By the end of Week 1, PLN will be capable of executing goal-directed task selection via an external Python scorer, while maintaining 100% backward compatibility and regression parity on all existing PLN tests.

---

## 2. Deliverables & Technical Tasks

### Task 1.1: Project Structure & Scorer Skeleton
- [x] Create the `prism/` package directory:
  - `prism/__init__.py`
  - `prism/scorer.py` (Main entry point called from MeTTa via `py-call`)
  - `prism/cache.py` (Memoization layer for `LimitSize` O(N²) mitigation)
  - `benchmarks/pycall_bench.py` (FFI latency & throughput benchmark)
- [x] Ensure `scorer.py` incorporates complete exception encapsulation (`try ... except Exception:`) to prevent Janus from propagating unhandled Python errors into SWI-Prolog.

### Task 1.2: Empirical `py-call` Latency & Throughput Benchmark
- [x] Create `benchmarks/benchmark_pycall.metta`.
- [x] Benchmark 1,000 to 10,000 round-trip calls through PeTTa's Janus FFI.
- [x] Measure:
  - Mean round-trip latency ($\text{target} < 1.0\text{ms}$).
  - P95 and P99 latency distribution.
  - Memory stability and garbage collection behavior during burst calls.
- [x] Benchmark error containment: verify that simulated Python exceptions gracefully return `"Error"` without aborting the MeTTa interpreter.

### Task 1.3: Goal-Threading & Hook Implementation in `lib_pln.metta`
- [x] **Thread `$Goal` parameter:**
  - Update `PLN.Query` (`lib_pln.metta:416-421`) to pass `$term` as `$Goal` to `PLN.Derive`.
  - Add 7-argument `PLN.Derive` signature accepting `$Goal`.
  - Retain legacy 6-argument `PLN.Derive` overload that defaults `$Goal` to `()`.
- [x] **Replace `PriorityRank` with `PriorityRankGoal`:**
  - Implement native curried definition in MeTTa:
    ```metta
    (= (PriorityRankGoal $Goal ()) -99999.0)
    (= (PriorityRankGoal $Goal (Sentence ($x (stv $f $c)) $Ev1))
       (if (== $Goal ())
           $c
           (let $score (py-call (scorer.score_candidate (Sentence ($x (stv $f $c)) $Ev1) $Goal))
                (if (== $score Error)
                    $c
                    $score))))
    ```
- [x] **Replace `PriorityRankNeg` with `PriorityRankNegGoal`:**
  - Implement negation using `PriorityRankGoal`.
- [x] **Update `LimitSizeGoal`:**
  - Pass curried `(PriorityRankNegGoal $Goal)` to `BestCandidate` for goal-aware queue trimming.

### Task 1.4: Regression Testing & Pass/Fail Verification
- [x] Run all 7 rule tests in `ruletests/*.metta`:
  - `RuleTester.metta`
  - `equivalenceToImplication.metta`
  - `evaluationImplicationRuleA.metta`
  - `evaluationWithNegationAndInheritanceInversion.metta`
  - `inversion.metta`
  - `memberDeductionA.metta`
  - `transitiveSimilarity.metta`
- [x] Run standard PLN examples:
  - `Smokes.metta`, `FlyingRaven.metta`, `Toothbrush.metta`, `RavenInduction.metta`, `DeductionRevision.metta`, `Robot.metta`.
- [x] Implement a new test `test_prism_hook.metta` demonstrating that when `$Goal` is provided, `scorer.py` actively influences task selection order.

---

## 3. Pass / Fail Acceptance Gates

| Gate ID | Criterion | Threshold / Target | Verification Method | Status |
|---|---|---|---|:---:|
| **GATE-1.1** | `py-call` Mean Latency | $< 1.0\text{ms}$ per call (target $< 0.1\text{ms}$) | `benchmark_pycall.metta` (1,000 iterations) | **PASSED** (0.015ms cached, 0.021ms uncached) |
| **GATE-1.2** | Exception Safety & Fallback | Zero interpreter crashes on Python exception; returns raw confidence `$c` | `test_fallback.metta` (error injection & empty goal) | **PASSED** (100% graceful fallback) |
| **GATE-1.3** | Backward Compatibility | 100% pass on all 7 `ruletests/*.metta` and valid examples via legacy path | `ruletests/*.metta` & all 6 standard examples | **PASSED** (13/13 tests green) |
| **GATE-1.4** | Goal-Directed Hook | `BestCandidate` correctly passes candidate + goal to Python and receives ranking | `test_prism_hook.metta` (goal vs distractor) | **PASSED** (Goal-aligned task chosen over 0.95 conf distractor) |

---

## 4. Week 1 Implementation Artifacts

```
pln/
├── milestone.md                   # Updated with Gate results
├── PRISM_Implementation_Specification.md
├── PRISM_Implementation_Specification.pdf
├── PRISM_PLN_Inference_Control_Proposal_final.pdf
├── PeTTa/
│   ├── src/metta.pl               # Hardened py-call with attribute stripping & exception catch
│   ├── run.sh                     # Exporting PRISM PYTHONPATH
│   └── repos/
│       └── PLN/
│           ├── lib_pln.metta      # Modified with PriorityRankGoal & Goal-threading
│           ├── ruletests/         # 7 regression tests (100% PASS)
│           └── examples/          # Standard examples (100% PASS)
└── prism/                         # PRISM package
    ├── __init__.py
    ├── scorer.py                  # py-call entry point with Tier 1 v1 heuristic
    ├── cache.py                   # Score memoization cache
    ├── benchmarks/
    │   ├── pycall_bench.py        # Python benchmark helper
    │   ├── benchmark_pycall.metta # MeTTa FFI cached latency benchmark
    │   └── benchmark_uncached.metta # MeTTa FFI uncached latency benchmark
    └── tests/
        ├── test_fallback.metta    # Fallback verification
        └── test_prism_hook.metta  # MeTTa goal-guided verification
```

---

## 5. Execution Summary & Gate Results

- [x] **Task 1.1:** Created `prism/` package structure, implemented `cache.py`, `scorer.py`, and `pycall_bench.py`.
- [x] **Task 1.2:** Ran `benchmark_pycall.metta` and `benchmark_uncached.metta`; measured **0.015 ms** cached and **0.021 ms** uncached latency (~46,800 to 66,700 calls/sec). Verified **GATE-1.1**.
- [x] **Task 1.3:** Applied `$Goal` threading to `PLN.Query` and `PLN.Derive`, implemented curried `PriorityRankGoal` and `PriorityRankNegGoal` in `lib_pln.metta`.
- [x] **Task 1.4:** Hardened `metta.pl` Janus FFI to strip attributed variables; verified fallback behavior; ran regression suite (7/7 rule tests + 6/6 standard examples passing 100%). Verified **GATE-1.2** and **GATE-1.3**.
- [x] **Task 1.5:** Ran `test_prism_hook.metta`; verified that `BestCandidate (PriorityRankGoal $Goal)` successfully overrides a 0.95 confidence distractor to select a goal-relevant 0.80 task. Verified **GATE-1.4**.

