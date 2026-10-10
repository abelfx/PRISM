# PRISM benchmarks: results and reproduction

This guide groups the recorded evaluations by experiment. PRISM decides which candidate inferences to explore; PLN in PeTTa's `lib_pln.metta` determines accepted conclusions, truth values and evidence stamps. The figures below are historical measurements on specified tasks, **not** one fresh run or a universal speedup claim. The main branch contains the PLN integration; the learned Tier 1 v2 evaluation is documented separately below with its required branch.

## Comparisons and metrics

| Experiment | Baseline | PRISM configuration | Main measurements |
|---|---|---|---|
| MeTTa derivation-loop sweeps | Goal-empty, confidence-prioritized `PLN.Derive` | Goal-aware Tier 1 v1, with or without Stage 0 | Fixed-budget success, wasted selections, distractor picks, elapsed time |
| Explicit proof agenda | Unguided FIFO/uniform-cost-style search | Heuristic best-first, with or without Stage 0 | Expansions, generated nodes, bounded success; **not the same baseline** as the MeTTa loop |
| KG similarity pilot | Goal-empty `PLN.Derive` | Stage 0 + Tier 1 + best-first/beam, applying real `PLN.Apply` | Held-out two-hop queries on the same source slice |
| Controlled scaling/transfer | Seeded-random applicable-premise ordering | Frozen PRISM configuration; accepted steps checked by PLN | Candidate-pair narrowing and fixed-budget success; **not native PLN** |
| Strategic and bidirectional search | Forward-only/unassisted explicit agenda | Optional PLN-established subgoals or two-frontier search | Budgeted completion, expansion allocation, provider overhead |

Do not pool speedups across these rows. Some early explicit-agenda numbers preceded the real `PLN.Apply` bridge: they measure a search-control algorithm, **not** independently verified PLN truth-value semantics. The later proof-replay audit is reported separately.

## PLN hook and MeTTa derivation-loop benchmarks

The chain sweeps below used synthetic `Inheritance` tasks with depths `D = 5, 8, 10`, distractor counts `N = 0, 10, 25, 50`, an 80-step budget, task queue 30 and belief queue 100. The archived unguided and Tier 1 sweeps used two repeats per configuration. Their full success, waste, step, distractor, time and notes columns are retained.

### PeTTa/Python bridge latency and throughput

| Metric | Target / Gate | Measured (Cached) | Measured (Uncached) | Status |
|---|:---:|:---:|:---:|:---:|
| **Mean Latency per Call** | $< 1.0\text{ms}$ (ideal $< 0.1\text{ms}$) | **0.0124 ms** (12 µs) | **0.0214 ms** (21 µs) | **PASSED** (47× to 80× faster than gate) |
| **Call Throughput** | $> 1,000$ calls/sec | **80,893** calls/sec | **46,825** calls/sec | **PASSED** |
| **Total Time (1,000 calls)** | $< 1.0\text{s}$ | **0.0124 s** | **0.0214 s** | **PASSED** |
| **Cache Hit Ratio** | — | **99.9%** (999/1000) | **0.0%** (1000 misses) | **VERIFIED** |

---

### Full unguided baseline sweep (`baseline_unguided.json`)

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

### Tier 1 v1 guided sweep (`baseline_guided_v1.json`)

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

### Tier 1 v1 + Stage 0 premise-filtering sweep

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

### Full three-way comparison

| Problem Configuration | Metric | Unguided Baseline | Tier 1 v1 | Tier 1 v1 + Stage 0 | Impact / Total Improvement |
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

Tier 1 alone made a material difference: at D5/N25 it changed success from 0% to 100%, cut distractor picks from 62.5 to 2.0 and reduced recorded waste by 38.75 percentage points. Adding Stage 0 is associated with zero distractor picks and 100% success on the reported high-noise D8/D10 cases. It did **not** solve clean or lightly distracted D8/D10 cases; on D5 it often increased time relative to Tier 1 alone. The runner's `Avg steps = 80` describes its full derivation budget, **not time to first proof**. Two repeats per cell are insufficient for a stable success or latency estimate.

