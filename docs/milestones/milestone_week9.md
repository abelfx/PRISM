# Milestone Week 9 - Scaling Tests & Cross-Domain Generalization

**Status:** Complete  
**Scope source:** PRISM Proposal rev. 5, sections 7.1-7.3 and 8; Implementation Specification, Week 9  
**Primary objective:** Demonstrate that PRISM's search-control gains survive increasing AtomSpace size and transfer across structurally different reasoning domains under fixed, reproducible budgets.

---

## 1. Why Week 9 Exists

Weeks 1-8 established the PLN integration, Stage 0 filtering, Tier 1 scoring,
best-first and bidirectional search, and sound Tier 2 waypoint guidance. Those
results were mainly controlled-domain demonstrations. Week 9 moves from
feature completion to scale and generalization evidence.

The papers require:

- scaling the same domains over increasing AtomSpace sizes;
- measuring whether wasted search grows sub-linearly;
- measuring Stage 0 frontier reduction independently of scorer speed;
- end-to-end wall time, including all enabled guidance overhead;
- fixed-budget proof success and proof-tree expansion reduction;
- applying one frozen heuristic configuration across structurally different
  domains and beating a deterministic random/static baseline;
- progressive evaluation on normalized external knowledge-graph data.

This milestone does **not** train Tier 1 v2 (Week 11) or claim million-edge
scalability. It establishes the reproducible scaling harness and measures the
range the current implementation can honestly support.

---

## 2. Evaluation Domains

1. **Linear transitive chains** - known optimal proof path, scalable irrelevant
   fact population.
2. **Diamond/multipath DAGs** - competing short and long proofs.
3. **Confluent tree DAGs** - two structurally distinct proof segments meeting
   at a junction.
4. **Latent semantic-gap graphs** - high-confidence, goal-overlapping decoys;
   Tier 2 must name a PLN-derivable waypoint rather than inject an axiom.
5. **External MeTTa KGs** - progressive, normalized `isa` slices from the
   clean WordNet export, duplicate-heavy Prolog-ready export, and large noisy
   KG, with stable evidence IDs, source hashes, and exact PLN execution.

The frozen Tier 1 v1 configuration is applied unchanged across the first four
families. This is a transfer test, not training/evaluation leakage.

---

## 3. Baselines

- **Unguided/static search:** `guided=False`, no goal-aware scoring.
- **Seeded-random ordering:** goal-blind, structurally applicable premise pairs
  shuffled by seed and validated by real `PLN.Apply`, with the same beam width
  and step budget.
- **Tier 1 + Stage 0:** frozen symbolic scorer and indexed premise filtering.
- **Full PRISM:** Tier 1 + Stage 0 plus Tier 2 only on a declared stall case.

Every baseline uses the same source facts, PLN rules, STVs, evidence policy,
beam width and step budget for a given comparison.

---

## 4. Metrics

- Initial facts / AtomSpace proxy size.
- Raw premise-pair frontier versus Stage 0 filtered pair frontier.
- Search steps, generated nodes, visited states and proof length.
- Wasted expansion count and waste ratio.
- End-to-end wall-clock time.
- Success rate under a fixed step budget.
- Scaling exponent of wasted expansions versus fact count.
- Cross-domain success rate versus seeded-random ordering.
- Returned goal STV and evidence stamp where applicable.
- PRISM, PeTTa and PLN revisions plus source-data SHA-256 for external KG runs.

Timing is reported but never used as a byte-for-byte reproducibility check.
Semantic outcomes and counts are the reproducible gate values.

---

## 5. Implementation Plan

### 5.1 Scaling harness

- [x] Add `benchmarks/evaluate_scaling_generalization.py`.
- [x] Add deterministic seeded-random candidate ordering.
- [x] Add proof-path waste accounting.
- [x] Add Stage 0 raw/filtered premise-pair accounting.
- [x] Add log-log wasted-expansion scaling exponent calculation.
- [x] Run the committed default sweep and save JSON under
  `benchmarks/results/reference/`.

### 5.2 Cross-domain transfer

- [x] Define chain, diamond, tree and semantic-gap cases behind one runner.
- [x] Keep one frozen `SearchConfig` across domain families.
- [x] Add real external-KG transitive proofs as a fifth transfer family.
- [x] Record five deterministic seeds for the random baseline.

### 5.3 Progressive external-KG scale

- [x] Preserve the existing reproducible KGAD loader and pilot.
- [x] Add slice levels (small, medium, full feasible subset) with explicit
  memory/time ceilings.
- [x] Report Stage 0 frontier reduction before running expensive inference.
- [x] Stop and report the measured feasibility boundary rather than
  extrapolating to million-edge performance.

### 5.4 Full-pipeline validation

- [x] Strengthen the Tier 2 semantic-gap gate: unassisted A* fails at the
  shared eight-step budget; live Tier 2 succeeds without axiom injection.
- [x] Repeat the live-provider result over multiple runs separately from the
  deterministic CI gate.

---

## 6. Acceptance Gates

