# PRISM Benchmarks Suite

This directory contains the profiling, latency benchmarking, and search-efficiency measurement harnesses for PRISM (Programmable Reduction & Inference Search Manager).

---

## 1. Directory Structure

```
benchmarks/
├── run_benchmark.py               # Main CLI benchmark driver & parameter sweep runner
├── evaluate_scaling_generalization.py # Week 9 scaling and cross-domain gates
├── domains/                       # Benchmark domain generators
│   ├── __init__.py
│   └── transitive_chain.py        # Synthetic transitive chain generator (D in [5, 20])
├── utils/                         # Measurement & profiling utilities
│   ├── __init__.py
│   ├── metrics.py                 # MetricsCollector and PeTTa log parser
│   └── pycall_bench.py            # FFI timing & argument inspection helper
├── metta/                         # Raw MeTTa benchmark scripts
│   ├── benchmark_pycall.metta     # Cached FFI round-trip latency test
│   └── benchmark_uncached.metta   # Uncached FFI latency test
└── results/reference/             # Curated empirical benchmark datasets
    ├── baseline_unguided.json     # Recorded unguided PLN baseline numbers
    ├── baseline_guided_v1.json    # Recorded PRISM Tier 1 v1 guided numbers (Week 2)
    └── baseline_guided_week3.json # Recorded PRISM Tier 1 v1 + Stage 0 numbers (Week 3)
```

---

## 2. Empirical Benchmark Results

### 2.1 Week 1: FFI Latency & Throughput (GATE-1.1)

| Metric | Target / Gate | Measured (Cached) | Measured (Uncached) | Status |
|---|:---:|:---:|:---:|:---:|
| **Mean Latency per Call** | $< 1.0\text{ms}$ (ideal $< 0.1\text{ms}$) | **0.0124 ms** (12 µs) | **0.0214 ms** (21 µs) | **PASSED** (47× to 80× faster than gate) |
| **Call Throughput** | $> 1,000$ calls/sec | **80,893** calls/sec | **46,825** calls/sec | **PASSED** |
| **Total Time (1,000 calls)** | $< 1.0\text{s}$ | **0.0124 s** | **0.0214 s** | **PASSED** |
| **Cache Hit Ratio** | — | **99.9%** (999/1000) | **0.0%** (1000 misses) | **VERIFIED** |

---

### 2.2 Full Unguided Baseline Sweep (`baseline_unguided.json`)

*Parameters: 80 max steps, Task Queue = 30, Belief Queue = 100, 2 repeats per configuration*

| Depth | Distractors | Success Rate | Avg Waste Ratio | Avg Steps | Avg Distractor Picks | Avg Wall Clock | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **D=5** | 0 | **100%** | 35.00% | 80.0 | 0.0 | 0.7455s | Solved reliably in absence of noise |
| **D=5** | 10 | **0% (FAILED)** | 75.62% | 80.0 | 49.5 | 0.6505s | Immediate failure; 62% steps on distractors |
| **D=5** | 25 | **0% (FAILED)** | 83.75% | 80.0 | 62.5 | 0.9782s | 78% steps wasted on distractors |
| **D=5** | 50 | **0% (FAILED)** | 84.38% | 80.0 | 65.0 | 0.6668s | 81% steps wasted on distractors |
| **D=8** | 0 | **0% (FAILED)** | 31.25% | 80.0 | 0.0 | 1.0974s | Derivation stalls before depth 8 |
| **D=8** | 10 | **0% (FAILED)** | 65.00% | 80.0 | 37.5 | 0.7039s | High distractor attraction |
| **D=8** | 25 | **0% (FAILED)** | 73.12% | 80.0 | 57.0 | 0.9873s | Severe distractor distraction |
| **D=8** | 50 | **0% (FAILED)** | 73.12% | 80.0 | 56.0 | 0.6576s | Severe distractor distraction |
| **D=10** | 0 | **0% (FAILED)** | 32.50% | 80.0 | 0.0 | 1.1614s | Derivation stalls before depth 10 |
| **D=10** | 10 | **0% (FAILED)** | 58.75% | 80.0 | 34.0 | 0.7283s | High distractor attraction |
| **D=10** | 25 | **0% (FAILED)** | 65.62% | 80.0 | 50.5 | 0.9321s | High distractor attraction |
| **D=10** | 50 | **0% (FAILED)** | 65.62% | 80.0 | 50.0 | 0.6444s | High distractor attraction |

---

### 2.3 Week 2 Guided Sweep (`baseline_guided_v1.json`)

*Preliminary Tier 1 v1 heuristic active (`PriorityRankGoal` with alpha=0.7, beta=0.3)*