**Provenance:** [Unguided](results/reference/baseline_unguided.json) and [Tier 1](results/reference/baseline_guided_v1.json) each have all 12 configurations and 24 runs. The committed [combined-filter JSON](results/reference/baseline_guided_week3.json) has **only D5/N10, one run**; the other filtered-sweep cells come from the milestone table, not a matching full-sweep JSON file. A local rerun on 2026-10-10 (`artifacts/evaluator-runs/chain-*.json`, not committed) did **not** reproduce the reported high-noise rescues: guided D8/N25 and D10/N25 both returned 0% success. The current `./run.sh bench-chain` path and archived filtered sweep must not be presented as equivalent without confirming Stage 0 activation and rerunning the same configuration.

## Branching proofs: diamond and two-branch tree

These are separate 80-step MeTTa-loop sweeps with two repeats per configuration. `U/G` denotes unguided/guided. Guided diamond search selected the shortcut in **12/12 reported runs**, although some unguided runs also did.

| Diamond short/long | N | Success U/G | Distractor picks U/G | Seconds U/G |
|---|---:|---|---:|---:|
| 2/5 | 0 | 100% / 100% | 0.0 / 0.0 | 1.19 / 0.42 |
| 2/5 | 10 | 100% / 100% | 36.0 / 0.0 | 0.89 / 0.42 |
| 2/5 | 25 | 100% / 100% | 59.0 / 37.0 | 1.04 / 1.11 |
| 3/6 | 0 | 100% / 100% | 0.0 / 0.0 | 1.48 / 1.46 |
| 3/6 | 10 | 100% / 100% | 36.5 / 14.5 | 0.88 / 1.11 |
| 3/6 | 25 | 100% / 100% | 54.0 / 34.5 | 1.06 / 1.12 |

| Tree left/right | N | Success U/G | Distractor picks U/G | Seconds U/G |
|---|---:|---|---:|---:|
| 2/2 | 0 | 100% / 100% | 0.0 / 0.0 | 0.49 / 0.20 |
| 2/2 | 10 | 100% / 100% | 52.0 / 0.0 | 0.68 / 0.22 |
| 2/2 | 25 | 0% / 100% | 64.5 / 0.0 | 1.05 / 0.29 |
| 3/3 | 0 | 0% / 100% | 0.0 / 0.0 | 1.01 / 0.24 |
| 3/3 | 10 | 0% / 100% | 44.0 / 0.0 | 0.73 / 0.28 |
| 3/3 | 25 | 0% / 0% | 61.0 / 27.0 | 1.04 / 0.75 |

Guided diamonds with 25 distractors were slower, and both variants failed the largest tree at N25. A smaller elapsed time when a baseline fails is **not** a time-to-proof speedup. The committed guided [diamond](results/reference/baseline_diamond_guided.json) and [tree](results/reference/baseline_tree_guided.json) JSON files each contain only **one clean configuration**; most cells above are milestone-only reports. The unguided [diamond](results/reference/baseline_diamond_unguided.json) and [tree](results/reference/baseline_tree_unguided.json) JSON files are also available.

## Explicit search and Stage 0 ablation

The original unfiltered agenda comparison used seed 42, budget 80, beam width 5 and minimum step cost 0.01. It **predated the real-PLN transition bridge**.

| Scenario | Success U/G | Expansions U/G | Nodes generated U/G | Seconds U/G |
|---|---|---:|---:|---:|
| Chain D4, N10 | 100% / 100% | 28 / 19 | 84 / 60 | 0.0148 / 0.0113 |
| Diamond 3/7, N30 | 100% / 100% | 17 / 7 | 51 / 21 | 0.0270 / 0.0100 |
| Chain D6, N25 | 0% / 0% | 80 / 80 | — | — |
| Tree 3/3, N20 | 0% / 0% | 80 / 80 | — | — |

