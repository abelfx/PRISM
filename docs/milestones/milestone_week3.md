# PRISM — Week 3 Milestone: Tier 1 Heuristic Completion & Stage 0 Indexing

**Milestone:** Week 3 — Tier 1 v1 Heuristic Completion, Depth Penalty & Stage 0 Premise Indexing  
**Project:** PRISM (Programmable Reduction & Inference Search Manager)  
**Prerequisite:** Week 2 Complete (Synthetic Baselines & Basic Tier 1 Scoring Active)  
**Timeline:** Week 3 of 12  
**Status:** Complete (All 5 Gates Passed)

---

## 1. Objectives & Rationale

During Week 2, we built the synthetic `transitive_chain` domains and recorded the unguided baselines, showing that unguided PLN collapses to 0% success under even 10 distractors. While the preliminary Tier 1 scorer demonstrated significant improvement, two critical architectural capabilities remained missing per the PRISM Master Specification (§4 & §5.1):

1. **Derivation Depth Penalty ($\delta \cdot \gamma^{depth}$):** The heuristic needed an explicit geometric discount based on derivation depth to penalize overly deep, winding inference paths.
2. **Stage 0 Premise Indexing & Pre-Filtering:** In $D=8$ and $D=10$ scenarios with 25–50 distractors, guided search still suffered from evaluating dozens of distractors (~24 to 26 picks). More critically, the unconditional `(superpose $Beliefs)` in `PLN.Derive` evaluated every belief in the buffer against the selected task, causing severe combinatorial overhead as the knowledge base scaled.
3. **Modular Architecture & Config Isolation:** Moving all weights ($\alpha, \beta, \delta, \gamma$), thresholds, and defaults out of algorithmic logic into an isolated configuration module (`config.py`).

By completing Week 3, PRISM features a fully mature Tier 1 v1 scorer and an active Stage 0 premise pre-filter that reduces distractor selections to **0.0 across all depths and distractor counts**.

---

## 2. Deliverables & Technical Tasks

### Task 3.1: Complete Tier 1 v1 Heuristic (`tier1_v1.py` & `config.py`)
- [x] Implemented `prism/config.py` containing immutable `Tier1Config`, `Stage0Config`, and master `PrismConfig`. No hardcoded constants in algorithmic code.
- [x] Implemented `extract_depth(sentence)` in `src/prism/tier1/heuristic_v1.py` deriving depth directly from the evidence stamp length ($\text{depth} = \max(0, \text{len}(\text{stamp}) - 1)$) without altering MeTTa signatures.
- [x] Implemented `compute_depth_discount(depth, delta, gamma)` computing $\delta \cdot \gamma^{depth}$.
- [x] Excluded relational operators (`Inheritance`, `Evaluation`, `Implication`, etc.) and wrappers (`Sentence`, `stv`, `Concept`, `Predicate`, `List`) from atom overlap calculation, ensuring only true domain concepts contribute to overlap.
- [x] Tuned hyperparameters ($\alpha=0.65, \beta=0.25, \delta=0.10, \gamma=0.90$) ensuring on-path premises comfortably dominate even maximum-confidence ($c=0.95$) distractors.

### Task 3.2: Stage 0 Indexed Premise Pre-Filter (`stage0_index.py`)
- [x] Implemented `PremiseIndex` class in `src/prism/stage0/index.py` per §4 of the implementation spec.
- [x] Implemented recursive `extract_concepts(expr)` capturing domain concepts at arbitrary nesting depths.
- [x] Implemented `filter_beliefs(candidate, goal, beliefs)` that restricts premise candidates passed to `superpose` to only those sharing concepts with the active task or goal.
- [x] Implemented safe fallback returning all beliefs when input is unguided (`Goal = ()`), empty, or if no concepts match, guaranteeing search never stalls.

### Task 3.3: Prolog FFI Bridge & MeTTa Integration (`prism_ffi.pl` & `lib_pln.metta`)
- [x] Implemented `'prism-filter-beliefs'/4` in `prism/prism_ffi.pl`, safely stripping logic variable attributes before Janus invocation and catching all exceptions with graceful fallback to unmodified beliefs.
- [x] Imported `prism-filter-beliefs` into `lib_pln.metta`.
- [x] Added `PremiseFilter` hook to `PLN.Derive` in `lib_pln.metta` using explicit `let $filteredBeliefs` binding before `(superpose $filteredBeliefs)`.
- [x] Preserved legacy queue eviction using fast `LimitSize` (confidence-based) to maintain sub-millisecond step latency.

