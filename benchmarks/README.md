# PRISM Benchmarks Suite

This directory contains the profiling, latency benchmarking, and search-efficiency measurement harnesses for PRISM (Programmable Reduction & Inference Search Manager).

---

## 1. Directory Structure

```
prism/benchmarks/
├── run_benchmark.py               # Main CLI benchmark driver & parameter sweep runner
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
└── results/                       # Empirical benchmark datasets
    ├── baseline_unguided.json     # Recorded unguided PLN baseline numbers
    └── baseline_guided_v1.json    # Recorded PRISM Tier 1 v1 guided numbers
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

### 2.2 Week 2: Unguided PLN vs PRISM-Guided (GATE-2.3 & GATE-2.4)

Benchmark runs across synthetic transitive chains ($D \in [5, 10]$) with varying distractor counts:

| Configuration | Metric | Unguided Baseline | PRISM Guided (v1) | Delta / Improvement |
|---|---|:---:|:---:|:---:|
| **D=5, 0 Distractors** | Success Rate | 100% | 100% | Parity |
| | Waste Ratio | 35.0% | 47.5% | — |
| | Wall Clock | 0.75s | 0.14s | **5.3× faster** |
| **D=5, 10 Distractors** | Success Rate | **0% (FAILED)** | **100% (SOLVED)** | **+100% success** |
| | Waste Ratio | 75.6% | 47.5% | **-28.1% waste** |
| | Distractor Picks | 49.5 / 80 steps | 0.0 / 80 steps | **100% eliminated** |
| | Wall Clock | 0.65s | 0.16s | **4.1× faster** |
| **D=5, 25 Distractors** | Success Rate | **0% (FAILED)** | **100% (SOLVED)** | **+100% success** |
| | Waste Ratio | 83.8% | 45.0% | **-38.8% waste (46.3% rel. reduction)** |
| | Distractor Picks | 62.5 / 80 steps | 2.0 / 80 steps | **96.8% eliminated** |
| | Wall Clock | 0.98s | 0.23s | **4.2× faster** |
| **D=5, 50 Distractors** | Success Rate | **0% (FAILED)** | **50% (SOLVED)** | **+50% success** |
| | Waste Ratio | 84.4% | 47.5% | **-36.9% waste** |
| | Distractor Picks | 65.0 / 80 steps | 4.5 / 80 steps | **93.1% eliminated** |
| | Wall Clock | 0.67s | 0.24s | **2.8× faster** |
| **D=8, 10 Distractors** | Distractor Picks | 37.5 / 80 steps | 0.5 / 80 steps | **98.7% eliminated** |
| | Wall Clock | 0.70s | 0.43s | **1.6× faster** |
| **D=10, 10 Distractors** | Distractor Picks | 34.0 / 80 steps | 0.5 / 80 steps | **98.5% eliminated** |
| | Wall Clock | 0.73s | 0.29s | **2.5× faster** |

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
cd /home/abel/Desktop/icog_labs/pln

# Run unguided baseline sweep
python3 -m prism.benchmarks.run_benchmark --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80

# Run PRISM-guided sweep
python3 -m prism.benchmarks.run_benchmark --guided --depths 5 8 10 --distractors 0 10 25 50 --repeats 2 --max-steps 80
```
