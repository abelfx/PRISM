# PRISM — Week 4 Milestone: Complex Topologies, Multi-Path DAGs & Trace Logging

**Milestone:** Week 4 — Non-Linear Benchmark Topologies (Diamond, Tree DAGs), Proof Trace Logging & Path Optimality  
**Project:** PRISM (Programmable Reduction & Inference Search Manager)  
**Prerequisite:** Week 3 Complete (Tier 1 v1 Heuristic, Stage 0 Premise Indexing, 0.0 Distractor Picks Verified)  
**Timeline:** Week 4 of 12  
**Status:** Completed (All 5 Gates Passed)  

---

## 1. Objectives & Strategic Rationale

By the end of Week 3, PRISM achieved a major milestone: on linear transitive deduction chains ($A \to B \to C \dots \to Z$), the combination of the Tier 1 v1 heuristic and Stage 0 premise pre-filtering reduced distractor selections to **0.0 across all depths ($D \in [5, 10]$) and up to 50 distractors**, converting previous 0% unguided failures into 100% successes.

However, linear transitive chains represent the simplest topological case in automated theorem proving. Real-world PLN reasoning over the AtomSpace exhibits significantly more complex geometries:

1. **Multi-Path & Diamond Topologies (Shortcuts vs. Scenic Paths):**
   Knowledge graphs rarely have only a single derivation route. There are frequently multiple valid deductive paths between a query's source and target:
   - A short, direct path (e.g., length $L=2$, high confidence).
   - A long, winding redundant path (e.g., length $L=5$, lower cumulative confidence).
   Unguided PLN often wanders down long paths because it cannot foresee derivation depth. Week 4 empirically verifies that PRISM's depth penalty ($\delta \cdot \gamma^{depth}$) actively steers search toward the **shortest, highest-confidence proof path**.

2. **Tree / DAG Proof Topologies (Conjunctive Subgoals):**
   Inferences frequently require synthesizing multiple independent branches. For example, deriving $(A \implies Z)$ requires first deriving lemma $(A \to M)$ from branch 1 and lemma $(M \to Z)$ from branch 2, then applying deduction. Search must balance exploration across multiple active frontiers without prematurely abandoning necessary lemmas.

3. **Structured Proof Trace Logging for Future Tiers:**
   Per the PRISM master specification, Week 5 introduces the Best-First Search manager, and Week 11 trains the Tier 1 v2 neural scoring model (PyTorch MLP). Both require structured training datasets of inference traces. Week 4 builds the **Trace Logger** to record step-by-step state-action-goal tuples with ground-truth proof attribution.

---

## 2. Deliverables & Technical Tasks

### Task 4.1: Multi-Path Diamond Domain Generator (`benchmarks/domains/multipath_dag.py`)
- [x] Implemented `generate_diamond(depth_short, depth_long, ...)`:
  - Generates a DAG with two parallel valid deduction routes connecting start concept $A$ to target $Z$:
    - **Path 1 (Shortcut):** $A \to S_1 \to \dots \to S_{k-1} \to Z$ (depth $k$).
    - **Path 2 (Long path):** $A \to L_1 \to \dots \to L_{m-1} \to Z$ (depth $m$, where $m > k$).
- [x] Implemented `generate_diamond_with_distractors(...)`:
  - Injects $N$ random distractors with reproducible seeds.
- [x] Implemented `classify_diamond_solution(evidence_stamp, spec)`:
  - Classifies whether the final proof utilized `SHORTCUT`, `LONG_PATH`, or `MIXED` premises.
- [x] Implemented `write_diamond_metta_file(...)` rendering runnable `.metta` benchmark files.

### Task 4.2: Tree / Conjunction Domain Generator (`benchmarks/domains/tree_dag.py`)
- [x] Implemented `generate_tree_conjunction(depth_left, depth_right, ...)`:
  - Branch 1 derives intermediate conclusion $(A \to M)$.
  - Branch 2 derives intermediate conclusion $(M \to Z)$.
  - Final deduction unifies $(A \to M) \land (M \to Z) \vdash (A \to Z)$.
- [x] Implemented `generate_tree_with_distractors(...)`:
  - Injects $N$ background distractors around the confluence.
