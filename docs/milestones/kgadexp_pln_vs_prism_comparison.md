# KGAD Real-KG Pilot: Previous PLN vs PRISM

**Evaluation date:** 22 September 2026  
**Dataset:** `kgadexp.metta`  
**Purpose:** Evaluate whether PRISM improves resource-bounded PLN search on a small, non-synthetic knowledge graph while preserving PLN truth-value calculations and evidence tracking.

---

## 1. Executive Summary

This experiment compared the previous unguided PLN search strategy with the current PRISM search manager on a normalized slice of `kgadexp.metta`.

The important architectural constraint was preserved:

- Previous PLN used the real `PLN.Derive` implementation in `PeTTa/repos/PLN/lib_pln.metta`.
- PRISM managed the search frontier in Python, but every inference transition was computed by the real `PLN.Apply` primitive in `lib_pln.metta`.
- PRISM did not calculate truth values independently.
- No synthetic facts or LLM-proposed axioms were inserted.

On the main 100-sentence pilot:

- PRISM solved **5 out of 5** held-out queries.
- Resource-bounded unguided PLN solved **2 out of 5** queries.
- PRISM took an average of approximately **0.51 seconds per query**.
- Unguided PLN took an average of approximately **1.04 seconds per query**.
- Whenever both systems solved a query, the returned PLN strength and confidence matched exactly.
- The systems sometimes selected different evidence paths because the graph contains many equivalent two-hop proofs.

This is evidence that PRISM's goal-aware search control can improve success and runtime under a fixed resource budget. It is not yet evidence of general performance on all ConceptNet relations or million-edge AtomSpaces.

---

## 2. Source Dataset Audit

The supplied file was inspected before any inference experiment.

### 2.1 Original structure

The source uses an adjacency-list-like representation:

```metta
(ants
  ((similarityLink abamectin ants)
   (similarityLink acetamiprid ants)
   ...))
```

This is MeTTa-shaped data, but it is not directly a PLN knowledge base. PLN expects beliefs in the following general form:

```metta
(Sentence
  ((Similarity abamectin ants) (stv 0.9 0.8))
  (1))
```

### 2.2 Dataset inventory

| Property | Observed value |
|---|---:|
| File size | Approximately 305 KB |
| Top-level adjacency entries | 161 |
| Raw `similarityLink` occurrences | 8,280 |
| Unique edges | 3,930 |
| Duplicate occurrences | 4,350 |
| Unique nodes | 161 |
| Connected components, treated as undirected | 1 |
| Self-loops | 0 |
| Reciprocal directed edges in the original export | 0 |
| Parenthesis balance | -1 |

The parenthesis imbalance comes from one extra closing parenthesis on line 131. Running the original file directly through PeTTa therefore produces a syntax error.

### 2.3 Graph shape

After deduplication, the graph is effectively a dense bipartite relation:

- 30 pesticide/chemical-like source nodes.
- 131 target/concept nodes.
- 3,930 unique source-target edges, equal to `30 × 131`.

Every selected source is linked to every selected target. This makes the dataset suitable for an initial two-hop similarity-search pilot, but it is unusually dense and contains many equivalent proof paths.

---

## 3. Dataset Normalization

The original file was left unchanged. The benchmark loader reads it as source data and performs the following transformations in memory.

### 3.1 Deduplication

All repeated `(similarityLink A B)` occurrences are collapsed into one unique source edge. This reduced the source from 8,280 edge occurrences to 3,930 unique edges.

### 3.2 PLN relation mapping

For this pilot only, the source relation `similarityLink` was mapped to PLN `Similarity`.

This mapping follows the explicit relation name in the source. It is not a general mapping policy for ConceptNet. A future ConceptNet import must map each relation independently rather than treating every relation as similarity.

### 3.3 Symmetric materialization

PLN `Similarity` is semantically symmetric. Both orientations were materialized:

```metta
(Sentence ((Similarity A B) (stv 0.9 0.8)) (evidence-id))
(Sentence ((Similarity B A) (stv 0.9 0.8)) (evidence-id))
```

The two orientations share the same evidence ID because they represent the same source assertion rather than two independent observations.

This is important for evidence safety: PLN must not combine the forward and reverse representation of the same edge as independent evidence.

