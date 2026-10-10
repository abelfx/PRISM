# PRISM — Programmable Reduction & Inference Search Manager

PRISM is a programmable **search-control layer** for Hyperon components. It helps a component choose which valid candidate to explore next, which alternatives to retain, and when to stop under a time or step budget. The component itself still defines valid operations and their outcomes.

The current reference integrations are **Probabilistic Logic Networks (PLN)** for inference and the iCog **PeTTa-OpenPSI** port for goal-directed planning. They exercise the same broad control problem through different adapters; they do **not** have identical features. A MOSES/program-search adapter is a possible extension, not an existing integration.

This repository is research code and an evaluation harness, not a drop-in replacement for PLN, OpenPsi, or Hyperon. PRISM's explicit PLN search agenda is largely Python-based, with real MeTTa/PeTTa rule application; PLN's own derivation loop remains in MeTTa. A more shared, MeTTa-native control runtime and a generalizable neural policy remain project goals.

## Why search control?

A backend can generate many legal next steps without knowing which sequence will reach a useful result within a finite budget. A local score can order today's candidates, but it cannot by itself remember dead ends, preserve alternatives, avoid cycles, or coordinate forward and backward exploration. PRISM separates these responsibilities:

1. **Backend adapter:** Exposes candidate operations and asks the backend to apply a chosen operation. Backend semantics remain authoritative.
2. **Stage 0 — candidate preparation:** Narrows an expensive candidate set before ranking, using a method appropriate to the backend.
3. **Tier 1 — fast ranking:** Scores likely usefulness. The current v1 implementation is a deterministic structural/goal-aware heuristic, not a trained neural model.
4. **Search manager:** Owns the frontier, visited states, path costs, budgets, and stopping conditions. A proof, plan, and program population need not use the same policy.
5. **Tier 2 — optional strategy:** Proposes waypoints when search stalls. A proposal is a subgoal to establish, never an automatically accepted fact or action.

Filtering can miss a valid route, so **soundness of an accepted result is not the same as completeness of the search**. PRISM must measure both, alongside runtime overhead.

## Current integrations

### PLN: inference and proof search

In the sibling PeTTa checkout, PLN's lib_pln.metta runs its real inference rules and truth-value formulas. PRISM adds goal-aware task priority and a premise filter around PLN.Derive while retaining confidence-based fallback for missing goals or scorer failure. Explicit best-first and bidirectional search use PLN.Apply for one-step rule applications; Python does not substitute its own deduction arithmetic. Evidence stamps and derived truth values come from PLN.

The PLN adapter includes chain, diamond, tree, semantic-gap, and supplied knowledge-graph workloads; proof replay and rule regressions check accepted results. Stage 0 currently uses a concept-based index, not a general AtomSpace-wide unification index. Search improvements are workload- and budget-dependent, so use the paired benchmark outputs rather than assuming every configuration wins.

### OpenPsi: goal-directed planning

The opt-in PeTTa-OpenPSI adapter searches over **OpenPsi-generated** applicable actions and successor states. It can rank a locally attractive action against a longer path to a goal, run a bounded plan search, and fall back to native selection. OpenPsi still owns its rules, action execution, demand updates, and affect.

In the evaluated repository conversation-rule graph, the fresh-process comparison reached **20/21 goals with PRISM versus 3/21 with native v2 selection**. Those are 21 goals on **one graph**, not independent domains; simple or unreachable cases can favor native selection on cost. A corrected symbolic feedback-loop fixture showed a valid PRISM plan updating demand where an invalid native plan did not. In the effectful ping-pong check, both selectors chose the same action and had the same outcome. These observations support a planning benefit in the tested cases, **not** a general real-world agent-outcome claim. See [OpenPsi integration](docs/openpsi-integration.md) for methods and limitations.

### Proposed extensions