- [x] Implemented `verify_tree_conjunction_solution(evidence_stamp, spec)`:
  - Validates that the final proof stamp contains evidence from both branches.
- [x] Implemented `write_tree_metta_file(...)` rendering runnable `.metta` benchmark files.

### Task 4.3: Proof Trace Instrumentation & Dataset Generator (`src/prism/observability/tracing.py`)
- [x] Implemented `ProofStepTrace` dataclass capturing per-step features:
  - Step number, statement string, truth values, evidence stamp, active goal.
  - Features: atom overlap, confidence, depth, depth discount, heuristic score, candidate pool size.
  - Supervised binary label: `on_proof_path`.
- [x] Implemented `ProofTraceSession`:
  - Hooks into derivation step outputs to record structured transitions.
  - Retroactively labels every selected step as `on_proof_path: true` or `false` by verifying whether its evidence stamp is a subset of the final goal's proof stamp ($\text{Stamp}(S_t) \subseteq \text{Stamp}_{\text{final}}$).
  - Implemented `export_jsonl(...)` producing standard JSON Lines datasets for Week 11 offline neural training.

### Task 4.4: Benchmark Runner & Metrics Enhancement (`run_benchmark.py` & `metrics.py`)
- [x] Enhanced `run_benchmark.py` with `--domain {chain, diamond, tree}` CLI flags.
- [x] Enhanced `metrics.py` to record `domain_type`, `solution_path`, and `conjunction_verified`.
- [x] Added `--export-traces <file.jsonl>` flag to record supervised training datasets during benchmark sweeps.

### Task 4.5: Unit Testing & Pass/Fail Verification
- [x] Wrote unit tests in `tests/unit/test_multipath.py` (5/5 passed).
- [x] Wrote unit tests in `tests/unit/test_tree_dag.py` (5/5 passed).
- [x] Wrote unit tests in `tests/unit/test_trace_logger.py` (4/4 passed).
- [x] Verified full unit test suite: **34/34 passed in 0.05s**.
- [x] Verified MeTTa integration suite: **4/4 passed**.
- [x] Verified upstream PLN ruletests regression: **7/7 passed**.

---

## 3. Mathematical Specifications

### 3.1 Path Optimality & Geometric Discount Formulation

In a diamond domain with shortcut path $P_S$ (depth $d_S$) and long path $P_L$ (depth $d_L$), where $d_S < d_L$:

$$\text{Score}(c, G) = \alpha \cdot \text{Overlap}(c, G) + \beta \cdot \text{Conf}(c) + \delta \cdot \gamma^{\text{depth}(c)}$$

When both paths share identical terminal atom overlap with goal $G$, the score differential is governed strictly by the depth bonus:

$$\Delta \text{Score} = \text{Score}(c_S) - \text{Score}(c_L) = \delta \cdot \left(\gamma^{d_S} - \gamma^{d_L}\right) + \beta \cdot \left(\text{Conf}(c_S) - \text{Conf}(c_L)\right)$$

With default parameters ($\delta = 0.10, \gamma = 0.90$):
- At $d_S = 2$: Depth discount bonus $= 0.10 \cdot (0.90)^2 = 0.081$.
- At $d_L = 5$: Depth discount bonus $= 0.10 \cdot (0.90)^5 = 0.059$.
- The shortcut path maintains a persistent positive gradient $\Delta \text{Score} > 0$, guaranteeing prioritized expansion of the shorter chain.

### 3.2 Proof Path Attribution Function

Let $S_{\text{final}} = \langle \text{Sentence}, \text{Statement}, \text{Stamp}_{\text{final}} \rangle$ be the sentence satisfying Goal $G$, where $\text{Stamp}_{\text{final}} = \{i_1, i_2, \dots, i_k\}$ is the multiset of base premise indices that produced $S_{\text{final}}$.

For any intermediate derivation step $t$ selecting sentence $S_t$ with stamp $\text{Stamp}(S_t)$:

$$\text{OnProofPath}(S_t) = \begin{cases} 
1 & \text{if } \text{Stamp}(S_t) \subseteq \text{Stamp}_{\text{final}} \\
0 & \text{otherwise}
\end{cases}$$

This provides a mathematically exact, ground-truth supervised binary label for every intermediate step.

---

## 4. Verification Gates (Audit Table)

