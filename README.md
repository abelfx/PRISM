# Programmable Reduction & Inference Search Manager

> **Learned Inference Control Layer for Probabilistic Logic Networks (PLN) in OpenCog Hyperon**  
> **Host Environment:** PeTTa (SWI-Prolog + Janus Python FFI) & `trueagi-io/PLN` (`lib_pln.metta`)  
> **Status:** Week 1, Week 2 & Week 3 Completed — Tier 1 Heuristic, Stage 0 Premise Indexing & 0.0 Distractor Picks Verified

---

## 1. Overview & Problem Statement

In OpenCog Hyperon, **Probabilistic Logic Networks (PLN)** serves as the core logic engine responsible for deriving new knowledge from stored facts while propagating truth values (strength and confidence). 

While PLN's inference rules (deduction, induction, abduction, revision) and truth-value formulas are mathematically well-specified, its **inference search** currently lacks guidance:
- At each step in a derivation, PLN blindly enumerates eligible rule-premise combinations.
- Binary inference rules create a combinatorial Cartesian product over the premise pool.
- Task selection in [`PLN.Derive`](PeTTa/repos/PLN/lib_pln.metta) historically evaluated candidates solely on raw confidence (`$c`), remaining completely blind to the query goal until search concluded.
- Consequently, search quickly stalls on shallow or low-value paths, making multi-hop reasoning over large knowledge graphs computationally intractable.

**PRISM resolves this by introducing a staged, learned inference-control layer.** It acts as an intelligent advisor standing beside PLN: observing candidate moves, scoring them by estimated usefulness and goal relevance, and prioritizing the search frontier—without ever modifying PLN's inference rules or truth-value arithmetic. Soundness is guaranteed by construction.

---

## 2. Staged System Architecture

PRISM replaces naive per-candidate LLM calls with a defensive, three-stage / two-tier architecture:

```
AtomSpace Knowledge Base (Tasks & Beliefs)
   │
   ▼
[ Stage 0: Indexed Premise Pre-Filter ] (stage0_index.py)
   │ Unification & concept overlap filter against active candidate & goal
   ▼
[ Candidate Frontier Generator ] (PLN.Derive, lib_pln.metta)
   │ Enumerates legally applicable (rule, premise) pairs
   ▼
[ Tier 1: Fast Policy / Heuristic Scorer ] (tier1_v1.py, < 0.05ms)
   │ v1: Symbolic structural overlap + confidence + depth geometric discount
   │ v2: Lightweight MLP / embedding ranker (trained on traces)
   ▼
[ Score Memoization Cache ] (cache.py)
   │ Prevents O(N²) FFI calls during queue pruning
   ▼
[ Priority Queue Selection ] (BestCandidate PriorityRankGoal)
   │
   ├─► [ Normal Progress ] ──────────────┐
   │                                      ▼
   └─► [ Search Stalled? ] ────► [ Tier 2: Strategic LLM Reasoner ]
         (Low scores for k steps)       Decomposes goal into subgoals (JSON)
                                           │
                                           ▼
                                  [ PLN Truth-Value Execution ]
                                  Authoritative, 100% sound PLN formulas
                                           │
                                           ▼
                              Derived Conclusion & Valid STV
```

1. **Stage 0 (Indexed Premise Pre-Filter):** Indexes beliefs by concept and link patterns to prevent combinatorial Cartesian products before MeTTa evaluation.
2. **Tier 1 (Fast Policy / Heuristic Scorer):** Operates on every task selection step ($< 0.05\text{ms}$ latency). v1 uses structural concept overlap, confidence, and geometric derivation depth decay ($\delta \cdot \gamma^{depth}$); v2 employs a learned model trained on proof traces.
3. **Tier 2 (Strategic LLM Reasoner):** Invoked sparingly only when search stalls ($\ge 5$ consecutive low-scoring steps) or reaches deep thresholds, proposing structured intermediate subgoals.
4. **Score Memoization Cache:** Caches `(sentence, goal) -> score` mappings to eliminate redundant FFI crossings during queue pruning.

---

## 3. Real Codebase Integration (`trueagi-io/PLN`)

PRISM is grounded directly in the live `trueagi-io/PLN` implementation located in `PeTTa/repos/PLN/lib_pln.metta`:

| Target Function | Location | Original Behavior | PRISM Modification |
|---|---|---|---|
| `PriorityRank` | `lib_pln.metta` | Returns raw confidence `$c$` | Replaced by `PriorityRankGoal` with goal-aware scoring via `prism-score` |
| `PremiseFilter` | `lib_pln.metta` | Unconditional `(superpose $Beliefs)` | Filters candidate premises via Stage 0 `prism-filter-beliefs` |
| `LimitSize` | `lib_pln.metta` | Repeatedly evicts lowest-priority item | Trims queues in pure MeTTa, bypassing FFI overhead |
| `PLN.Derive` | `lib_pln.metta` | 6-argument recursive loop | 7-argument goal-aware recursive loop; legacy 6-arg and 5-arg overloads preserved |
| `PLN.Query` | `lib_pln.metta` | Discarded `$term` during derivation | Forwards `$term` as `$Goal` directly into 7-arg `PLN.Derive` |

---

## 4. PRISM Package Layout

The PRISM repository follows a modular, layer-separated architecture. For detailed architectural guidelines, invariants, and implementation roadmap placement, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

```
prism/
├── ARCHITECTURE.md                    # System architecture, layer ownership & invariants
├── AGENTS.md                          # Quick-reference context & checklist for AI agents
├── README.md                          # Package documentation and milestone roadmap
├── __init__.py                        # Master public package API
│
├── core/                              # System-wide foundation (config, coordinator, cache)
│   ├── __init__.py
│   ├── config.py                      # Immutable hyperparameter dataclasses
│   ├── cache.py                       # LRU / Dict memoization cache
│   └── scorer.py                      # System coordinator, fallback & FFI entry points
│
├── stage0/                            # Low-cost premise pre-filtering
│   ├── __init__.py
│   └── index.py                       # Inverted index on sentence terms (PremiseIndex)
│
├── tier1/                             # Fast policy heuristic scorers (<0.05ms)
│   ├── __init__.py
│   └── heuristic_v1.py                # Symbolic term overlap & geometric depth decay
│
├── ffi/                               # Safe Foreign Function Interface bridge
│   ├── __init__.py
│   └── prism_ffi.pl                   # Prolog/Janus FFI predicates and exception guards
│
├── benchmarks/                        # Benchmark suite & parameter sweep runners
│   ├── README.md                      # Documentation of benchmark suite
│   ├── run_benchmark.py               # Main CLI benchmark driver & parameter sweep runner
│   ├── domains/                       # Problem domain generators
│   │   ├── __init__.py
│   │   └── transitive_chain.py        # Synthetic transitive chain generator (D in [5, 20])
│   ├── utils/                         # Metrics collection & profiling utilities
│   │   ├── __init__.py
│   │   ├── metrics.py                 # MetricsCollector and PeTTa log parser
│   │   └── pycall_bench.py            # FFI timing & argument inspection helper
│   ├── metta/                         # Raw MeTTa benchmark scripts
│   │   ├── benchmark_pycall.metta     # Cached FFI latency test
│   │   └── benchmark_uncached.metta   # Uncached FFI latency test
│   └── results/                       # Empirical benchmark datasets
│       ├── baseline_unguided.json     # Recorded unguided PLN baseline numbers
│       ├── baseline_guided_v1.json    # Recorded PRISM Tier 1 v1 guided numbers (Week 2)
│       └── baseline_guided_week3.json # Recorded PRISM Tier 1 v1 + Stage 0 numbers (Week 3)
│
├── tests/                             # Unit and integration test suites
│   ├── conftest.py                    # Pytest environment & path configuration
│   ├── README.md                      # Documentation of test suite
│   ├── unit/                          # Python unit tests (pytest)
│   │   ├── __init__.py
│   │   ├── test_config.py             # Config immutability & validation
│   │   ├── test_tier1_v1.py           # Overlap math & depth discount
│   │   ├── test_stage0_index.py       # Premise indexing & filtering
│   │   └── test_scorer.py             # Scorer coordinator & cache
│   └── integration/                   # MeTTa integration tests (PeTTa run.sh)
│       ├── test_fallback.metta        # MeTTa exception containment test
│       ├── test_prism_hook.metta      # MeTTa goal-directed task steering test

```

---

## 5. Milestone & Gate Status

### 5.1 Week 1: Foundation & De-risking (ALL GATES PASSED)
- **GATE-1.1:** `py-call` Round-Trip Latency $< 1.0\text{ms}$ (**0.012 ms** cached, **0.021 ms** uncached).
- **GATE-1.2:** Exception Safety & Fallback (empty goal and exceptions safely degrade to raw confidence `$c$`).
- **GATE-1.3:** Backward Compatibility (**100% PASS** on all 7 `ruletests/*.metta` and all standard examples).
- **GATE-1.4:** Goal-Directed Hook Steering demonstrated live in `test_prism_hook.metta`.