The later filtered-agenda record is a **different run**. It reported 48 raw candidates reduced to roughly 4–11 with Stage 0 on a noisy D6 chain. Do not combine the earlier 80-step failures with this run's 19-step unguided successes as though one isolated change caused the difference.

| Scenario | Unguided expansions | Filtered guided expansions | Reduction | Guided seconds |
|---|---:|---:|---:|---:|
| Chain D4, N10 | 9 | 7 | 22.2% | 0.0092 |
| Chain D6, N25 | 19 | 16 | 15.8% | 0.0293 |
| Diamond 3/7, N30 | 12 | 6 | 50.0% | 0.0125 |
| Tree 3/3, N20 | 19 | 16 | 15.8% | 0.0281 |

For **current** PLN-backed comparisons use `./run.sh bench-search` and `./run.sh bench-ablation`. The four-way ablation distinguishes unguided, Stage 0 only, Tier 1 only and both. Candidate-pool reduction, expansions, success and wall time are different metrics.

## Real knowledge-graph pilot

The supplied `kgadexp.metta` contains 161 unique nodes, 3,930 unique similarity edges and 4,350 duplicate edge occurrences in its raw export. The benchmark deduplicates and maps links to PLN `Similarity`, materializes both directions, assigns the explicit test STV `(stv 0.9 0.8)` and holds out five two-hop goals. The **selected** slice is five sources × ten targets = 50 undirected edges / 100 PLN sentences; it is not the entire graph. Native PLN uses goal-empty `PLN.Derive`; PRISM uses best-first/beam search with real `PLN.Apply`. Budget: 40 steps, queue size 150, beam width 5, timeout 30 seconds.

| Result on five held-out queries | Native PLN | PRISM |
|---|---:|---:|
| Queries answered | 2/5 | 5/5 |
| Mean elapsed time per query, recalculated from [per-query JSON](results/reference/kgadexp_pilot_5x10.json) | 0.985 s | 0.454 s |
| Expanded steps per PRISM answer | — | 2 |

The two jointly answered queries had identical strength and confidence, though evidence stamps differed because the graph has multiple valid two-hop paths. The milestone narrative says **1.04 s versus 0.51 s** for this five-query run; those means do not match the saved per-query timings, so this table uses JSON-derived means. A separate [higher-budget run](results/reference/kgadexp_pilot_5x10_high_budget.json) used 100 steps, queues of 500 and three queries: native PLN solved **1/3** in **18.379 s/query** on average; PRISM solved **3/3** in **0.506 s/query**. The favorable topology and selected queries do not establish arbitrary-KG performance.

## Scaling, transfer and external-KG slices

The controlled scaling run fixed a depth-5 chain and 30-step budget. Random ordering used five seeds (`11, 23, 42, 67, 89`); selected actions were still checked by `PLN.Apply`. PRISM has **one recorded run per size**, not five. Stage 0 pair reduction compares a raw Cartesian-pair **proxy** with the filtered candidate count; it is not measured memory or elapsed-time reduction.

| Facts | Raw pairs → filtered | Pair reduction | Random success | PRISM success | Random mean wasted expansions / PRISM |
|---:|---:|---:|---:|---:|---:|
| 5 | 25 → 6 | 76.00% | 5/5 | 1/1 | 0 / 0 |
| 15 | 225 → 6 | 97.33% | 0/5 | 1/1 | 29 / 0 |
| 30 | 900 → 6 | 99.33% | 0/5 | 1/1 | 29 / 0 |
| 55 | 3,025 → 6 | 99.80% | 0/5 | 1/1 | 29 / 0 |

On a separate frozen-configuration, 20-step transfer test, PRISM solved controlled chain, diamond, tree and semantic-gap tasks (**4/4**); seeded random solved **0/20** across those families and five seeds. The recorded waste-growth exponents were **0.000 PRISM vs 1.416 random** on the four-point chain sweep, but failed random trials consume the full budget in this calculation. These are constructed families, not a domain-held-out learned-model test. [Scaling and transfer data](results/reference/week9_scaling_generalization.json).

