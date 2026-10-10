# PRISM — Programmable Reduction & Inference Search Manager

PRISM studies **how to allocate search effort** when a Hyperon component can generate more valid next steps than it can afford to explore. A component defines legal operations and their outcomes; PRISM filters, ranks, schedules, and measures the exploration of those operations under a budget.

**This main branch implements the PLN reference integration.** OpenPsi integration and learned Tier 1 v2 work are on experimental branches and are not presented here as runnable main-branch features. The broader project aims for reusable search control, but cross-component generality remains a research goal rather than a claim demonstrated by this branch alone.

## Why PRISM exists

PLN derives conclusions from uncertain premises, carrying truth values and evidence through each rule application. Its rules say what follows from selected premises; they do not make every potentially useful path cheap to discover. In a branching knowledge base, a confidence-only task priority can spend a limited search budget on high-confidence but goal-irrelevant work.

PRISM adds control around that process without replacing PLN's logic:

- **Stage 0 — premise preparation:** A concept-based index narrows candidate beliefs before expensive rule matching. It is not a general AtomSpace-wide unification index.
- **Tier 1 — fast candidate selection:** A deterministic v1 heuristic combines structural goal overlap, confidence, and a depth discount. The current code does **not** use a trained neural policy.
- **Search manager:** Best-first and bidirectional agendas manage open candidates, visited states, alternatives, step budgets, and stopping conditions. This is separate from scoring one candidate: a score cannot remember a failed branch or decide when to return to another path.
- **Tier 2 — optional strategy:** A mock or configured LLM can suggest an intermediate subgoal after a stall. A suggestion must still be established through PLN; it is not inserted as a fabricated belief.

PRISM changes which steps are explored and when. It does not calculate PLN truth values. Explicit search asks the real PLN.Apply primitive in lib_pln.metta to perform one-step inference, and accepted conclusions retain PLN's truth values and evidence stamps. Search filtering can still miss a valid route, so **proof soundness and search completeness are different properties**.

## What is implemented on main

The sibling PeTTa/repos/PLN checkout contains the MeTTa-side goal-aware priority and premise-filter hooks around PLN.Derive. The PRISM package contains the Python scorer, concept index, cache, explicit search agendas, Tier 2 subgoal handling, PeTTa bridge, tracing, and independent proof-replay checks. The built-in PLN derivation loop remains in MeTTa; PRISM's explicit best-first/bidirectional agenda is mainly Python.

The repository evaluates chain, diamond, tree, semantic-gap, and supplied knowledge-graph tasks. Paired unguided/guided sweeps, a four-way Stage 0/Tier 1 ablation, proof soundness checks, and PLN regressions are available. Performance is workload- and budget-dependent; the recorded results are evidence for the tested domains, not a guarantee that every query or larger knowledge graph improves.

Experimental OpenPsi planning and learned-v2 policy work may be developed on other branches. **There are no OpenPsi or learned-v2 commands in this branch's runner.** A future shared controller interface and additional backend adapters, such as MOSES, are proposals rather than main-branch integrations.

## Repository layout

~~~text
prism/
├── run.sh                     Tests and benchmark entry point
├── src/prism/
│   ├── core/                  Configuration, scoring bridge, cache and safety
│   ├── stage0/                PLN premise index
│   ├── tier1/                 Fast structural v1 heuristic
│   ├── tier2/                 Optional stall and subgoal guidance
│   ├── search/                Best-first and bidirectional agendas
│   ├── adapters/petta/        PeTTa bridge to real PLN rules
│   ├── observability/         Search traces
│   └── verification/          PLN proof replay and soundness checks
├── tests/                     Python and direct MeTTa tests
├── benchmarks/                Paired experiments and reference results
├── docs/papers/               Original PLN-focused proposal/specification
└── artifacts/                 Locally generated benchmark outputs
~~~

The PLN rules, truth-value formulas, and MeTTa hooks are in the sibling **PeTTa/repos/PLN** checkout, not copied into this package.

## Set up

For the complete evaluator suite, use Python **3.12** and SWI-Prolog with PeTTa's Janus Python bridge. The package metadata permits older Python, but the current bidirectional benchmark uses Python 3.12 f-string syntax. The expected full-workspace layout is:

~~~text
<workspace>/
├── prism/
├── PeTTa/
│   └── repos/PLN/
├── kgadexp.metta                 Optional small-KG input
├── kg.metta                      External-KG input
├── wordnet_stv_clean.metta       External-KG input
└── output_prolog_ready.metta     External-KG input
~~~

~~~bash
cd <workspace>/prism
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
./run.sh doctor
~~~

The Python tests need the package/test dependencies. Direct MeTTa checks and PLN benchmarks also require the sibling PeTTa/PLN checkout; KG benchmarks need their listed workspace data files. PETTA_HOME can select a different PeTTa checkout for PLN-specific commands.

## Run tests and benchmarks

From prism/:

~~~bash
./run.sh help                  # List all commands and their purpose
./run.sh test                  # Python, direct MeTTa and seven PLN rule tests
./run.sh test-pln-examples     # Six additional upstream PLN examples
./run.sh bench-ffi             # Measure cached and uncached FFI overhead
./run.sh bench-chain           # Compare unguided PLN and PRISM on chains
./run.sh bench-ablation        # Isolate Stage 0, Tier 1 and full PRISM
./run.sh bench-kg              # Run the supplied small-KG pilot
./run.sh bench-all             # All offline suites; can take many minutes
~~~

Each command is explained by a short comment inside [run.sh](run.sh). The launcher works from other directories when called by path. New JSON and logs go to **artifacts/evaluator-runs/**, not the curated benchmarks/results/reference/ files. Set PRISM_RESULTS_DIR to write elsewhere or PRISM_PYTHON to choose a Python executable.

The optional live provider check is ./run.sh bench-tier2-live and requires OPENROUTER_API_KEY; it is excluded from bench-all. The broad upstream PLN test script currently includes a failing Direct.metta example, so this runner uses the seven pinned rule tests and six working examples.

## Evidence and documentation

- [Benchmark guide](benchmarks/README.md): workloads, historical numbers, and interpretation. Use run.sh for current reruns rather than older commands that write into reference paths.
- [Test guide](tests/README.md): Python and direct MeTTa coverage.
- [Implementation specification](docs/papers/PRISM_Implementation_Specification.md): PLN-focused design and formulas; proposals in it are not automatically implemented on main.
- [Original PLN proposal](docs/papers/PRISM_PLN_Inference_Control_Proposal_final.pdf): historical project framing.