### 3.4 Edge truth values

The source file does not contain weights, probabilities, provenance confidence or PLN truth values. The pilot therefore used configurable placeholder values:

```text
strength   = 0.9
confidence = 0.8
```

These values were applied consistently to both systems. They allow comparison of search behavior and PLN truth-value agreement, but they should not be interpreted as calibrated domain truth.

### 3.5 Concept priors

PLN's transitive similarity formula requires base concept STVs. For each selected slice, every included concept received:

```text
strength   = 1 / number_of_concepts_in_slice
confidence = 0.9
```

Both baseline PLN and PRISM received the same concept priors.

### 3.6 Evidence IDs

Every unique undirected source edge received one deterministic evidence ID. The inferred conclusion's evidence stamp was therefore traceable to the two source edges used in its proof.

---

## 4. Query Construction

The source graph contains pesticide-to-target similarity edges, but no direct pesticide-to-pesticide edges.

Held-out goals were constructed between pairs of source nodes. For example:

```metta
(Similarity abamectin acetamiprid)
```

Such a goal can be derived through any shared target:

```text
Similarity(abamectin, ants)
Similarity(ants, acetamiprid)
--------------------------------
Similarity(abamectin, acetamiprid)
```

The final goal edge was not present as an input belief. Each answer therefore required a real two-premise application of PLN's transitive similarity rule.

Because the graph is dense, each source pair has multiple valid shared targets. Consequently, two sound searches may return the same STV through different evidence stamps.

---

## 5. Systems Compared

### 5.1 Previous PLN baseline

The baseline used the existing `PLN.Derive` implementation from `lib_pln.metta`.

It was deliberately run with an empty goal:

```metta
(PLN.Derive $kb $kb 1 $maxsteps $taskqueuesize $beliefqueuesize ())
```

Passing `()` as the goal is important because it disables PRISM's goal-aware ranking and Stage 0 premise filtering. Candidate selection therefore falls back to the previous confidence-based PLN behavior.

The baseline still used all authoritative PLN components:

- `|-` inference rules.
- `Truth_transitiveSimilarity`.
- evidence-stamp disjointness.
- confidence-based task selection.
- bounded task and belief queues.

### 5.2 PRISM

PRISM used:

- Python-managed best-first/beam frontier.
- Stage 0 goal/candidate concept filtering.
- Tier 1 symbolic goal relevance.
- closed-state tracking.
- live, persistent PeTTa session.
- real `PLN.Apply` for every accepted inference transition.

PRISM did not use a Python truth-value implementation. For each candidate pair, `PLN.Apply` invoked the rules and truth-value formulas in `lib_pln.metta` and returned the resulting `Sentence`, STV and evidence stamp.

Tier 2 and bidirectional search were not needed for these two-hop pilot queries and were not part of this comparison.

---

## 6. Main Experiment Configuration

The main comparison used a deterministic slice selected from the densest part of the source graph.

| Parameter | Value |
|---|---:|
| Selected source nodes | 5 |
| Selected target nodes | 10 |
| Unique undirected source edges | 50 |
| Materialized PLN sentences | 100 |
| Held-out queries | 5 |
| Maximum search steps | 40 |
| Baseline task queue size | 150 |
| Baseline belief queue size | 150 |
| PRISM beam width | 5 |
| Edge STV | `(stv 0.9 0.8)` |
| Per-query timeout | 30 seconds |

The exact result file is:

```text
benchmarks/results/reference/kgadexp_pilot_5x10.json
```

---

## 7. Main Experiment Results

### 7.1 Aggregate results

| Metric | Unguided PLN | PRISM |
|---|---:|---:|
| Queries solved | 2 / 5 | 5 / 5 |
| Success rate | 40% | 100% |
| Mean wall time per query | 1.04 s | 0.51 s |
| Mean relative wall time | 2.06× PRISM time | 1.00× |
| Returned invalid conclusions | 0 | 0 |
| Synthetic axioms inserted | 0 | 0 |

PRISM improved success by 60 percentage points under the fixed resource budget and took approximately half the mean wall-clock time.

### 7.2 Per-query outcomes