Three external MeTTa exports were evaluated as **bounded slices** with 100, 1,000 and 5,000 unique edges each. The runner mapped only source `isa` to PLN `Inheritance`, selected one existing three-edge chain per slice and held out its transitive goal. Unweighted source edges received the recorded `(0.8, 0.9)` benchmark default. No claim is made about all source relations or full-source inference.

| Source | 100 edges: success / s | 1,000 edges: success / s | 5,000 edges: success / s |
|---|---:|---:|---:|
| `wordnet_stv_clean.metta` | yes / 0.112 | yes / 0.580 | yes / 10.753 |
| `output_prolog_ready.metta` | yes / 0.394 | yes / 3.942 | yes / 28.762 |
| `kg.metta` | yes / 0.690 | yes / 6.936 | yes / 37.512 |

All **9/9** selected goals took three expansions. At 5,000 edges the **25,000,000 raw-pair proxy** narrowed to six candidate pairs, yet wall time rose sharply with slice size. This shows bounded irrelevant-edge filtering, **not** constant-time scaling or million-edge in-engine evaluation. [External-slice data](results/reference/week9_external_kg_scaling.json).

## Strategic subgoals and bidirectional search

| Controlled semantic-gap case | Unassisted | Tier 2 assisted | Interpretation |
|---|---|---|---|
| Small latent bridge, 10 distractors | Success, 6 expansions | Success, 7 | PLN established the waypoint; no search advantage |
| Dead-end-heavy case, budget 8; deterministic proposal | Failed at 8 | Success at 7 | Fixed-budget success advantage |
| Same hard case, three live-provider repetitions | 0/3 | 3/3 at 6, 7, 6 expansions | Provider-dependent; assisted time 3.22–5.86 s |

The live provider proposed different waypoints; none was inserted as a true belief without PLN derivation. These runs show bounded completion, **not a latency gain**. [Live-run data](results/reference/week9_tier2_live_repeats.json).

### Run the Tier 2 OpenRouter evaluation on `main`

The offline `./run.sh bench-tier2` uses a deterministic mock and needs no API key. To test the actual OpenRouter call, set `OPENROUTER_API_KEY` in your shell and run the separate live command from `prism/`:

```bash
export OPENROUTER_API_KEY='YOUR_OPENROUTER_KEY'
./run.sh bench-tier2-live
```

Do not commit the key or paste it into a result file. The live command runs **three** provider-assisted trials (`--live --runs 3`); its current configured model is `nex-agi/nex-n2.5-mini:free`. It writes `artifacts/evaluator-runs/tier2-live.json` and `artifacts/evaluator-runs/tier2-live.log`, leaving the curated reference JSON untouched. `bench-all` intentionally excludes this provider-dependent run. Compare the assisted and unassisted success/expansion counts in the output, and report wall time separately because API latency can dominate.

Bidirectional search on chains with 20 distractors reported:

| Depth | Forward-only expansions / nodes / s | Bidirectional forward+backward expansions / nodes / s | Reduction in forward expansions | Reduction in **total** expansions |
|---:|---|---|---:|---:|
| 6 | 6 / 6 / 0.0913 | 2+3 / 7 / 0.0071 | 66.7% | 16.7% |
| 8 | 8 / 8 / 0.0340 | 3+4 / 9 / 0.0124 | 62.5% | 12.5% |
| 10 | 10 / 10 / 0.0605 | 4+5 / 11 / 0.0190 | 60.0% | 10.0% |
| 12 | 12 / 12 / 0.0853 | 5+6 / 13 / 0.0295 | 58.3% | 8.3% |

The 58–67% figures apply to **forward expansions only**. Total expansions fell much less and generated nodes **increased**. The connection is replayed by PLN; this is not evidence of a 58–67% reduction in total search space.

## Proof validity, fallback and test coverage