| Depth | Distractors | Success Rate | Avg Waste Ratio | Avg Steps | Avg Distractor Picks | Avg Wall Clock | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **D=5** | 0 | **100%** | 47.50% | 80.0 | 0.0 | 0.1429s | 5.2× faster than unguided |
| **D=5** | 10 | **100%** | 47.50% | 80.0 | 0.0 | 0.1597s | 0 distractor picks (100% eliminated) |
| **D=5** | 25 | **100%** | 45.00% | 80.0 | 2.0 | 0.2323s | 46.3% relative waste reduction |
| **D=5** | 50 | **50%** | 47.50% | 80.0 | 4.5 | 0.2407s | 93% distractor reduction |
| **D=8** | 0 | **0%** | 35.00% | 80.0 | 0.0 | 0.3886s | 2.8× faster wall clock |
| **D=8** | 10 | **0%** | 30.63% | 80.0 | 0.5 | 0.4347s | 98.7% distractor reduction |
| **D=8** | 25 | **0%** | 52.50% | 80.0 | 24.0 | 0.5285s | Distractor attraction remains |
| **D=8** | 50 | **0%** | 55.62% | 80.0 | 26.5 | 0.4527s | Distractor attraction remains |
| **D=10** | 0 | **0%** | 35.00% | 80.0 | 0.0 | 0.2126s | 5.5× faster wall clock |
| **D=10** | 10 | **0%** | 27.50% | 80.0 | 0.5 | 0.2935s | 98.5% distractor reduction |
| **D=10** | 25 | **0%** | 51.25% | 80.0 | 23.5 | 0.5085s | Distractor attraction remains |
| **D=10** | 50 | **0%** | 49.38% | 80.0 | 24.5 | 0.4561s | Distractor attraction remains |

---

### 2.4 Week 3 Guided Sweep: Tier 1 v1 + Stage 0 Premise Indexing (`baseline_guided_week3.json`)

*Full Tier 1 v1 heuristic (alpha=0.65, beta=0.25, delta=0.10, gamma=0.90) with active Stage 0 premise pre-filter*

| Depth | Distractors | Success Rate | Avg Waste Ratio | Avg Steps | Avg Distractor Picks | Avg Wall Clock | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **D=5** | 0 | **100%** | 47.50% | 80.0 | **0.0** | 0.2045s | Parity |
| **D=5** | 10 | **100%** | 47.50% | 80.0 | **0.0** | 0.2355s | 100% distractors eliminated |
| **D=5** | 25 | **100%** | 45.00% | 80.0 | **0.0** | 0.3044s | 100% distractors eliminated (2.0 → 0.0) |
| **D=5** | 50 | **100%** | 47.50% | 80.0 | **0.0** | 0.2949s | Success: 50% → 100%; Picks: 4.5 → 0.0 |
| **D=8** | 0 | 0% | 43.75% | 80.0 | **0.0** | 0.7221s | Stalls at budget limit |
| **D=8** | 10 | 0% | 38.75% | 80.0 | **0.0** | 0.6987s | 0.0 distractor picks |
| **D=8** | 25 | **100%** | 45.00% | 80.0 | **0.0** | **0.3250s** | Success: 0% → 100%; Picks: 24.0 → 0.0 |
| **D=8** | 50 | **100%** | 47.50% | 80.0 | **0.0** | **0.3092s** | Success: 0% → 100%; Picks: 26.5 → 0.0 |
| **D=10** | 0 | 0% | 42.50% | 80.0 | **0.0** | 0.3506s | Stalls at budget limit |
| **D=10** | 10 | 0% | 37.50% | 80.0 | **0.0** | 0.5615s | 0.0 distractor picks |
| **D=10** | 25 | **100%** | 45.00% | 80.0 | **0.0** | **0.3411s** | Success: 0% → 100%; Picks: 23.5 → 0.0 |
| **D=10** | 50 | **100%** | 47.50% | 80.0 | **0.0** | **0.3234s** | Success: 0% → 100%; Picks: 24.5 → 0.0 |

---

### 2.5 Side-by-Side 3-Way Comparative Performance Analysis