### 5.2 Week 2: Synthetic Evaluation Domains & Baselines (ALL GATES PASSED)
- **GATE-2.1:** Chain Generation for $D \in [5, 20]$.
- **GATE-2.2:** Metrics Parsing (`parse_selected_log`).
- **GATE-2.3:** Unguided Baseline Recorded in `baseline_unguided.json`.
- **GATE-2.4:** Guided vs Unguided Delta (waste reduced by up to 38.8% absolute on $D=5$).
- **GATE-2.5:** Soundness Preservation (`[0.60645, 0.16888]`).

### 5.3 Week 3: Tier 1 v1 Completion & Stage 0 Indexing (ALL GATES PASSED)
- **GATE-3.1:** Depth Penalty Active (shallow proof outscores deep proof: 0.7733 vs 0.7353).
- **GATE-3.2:** Stage 0 Lookup Accuracy (preserves on-path beliefs, excludes distractors).
- **GATE-3.3:** MeTTa Integration (clean execution via `prism_ffi.pl` without crashing Janus).
- **GATE-3.4:** Soundness Preservation (100% STV and evidence stamp match with unguided baseline).
- **GATE-3.5:** Efficiency Gain & Distractor Elimination (distractor picks reduced to **0.0 across all depths and distractor counts**).

#### Week 3 Comparative Benchmark Table:

| Depth | Distractors | Unguided Success | Week 2 Guided Success | Week 3 Guided Success | Unguided Distractor Picks | Week 2 Distractor Picks | **Week 3 Distractor Picks** | Week 3 Wall Clock |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **D=5** | 0 | 100% | 100% | **100%** | 0.0 | 0.0 | **0.0** | 0.20s |
| **D=5** | 10 | 0% (FAILED) | 100% | **100%** | 49.5 | 0.0 | **0.0** | 0.24s |
| **D=5** | 25 | 0% (FAILED) | 100% | **100%** | 62.5 | 2.0 | **0.0** | 0.30s |
| **D=5** | 50 | 0% (FAILED) | 50% | **100%** | 65.0 | 4.5 | **0.0** | 0.29s |
| **D=8** | 25 | 0% (FAILED) | 0% (FAILED) | **100%** | 57.0 | 24.0 | **0.0** | **0.32s** |
| **D=8** | 50 | 0% (FAILED) | 0% (FAILED) | **100%** | 56.0 | 26.5 | **0.0** | **0.31s** |
| **D=10** | 25 | 0% (FAILED) | 0% (FAILED) | **100%** | 50.5 | 23.5 | **0.0** | **0.34s** |
| **D=10** | 50 | 0% (FAILED) | 0% (FAILED) | **100%** | 50.0 | 24.5 | **0.0** | **0.32s** |

For detailed milestone reports, consult [`milestones/milestone_week1.md`](../milestones/milestone_week1.md), [`milestones/milestone_week2.md`](../milestones/milestone_week2.md), and [`milestones/milestone_week3.md`](../milestones/milestone_week3.md).

---

## 6. How to Run Benchmarks and Tests

### 1. Running Unit Tests (Pytest)
```bash
cd /home/abel/Desktop/icog_labs/pln
python3 -m pytest prism/tests/
```

### 2. Running MeTTa PRISM Integration Tests
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
sh run.sh ../prism/tests/integration/test_depth_penalty.metta
sh run.sh ../prism/tests/integration/test_stage0_metta.metta
sh run.sh ../prism/tests/integration/test_fallback.metta
sh run.sh ../prism/tests/integration/test_prism_hook.metta
```

### 3. Running Synthetic Chain Parameter Sweeps
```bash
cd /home/abel/Desktop/icog_labs/pln

# Run unguided baseline sweep
python3 -m prism.benchmarks.run_benchmark --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80

# Run PRISM-guided sweep (Week 3)
python3 -m prism.benchmarks.run_benchmark --guided --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80 --output prism/benchmarks/results/baseline_guided_week3.json
```

### 4. Running Full PLN Regression Suite
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
# Run all 7 rule tests
for f in ./repos/PLN/ruletests/*.metta; do sh run.sh "$f" | grep "should"; done
```
