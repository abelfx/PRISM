# PRISM Benchmarks Suite

This directory contains the profiling, latency benchmarking, and search-efficiency measurement harnesses for PRISM (Programmable Reduction & Inference Search Manager).

---

## 1. Directory Contents

| File | Purpose | Language |
|---|---|:---:|
| `benchmark_pycall.metta` | Measures cached round-trip FFI latency across 1,000 derivation iterations via PeTTa's Janus bridge | MeTTa |
| `benchmark_uncached.metta` | Measures worst-case uncached FFI round-trip latency across 1,000 distinct terms (100% cache misses) | MeTTa |
| `pycall_bench.py` | Python-side profiling helper providing timing routines, argument inspection, and failure testing | Python |
| *(Upcoming Week 2)* `transitive_chain.py` | Synthetic transitive chain generator ($D \in [5, 20]$) with controllable distractor branching factors | Python |
| *(Upcoming Week 2)* `metrics.py` | Metrics collector tracking search steps, node expansion, waste ratio, and wall-clock times | Python |

---

## 2. Empirical Results (Week 1 / GATE-1.1)

The Python-MeTTa FFI performance was benchmarked directly on the host machine using PeTTa's SWI-Prolog Janus bridge over 1,000 iterations:

| Metric | Target / Gate | Measured (Cached) | Measured (Uncached) | Status |
|---|:---:|:---:|:---:|:---:|
| **Mean Latency per Call** | $< 1.0\text{ms}$ (ideal $< 0.1\text{ms}$) | **0.0150 ms** (15 µs) | **0.0214 ms** (21 µs) | **PASSED** (47× to 66× faster than gate) |
| **Call Throughput** | $> 1,000$ calls/sec | **66,731** calls/sec | **46,825** calls/sec | **PASSED** |
| **Total Time (1,000 calls)** | $< 1.0\text{s}$ | **0.0149 s** | **0.0214 s** | **PASSED** |
| **Cache Hit Ratio** | — | **99.9%** (999/1000) | **0.0%** (1000 misses) | **VERIFIED** |

### Key Takeaways
1. **Sub-Millisecond Verification:** The hypothesis that FFI calls between MeTTa and Python would introduce prohibitive latency is conclusively disproven. Even with 100% cache misses, a full Python call round-trip takes only **21 microseconds**.
2. **Memoization Impact:** In derivations where the same sentence is re-evaluated, `ScoreCache` resolves queries in **15 microseconds**, bypassing re-tokenization and scoring overhead.

---

## 3. How to Run the Benchmarks

All benchmarks are invoked from the `PeTTa/` directory using `run.sh`:

### 1. Run the Cached FFI Benchmark
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
sh run.sh ../prism/benchmarks/benchmark_pycall.metta
```
**Expected Output:**
```
(BENCHMARK_RESULTS: (iterations: 1000) (total_seconds: 0.0149...) (avg_latency_ms: 0.0149...) (throughput_calls_per_sec: 66731...))
(CACHE_STATS: (dict py 1 size 999 hits 1 misses 99.90% hit_ratio))
(EXCEPTION_HANDLING: 0.15)
```

### 2. Run the Uncached FFI Benchmark
```bash
cd /home/abel/Desktop/icog_labs/pln/PeTTa
sh run.sh ../prism/benchmarks/benchmark_uncached.metta
```
**Expected Output:**
```
(UNCACHED_BENCHMARK_RESULTS: (iterations: 1000) (total_seconds: 0.0213...) (avg_latency_ms: 0.0213...) (throughput_calls_per_sec: 46824...))
(UNCACHED_CACHE_STATS: (dict py 1000 size 0 hits 1000 misses 0.00% hit_ratio))
```

---

## 4. Upcoming Week 2 Benchmark Specifications

In Week 2, this directory will be expanded to host:
- **Synthetic Transitive Chains (`transitive_chain.py`):** Generates clean chains of form $A \to B \to C \to \dots \to Z$ at depths $D \in [5, 20]$ with optimal proof paths known a priori, parameterized by distractor facts to test branching resistance.
- **Waste Ratio Metric:**
  $$\text{Waste Ratio} = 1.0 - \frac{\text{Rules on Proof Path}}{\text{Total Rules Fired}}$$
  Comparing unguided PLN vs. PRISM-guided search to quantify search pruning efficiency.
