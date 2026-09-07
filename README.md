# PRISM: Programmable Reduction & Inference Search Manager

> **Learned Inference Control Layer for Probabilistic Logic Networks (PLN) in OpenCog Hyperon**  
> **Target:** iCog Labs AGI Engineering Competition — Track A: Hybrid AGI  
> **Host Environment:** PeTTa (SWI-Prolog + Janus Python FFI) & `trueagi-io/PLN` (`lib_pln.metta`)  
> **Status:** Week 1 Completed — FFI Foundation & Goal-Directed Hook De-risked (All 4 Acceptance Gates Passed)

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
| `PriorityRank` | `lib_pln.metta:362-363` | Returns raw confidence `$c$` | Replaced by `PriorityRankGoal` with goal-aware scoring via `py-call` |
| `PriorityRankNeg` | `lib_pln.metta:366-367` | Returns negated confidence `-c` | Retained for microsecond pure MeTTa queue trimming |
| `LimitSize` | `lib_pln.metta:370-374` | Repeatedly evicts lowest-priority item | Trims queues in pure MeTTa, bypassing FFI overhead |
| `PLN.Derive` | `lib_pln.metta:377-415` | 6-argument recursive loop | 7-argument goal-aware recursive loop; legacy 6-arg and 5-arg overloads preserved |
| `PLN.Query` | `lib_pln.metta:438-445` | Discarded `$term` during derivation | Forwards `$term` as `$Goal` directly into 7-arg `PLN.Derive` |

---

## 4. Repository Directory Layout

```
.
├── README.md                              # This document
├── milestone.md                           # Week-by-week execution plan and pass/fail gate tracker
├── PRISM_Implementation_Specification.md  # Comprehensive technical implementation companion
├── PRISM_Implementation_Specification.pdf # Formatted PDF implementation specification
├── PRISM_PLN_Inference_Control_Proposal_final.pdf # Competition project proposal (rev. 5)
│
├── PeTTa/                                 # PeTTa interpreter environment
│   ├── run.sh                             # Main runner (exports PRISM PYTHONPATH)
│   ├── src/metta.pl                       # Prolog interpreter core (hardened py-call FFI)
│   └── repos/
│       └── PLN/                           # Production PLN engine
│           ├── lib_pln.metta              # Modified core engine with PRISM hooks
│           ├── ruletests/                 # 7 rule regression tests (100% PASS)
│           └── examples/                  # Standard PLN examples (100% PASS)
│
├── prism/                                 # PRISM Python & MeTTa guidance package
│   ├── __init__.py                        # Package init
│   ├── scorer.py                          # Main py-call entry point (Tier 1 v1 heuristic + safety wrapper)
│   ├── cache.py                           # Score memoization cache
│   ├── benchmarks/                        # FFI latency & throughput benchmarks
│   │   ├── README.md                      # Documentation of benchmark suite
│   │   ├── pycall_bench.py                # Python benchmark helper
│   │   ├── benchmark_pycall.metta         # Cached FFI round-trip latency benchmark
│   │   └── benchmark_uncached.metta       # Uncached FFI latency benchmark
│   └── tests/                             # Unit, integration, and verification tests
│       ├── README.md                      # Documentation of test suite
│       ├── test_fallback.metta            # Exception containment & empty-goal fallback test
│       └── test_prism_hook.metta          # Live goal-directed prioritization verification test
│
└── pln-experimental/                      # Legacy experimental predecessor repo
```

---

## 5. Milestone & Gate Status (Week 1 of 12)

All four **Week 1 Acceptance Gates** have been implemented, tested, and passed on the live PeTTa environment:

| Gate | Requirement | Measured Result | Status |
|---|---|---|:---:|
| **GATE-1.1** | `py-call` Round-Trip Latency $< 1.0\text{ms}$ | **0.015 ms** cached, **0.021 ms** uncached (~47,000–66,700 calls/sec). Over 47× faster than requirement. | **PASSED** |
| **GATE-1.2** | Exception Safety & Fallback | Empty goal and malformed expressions safely degrade to raw confidence `$c$`. Zero crashes. | **PASSED** |
| **GATE-1.3** | Backward Compatibility | **100% PASS** on all 7 `ruletests/*.metta` and all 6 standard examples (`Smokes`, `FlyingRaven`, `Robot`, `Toothbrush`, `RavenInduction`, `DeductionRevision`). | **PASSED** |
| **GATE-1.4** | Goal-Directed Hook Steering | Demonstrated live in `test_prism_hook.metta`: PRISM prioritizes goal-relevant task (Alice $\to$ Person) over an irrelevant 0.95-confidence distractor. | **PASSED** |

For details on upcoming deliverables (Weeks 2–12), consult [`milestone.md`](milestone.md).

---

## 6. How to Run Benchmarks and Tests

All runs are executed through PeTTa's `run.sh`:

### Running FFI Latency Benchmarks
```bash
cd PeTTa
sh run.sh ../prism/benchmarks/benchmark_pycall.metta
sh run.sh ../prism/benchmarks/benchmark_uncached.metta
```

### Running PRISM Verification Tests
```bash
cd PeTTa
# Test fallback and error containment
sh run.sh ../prism/tests/test_fallback.metta

# Test goal-directed task steering
sh run.sh ../prism/tests/test_prism_hook.metta
```

### Running Full PLN Regression Suite
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
- **[PRISM Proposal (rev. 5)](PRISM_PLN_Inference_Control_Proposal_final.pdf)** — Core motivation, gap analysis, and competition presentation document.
- **[PRISM Implementation Specification](PRISM_Implementation_Specification.md)** — In-depth architectural companion detailing equations, pseudo-code, and system constraints.
- **[Milestone Tracker](milestone.md)** — Weekly sprint gates and deliverables.