### Task 3.4: Comprehensive Unit & Regression Testing
- [x] Wrote 20 unit tests across `test_config.py`, `test_tier1_v1.py`, `test_stage0_index.py`, and `test_scorer.py` (100% pass rate).
- [x] Wrote MeTTa integration tests `test_depth_penalty.metta` and `test_stage0_metta.metta` (100% pass rate).
- [x] Verified zero regression on all 7 PLN ruletests in `PeTTa/repos/PLN/ruletests/` (100% pass rate).
- [x] Executed full multi-seed parameter sweep recorded in `benchmarks/results/reference/baseline_guided_week3.json`.
- [x] Verified 100% mathematical soundness against unguided baseline on $D=5$.

---

## 3. Pass / Fail Acceptance Gates

| Gate ID | Criterion | Threshold / Target | Verification Method | Status |
|---|---|---|---|:---:|
| **GATE-3.1** | Depth Penalty Active | Scorer correctly applies geometric discount; shallower proofs outscore deeper ones | `test_depth_penalty.metta` & `test_tier1_v1.py` | **PASSED** (Shallow 0.7733 vs Deep 0.7353) |
| **GATE-3.2** | Stage 0 Lookup Accuracy | `filter_beliefs` retains all required proof premises and excludes noise | `test_stage0_index.py` & `test_stage0_metta.metta` | **PASSED** (On-path preserved, distractors filtered) |
| **GATE-3.3** | MeTTa Integration | `lib_pln.metta` uses Stage 0 via `prism_ffi.pl` without crashing Janus or PeTTa | Live execution of synthetic chains & ruletests | **PASSED** (100% clean execution, zero crashes) |
| **GATE-3.4** | Soundness Preservation | Final truth-values and evidence stamps match unguided baseline perfectly | STV & stamp equality test | **PASSED** (STV: `[0.60645, 0.16888]`, Stamp: `['1', '2', '3', '4', '5']`) |
| **GATE-3.5** | Efficiency Gain | Wall-clock time on $D=10$ with 50 distractors $\le$ Week 2 guided times; 0 distractor picks | Benchmark comparison vs `baseline_guided_v1.json` | **PASSED** (Time: 0.323s vs 0.456s; Distractor picks: **0.0 vs 24.5**) |

---

## 4. Empirical Results: Week 3 Benchmark Sweep (`baseline_guided_week3.json`)

*Step budget = 80 steps, Task Queue = 30, Belief Queue = 100, Repetitions = 2 per cell*

| Depth | Distractors | Success Rate | Avg Waste Ratio | Avg Steps | Avg Distractor Picks | Avg Wall Clock | Comparison vs Week 2 Guided |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **D=5** | 0 | **100%** | 47.50% | 80.0 | **0.0** | 0.2045s | Parity |
| **D=5** | 10 | **100%** | 47.50% | 80.0 | **0.0** | 0.2355s | 100% distractors eliminated |
| **D=5** | 25 | **100%** | 45.00% | 80.0 | **0.0** | 0.3044s | Distractor picks: 2.0 → **0.0** |
| **D=5** | 50 | **100%** | 47.50% | 80.0 | **0.0** | 0.2949s | Success: 50% → **100%**; Picks: 4.5 → **0.0** |
| **D=8** | 0 | 0% | 43.75% | 80.0 | **0.0** | 0.7221s | Stalls at budget limit |
| **D=8** | 10 | 0% | 38.75% | 80.0 | **0.0** | 0.6987s | Distractor picks: 0.5 → **0.0** |
| **D=8** | 25 | **100%** | 45.00% | 80.0 | **0.0** | 0.3250s | Success: 0% → **100%**; Picks: 24.0 → **0.0**; Time: 0.528s → **0.325s** |
| **D=8** | 50 | **100%** | 47.50% | 80.0 | **0.0** | 0.3092s | Success: 0% → **100%**; Picks: 26.5 → **0.0**; Time: 0.452s → **0.309s** |
| **D=10** | 0 | 0% | 42.50% | 80.0 | **0.0** | 0.3506s | Stalls at budget limit |
| **D=10** | 10 | 0% | 37.50% | 80.0 | **0.0** | 0.5615s | Distractor picks: 0.5 → **0.0** |
| **D=10** | 25 | **100%** | 45.00% | 80.0 | **0.0** | 0.3411s | Success: 0% → **100%**; Picks: 23.5 → **0.0**; Time: 0.508s → **0.341s** |
| **D=10** | 50 | **100%** | 47.50% | 80.0 | **0.0** | 0.3234s | Success: 0% → **100%**; Picks: 24.5 → **0.0**; Time: 0.456s → **0.323s** |