| Gate | Criterion | Target | Status |
|---|---|---|:---:|
| **GATE-9.1** | Scaling harness | At least four increasing sizes with fixed budgets and complete metrics | **PASS** |
| **GATE-9.2** | Stage 0 scaling | Filtered premise-pair frontier grows more slowly than the raw Cartesian frontier and is reduced by at least 40% at the largest size | **PASS (99.80%)** |
| **GATE-9.3** | Waste growth | Guided wasted-expansion exponent is below 1.0 and below the unguided/random baseline | **PASS (0.000 vs 1.416)** |
| **GATE-9.4** | Cross-domain transfer | Frozen PRISM configuration beats seeded-random success across at least three structurally different domains | **PASS (4/4 vs 0/20 over five seeds)** |
| **GATE-9.5** | Full-pipeline stall rescue | Same budget: unassisted fails, Tier 2 succeeds, every accepted step is PLN-derived | **PASS (3/3 live; unassisted 0/3)** |
| **GATE-9.6** | External KG progression | Reproducible multi-size external-KG results with revisions, source hashes and an explicit tested boundary | **PASS (9/9 at up to 5,000 edges)** |

---

## 7. Current Verified Result

### 7.1 Scaling and cross-domain run

The default committed sweep uses a depth-5 chain, 30 search steps, fact counts
5, 15, 30 and 55, and random seeds 11, 23, 42, 67 and 89.

| Facts | Stage 0 reduction | Random success | PRISM success | Random waste | PRISM waste |
|---:|---:|:---:|:---:|---:|---:|
| 5 | 76.00% | 5/5 | Yes | 0.0 mean | 0 |
| 15 | 97.33% | 0/5 | Yes | 29.0 mean | 0 |
| 30 | 99.33% | 0/5 | Yes | 29.0 mean | 0 |
| 55 | 99.80% | 0/5 | Yes | 29.0 mean | 0 |

The random curve is budget-censored after 30 steps at the three larger sizes;
its failures are counted as a full budget of waste, not as zero. PRISM's
measured wasted-expansion exponent is 0.000 across this range.

With one frozen configuration and a 20-step cross-domain budget, PRISM solved
chain, diamond, tree and semantic-gap cases (4/4). Seeded-random ordering solved
0/20 trials across five seeds. Every random seed produced a waste-growth
exponent of 1.415894; PRISM remained at 0.000000. The exact machine-readable result is
`benchmarks/results/reference/week9_scaling_generalization.json`.

### 7.2 Tier 2 bounded rescue

The strengthened semantic-gap benchmark uses five high-confidence,
goal-overlapping dead-end chains and an eight-step budget for both systems.

- Unassisted A*: failed at 8/8 steps.
- Deterministic Tier 2: passed in 7 steps using the PLN-derived `C -> M`
  waypoint.
- Repeated live OpenRouter Tier 2: passed 3/3 runs in 6, 7 and 6 steps.
- The three live proposals were independently useful PLN-derivable waypoints:
  `H -> N`, `C -> M`, and `A -> C`.
- Unassisted A* failed 3/3 times at the same eight-step limit.
- No LLM output was inserted as a belief.

This is evidence of repeatable bounded-search success improvement. It is not a
latency win: the assisted live runs took 3.22-5.86 seconds and the provider call
dominates that wall time. Exact proposals, outcomes, revisions and timing are
stored in `benchmarks/results/reference/week9_tier2_live_repeats.json`.

### 7.3 External-KG progression

The runner streams and deduplicates the three supplied files without modifying
or evaluating them. Only `isa` is mapped to PLN `Inheritance`; unrelated
relations are preserved in the source audit but are not assigned invented PLN
semantics. Each slice contains a real three-edge source chain, holds out its
transitive closure as the goal, and fills the remaining capacity with genuine
source edges.

- Sources: `wordnet_stv_clean.metta`, `output_prolog_ready.metta`, `kg.metta`.
- Slice sizes: 100, 1,000 and 5,000 unique source edges.
- Outcome: PRISM passed all 9 runs in 3 expansions with zero measured waste.
- At 5,000 edges, Stage 0 reduced the raw 25,000,000 premise-pair proxy to 6
  pairs before PLN calls (reported reduction rounds to 100.000%).
- The two WordNet exports retain their uniform `(0.8, 0.9)` source TV. The
  unweighted KG uses the same explicitly recorded benchmark default.
- The largest successful tested boundary is 5,000 edges per source. This is
  not a claim that 5,000 is the failure boundary or that the full source was
  loaded into the PLN search loop.

These slices test scaling under controlled irrelevant-edge growth. They do not
measure a random distribution of arbitrary source queries. The required
five-seed baseline is complete for the four controlled cross-domain families;
it is not presented as an arbitrary-query external-KG baseline.

---

## 8. Reproduction

From the repository root:

```bash
python3 -m benchmarks.evaluate_scaling_generalization \
  --output benchmarks/results/reference/week9_scaling_generalization.json

python3 -m benchmarks.evaluate_gap_rescue

python3 -m benchmarks.evaluate_external_kg_scaling \
  --output benchmarks/results/reference/week9_external_kg_scaling.json
```

Live Tier 2 is optional and must never be required by CI:

```bash
OPENROUTER_API_KEY=... \
python3 -m benchmarks.evaluate_gap_rescue --live --runs 3 \
  --output benchmarks/results/reference/week9_tier2_live_repeats.json
```

---

## 9. Honest Interpretation Rule

Week 9 passes only on measured results. A bounded or failed run is still useful
if the runner records the exact size, budget and failure mode. Do not call a
curve sub-linear from two points, do not treat timeout as zero waste, and do not
generalize KGAD's dense `Similarity` topology to all ConceptNet relations.
