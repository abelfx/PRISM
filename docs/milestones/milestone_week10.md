# Milestone Week 10 - Soundness, Robustness & Graceful Degradation

**Status:** Planned  
**Scope source:** PRISM Implementation Specification, Sections 11-14, Week 10  
**Prerequisites:** Weeks 1-9 complete  
**Primary objective:** Demonstrate that PRISM never changes PLN's logical
semantics and that optional search-control components fail safely, visibly and
without fabricating conclusions.

---

## 1. Why Week 10 Exists

Weeks 1-9 established the inference bridge, Stage 0 filtering, Tier 1 scoring,
best-first and bidirectional search, Tier 2 waypoint guidance, cross-domain
transfer, and progressive external-KG scaling. Week 10 is the release-hardening
milestone before training Tier 1 v2 in Week 11.

PRISM controls which legal inference PLN attempts next. It must never become a
second inference engine or silently alter truth-value formulas. A fast proof is
unacceptable if a conclusion, truth value, or evidence stamp cannot be
reproduced by the authoritative PLN implementation.

The implementation specification requires:

- 100% soundness on all benchmark runs;
- independent re-evaluation of derived conclusions with PLN;
- graceful degradation when the scorer or optional guidance fails;
- containment of malformed or unavailable Tier 2 output;
- preservation of the existing PLN rule and PRISM regression suites.

---

## 2. Soundness Contract

A PRISM proof passes Week 10 only when all of the following hold:

1. **PLN authority:** Every derived action can be reproduced by the pinned
   local `PLN.Apply`; Python does not substitute its own truth-value formula.
2. **Term equivalence:** Replayed relation, subject and object exactly match the
   recorded derived term.
3. **Truth-value equivalence:** Replayed strength and confidence match the
   recorded values within a declared numeric tolerance used only for text and
   floating-point serialization.
4. **Evidence integrity:** Every derived evidence stamp is the valid union of
   disjoint premise evidence, contains only source evidence IDs, and does not
   introduce or erase support.
5. **Acyclicity:** A conclusion cannot depend on itself, directly or through a
   repeated evidence path.
6. **Goal validity:** A successful result contains a replayable goal sentence;
   reaching a search waypoint alone is not success.
7. **No LLM authority:** Tier 2 output is a planning proposal only. A proposed
   waypoint enters the belief state only if PLN derives it from existing
   premises.
8. **Fail closed at the kernel:** If PeTTa/PLN itself is unavailable or its
   response is invalid, PRISM returns a controlled failure and no conclusion.
   It must not replace the kernel with an approximate Python inference.

Soundness is evaluated against the exact recorded PRISM, PeTTa and PLN
revisions. It is not inferred from search success alone.

---

## 3. Evaluation Coverage

### 3.1 Proof families

The soundness harness will generate and replay fresh proofs from:

- transitive chains at multiple depths and distractor levels;
- diamond/multipath DAGs;
- confluent tree DAGs;
- semantic-gap search with deterministic Tier 2 waypoints;
- bidirectional proofs, including the stitched seam;
- the three Week 9 external-KG sources at the accepted bounded slice sizes;
- representative PLN rule tests already present in the pinned PLN checkout.

Saved Week 9 JSON is provenance evidence, not a substitute for fresh replay.
Week 10 must execute the proof steps again.

### 3.2 Failure and fallback matrix

The robustness suite will inject deterministic failures at component
boundaries:

- Tier 1 scorer raises an exception;
- Tier 1 scorer returns malformed, non-numeric, non-finite or out-of-range data;
- score-cache lookup or computation fails;
- Stage 0 filtering raises or returns no usable premises;
- Tier 2 has no API key, times out, returns an HTTP/provider error, returns
  malformed JSON, proposes an invalid atom, or proposes an underivable lemma;
- bidirectional proof stitching produces an invalid or unreplayable seam;
- candidate generation produces an empty frontier;
- the search reaches its step budget without proving the goal;
- PeTTa/PLN exits, returns a protocol error, or returns an unevaluated
  `PLN.Apply` expression.

Expected behavior depends on which layer fails:

- **Tier 2 failure:** continue with Tier 1/ordinary search and add no belief.
- **Tier 1 failure:** use the documented conservative/static fallback ordering.
- **Stage 0 failure:** use the full unfiltered belief set.
- **Bidirectional validation failure:** reject the stitched proof and fall back
  to a sound forward search when the configured budget permits.
- **PLN kernel failure:** return a structured failure with no derived result.

Graceful degradation means safe and deterministic behavior. It does not mean
that every degraded run must still solve the goal.

---

## 4. Deliverables

### 4.1 Independent proof verifier

- [ ] Add a verifier that accepts initial facts, a recorded proof path and a
  goal, then replays every derived action through `PLN.Apply`.
- [ ] Match each recorded action to an available pair of prior premises.
- [ ] Compare term, STV and evidence stamp independently of search priority.
- [ ] Produce a structured failure reason identifying the first invalid step.
- [ ] Reject incomplete paths, circular evidence, unknown source evidence and
  unsupported injected sentences.

