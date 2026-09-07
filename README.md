# PRISM: Programmable Reduction & Inference Search Manager

> **Learned Inference Control Layer for Probabilistic Logic Networks (PLN) in OpenCog Hyperon**  
> **Host Environment:** PeTTa (SWI-Prolog + Janus Python FFI) & `trueagi-io/PLN` (`lib_pln.metta`)  
> **Status:** Week 1 & Week 2 Completed — FFI Foundation, Goal-Directed Hook & Baseline Benchmarks Verified

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
[ Stage 0: Indexed Premise Pre-Filter ] (Conditional)
   │ Structural / unification backward lookup from goal
   ▼
[ Candidate Frontier Generator ] (PLN.Derive, lib_pln.metta)
   │ Enumerates legally applicable (rule, premise) pairs
   ▼
[ Tier 1: Fast Policy / Heuristic Scorer ] (< 0.05ms)
   │ v1: Symbolic structural overlap + confidence decay
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

1. **Stage 0 (Indexed Premise Pre-Filter — Conditional):** Indexes beliefs by predicate/argument patterns to prevent combinatorial explosion before scoring. Evaluated if benchmark domains exhibit frontier blowup.
2. **Tier 1 (Fast Policy / Heuristic Scorer):** Operates on every task selection step ($< 0.05\text{ms}$ latency target). v1 utilizes a symbolic Jaccard-style term overlap with confidence decay; v2 employs a learned model trained on proof traces.
3. **Tier 2 (Strategic LLM Reasoner):** Invoked sparingly only when search stalls ($\ge 5$ consecutive low-scoring steps) or reaches deep thresholds, proposing structured intermediate subgoals.
4. **Score Memoization Cache:** Caches `(sentence, goal) -> score` mappings to eliminate redundant FFI crossings during queue pruning.

---

## 3. Real Codebase Integration (`trueagi-io/PLN`)

PRISM is grounded directly in the live `trueagi-io/PLN` implementation located in `PeTTa/repos/PLN/lib_pln.metta`:

| Target Function | Location | Original Behavior | PRISM Modification |
|---|---|---|---|
| `PriorityRank` | `lib_pln.metta:362-363` | Returns raw confidence `$c$` | Replaced by `PriorityRankGoal` with goal-aware scoring via `prism-score` |
| `PriorityRankNeg` | `lib_pln.metta:366-367` | Returns negated confidence `-c` | Retained for microsecond pure MeTTa queue trimming |
| `LimitSize` | `lib_pln.metta:370-374` | Repeatedly evicts lowest-priority item | Trims queues in pure MeTTa, bypassing FFI overhead |
| `PLN.Derive` | `lib_pln.metta:377-415` | 6-argument recursive loop | 7-argument goal-aware recursive loop; legacy 6-arg and 5-arg overloads preserved |
| `PLN.Query` | `lib_pln.metta:438-445` | Discarded `$term` during derivation | Forwards `$term` as `$Goal` directly into 7-arg `PLN.Derive` |

---

## 4. PRISM Package Layout

```
prism/
├── README.md                          # Package documentation
├── __init__.py                        # Package init
├── scorer.py                          # Main Python entry point (Tier 1 v1 heuristic + safety wrapper)
├── cache.py                           # Score memoization cache
├── prism_ffi.pl                       # Safe Prolog FFI bridge (logic variable handling)
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
│       └── baseline_guided_v1.json    # Recorded PRISM Tier 1 v1 guided numbers
└── tests/                             # Unit, integration, and verification tests
    ├── README.md                      # Documentation of test suite
    ├── test_fallback.metta            # Exception containment & empty-goal fallback test
    └── test_prism_hook.metta          # Live goal-directed prioritization verification test
```

---

## 5. Milestone & Gate Status

### 5.1 Week 1: Foundation & De-risking (ALL GATES PASSED)

| Gate | Requirement | Measured Result | Status |
|---|---|---|:---:|
| **GATE-1.1** | `py-call` Round-Trip Latency $< 1.0\text{ms}$ | **0.012 ms** cached, **0.021 ms** uncached (~47,000–80,000 calls/sec). Over 47× faster than requirement. | **PASSED** |
| **GATE-1.2** | Exception Safety & Fallback | Empty goal and malformed expressions safely degrade to raw confidence `$c$`. Zero crashes. | **PASSED** |
| **GATE-1.3** | Backward Compatibility | **100% PASS** on all 7 `ruletests/*.metta` and all 6 standard examples (`Smokes`, `FlyingRaven`, `Robot`, `Toothbrush`, `RavenInduction`, `DeductionRevision`). | **PASSED** |
| **GATE-1.4** | Goal-Directed Hook Steering | Demonstrated live in `test_prism_hook.metta`: PRISM prioritizes goal-relevant task (Alice $\to$ Person) over an irrelevant 0.95-confidence distractor. | **PASSED** |

### 5.2 Week 2: Synthetic Evaluation Domains & Baselines (ALL GATES PASSED)

