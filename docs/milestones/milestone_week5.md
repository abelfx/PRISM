# PRISM — Week 5 Milestone: Learned A* / Best-First Search Engine

**Milestone:** Week 5 — Learned A* / Best-First Search Loop, Global Agenda Management & Trace Streaming  
**Project:** PRISM (Programmable Reduction & Inference Search Manager)  
**Prerequisites:** Weeks 1–4 Complete (FFI Bridge, Synthetic Baselines, Tier 1 v1 Heuristic, Stage 0 Indexing, Complex Topologies, Trace Logger)  
**Timeline:** Week 5 of 12 (First half of Weeks 5–6 Search Engine block)  
**Status:** Complete (All 5 Gates Passed)  

---

## 1. Objectives & Strategic Rationale

Throughout Weeks 1 to 4, PRISM's guidance operated exclusively as a **local candidate-selection hook** within PeTTa's native recursion:
* At each step, PeTTa's `PLN.Derive` loop invokes `PriorityRankGoal` to choose which sentence from the active queue to expand next.
* While this local guidance achieved impressive results (0.0 distractor picks on linear chains, 100% shortcut selection on diamond DAGs, and complete rescue of 0% unguided failures on tree conjunctions), it remains bounded by the architectural limits of PeTTa's internal forward derivation stack:
  1. **Greedy Traversal Without Backtracking:** Once PeTTa commits to a derivation branch, it cannot easily back up to an earlier, higher-promise alternative branch if the current path degrades.
  2. **Fixed Memory Horizons:** Priority queue eviction inside `LimitSize` permanently discards candidates that might become valuable later.
  3. **Absence of Cumulative Path Cost ($g(n)$):** The local heuristic scores candidate promises ($h(n)$), but does not account for the cumulative uncertainty or cost accumulated along the derivation path ($g(n)$).

### The Week 5 Objective:
Per Section 8 of the PRISM Proposal and Section 8 of the Implementation Specification, Week 5 transitions PRISM from a local selection hook to a **formal, global Learned A* / Best-First Search engine** (`src/prism/search/`):
* Implement an explicit global open-set priority queue managing state nodes $\langle f(n), \text{step}, \text{state} \rangle$.
* Implement the dual-component cost formulation $f(n) = g(n) + h(n)$, combining cumulative path cost with inverted Tier 1 heuristic distance.
* Implement closed-set visited state hashing to prevent circular reasoning and duplicate derivation.
* Hook the Week 4 Proof Trace Logger directly into the search engine to stream training transitions into JSONL.

---

## 2. Deliverables & Technical Tasks

### Task 5.1: Search Configuration & Hyperparameter Dataclass (`src/prism/core/config.py`)
- [x] Added `SearchConfig` dataclass to `src/prism/core/config.py` following strict modularity principles:
  * `max_steps`: Global derivation step budget (default: 100).
  * `beam_width` / `top_k`: Maximum number of candidate derivations expanded per state (default: 5).
  * `cost_confidence_weight`: Scaling weight for action cost $1.0 - \text{confidence}$ (default: 1.0).
  * `min_step_cost`: Floor cost per deduction step to prevent 0-cost cycles (default: 0.01).
  * `stall_threshold`: Tier 1 score threshold below which a state is considered stalled (default: 0.15).
  * `deduplicate_beliefs`: Enable/disable closed-set state hashing (default: True).
- [x] Integrated `SearchConfig` into the master `PrismConfig`.
- [x] Added unit tests for `SearchConfig` in `tests/unit/test_config.py`.

### Task 5.2: State Representation & Node Abstraction (`src/prism/search/state.py`)
- [x] Defined `SearchNode` dataclass in `src/prism/search/state.py`:
  * `state_id`: Unique monotonic identifier.
  * `tasks`: Active task queue (sentences pending expansion).
  * `beliefs`: Cumulative belief buffer (facts known and derived).
  * `g_cost`: Cumulative path cost from start state to current state.
  * `h_cost`: Heuristic estimate of remaining distance to target goal.
  * `f_cost`: Combined evaluation score $f(n) = g(n) + h(n)$.
  * `depth`: Derivation step depth.
  * `parent_id`: Pointer to ancestor node for proof reconstruction.
  * `action`: Sentence/rule that generated this state transition.
  * Implemented min-heap comparison (`__lt__`) ordering by `f_cost`, breaking ties with `h_cost`, then `state_id`.
- [x] Implemented canonical state hashing `hash_belief_state(beliefs)` for closed-set duplicate detection (permutation-invariant SHA-256 digest).
- [x] Implemented robust goal checking `matches_goal(sentence, goal)` and proof path reconstruction `extract_proof_path(final_node, registry)`.

### Task 5.3: Forward Rule Application & Candidate Generation (`src/prism/search/rules.py`)
- [x] Implemented `ParsedSentence` dataclass and robust S-expression parser `parse_sentence`.
- [x] Implemented `deduce_pair(p1, p2)` for transitive `Inheritance` and `Similarity` deduction with truth value formulas and strict evidence disjointness enforcement.
- [x] Implemented `generate_forward_candidates(tasks, beliefs)` matching active tasks against known beliefs.
- [x] Implemented `apply_candidate(candidate, tasks, beliefs)` returning updated task and belief collections.