### 4.2 Soundness test suite

- [ ] Add `tests/unit/test_soundness.py`.
- [ ] Cover forward A*, bidirectional stitching and Tier 2-assisted proofs.
- [ ] Cover chain, diamond, tree, semantic-gap and external-KG proof families.
- [ ] Verify successful results against the pinned PLN runtime rather than
  duplicating truth-value arithmetic in test code.

### 4.3 Robustness and fallback suite

- [ ] Add `tests/unit/test_fallback.py`.
- [ ] Convert relevant existing fallback checks into explicit Week 10 cases
  without deleting their earlier regression coverage.
- [ ] Use mocks or dependency injection for provider and component failures;
  no live API key is required for the deterministic gate.
- [ ] Assert both the fallback selected and the absence of unsupported beliefs.
- [ ] Ensure errors are observable through structured results or logs instead
  of being silently swallowed.

### 4.4 Evaluation runner and artifact

- [ ] Add `benchmarks/evaluate_soundness_robustness.py`.
- [ ] Save `benchmarks/results/reference/week10_soundness_robustness.json`.
- [ ] Record PRISM, PeTTa and PLN revisions, parameters, case IDs and failure
  injections.
- [ ] Report replayed steps, sound/unsound counts, fallback outcomes and first
  failure reasons.
- [ ] Keep timing informational; semantic equivalence is the gate.

### 4.5 Documentation

- [ ] Update `tests/README.md` with Week 10 coverage and commands.
- [ ] Update `benchmarks/README.md` with the evaluation command and
  interpretation rules.
- [ ] Replace planned statuses in this file with measured results only after
  the committed artifact and full regression suite pass.

---

## 5. Acceptance Gates

| Gate | Criterion | Target | Status |
|---|---|---|:---:|
| **GATE-10.1** | Step replay soundness | 100% of recorded derived actions reproduced by pinned `PLN.Apply` | **PENDING** |
| **GATE-10.2** | Final-result equivalence | 100% term, STV and evidence agreement for successful benchmark goals | **PENDING** |
| **GATE-10.3** | Evidence integrity | Zero unknown, overlapping, circular or fabricated evidence stamps | **PENDING** |
| **GATE-10.4** | Graceful fallback | Every declared non-kernel failure selects its documented safe fallback without an unhandled exception | **PENDING** |
| **GATE-10.5** | Kernel fail-closed behavior | PeTTa/PLN failure returns no conclusion and a controlled diagnostic | **PENDING** |
| **GATE-10.6** | Tier 2 containment | Malformed, failed and underivable proposals add zero beliefs; valid proposals remain PLN-derived | **PENDING** |
| **GATE-10.7** | Zero regression | Full PRISM suite and pinned PLN rule suite pass | **PENDING** |
| **GATE-10.8** | Reproducibility | Machine-readable artifact records revisions, cases and exact outcomes | **PENDING** |

Week 10 is complete only when every gate passes. A case skipped because a
component is difficult to inject is not a pass.

---

## 6. Planned Result Schema

The machine-readable result will contain:

```text
schema_version
reproducibility
  prism_revision
  petta_revision
  pln_revision
  parameters
soundness
  cases
    case_id
    domain
    search_mode
    success
    steps_recorded
    steps_replayed
    term_match
    stv_match
    evidence_match
    first_failure
  sound_cases
  total_cases
fallback
  cases
    case_id
    injected_failure
    expected_policy
    observed_policy
    unhandled_exception
    unsupported_beliefs_added
  passed_cases
  total_cases
gates
```

Secrets, provider credentials, raw environment dumps and unrestricted absolute
paths must not be written to the artifact.

---

## 7. Reproduction Target

From the repository root:

```bash
python3 -m benchmarks.evaluate_soundness_robustness \
  --output benchmarks/results/reference/week10_soundness_robustness.json

pytest -q tests/unit/test_soundness.py \
  tests/unit/test_fallback.py

pytest -q prism/tests

cd PeTTa/repos/PLN
./test.sh
```

The exact PLN regression command may be adjusted to the pinned checkout's
supported runner, but the executed command and result must be recorded.

---

## 8. Explicit Non-Goals

Week 10 does not:

- train or evaluate Tier 1 v2; that is Week 11;
- extend the accepted Week 9 boundary to full external KGs;
- invent semantics for external relations not mapped to PLN;
- require a live LLM provider;
- treat provider availability or proof latency as a soundness condition;
- redesign PLN truth-value formulas;
- accept a Python-only reconstruction as proof of PLN soundness.

---

## 9. Completion Rule

The milestone may be marked complete only when the saved Week 10 artifact shows
100% replay soundness, every declared fallback case behaves as documented, the
kernel fails closed, and both the PRISM and PLN regression suites pass. Any
unsound conclusion is a release blocker regardless of benchmark speed.
