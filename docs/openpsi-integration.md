# PRISM ↔ PeTTa-OpenPSI: goal-reachable action control

## Use case

PeTTa-OpenPSI's `action-planner-v2.metta` produces applicable actions from its
actual cognitive-schema rule space, applies them to get successor states, and
chooses a successor by its existing `distance` function. In a branching rule
space, that local distance can tie a dead end with a route that eventually
reaches the goal. PRISM adds an **opt-in** selector for this exact choice.

The integration does not implement OpenPsi rules or state transitions in
Python. OpenPsi's `getApplicableActions` and `applyCurrentActions` produce the
only legal candidates. PRISM inspects the live rule atoms to construct a
bounded, goal-directed reachability ranking and returns **one of those exact
candidate pairs**. If scoring fails or none is reachable, the adapter calls
OpenPsi's original `findMinDistance` selector. The native planner remains
unchanged.

## Ownership and files

- OpenPsi rule matching and successor generation:
  `other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v2.metta`
- Optional MeTTa entry point and bounded plan loop:
  `other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/prism-openpsi.metta`
- Pure ranking over OpenPsi's rule/candidate terms:
  `prism/src/prism/adapters/openpsi/selection.py`
- Exception-contained PeTTa–Python bridge:
  `prism/src/prism/adapters/openpsi/openpsi_ffi.pl`

From a MeTTa entry point, import `action-planner-v2` and `prism-openpsi`
separately, then call `(PRISM.OpenPsi.Plan $state $goal $ruleSpace $budget)`.
PeTTa resolves nested relative imports against the entry point, which is why
the optional module does not import the native planner on its own. Run from
the workspace's `PeTTa` directory with `PYTHONPATH` including `prism/src`.
For the OpenPsi feedback loop, import `action-planner-v2` and `prism-openpsi`
**before** `feedback-loop.metta`, then call `(psi-agent-loop-prism $state $kb)`.
PeTTa compiles imported functions in order. The regular
`psi-agent-loop` continues to use its original planner. The opt-in loop uses a
32-expansion planning budget; it does not alter demand, emotion, or modulator
updates.

## Reproduce the live comparison

```bash
cd <workspace>/prism
PYTHONPATH=src python3 -m pytest \
  tests/unit/test_openpsi_selection.py \
  tests/integration/test_openpsi_planner.py -q
```

The integration test builds a real OpenPsi rule space with an `idle` dead end
and a two-action `explore → finish` route. The native local-distance selector
first picks `(idle deadend)`; PRISM picks `(explore middle)` from the *same*
OpenPsi-generated candidates and returns `(explore finish)` within four
expansions. A one-expansion budget cannot complete the route. The Python test
requires explicit output markers because PeTTa's top-level `true` can also
appear when a MeTTa expression produces no result.
Separate tests check that the opt-in feedback-loop dispatcher uses PRISM and
that the native feedback-loop dispatcher still works without loading PRISM.

## Controlled evaluation (2026-10-08)

Run the same bounded traversal with only the selector changed:

```bash
cd <workspace>/prism
PYTHONPATH=src python3 -m benchmarks.evaluate_openpsi \
  --output benchmarks/results/reference/openpsi_selection_eval.json
```

The 15-step sweep uses 21 named targets from OpenPsi's existing conversation
rule graph. PRISM reached 20; native `findMinDistance` reached 3. These are 21
queries on **one graph**, not 21 independent domains. Three repeats per target
measure timing stability, not success-rate confidence. PRISM produced a native
eight-action path to `Understand-User-Interests`; the native local selector
dead-ended after three steps in the original insertion order.

The advantage is conditional. Both selectors solve a one-step goal, where
PRISM takes roughly twice as long after warm-up. On an unreachable goal both
fail and PRISM costs more. With 50 constructed decoys, PRISM succeeds in two
steps while native dead-ends in one; PRISM's warm median is roughly half the
native median. A first Python call costs tens of milliseconds, so warm-query
latency alone understates cold-start cost.

Reversing the insertion order lets native selection solve the deep conversation
goal (9 steps) while PRISM still uses 8 steps but is about three times slower.
For a different reversed-order target, native exhausts the
15-step budget while PRISM succeeds in 3. Thus some measured rescue reflects
the native selector's order-sensitive local-distance ties. The full result,
including every timed run, is in
`benchmarks/results/reference/openpsi_selection_eval.json`.

A separate diagnostic calls the **actual v1 planner** used by the default
feedback loop, then replays its action list through OpenPsi's native
`applyCurrentActions`. It returns a valid two-action plan for the short
conversation goal, but its four-action plan for
`Understand-User-Interests` does **not** reach that goal; PRISM's eight-action
plan does. This v1 check is not the matched timing experiment and does not
establish a general success rate for v1.

## Scope and limitations

This is a concrete second-backend integration, **not** PLN feature parity.
It covers Stage-0-like applicable-rule selection, deterministic goal-aware
ranking, bounded plan traversal, a native fallback, and a live MeTTa test.
It does not yet integrate Tier 1 v2, Tier 2, bidirectional planning, demand
selection, rewards, or stochastic action outcomes. The optional feedback-loop
entry point is dispatch-tested and has one noninteractive smoke check below,
but its full demand/emotion cycle has not been validated end to end. The
reachability map reflects current *schema* links; a
path in that map is not a guarantee that real-world action execution will
succeed. The controlled evaluation includes one repository-owned conversation
graph and constructed branching workloads. It is not a generalization claim
across OpenPsi agents: the actual v1 feedback-loop planner has only the two
replayed diagnostic goals above; the alternative OpenPsi A* schema and real
action execution have not been compared.

### Full feedback-loop smoke check

Run `PYTHONPATH=src python3 -m benchmarks.evaluate_openpsi_full_cycle` from
`prism/`. This executes the actual PeTTa-OpenPSI `psi-agent-loop` and opt-in
`psi-agent-loop-prism` in separate fresh PeTTa processes on the same
noninteractive three-rule fixture. It is a constructed graph, not a deployed
agent. The fixture explicitly imports OpenPsi's normalization module, which
the feedback-loop source does not import itself.

Native v1 returned `(idle finish)`, which fails replay through OpenPsi's own
`applyCurrentActions`; PRISM returned `(explore finish)`, which replays to the
target. **Both** loops nevertheless printed `goalMet true`, identical emotion
values, and an unchanged competence demand of `0.1`. Thus this test supports
better *plan validity* on the fixture but **not** improved demand satisfaction
or affective behavior. The loop's `isGoalMet?` checks a rule for only the last
action, not the entire plan, so the invalid native path is falsely reported
as successful. The demand-update path also did not modify the demand in this
fixture. These are existing OpenPsi feedback-loop limitations, not evidence
that PRISM fixes end-to-end agent behavior.