| Gate | Requirement | Measured Result | Status |
|---|---|---|:---:|
| **GATE-2.1** | Chain Generation | Transitive chains at D ∈ [5, 20] generate valid `.metta` files that execute under PeTTa without errors. | **PASSED** |
| **GATE-2.2** | Metrics Parsing | `parse_selected_log` correctly classifies on-path vs off-path selections for a known D=5 chain. | **PASSED** |
| **GATE-2.3** | Unguided Baseline Recorded | Baseline waste ratios recorded across depths and distractors in `baseline_unguided.json`. | **PASSED** |
| **GATE-2.4** | Guided vs Unguided Delta | PRISM-guided search eliminates distractors by up to 100%, reducing waste by 38.8% absolute (46.3% relative) on D=5. | **PASSED** |
| **GATE-2.5** | Soundness Preservation | PRISM-guided runs produce the exact same final truth-value conclusions as unguided runs (`[0.60645, 0.16888]`). | **PASSED** |

#### Week 2 Comparative Performance Table (Unguided PLN vs PRISM Tier 1 v1):

| Problem Configuration | Metric | Unguided Baseline | PRISM Guided (Tier 1 v1) | Performance Delta / Impact |
|---|---|:---:|:---:|:---:|
| **D=5, 0 Distractors** | Success Rate | 100% | 100% | Parity |
| | Waste Ratio | 35.0% | 47.5% | +12.5% (heuristic explores goal neighborhood) |
| | Wall Clock | 0.75s | 0.14s | **5.3× faster end-to-end** |
| **D=5, 10 Distractors** | Success Rate | **0% (FAILED)** | **100% (SOLVED)** | **+100% success (Rescued from failure)** |
| | Waste Ratio | 75.6% | 47.5% | **-28.1% absolute waste** |
| | Distractor Picks | 49.5 / 80 steps | 0.0 / 80 steps | **100% distractors eliminated** |
| | Wall Clock | 0.65s | 0.16s | **4.1× faster** |
| **D=5, 25 Distractors** | Success Rate | **0% (FAILED)** | **100% (SOLVED)** | **+100% success (Rescued from failure)** |
| | Waste Ratio | 83.8% | 45.0% | **-38.8% absolute waste (46.3% rel. reduction)** |
| | Distractor Picks | 62.5 / 80 steps | 2.0 / 80 steps | **96.8% distractors eliminated** |
| | Wall Clock | 0.98s | 0.23s | **4.2× faster** |
| **D=5, 50 Distractors** | Success Rate | **0% (FAILED)** | **50% (SOLVED)** | **+50% success** |
| | Waste Ratio | 84.4% | 47.5% | **-36.9% absolute waste** |
| | Distractor Picks | 65.0 / 80 steps | 4.5 / 80 steps | **93.1% distractors eliminated** |
| | Wall Clock | 0.67s | 0.24s | **2.8× faster** |
| **D=8, 10 Distractors** | Distractor Picks | 37.5 / 80 steps | 0.5 / 80 steps | **98.7% distractors eliminated** |
| | Wall Clock | 0.70s | 0.43s | **1.6× faster** |
| **D=10, 10 Distractors** | Distractor Picks | 34.0 / 80 steps | 0.5 / 80 steps | **98.5% distractors eliminated** |
| | Wall Clock | 0.73s | 0.29s | **2.5× faster** |

For detailed weekly reports, consult [`milestones/milestone_week1.md`](../milestones/milestone_week1.md) and [`milestones/milestone_week2.md`](../milestones/milestone_week2.md).

---

## 6. How to Run Benchmarks and Tests

All runs are executed through PeTTa's `run.sh`:

### 1. Running FFI Latency Benchmarks
```bash
cd PeTTa
sh run.sh ../prism/benchmarks/metta/benchmark_pycall.metta
sh run.sh ../prism/benchmarks/metta/benchmark_uncached.metta
```

### 2. Running Synthetic Chain Parameter Sweeps
```bash
cd /home/abel/Desktop/icog_labs/pln

# Run unguided baseline sweep
python3 -m prism.benchmarks.run_benchmark --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80

# Run PRISM-guided sweep
python3 -m prism.benchmarks.run_benchmark --guided --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80
```

### 3. Running PRISM Verification Tests
```bash
cd PeTTa
# Test fallback and error containment
sh run.sh ../prism/tests/test_fallback.metta

# Test goal-directed task steering
sh run.sh ../prism/tests/test_prism_hook.metta
```

### 4. Running Full PLN Regression Suite
```bash
cd PeTTa
# Run all 7 rule tests
for f in ./repos/PLN/ruletests/*.metta; do sh run.sh "$f" | grep "✅"; done

# Run standard examples
for f in DeductionRevision.metta FlyingRaven.metta RavenInduction.metta Robot.metta Smokes.metta Toothbrush.metta; do
    sh run.sh "./repos/PLN/examples/$f" | grep "✅"
done
```

---

## 7. Primary Documentation References
- **[PRISM Proposal (rev. 5)](https://docs.google.com/document/d/1-xqp9HK9RSVpcdMUAas79gD-n0VRl2uwBDy1a5ueSb4/edit?usp=sharing)** — Core motivation, gap analysis, and competition presentation document.
- **[PRISM Implementation Specification](https://docs.google.com/document/d/1vTCytnvsdjlguaFCh9tLzPl8h26d609kxiINFR5bpJc/edit?usp=sharing)** — In-depth architectural companion detailing equations, pseudo-code, and system constraints.