### Task 5.4: Learned A* Search Engine Core (`src/prism/search/engine.py`)
- [x] Implemented `AStarSearchEngine`:
  * Min-heap agenda with deterministic tie-breaking.
  * Cumulative path cost tracking $g(n) = \sum (1.0 - \text{conf})$.
  * Inverted Tier 1 heuristic distance $h(n) = \max(0.0, 1.0 - \text{Score}_{\text{tier1}})$.
  * Cached scoring via `ScoreCache` to prevent redundant computations.
  * Beam width pruning expanding top-$K$ candidates per state.
  * Closed-set visited state deduplication.
  * Stall detection flag (`stalled = True` when top candidate scores fall below `stall_threshold`).
  * Complete ancestor proof path reconstruction returning unbroken lemma sequence.
- [x] Wired `trace_session` directly into the search loop, streaming transition events and retroactively attributing proof path labels upon completion.

### Task 5.5: Comprehensive Unit & Regression Testing
- [x] Wrote 10 search unit tests in `tests/unit/test_search.py`:
  * Min-heap ordering verification.
  * Belief state hashing permutation invariance.
  * Multi-format goal matching.
  * Forward PLN deduction rule with circular evidence rejection.
  * End-to-end A* linear chain proof search.
  * Closed-set cycle prevention.
  * Step budget exhaustion handling.
  * Diamond domain shortcut preference.
  * Proof trace streaming and retroactive attribution.
  * Stall detection on low-scoring candidate sets.
- [x] Verified full unit test suite: **46/46 passed in 0.05s**.
- [x] Verified MeTTa integration suite: **4/4 passed**.
- [x] Verified upstream PLN ruletests regression: **7/7 passed**.

---

## 3. Mathematical Specifications

### 3.1 A* Cost Formulation

For search node $n$ reached via derivation sequence $\langle S_1, S_2, \dots, S_k \rangle$:

$$f(n) = g(n) + h(n)$$

#### 1. Cumulative Path Cost $g(n)$:
Each inference step incurs an uncertainty cost inversely proportional to the conclusion's confidence:

$$c(S_{i}) = \max\left(\text{min\_cost},\ (1.0 - \text{Confidence}(S_{i})) \cdot w_c\right)$$

$$g(n) = \sum_{i=1}^{k} c(S_{i})$$

* **Property:** Shorter derivations and derivations utilizing high-confidence premises have strictly smaller $g(n)$.
* **Monotonicity:** Because $c(S_i) \ge \text{min\_cost} > 0$, path cost $g(n)$ is strictly monotonically increasing, preventing zero-cost infinite loops.

#### 2. Heuristic Distance to Goal $h(n)$:
The heuristic estimate is derived by inverting the normalized Tier 1 v1 score:

$$h(n) = \max\left(0.0,\ 1.0 - \text{Score}_{\text{tier1}}(S_k, \text{Goal})\right)$$

Where $\text{Score}_{\text{tier1}} \in [0, 1]$ combines atom overlap, confidence, and geometric depth bonus:

$$\text{Score}_{\text{tier1}}(S_k, G) = \alpha \cdot \text{Overlap}(S_k, G) + \beta \cdot \text{Conf}(S_k) + \delta \cdot \gamma^{\text{depth}(S_k)}$$

* **Intuition:**
  * When candidate $S_k$ directly matches the goal, $\text{Score}_{\text{tier1}} \approx 1.0 \implies h(n) \approx 0.0$ (goal reached).
  * When candidate $S_k$ is an irrelevant distractor, $\text{Score}_{\text{tier1}} \approx 0.0 \implies h(n) \approx 1.0$ (maximum distance).

---

## 4. Verification Gates (Audit Table)

| Gate ID | Criterion | Target Threshold | Measured Result | Status |
|---|---|---|---|:---:|
| **GATE-5.1** | **Priority Queue Ordering** | Min-heap strictly orders open states by $f(n) = g(n) + h(n)$ with deterministic tie-breaking | Verified via `test_search_node_min_heap_ordering` | **PASS** |
| **GATE-5.2** | **Cycle & Loop Detection** | Visited set correctly hashes belief states and prunes duplicate states | Verified via `test_belief_state_hashing_invariance` & `test_astar_search_cycle_pruning` | **PASS** |
| **GATE-5.3** | **Goal Proof Extraction** | Engine identifies goal satisfaction and reconstructs complete, valid ancestor chain | Verified via `test_astar_search_linear_chain_success` | **PASS** |
| **GATE-5.4** | **Search Step Reduction & Path Preference** | Guided A* search reaches goal prioritizing shortcut over long path | Verified via `test_astar_search_diamond_shortcut_preference` | **PASS** |
| **GATE-5.5** | **Zero Upstream Regression** | All existing unit tests, MeTTa integration tests, and PLN rule tests remain 100% passing | **46/46 Unit, 4/4 MeTTa, 7/7 PLN Rules** | **PASS** |