| Problem Configuration | Metric | Unguided Baseline | Week 2 Guided (v1) | Week 3 Guided (v1 + Stage 0) | Impact / Total Improvement |
|---|---|:---:|:---:|:---:|:---:|
| **D=5, 10 Distractors** | Success Rate | **0% (FAILED)** | **100% (SOLVED)** | **100% (SOLVED)** | Rescued from complete failure |
| | Distractor Picks | 49.5 / 80 | 0.0 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.65s | 0.16s | 0.24s | 2.7× faster than unguided |
| **D=5, 25 Distractors** | Success Rate | **0% (FAILED)** | **100% (SOLVED)** | **100% (SOLVED)** | Rescued from complete failure |
| | Distractor Picks | 62.5 / 80 | 2.0 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.98s | 0.23s | 0.30s | 3.3× faster than unguided |
| **D=5, 50 Distractors** | Success Rate | **0% (FAILED)** | 50% | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 65.0 / 80 | 4.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.67s | 0.24s | 0.29s | 2.3× faster than unguided |
| **D=8, 25 Distractors** | Success Rate | **0% (FAILED)** | **0% (FAILED)** | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 57.0 / 80 | 24.0 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.99s | 0.53s | **0.32s** | **3.1× faster than unguided** |
| **D=8, 50 Distractors** | Success Rate | **0% (FAILED)** | **0% (FAILED)** | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 56.0 / 80 | 26.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.66s | 0.45s | **0.31s** | **2.1× faster than unguided** |
| **D=10, 25 Distractors** | Success Rate | **0% (FAILED)** | **0% (FAILED)** | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 50.5 / 80 | 23.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.93s | 0.51s | **0.34s** | **2.7× faster than unguided** |
| **D=10, 50 Distractors** | Success Rate | **0% (FAILED)** | **0% (FAILED)** | **100% (SOLVED)** | **+100% rescue from failure** |
| | Distractor Picks | 50.0 / 80 | 24.5 / 80 | **0.0 / 80** | **100% distractors eliminated** |
| | Wall Clock | 0.64s | 0.46s | **0.32s** | **2.0× faster than unguided** |

---

### 2.6 Key Empirical Findings

1. **Complete Distractor Elimination Across All Depths:** With the addition of Stage 0 premise pre-filtering and depth-discount tuning in Week 3, distractor picks dropped to **0.0 across all depths (D=5, 8, 10) and all distractor counts (10, 25, 50)**.
2. **Rescuing Deep High-Noise Problems:** In Week 2, D=8 and D=10 with 25–50 distractors failed (0% success) because high-confidence distractors saturated the belief buffer. Week 3 restores success rate to **100%** on these configurations while cutting wall-clock times to ~0.32s.
3. **Net Wall-Clock Acceleration:** PRISM search with Stage 0 runs **2.0× to 3.3× faster** than unguided search, confirming that pre-filtering candidate premises in Python avoids expensive MeTTa/Prolog backtracking.
4. **100% Mathematical Soundness:** On all solved chains, PRISM and unmodified PLN produce identical conclusions: STV `[0.60645, 0.16888]` and evidence stamp `['1', '2', '3', '4', '5']`.

---

## 3. How to Run the Benchmarks

### 1. Run FFI Latency Benchmarks
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
sh run.sh ../prism/benchmarks/metta/benchmark_pycall.metta
sh run.sh ../prism/benchmarks/metta/benchmark_uncached.metta
```

### 2. Run Synthetic Chain Parameter Sweeps
```bash
cd <prism-repo>

# Run unguided baseline sweep
python3 -m benchmarks.run_benchmark --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80

# Run PRISM-guided sweep (Week 3)
python3 -m benchmarks.run_benchmark --guided --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80 --output benchmarks/results/reference/baseline_guided_week3.json
```

### 3. Run Scaling and Cross-Domain Evaluation

```bash
cd <repo-root>
python3 -m benchmarks.evaluate_scaling_generalization \
  --output benchmarks/results/reference/week9_scaling_generalization.json
```

This records four increasing AtomSpace proxy sizes, Stage 0 pair-frontier
reduction, end-to-end search metrics, waste-growth exponents, and frozen-config
transfer across chain, diamond, tree, and semantic-gap domains. The random
baseline uses the recorded seeds 11, 23, 42, 67 and 89. Its goal-blind
structurally applicable premise pairs are shuffled and every selected action is
validated by real `PLN.Apply`; with beam width one, unused later candidates are
not evaluated.

The recorded repeated live Tier-2 check passed 3/3 assisted runs while the
same-budget unassisted search failed 3/3. The live model proposed three
different PLN-derivable waypoints (`H -> N`, `C -> M`, and `A -> C`); proposals
were never inserted as beliefs. Reproduce the optional provider-dependent run
with:

```bash
OPENROUTER_API_KEY=... \
python3 -m benchmarks.evaluate_gap_rescue --live --runs 3 \
  --output benchmarks/results/reference/week9_tier2_live_repeats.json
```

### 4. Run Progressive External-KG Evaluation

```bash
cd <repo-root>
python3 -m benchmarks.evaluate_external_kg_scaling \
  --output benchmarks/results/reference/week9_external_kg_scaling.json
```

This streams the three supplied MeTTa exports, maps only `isa` to PLN
`Inheritance`, deduplicates source edges, constructs held-out source-derived
transitive goals, and evaluates 100-, 1,000-, and 5,000-edge slices. Raw files
are never changed. Missing TVs use the explicit recorded default `(0.8, 0.9)`;
uniform source TVs are retained.