A neural Tier 1 policy trained on candidate/outcome traces, a more reusable controller interface, further MeTTa-native control, and a MOSES adapter are research directions. The historical Week 11 Tier 1 v2 result files are present, but the evaluator/training source and checkpoint are **not** present in this checkout; do not present v2 as currently runnable. The OpenPsi adapter also does not yet implement every PLN-side policy or every OpenPsi rule schema.

## Repository layout

~~~text
prism/
├── run.sh                    Evaluator entry point and command help
├── src/prism/
│   ├── core/                 Configuration, scoring bridge, cache and safety
│   ├── stage0/               PLN premise filtering
│   ├── tier1/                Fast v1 heuristic
│   ├── tier2/                Optional subgoal guidance and stall detection
│   ├── search/               Best-first and bidirectional PLN agendas
│   ├── adapters/petta/       PeTTa / real PLN.Apply bridge
│   ├── adapters/openpsi/     OpenPsi selection bridge
│   └── verification/         Independent PLN proof replay
├── tests/                    Python and direct MeTTa checks
├── benchmarks/               Paired evaluations and curated reference outputs
├── docs/                     Integration and technical background
└── artifacts/                Generated local runs; not curated evidence
~~~

The OpenPsi MeTTa adapter lives in the sibling PeTTa-OpenPSI checkout, not inside this Python package. The PLN hooks live in the sibling PeTTa/repos/PLN checkout.

## Set up and run

The full evaluator setup expects this workspace layout:

~~~text
<workspace>/
├── prism/
├── PeTTa/
│   └── repos/PLN/
├── other_hyperon/PeTTa-OpenPSI/
└── kgadexp.metta                 Small optional KG pilot input
~~~

Use Python **3.12** for the complete benchmark suite, plus SWI-Prolog with the Janus Python bridge required by PeTTa. The package metadata permits Python 3.10, but the current bidirectional benchmark uses Python 3.12 f-string syntax. Install the Python test dependencies:

~~~bash
cd <workspace>/prism
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
./run.sh doctor
~~~

The launcher runs from any working directory once given its path. From prism/:

~~~bash
./run.sh help                  # List every test and benchmark command
./run.sh test                  # Python, PRISM MeTTa, and seven PLN rule tests
./run.sh test-pln-examples     # Six additional upstream PLN examples
./run.sh bench-chain          # Paired native PLN / PRISM chain sweep
./run.sh bench-openpsi        # Native / PRISM OpenPsi selector comparison
./run.sh bench-openpsi-fresh  # Fresh-process v1, v2 and PRISM plan comparison
./run.sh bench-all            # All offline suites; may take many minutes
~~~

Each command has a one-line explanation in run.sh and in its help output. Fresh logs and JSON are written under **artifacts/evaluator-runs/**; the curated benchmarks/results/reference/ files are not overwritten. Set PRISM_RESULTS_DIR for another output folder or PRISM_PYTHON for another Python executable. PETTA_HOME can override the PLN-side PeTTa path, but some OpenPsi evaluators still require the sibling checkout layout shown above.

The live Tier 2 command is **opt-in** and requires OPENROUTER_API_KEY: ./run.sh bench-tier2-live. It is excluded from bench-all. ./run.sh bench-v2 explains why the archived v2 evaluation cannot be regenerated from this checkout. The broader upstream PLN test script also includes a pre-existing failing Direct.metta example; this runner uses the seven pinned rule tests and six working examples instead.

## Evidence and further reading

- [OpenPsi integration](docs/openpsi-integration.md): adapter ownership, comparisons, feedback-loop and effectful-action limitations.
- [Benchmark guide](benchmarks/README.md): workload definitions and historical reference outputs. Some older commands and labels refer to earlier checkout states; use run.sh for current reruns.
- [Test guide](tests/README.md): unit and MeTTa integration coverage.
- [PLN technical specification](docs/papers/PRISM_Implementation_Specification.md): original PLN-focused design; it is not the complete cross-component roadmap.
- [Milestone records](../milestones/): measured PLN results and the separate [OpenPsi evaluation](../milestones/openpsi_evaluation.md).