A recorded independent audit replayed **22/22 proof actions across 8/8 cases** through pinned `PLN.Apply`, with term, STV and evidence agreement on successful goals. Cases covered chain, diamond, confluent tree, strategic subgoal, bidirectional stitching and a 100-edge slice from each external source. **16/16 injected failure cases** followed their documented fallback or fail-closed path without unsupported beliefs. The recorded regression snapshot was **121/121 Python, 4/4 direct MeTTa and 7/7 pinned PLN rule tests**. This is tested-case soundness, not a proof over every PLN rule or workload. [Proof and fallback artifact](results/reference/week10_soundness_robustness.json).

## Learned Tier 1 v2: experimental branch

The v2 evaluator, training code, saved model and stress evaluator live on **`feat/leanred_tier1_v2`**, not on `main`. The commands below are for a **separate checkout of that branch**, with PeTTa/PLN available in the expected workspace layout. Do not run them from this main-branch checkout, and do not overwrite the branch's curated reference JSON.

```bash
cd <prism-v2-branch-checkout>
python3 -m benchmarks.evaluate_tier1_v2 \
  --traces artifacts/training/tier1_v2_traces.jsonl \
  --model artifacts/models/tier1_v2.npz \
  --output artifacts/evaluator-runs/tier1-v2.json

python3 -m benchmarks.evaluate_tier1_v2_stress \
  --traces artifacts/training/tier1_v2_traces.jsonl \
  --model artifacts/models/tier1_v2.npz \
  --output artifacts/evaluator-runs/tier1-v2-stress.json
```

The first command collects fresh PLN-backed chain, diamond and tree traces, trains the model, and compares it with v1 on held-out runs. Run it before the second command, which uses its traces and checkpoint to test unseen symbols, an unseen predicate, three supplied external-KG sources, adversarial frontiers and label noise. That stress run needs the external KG source files as well.

| Recorded v2 result on that branch | Outcome |
|---|---:|
| Candidate examples / held-out examples | 784 / 215 |
| Held-out template classification | 215/215 correct |
| Top-1 ranking on 43 eligible decisions | v1 100%; v2 100% (tie) |
| CPU score latency, median / p95 | 0.121 / 0.166 ms |
| Renamed-atom classification accuracy / positive recall | 58.14% / 35.25% |
| External-KG proof-path positive recall | 0/9 |
| Adversarial top-1 ranking | v1 0%; v2 0% |

The branch's recorded artifacts are `benchmarks/results/reference/week11_tier1_v2.json` and `benchmarks/results/reference/week11_tier1_v2_stress.json`. These results establish a working training/evaluation pipeline, **not a demonstrated improvement over v1**; v1 remains the runtime default. The stress artifact records `performance_boost_proven: false`.

## Reproduce on this checkout

Run from `prism/` with Python 3.12, SWI-Prolog, the sibling `PeTTa/repos/PLN` checkout and benchmark-specific source files. `./run.sh doctor` checks the main paths. New JSON and logs go to `artifacts/evaluator-runs/`; **do not overwrite `benchmarks/results/reference/`**.

```bash
./run.sh doctor
./run.sh test
./run.sh bench-ffi
./run.sh bench-chain
./run.sh bench-diamond
./run.sh bench-tree
./run.sh bench-search
./run.sh bench-ablation
./run.sh bench-bidirectional
./run.sh bench-tier2
./run.sh bench-kg
./run.sh bench-scaling
./run.sh bench-external-kg
./run.sh bench-soundness
```

`./run.sh bench-all` runs the complete **offline** set and can take many minutes. `./run.sh bench-tier2-live` is separate, requires `OPENROUTER_API_KEY`, and makes provider calls. `./run.sh help` explains every command. The external-KG command requires the three supplied source files beside `prism/`; the small-KG command requires `kgadexp.metta` there. If rerun results differ, preserve both outputs and report checkout revisions, source hashes, seeds, queue/beam settings and cold/warm timing conditions rather than replacing historical measurements.