| Goal | Unguided PLN | PRISM | STV comparison when both solved |
|---|---:|---:|---|
| `Similarity(abamectin, acetamiprid)` | Pass | Pass | Exact strength/confidence match |
| `Similarity(abamectin, alachlor)` | Fail | Pass | Baseline returned no answer |
| `Similarity(abamectin, aldicarb)` | Fail | Pass | Baseline returned no answer |
| `Similarity(abamectin, aldrin)` | Fail | Pass | Baseline returned no answer |
| `Similarity(acetamiprid, alachlor)` | Pass | Pass | Exact strength/confidence match |

PRISM solved each goal in two expanded search steps and generated two search-state nodes per query.

### 7.3 Truth-value agreement

For every query solved by both systems, strength and confidence were numerically identical.

An observed conclusion STV was:

```text
(stv 0.8143959791953331 0.6336000000000002)
```

This agreement is expected because both systems use the same `Truth_transitiveSimilarity` implementation in `lib_pln.metta`. PRISM changes which legal candidate is attempted first; it does not change PLN truth arithmetic.

### 7.4 Evidence-path differences

On the main experiment, both overlapping answers had equal STVs but different evidence stamps.

For example, the baseline could prove a goal through one shared target while PRISM proved it through another. Because the graph is complete bipartite and all relevant edge STVs are equal, these are equivalent legal proofs with equal truth values.

Therefore:

- Different evidence IDs do not automatically indicate a soundness error.
- Each evidence stamp must correspond to a valid independent source-edge pair.
- Exact STV agreement is expected for equal-weight alternative paths.
- Exact evidence equality should only be required when a benchmark has one unique proof path.

---

## 8. Higher-Budget Baseline Stress Test

A second run increased baseline resources substantially.

| Parameter | Value |
|---|---:|
| PLN sentences | 100 |
| Queries | 3 |
| Maximum steps | 100 |
| Task queue size | 500 |
| Belief queue size | 500 |
| PRISM beam width | 5 |

The exact result file is:

```text
benchmarks/results/reference/kgadexp_pilot_5x10_high_budget.json
```

### 8.1 Results

| Metric | Unguided PLN | PRISM |
|---|---:|---:|
| Queries solved | 1 / 3 | 3 / 3 |
| Success rate | 33.3% | 100% |
| Mean wall time per query | 18.38 s | 0.51 s |

Increasing the unguided queue and step budget did not reliably recover the goals. Instead, it allowed many irrelevant or redundant derivations to remain active, increasing runtime substantially.

On the one query solved by both systems:

- Strength matched exactly.
- Confidence matched exactly.
- Evidence stamp matched exactly.

This run demonstrates the issue PRISM targets: giving unguided PLN more resources does not necessarily improve useful search proportionally because the candidate space grows faster than the goal-directed proof path.

---

## 9. Interpretation

### 9.1 What the experiment supports

The pilot supports the following claims:

1. **PRISM can operate on normalized external KG data.**
   The experiment was not generated from the synthetic chain, tree or diamond domain generators.

2. **PRISM remains grounded in real PLN.**
   All conclusions and STVs came from `PLN.Apply` in `lib_pln.metta`.

3. **Goal-aware control improves bounded search success.**
   PRISM solved all five held-out goals while confidence-driven PLN solved two under the same general problem and bounded-resource setting.

4. **PRISM can reduce wall-clock time.**
   On the main pilot, mean query time was approximately halved.

5. **The improvement is search-control improvement rather than altered logic.**
   Overlapping answers had exactly matching PLN strengths and confidences.

6. **Larger unguided queues can worsen practical behavior.**
   The higher-budget baseline spent approximately 18 seconds per query and still missed two of three goals.

### 9.2 Why PRISM performed better

The graph contains many high-confidence beliefs with equal or similar priority. Confidence alone gives baseline PLN little information about which edge pair is relevant to the requested source-source goal.

PRISM uses the goal concepts to select source-adjacent tasks and filters candidate premises to those sharing concepts with the task or goal. This drastically reduces the number of candidate combinations sent to PLN.

The logical proof remains two steps/evidence edges long. The difference is whether the search manager reaches that proof before queue and step resources are consumed by unrelated combinations.

---

## 10. Limitations

This result is encouraging but must not be overstated.

### 10.1 Favorable topology

The source graph is complete bipartite. Every selected source pair has many shared targets, so the held-out goals are guaranteed to have short two-hop proofs.