---

## 5. Comparative Performance Analysis

| Problem Configuration | Metric | Unguided Baseline | Week 2 Guided (v1) | Week 3 Guided (v1 + Stage 0) | Total Improvement |
|---|---|:---:|:---:|:---:|:---:|
| **D=5, 50 Distractors** | Success Rate | 0% (FAILED) | 50% | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 65.0 / 80 | 4.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.67s | 0.24s | 0.29s | 2.3× faster than unguided |
| **D=8, 25 Distractors** | Success Rate | 0% (FAILED) | 0% (FAILED) | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 57.0 / 80 | 24.0 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.99s | 0.53s | **0.32s** | **3.1× faster than unguided** |
| **D=8, 50 Distractors** | Success Rate | 0% (FAILED) | 0% (FAILED) | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 56.0 / 80 | 26.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.66s | 0.45s | **0.31s** | **2.1× faster than unguided** |
| **D=10, 25 Distractors** | Success Rate | 0% (FAILED) | 0% (FAILED) | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 50.5 / 80 | 23.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.93s | 0.51s | **0.34s** | **2.7× faster than unguided** |
| **D=10, 50 Distractors** | Success Rate | 0% (FAILED) | 0% (FAILED) | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 50.0 / 80 | 24.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.64s | 0.46s | **0.32s** | **2.0× faster than unguided** |

---

## 6. Assumptions, Non-Tested Scope & Real-Repo Verification Checklist

Per the strict engineering practices required for PRISM development, here is the explicit audit trail:

### What Was Assumed:
1. **Evidence Stamp as Derivation Depth:** We assumed that in forward PLN derivation, a sentence's derivation depth is proportional to its evidence stamp length ($\max(0, \text{len}(\text{stamp}) - 1)$). This holds true for all standard tree derivations where base premises have singleton stamps.
2. **Concept Intersection Condition for Syllogisms:** We assumed that binary inference rules in `lib_pln.metta` require premise 1 and premise 2 to share at least one concept/atom. If a premise shares no concept with the candidate task or goal, it cannot fire a syllogistic rule (deduction, induction, abduction, revision).
3. **Queue Eviction Bottleneck:** We determined and verified that applying goal-directed FFI evaluation during `LimitSize` queue pruning creates an $O((N-K) \times N)$ FFI bottleneck (~2,200 FFI calls/step). We therefore kept `LimitSize` confidence-based, which maintains sub-millisecond derivation steps while letting Stage 0 and `PriorityRankGoal` handle selection.

### What Was NOT Tested:
1. **Cycles in Derivation Stamps:** We did not test domains where circular inference paths cause artificial stamp inflation beyond true tree depth.
2. **Non-Deductive Complex Domains:** We tested transitive chains and all 7 standard PLN ruletests (`Evaluation`, `Implication`, `Inversion`, `Similarity`, `Member`), but did not test large-scale multi-hop Knowledge Graphs with hundreds of relation types (scheduled for Week 9).
3. **Multi-threading FFI Safety:** All benchmarks were run in single-threaded SWI-Prolog Janus environments. Multi-threaded FFI calls were not benchmarked.

### What Should Be Double-Checked Against the Real Repo:
1. **`lib_pln.metta` Git Tracking:** Confirm that changes to `lib_pln.metta` (the Stage 0 `PremiseFilter` hook) remain isolated to `PeTTa/repos/PLN/` and that upstream `PeTTa/src/` remains completely clean.
2. **Janus Python Path:** Confirm `PYTHONPATH` in deployment scripts includes `prism/` so `prism_ffi.pl` can import `scorer` without requiring root symlinks.
