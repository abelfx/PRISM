# PRISM Test Suite & Verification Harness

This directory contains unit tests, MeTTa integration checks, and robustness verification scripts for PRISM (Programmable Reduction & Inference Search Manager).

The test suite is partitioned into two tiers:
1. `tests/unit/`: Fast Python unit tests executed via Pytest.
2. `tests/integration/`: End-to-end MeTTa derivation tests executed via PeTTa (`run.sh`).

---

## 1. Directory Contents

### 1.1 Python Unit Tests (`tests/unit/`)

| Test File | Verified Component | Purpose |
|---|---|---|
| `test_config.py` | `prism.core.config` | Tests immutable dataclass instantiation, default hyperparameter values, and post-init validation rules |
| `test_tier1_v1.py` | `prism.tier1.heuristic_v1` | Tests atom extraction, Jaccard term overlap calculation, geometric depth discount decay, and combined score computation |
| `test_stage0_index.py` | `prism.stage0.index` | Tests `PremiseIndex` inverted symbol indexing, fast set-intersection filtering, and empty/unmatched safe fallbacks |
| `test_scorer.py` | `prism.tier1.scorer` | Tests FFI coordinator entry points, memoization cache hits/misses, fallback on malformed inputs, and belief filtering |

### 1.2 MeTTa Integration Tests (`tests/integration/`)

| Test File | Verified Gate | Purpose | Expected Result |
|---|:---:|---|---|
| `test_fallback.metta` | **GATE-1.2** | Verifies exception safety, error containment, and graceful degradation to raw confidence when no goal is present or when an error occurs | All 3 sub-tests return `"PASS"` |
| `test_prism_hook.metta` | **GATE-1.4** | Tests that `PriorityRankGoal` actively steers candidate selection toward goal-relevant tasks over competing high-confidence distractors | Selects goal-relevant premise ($c=0.80$) over distractor ($c=0.95$) |
| `test_depth_penalty.metta` | **GATE-3.1** | Verifies geometric depth discounting: ensures that a shallow premise receives a higher priority score than an otherwise identical deep premise | Returns `"PASS"` (shallow 0.733 > deep 0.714) |
| `test_stage0_metta.metta` | **GATE-3.2** | Verifies MeTTa FFI invocation of Stage 0 `PremiseIndex`: excludes distractors while preserving on-path candidate premises | Both sub-tests return `"PASS"` |
| *(Week 10)* `test_soundness.py` | Release Gate | Re-evaluates final derived conclusions against unmodified PLN formulas to guarantee 100% truth-value soundness | 100% equivalence on all proofs |

---

## 2. How to Run the Tests

### 2.1 Running All Python Unit Tests
From the workspace root (`/home/abel/Desktop/icog_labs/pln`):
```bash
python3 -m pytest prism/tests/
```
Expected outcome: **24/24 passed in < 0.05s**.

### 2.2 Running MeTTa Integration Tests
From the PeTTa directory (`/home/abel/Desktop/icog_labs/pln/PeTTa`):
```bash
# 1. Depth penalty verification
sh run.sh ../prism/tests/integration/test_depth_penalty.metta

# 2. Stage 0 premise pre-filtering verification
sh run.sh ../prism/tests/integration/test_stage0_metta.metta

# 3. Exception containment and fallback verification
sh run.sh ../prism/tests/integration/test_fallback.metta

# 4. Goal-directed task selection verification
sh run.sh ../prism/tests/integration/test_prism_hook.metta
```

---

## 3. Full PLN Regression Suite (GATE-1.3)

To confirm that PRISM modifications in [`lib_pln.metta`](../../PeTTa/repos/PLN/lib_pln.metta) do not cause regressions in standard PLN inference, run the full regression test suite:

### 3.1 All 7 Rule Tests
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
for f in ./repos/PLN/ruletests/*.metta; do
    echo -n "$f: "
    sh run.sh "$f" | grep "should"
done
```
**Verified Status: 7/7 PASSED [PASS]**
- `RuleTester.metta` [PASS]
- `equivalenceToImplication.metta` [PASS]
- `evaluationImplicationRuleA.metta` [PASS]
- `evaluationWithNegationAndInheritanceInversion.metta` [PASS]
- `inversion.metta` [PASS]
- `memberDeductionA.metta` [PASS]
- `transitiveSimilarity.metta` [PASS]

### 3.2 Standard PLN Examples
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
for f in DeductionRevision.metta FlyingRaven.metta RavenInduction.metta Robot.metta Smokes.metta Toothbrush.metta; do
    echo -n "$f: "
    sh run.sh "./repos/PLN/examples/$f" | grep "should"
done
```
**Verified Status: 6/6 PASSED [PASS]**
- `DeductionRevision.metta` [PASS]
- `FlyingRaven.metta` [PASS]
- `RavenInduction.metta` [PASS]
- `Robot.metta` [PASS]
- `Smokes.metta` [PASS]
- `Toothbrush.metta` [PASS]