This evaluates resource control under high branching and redundancy. It does not evaluate sparse long-distance reasoning.

### 10.2 Single relation family

The pilot evaluates only `Similarity` and PLN's transitive similarity rule. It does not evaluate:

- `Inheritance`.
- `Implication`.
- `Evaluation`.
- induction or abduction.
- negation.
- nested predicates and products.

### 10.3 Placeholder truth values

The source contains no calibrated weights. The experiment's `(stv 0.9 0.8)` assignments are controlled placeholders shared by both systems.

ConceptNet-scale evaluation must derive STVs from source weights and provenance using a documented conversion policy.

### 10.4 Small selected slice

The main result used 100 PLN sentences, not the full 7,860 directed-sentence representation and not millions of ConceptNet edges.

### 10.5 Runtime includes different control implementations

Unguided PLN runs the recursive MeTTa derivation loop. PRISM manages the frontier in Python and uses a persistent PeTTa process for one-step PLN calls. Wall-clock comparison therefore measures the complete systems, including their control-layer implementations, which is appropriate for end-to-end performance but not a microbenchmark of MeTTa versus Python.

### 10.6 Queue-order sensitivity

The baseline result depends on deterministic candidate and queue ordering. This is itself part of the inference-control problem, but future experiments should randomize source ordering and report distributions over repeated runs.

---

## 11. Reproduction

The runner imports the exact local `PeTTa/repos/PLN/lib_pln.metta` checkout for
both systems; it performs no network `git-import!`. Each result records the
PRISM, PeTTa and PLN commit IDs, the dataset SHA-256, Python version and all
search parameters. Compare semantic outcomes rather than wall-clock fields,
which naturally vary by machine and load.

### 11.1 Main pilot

From the repository root:

```bash
python3 -m benchmarks.evaluate_kg_similarity \
  --sources 5 \
  --targets 10 \
  --queries 5 \
  --max-steps 40 \
  --queue-size 150 \
  --timeout 30 \
  --output benchmarks/results/reference/kgadexp_pilot_5x10.json
```

### 11.2 Higher-budget baseline stress test

```bash
python3 -m benchmarks.evaluate_kg_similarity \
  --sources 5 \
  --targets 10 \
  --queries 3 \
  --max-steps 100 \
  --queue-size 500 \
  --timeout 30 \
  --output benchmarks/results/reference/kgadexp_pilot_5x10_high_budget.json
```

### 11.3 Loader tests

```bash
python3 -m pytest tests/unit/test_kg_similarity.py -q
```

### 11.4 Complete unit suite at evaluation time

```text
99 passed in 0.87 seconds
```

---

## 12. Files Added for the Experiment

| File | Purpose |
|---|---|
| `benchmarks/domains/kg_similarity.py` | Parse, audit, deduplicate, slice and convert the source graph into PLN sentences |
| `benchmarks/evaluate_kg_similarity.py` | Run unguided PLN and PRISM over identical KG slices and queries |
| `tests/unit/test_kg_similarity.py` | Verify source inventory and deterministic conversion behavior |
| `benchmarks/results/reference/kgadexp_pilot_5x10.json` | Main five-query result set |
| `benchmarks/results/reference/kgadexp_pilot_5x10_high_budget.json` | Higher-budget three-query stress-test results |

---

## 13. Conclusion

The KGAD pilot provides preliminary real-data evidence for PRISM's central hypothesis.

The previous confidence-driven PLN search can consume its bounded queue and step budget exploring many equally confident but goal-irrelevant combinations. PRISM uses goal-aware filtering and ordering to reach short valid proofs earlier. Because every accepted inference is still computed by `lib_pln.metta`, this improvement does not require changing PLN rules or truth-value formulas.

On the tested 100-sentence slice, PRISM achieved 100% query success, compared with 40% for bounded unguided PLN, while reducing mean wall-clock time by approximately half. Under a much larger unguided budget, PRISM remained substantially faster and more reliable.

The result justifies continued evaluation on larger and more diverse knowledge graphs. It does not yet establish million-edge scalability or cross-relation ConceptNet performance. Those claims require relation-aware import, calibrated STVs, indexed neighborhood retrieval, batching, repeated-order trials and progressive scale tests.