---

## 5. File & Directory Layout for Week 5

```
prism/
├── core/
│   ├── config.py              # UPDATE: SearchConfig dataclass
│   ├── scorer.py              # Existing FFI scorer
│   └── cache.py               # Existing ScoreCache
│
├── search/                    # NEW: Search engine subsystem
│   ├── __init__.py            # Exported search symbols
│   ├── state.py               # SearchNode, state hashing, goal matching, proof extraction
│   ├── rules.py               # ParsedSentence, forward deduction, candidate generation
│   └── engine.py              # AStarSearchEngine & SearchResult
│
├── benchmarks/
│   ├── domains/               # Chain, diamond, tree generators
│   └── utils/
│       ├── metrics.py         # Metrics engine
│       └── trace_logger.py    # Search trace recorder
│
└── tests/
    └── unit/
        ├── test_config.py     # SearchConfig unit tests
        ├── test_search.py     # NEW: 10 comprehensive search engine unit tests
        ├── test_multipath.py  # Week 4 diamond tests
        ├── test_tree_dag.py   # Week 4 tree tests
        └── test_trace_logger.py
```

---

## 6. Empirical Search Comparison: Unguided vs. PRISM Learned A*

To validate the search space reduction and path optimality of the new A* search engine (`src/prism/search/engine.py`), a comparative evaluation was conducted using `benchmarks/evaluate_search_comparison.py`.

The evaluation benchmarked:
1. **Unguided Uniform-Cost / FIFO Search:** $h(n) = 0.0$ (relying strictly on path cost / FIFO expansion).
2. **PRISM Learned A* Search:** $f(n) = g(n) + h(n)$ guided by Tier 1 v1 heuristic scoring and cumulative uncertainty cost tracking.

All tests ran with an identical budget of 80 derivation steps, beam width $K=5$, and minimum step cost of 0.01 across synthetic domains generated with seed 42.

### 6.1 Head-to-Head Benchmark Table

| Benchmark Scenario | Goal | Facts | Distractors | Metric | Unguided Search | PRISM A* Search | Efficiency Gain / Impact |
|:---|:---:|:---:|:---:|---|:---:|:---:|:---:|
| **Linear Chain D=4** | `(Inheritance A E)` | 14 | 10 | Success Rate | **100%** | **100%** | Solved |
| | | | | Steps Expanded | 28 | **19** | **32.1% fewer steps** |
| | | | | Nodes Generated | 84 | **60** | **28.6% search space reduction** |
| | | | | Proof Path Length | 4 steps | 4 steps | 100% sound proof |
| | | | | Wall-Clock Time | 0.0148s | **0.0113s** | **1.31x faster** |
| **Diamond DAG (D=3 vs D=7)** | `(Inheritance A Z)` | 40 | 30 | Success Rate | **100%** | **100%** | Solved |
| | | | | Steps Expanded | 17 | **7** | **58.8% fewer steps** |
| | | | | Nodes Generated | 51 | **21** | **58.8% search space reduction** |
| | | | | Solution Path | Mixed / Redundant | **Shortcut ($P_S$)** | **Optimal path preference** |
| | | | | Wall-Clock Time | 0.0270s | **0.0100s** | **2.70x faster** |
| **Linear Chain D=6 (High Noise)** | `(Inheritance A G)` | 31 | 25 | Success Rate | 0% (Stalled) | 0% (Stalled) | Budget reached (80 steps) |
| | | | | Steps Expanded | 80 | 80 | Frontier contention |
| **Tree Conjunction L(3,3)** | `(Inheritance A Z)` | 26 | 20 | Success Rate | 0% (Stalled) | 0% (Stalled) | Budget reached (80 steps) |
| | | | | Steps Expanded | 80 | 80 | Multi-branch confluence budget |

### 6.2 Key Empirical Findings & Insights

1. **Substantial Search Space Reduction:** On the multi-path Diamond DAG with 30 distractors, PRISM A* achieved a **58.8% reduction in expanded steps (7 vs. 17)** and a **58.8% reduction in generated nodes (21 vs. 51)**.
2. **Path Optimality Commitment:** In the Diamond domain, unguided search wasted effort exploring the 7-step long path alongside the shortcut path. PRISM A* strictly committed to the 3-step shortcut path $P_S$, discovering the complete proof in only 7 derivation steps (**2.70x faster wall clock**).
3. **Linear Chain Efficiency:** On the $D=4$ chain with 10 distractors, PRISM reduced expansion steps by **32.1% (19 vs. 28)** and wall-clock execution time by **23.6%**.
4. **Engineering Boundary & Bridge to Week 6:** In high-noise environments ($N \ge 20$ distractors) on deep chains ($D \ge 6$) or confluent trees, forward Cartesian candidate generation with narrow beam width ($K=5$) encounters frontier contention without premise filtering. This highlights the strategic necessity of **Week 6 (Backward Chaining & Stage 0 Indexing Integration)** to prune unviable premise combinations prior to candidate generation.
