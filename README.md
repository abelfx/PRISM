# PRISM — Programmable Reduction & Inference Search Manager

> **Learned Inference Control Layer for Probabilistic Logic Networks (PLN) in OpenCog Hyperon**
> **Host Environment:** PeTTa (SWI-Prolog + Janus Python FFI) & `trueagi-io/PLN` (`lib_pln.metta`)

For current implementation progress and results, see [Documentation Map](#7-documentation-map) below — this README covers architecture and setup only.

---

## 1. Overview & Problem Statement

In OpenCog Hyperon, **Probabilistic Logic Networks (PLN)** serves as the core logic engine responsible for deriving new knowledge from stored facts while propagating truth values (strength and confidence).

While PLN's inference rules (deduction, induction, abduction, revision) and truth-value formulas are mathematically well-specified, its **inference search** currently lacks guidance:
- At each step in a derivation, PLN blindly enumerates eligible rule-premise combinations.
- Binary inference rules create a combinatorial Cartesian product over the premise pool.
- Task selection in [`PLN.Derive`](PeTTa/repos/PLN/lib_pln.metta) historically evaluated candidates solely on raw confidence (`$c`), remaining completely blind to the query goal until search concluded.
- Consequently, search quickly stalls on shallow or low-value paths, making multi-hop reasoning over large knowledge graphs computationally intractable.

**PRISM resolves this by introducing a staged, learned inference-control layer.** It acts as an intelligent advisor standing beside PLN: observing candidate moves, scoring them by estimated usefulness and goal relevance, and prioritizing the search frontier — without ever modifying PLN's inference rules or truth-value arithmetic. Soundness is guaranteed by construction, not by testing alone: PRISM never touches the code path that computes a conclusion's truth value, only the order in which legal candidates are tried.

---

## 2. System Architecture

PRISM replaces naive per-candidate LLM calls with a staged, three-part architecture — a cheap pre-filter, a fast scorer that runs on every step, and an expensive strategic reasoner invoked only when the fast path stalls:

```
AtomSpace Knowledge Base (Tasks & Beliefs)
   │
   ▼
[ Stage 0: Indexed Premise Pre-Filter ] (stage0/index.py)
   │ Unification & concept overlap filter against active candidate & goal
   ▼
[ Candidate Frontier Generator ] (PLN.Derive, lib_pln.metta)
   │ Enumerates legally applicable (rule, premise) pairs
   ▼
[ Tier 1: Fast Policy / Heuristic Scorer ] (tier1/heuristic_v1.py, < 0.05ms)
   │ v1: Symbolic structural overlap + confidence + depth geometric discount
   │ v2: Lightweight MLP / embedding ranker (trained on traces)
   ▼
[ Score Memoization Cache ] (core/cache.py)
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
2. **Tier 1 (Fast Policy / Heuristic Scorer):** Operates on every task selection step (< 0.05ms target latency). v1 uses structural concept overlap, confidence, and geometric derivation depth decay ($\delta \cdot \gamma^{depth}$); v2 employs a learned model trained on proof traces.
3. **Tier 2 (Strategic LLM Reasoner):** Invoked sparingly, only when search stalls (≥5 consecutive low-scoring steps) or reaches deep thresholds, proposing structured intermediate subgoals.
4. **Score Memoization Cache:** Caches `(sentence, goal) → score` mappings to eliminate redundant FFI crossings during queue pruning.

The full mathematical specification (cost formulas, training objectives, stall-detection conditions) lives in the Implementation Specification — see §7.

---

## 3. Real Codebase Integration (`trueagi-io/PLN`)

PRISM is grounded directly in the live `trueagi-io/PLN` implementation located in `PeTTa/repos/PLN/lib_pln.metta`. This table is the fast reference for exactly what PRISM touches — for the full reasoning behind each change, see the Implementation Specification:

| Target Function | Location | Original Behavior | PRISM Modification |
|---|---|---|---|
| `PriorityRank` | `lib_pln.metta` | Returns raw confidence `$c` | Replaced by curried `PriorityRankGoal`, goal-aware scoring via `prism-score`, falls back to `$c` on missing goal or scorer failure |
| `PriorityRankNeg` | `lib_pln.metta` | Negated raw confidence | Replaced by `PriorityRankNegGoal`, identical goal-aware/fallback treatment |
| Belief filtering | `lib_pln.metta` | Unconditional `(superpose $Beliefs)` | Filters candidate premises via Stage 0 `prism-filter-beliefs` |
| `LimitSize` | `lib_pln.metta` | Repeatedly evicts lowest-priority item | Goal-aware variant, trims queues in pure MeTTa, cached scores avoid repeated FFI crossings |
| `PLN.Derive` | `lib_pln.metta` | 6-argument recursive loop | 7-argument goal-aware overload added; legacy 6-argument overload preserved unchanged |
| `PLN.Query` | `lib_pln.metta` | Discarded `$term` during derivation | Forwards `$term` as `$Goal` directly into the 7-arg `PLN.Derive` |

**Invariant this table exists to protect:** every row above is either a new addition or a drop-in-compatible replacement. No existing call site, rule, or truth-value formula in `lib_pln.metta` is modified in a way that changes behavior when `$Goal` is absent.

---

## 4. Package Layout

```
prism/
├── ARCHITECTURE.md                    # System architecture, layer ownership & invariants
├── AGENTS.md                          # Quick-reference context & checklist for AI agents
├── README.md                          # This file
├── __init__.py                        # Master public package API
│
├── core/                              # System-wide foundation
│   ├── config.py                      # Immutable hyperparameter dataclasses
│   ├── cache.py                       # Score memoization cache
│   └── scorer.py                      # System coordinator, fallback & FFI entry points
│
├── stage0/                            # Low-cost premise pre-filtering
│   └── index.py                       # Inverted index on sentence terms (PremiseIndex)
│
├── tier1/                             # Fast policy heuristic scorers (<0.05ms)
│   └── heuristic_v1.py                # Symbolic term overlap & geometric depth decay
│
├── search/                            # Global search engine
│   ├── engine.py                      # AStarSearchEngine: f(n) = g(n) + h(n)
│   ├── state.py                       # SearchNode, belief-state hashing, goal matching
│   ├── rules.py                       # Forward candidate generation
│   └── backward.py                    # Backward chaining, meet-in-the-middle detection
│
├── tier2/                             # Strategic LLM reasoner
│   ├── stall_detector.py              # Plateau/depth/cooldown-based stall detection
│   ├── prompt.py                      # Context-aware prompt builder
│   ├── client.py                      # Multi-backend LLM client (OpenRouter, Ollama, Mock)
│   ├── parser.py                      # Subgoal JSON parser & hallucination guard
│   └── reasoner.py                    # Strategic reasoning coordinator
│
├── ffi/                               # Safe Foreign Function Interface bridge
│   └── prism_ffi.pl                   # Prolog/Janus FFI predicates and exception guards
│
├── benchmarks/                        # Benchmark suite & parameter sweep runners
│   ├── run_benchmark.py               # CLI benchmark driver
│   ├── domains/                       # Problem domain generators (chains, diamonds, trees)
│   ├── utils/                         # Metrics collection & FFI profiling
│   ├── metta/                         # Raw MeTTa benchmark scripts
│   └── results/                       # Empirical benchmark datasets (JSON)
│
└── tests/
    ├── unit/                          # Python unit tests (pytest)
    └── integration/                   # MeTTa integration tests (run via PeTTa)
```

For layer ownership, invariants, and where new work should go, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 5. Design Guarantees

These hold regardless of implementation progress — they are architectural commitments, not results to be verified week by week:

- **Soundness by construction:** PRISM never computes or influences a truth value. Every conclusion PLN reaches is computed entirely by PLN's own unmodified formulas, regardless of which tier proposed the candidate.
- **Graceful degradation:** a missing goal, a malformed sentence, or a scorer/FFI failure always falls back to PLN's original confidence-only behavior — never a crash, never a silent wrong answer.
- **Backward compatibility:** every existing call site, rule, and example that doesn't pass a goal continues to behave exactly as it did before PRISM existed.

---

## 6. How to Run

### Unit tests
```bash
cd <repo-root>
python3 -m pytest prism/tests/
```

### MeTTa integration tests
```bash
cd <repo-root>/PeTTa
sh run.sh ../prism/tests/integration/test_fallback.metta
sh run.sh ../prism/tests/integration/test_prism_hook.metta
```

### Synthetic benchmark sweeps
```bash
cd <repo-root>

# Unguided baseline
python3 -m prism.benchmarks.run_benchmark --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80

# PRISM-guided
python3 -m prism.benchmarks.run_benchmark --guided --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80 --output prism/benchmarks/results/<name>.json
```

### Full PLN regression suite
```bash
cd <repo-root>/PeTTa
for f in ./repos/PLN/ruletests/*.metta; do sh run.sh "$f" | grep "should"; done
```

---

## 7. Documentation Map

This project's documentation is split by purpose — each document below covers a different concern, so results and status are never duplicated here:

| Document | Covers |
|---|---|
| `PRISM_PLN_Inference_Control_Proposal.docx` | The what and why — problem, gaps, AGI relevance, proposed solution |
| `PRISM_Implementation_Specification.docx` | The how — file-level code changes, formulas, training objectives |
| `milestones/milestone_week*.md` | Full per-week deliverables, gate criteria, and raw benchmark data |
| `PRISM_Results_Synthesis.docx` | The presentation narrative — headline results, honest limitations, updated as weeks land |
| `ARCHITECTURE.md` | Layer ownership, invariants, where new work belongs |
| `AGENTS.md` | Quick-reference context for AI coding agents working in this repo |
