# PRISM Test Suite & Verification Harness

This directory contains acceptance tests, integration checks, and robustness verification scripts for PRISM (Programmable Reduction & Inference Search Manager).

---

## 1. Directory Contents

| Test File | Verified Gate | Purpose | Expected Result |
|---|:---:|---|---|
| `test_fallback.metta` | **GATE-1.2** | Verifies exception safety, error containment, and graceful degradation to raw confidence when no goal is present or when an error occurs | All 3 sub-tests return `"PASS"` |
| `test_prism_hook.metta` | **GATE-1.4** | Tests that `PriorityRankGoal` actively steers candidate selection toward goal-relevant tasks over competing high-confidence distractors | Selects goal-relevant premise ($c=0.80$) over distractor ($c=0.95$) |
| *(Week 10)* `test_soundness.py` | Release Gate | Re-evaluates final derived conclusions against unmodified PLN formulas to guarantee 100% truth-value soundness | 100% equivalence on all proofs |

---

## 2. Test Specifications & How to Run

All tests are executed through PeTTa's `run.sh`:

### 1. Fallback & Robustness Test (`test_fallback.metta`)
Verifies that PRISM never halts derivation when:
- No goal is provided (`$Goal = ()`).
- A malformed or un-tokenizable sentence is evaluated.
- An empty candidate base case is checked (`() -> -99999.0`).

```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
sh run.sh ../prism/tests/test_fallback.metta
```
**Expected Output:**
```
(FALLBACK_NO_GOAL: 0.77 "PASS")
(GUIDED_SCORE: 0.7216666666666667 "PASS")
(EMPTY_ITEM_GUARD: -99999.0 "PASS")
```

---

### 2. Goal-Directed Hook Verification Test (`test_prism_hook.metta`)
Sets up a competing scenario with two tasks in the knowledge base:
1. `Animal -> LivingThing` (Raw confidence $c=0.95$, completely irrelevant to goal).
2. `Alice -> Person` (Raw confidence $c=0.80$, directly on the path to goal `Alice -> Mortal`).

Under unguided PLN, task selection blindly chooses `Animal -> LivingThing` because $0.95 > 0.80$.  
Under PRISM guidance (`Goal = (Inheritance Alice Mortal)`), `PriorityRankGoal` calls `scorer.py`, detects structural term overlap (`Alice`), and scores `Alice -> Person` higher, correctly selecting it first.

```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
sh run.sh ../prism/tests/test_prism_hook.metta
```
**Expected Output:**
```
(HOOK_VERIFICATION: 
  (goal: (Inheritance Alice Mortal)) 
  (unguided_pick_selected_raw_conf: (Sentence ((Inheritance Animal LivingThing) (stv 0.95 0.95)) (1))) 
  (prism_guided_pick_selected_overlap: (Sentence ((Inheritance Alice Person) (stv 0.9 0.8)) (2))))
```

---

## 3. Full PLN Regression Suite (GATE-1.3)

To confirm that PRISM modifications in [`lib_pln.metta`](../../PeTTa/repos/PLN/lib_pln.metta) do not cause regressions in standard PLN inference, run the full regression test suite:

### 3.1 All 7 Rule Tests
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
for f in ./repos/PLN/ruletests/*.metta; do
    echo -n "$f: "
    sh run.sh "$f" | grep
done
```
**Verified Status: 7/7 PASSED **
- `RuleTester.metta` 
- `equivalenceToImplication.metta` 
- `evaluationImplicationRuleA.metta` 
- `evaluationWithNegationAndInheritanceInversion.metta` 
- `inversion.metta` 
- `memberDeductionA.metta`
- `transitiveSimilarity.metta`

### 3.2 Standard PLN Examples
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
for f in DeductionRevision.metta FlyingRaven.metta RavenInduction.metta Robot.metta Smokes.metta Toothbrush.metta; do
    echo -n "$f: "
    sh run.sh "./repos/PLN/examples/$f" | grep 
done
```
**Verified Status: 6/6 PASSED **
- `DeductionRevision.metta` 
- `FlyingRaven.metta` 
- `RavenInduction.metta` 
- `Robot.metta` 
- `Smokes.metta`
- `Toothbrush.metta` 