| Gate ID | Criterion | Target Threshold | Measured Result | Status |
|---|---|---|---|:---:|
| **GATE-4.1** | **Diamond Domain Generation** | Exact $D_{short}$ and $D_{long}$ topology with ground truth | 5/5 unit tests passed | **PASS** |
| **GATE-4.2** | **Tree / Conjunction Generation** | 2-branch confluent derivation DAG with junction routing | 5/5 unit tests passed | **PASS** |
| **GATE-4.3** | **Shortcut Path Preference** | Guided search reaches goal via $P_S$ in $\ge 90\%$ of runs | **100% Shortcut Rate (12/12 runs)** | **PASS** |
| **GATE-4.4** | **Trace Logger Completeness** | 100% of derivation steps logged with exact features & labels | Verified on JSONL output | **PASS** |
| **GATE-4.5** | **Zero Upstream Regression** | 7/7 PLN rule tests and unit test suite remain passing | **34/34 Unit, 7/7 PLN Rules** | **PASS** |

---

## 5. Full Empirical Benchmark Results & Comparative Analysis

All benchmark runs were executed with a step budget of 80 steps, priority queue size of 30, and belief queue size of 100 across multiple random seeds.

### 5.1 Multi-Path Diamond DAG Benchmark Results

Evaluated across shortcut depth $D_{short} \in \{2, 3\}$, long path depth $D_{long} \in \{5, 6\}$, and distractor counts $N \in \{0, 10, 25\}$.

| Domain Configuration | Distractors | Unguided Success | Guided Success | Unguided Path | **Guided Path** | Unguided Distractor Picks | **Guided Distractor Picks** | Unguided Wall Clock | **Guided Wall Clock** |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **D(2, 5)** | 0 | 100% | **100%** | MIXED | **SHORTCUT (100%)** | 0.0 | **0.0** | 1.19s | **0.42s (2.8x faster)** |
| **D(2, 5)** | 10 | 100% | **100%** | SHORTCUT | **SHORTCUT (100%)** | 36.0 | **0.0** | 0.89s | **0.42s (2.1x faster)** |
| **D(2, 5)** | 25 | 100% | **100%** | SHORTCUT | **SHORTCUT (100%)** | 59.0 | **37.0** | 1.04s | **1.11s** |
| **D(3, 6)** | 0 | 100% | **100%** | SHORTCUT | **SHORTCUT (100%)** | 0.0 | **0.0** | 1.48s | **1.46s** |
| **D(3, 6)** | 10 | 100% | **100%** | SHORTCUT | **SHORTCUT (100%)** | 36.5 | **14.5** | 0.88s | **1.11s** |
| **D(3, 6)** | 25 | 100% | **100%** | SHORTCUT | **SHORTCUT (100%)** | 54.0 | **34.5** | 1.06s | **1.12s** |

#### Diamond Analysis & Insights:
1. **Shortcut Optimality:** In 100% of guided diamond runs, PRISM selected `path=SHORTCUT`, avoiding the redundant long path.
2. **Elimination of Redundant Exploration:** In the clean diamond domain ($D_{2,5}$, 0 distractors), unguided PLN explored both paths simultaneously and merged them (`path=MIXED`), requiring 1.19s. PRISM focused exclusively on the shortcut path, completing the derivation in 0.42s (**2.8x speedup**).
3. **Branching Resistance:** In $D_{2,5}$ with 10 distractors, unguided PLN wasted 36 out of 80 steps exploring distractors (45% waste). PRISM reduced distractor selections to **0.0**.

---

### 5.2 Tree Conjunction DAG Benchmark Results

Evaluated on multi-branch confluence topologies where deriving $(A \to Z)$ requires proving $(A \to M)$ from Branch 1 and $(M \to Z)$ from Branch 2.

| Domain Configuration | Distractors | Unguided Success Rate | **Guided Success Rate** | Unguided Conjunction | **Guided Conjunction** | Unguided Distractor Picks | **Guided Distractor Picks** | Unguided Wall Clock | **Guided Wall Clock** | Total Outcome |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Tree L(2, 2)** | 0 | 100% | **100%** | Verified | **Verified** | 0.0 | **0.0** | 0.49s | **0.20s** | 2.5x faster |
| **Tree L(2, 2)** | 10 | 100% | **100%** | Verified | **Verified** | 52.0 | **0.0** | 0.68s | **0.22s** | **52 distractors eliminated; 3.1x faster** |
| **Tree L(2, 2)** | 25 | 0% (FAILED) | **100%** | FAILED | **Verified** | 64.5 | **0.0** | 1.05s | **0.29s** | **Rescued 0% failure to 100% success; 3.6x faster** |
| **Tree L(3, 3)** | 0 | 0% (FAILED) | **100%** | FAILED | **Verified** | 0.0 | **0.0** | 1.01s | **0.24s** | **Rescued 0% failure to 100% success; 4.2x faster** |
| **Tree L(3, 3)** | 10 | 0% (FAILED) | **100%** | FAILED | **Verified** | 44.0 | **0.0** | 0.73s | **0.28s** | **Rescued 0% failure to 100% success; 2.6x faster** |
| **Tree L(3, 3)** | 25 | 0% (FAILED) | 0% (FAILED) | FAILED | FAILED | 61.0 | 27.0 | 1.04s | 0.75s | Distractors reduced by 56% |

#### Tree Conjunction Analysis & Insights:
1. **Conjunctive Proof Rescue:** For $L(2, 2)$ under 25 distractors, and $L(3, 3)$ under 0 and 10 distractors, **unguided PLN failed completely (0% success)** because its unguided queue became flooded with irrelevant derivations or one branch starved the other. PRISM achieved **100% success**, verifying both branches in under 0.3 seconds.
2. **Complete Distractor Elimination:** Across all successful guided tree configurations ($L(2, 2)$ with 0, 10, 25 distractors and $L(3, 3)$ with 0, 10 distractors), PRISM maintained **0.0 distractor selections**, demonstrating that Stage 0 pre-filtering successfully indexes multi-branch premises.
3. **Execution Speedup:** On $L(3, 3)$ with 0 distractors, PRISM found the conjunctive proof in **0.24s**, while unguided PLN timed out at 80 steps (1.01s) without finding the goal (**4.2x speedup**).

---

### 5.3 Proof Trace Dataset Validation

The proof trace logger (`trace_logger.py`) was verified by streaming traces to `benchmarks/scratch/test_traces.jsonl`.
Sample extracted record:

```json
{
  "step": 2,
  "statement": "(Inheritance A Z)",
  "strength": 0.81166725,
  "confidence": 0.6561,
  "evidence_stamp": ["1", "2"],
  "goal": "(Inheritance A Z)",
  "candidate_pool_size": 1,
  "depth": 0,
  "atom_overlap": 1.0,
  "depth_discount": 0.1,
  "heuristic_score": 0.914,
  "on_proof_path": true,
  "domain_name": "diamond_(2, 5)_dist0_s100",
  "goal_reached": true
}
```

Off-path candidate rejection example:
```json
{
  "step": 14,
  "statement": "(Inheritance A L1)",
  "strength": 0.9,
  "confidence": 0.9,
  "evidence_stamp": ["3"],
  "goal": "(Inheritance A Z)",
  "candidate_pool_size": 1,
  "depth": 0,
  "atom_overlap": 0.6667,
  "depth_discount": 0.1,
  "heuristic_score": 0.7583,
  "on_proof_path": false,
  "domain_name": "diamond_(2, 5)_dist0_s100",
  "goal_reached": true
}
```

- In Step 14, the candidate `(Inheritance A L1)` belonged to the long path (stamp `["3"]`).
- Because the derivation reached the goal via the shortcut path (stamp `["1", "2"]`), the trace logger retroactively and accurately labeled Step 14 as `on_proof_path: false`.
- This confirms that the trace instrumentation produces clean supervised labels for training Tier 1 v2.

---

## 6. Assumptions & Engineering Boundaries

1. **Stamp Subset as Proof Attribution:** Proof path attribution assumes the multiset intersection of evidence stamps is necessary and sufficient to identify contributing steps in forward PLN deductions.
2. **Junction Node Grounding:** In tree conjunction benchmarks, the junction concept ($M$) serves as the semantic bridge connecting Branch 1 to Branch 2. Both branches must progress to allow the confluence deduction to fire.
3. **Zero Hardcoded Constants:** All benchmark parameters and thresholds continue to adhere to the project's strict modular architecture.
