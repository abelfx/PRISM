# PRISM ↔ PeTTa-OpenPSI: goal-reachable action control

## Use case

PRISM's target is **better planning/search control**, not a general increase
in OpenPsi agent performance. Judge it primarily by whether it selects legal
steps and finds valid goal-reaching plans within a given budget, plus its
runtime cost. OpenPsi remains responsible for executing actions and updating
demands and affect. Real task success is a useful downstream test when there
is an executor, but a one-step tie does not negate a harder planning benefit;
nor does a planning gain by itself establish better agent outcomes.

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
selection, rewards, or real stochastic action outcomes. The optional feedback-loop
entry point is dispatch-tested and has noninteractive checks below,
but its real user-facing demand/emotion cycle has not been validated. The
reachability map reflects current *schema* links; a
path in that map is not a guarantee that real-world action execution will
succeed. The controlled evaluation includes one repository-owned conversation
graph and constructed branching workloads. It is not a generalization claim
across OpenPsi agents: the alternative OpenPsi A* schema and real
action execution have not been compared. A later 21-goal, fresh-process v1
comparison is described below.

### Original feedback-loop smoke check, before local correction

Run `PYTHONPATH=src python3 -m benchmarks.evaluate_openpsi_full_cycle` from
`prism/`. This executes the actual PeTTa-OpenPSI `psi-agent-loop` and opt-in
`psi-agent-loop-prism` in separate fresh PeTTa processes on the same
noninteractive three-rule fixture. It is a constructed graph, not a deployed
agent. At the time of this first run, the fixture had to explicitly import
OpenPsi's normalization module.

Native v1 returned `(idle finish)`, which fails replay through OpenPsi's own
`applyCurrentActions`; PRISM returned `(explore finish)`, which replays to the
target. **Both** loops nevertheless printed `goalMet true`, identical emotion
values, and an unchanged competence demand of `0.1`. Thus this test supports
better *plan validity* on the fixture but **not** improved demand satisfaction
or affective behavior. The loop's former `isGoalMet?` checked a rule for only the last
action, not the entire plan, so the invalid native path is falsely reported
as successful. The demand-update path also did not modify the demand in this
fixture. These were OpenPsi feedback-loop limitations, not evidence
that PRISM fixed end-to-end agent behavior. The local corrections and new
results below supersede this smoke check; it remains here as the pre-fix
baseline.

### Follow-up: path-valid demand update and fresh planner comparison

The local PeTTa-OpenPSI checkout now replays the entire proposed route using
its native rule matcher and only treats it as successful when it ends at the
target. A separate bounded-demand updater preserves the five-field demand
form, removes stale demand atoms when syncing back to the KB, and the feedback
loop imports its normalization dependency. These are
OpenPsi-side local changes, not PRISM features or an upstream release.

Run the corrected paired loops in separate fresh PeTTa processes:

```bash
PYTHONPATH=src python3 -m benchmarks.evaluate_openpsi_full_cycle \
  --output benchmarks/results/reference/openpsi_full_cycle_constructed.json
PYTHONPATH=src python3 -m benchmarks.evaluate_openpsi_full_cycle \
  --scenario conversation \
  --output benchmarks/results/reference/openpsi_full_cycle_conversation.json
```

On the constructed three-rule fixture, native v1 returns invalid
`(idle finish)` and competence stays at `0.10`; PRISM returns valid
`(explore finish)` and competence becomes `0.55`. On the repository's
conversation rules with `Understand-User-Interests` as the demand goal,
native v1's four-action route is invalid and leaves competence at `0.10`;
PRISM's eight-action route is valid and raises it to `0.55`. A second cycle
on the constructed case increases one selected PRISM demand, while the KB
retains only current bounded demands; native remains unchanged. Second-cycle
demand selection is stochastic: competence sometimes reaches `0.775`, while
another `0.90` demand may instead reach `0.95`. Emotion outputs
differ after the valid update. This establishes a symbolic feedback-loop difference
under the corrected local code, not real action execution. The saved outputs
are `benchmarks/results/reference/openpsi_full_cycle_constructed.json` and
`benchmarks/results/reference/openpsi_full_cycle_conversation.json`.

For the same 21 conversation goals, the fresh-process runner compares the
default v1 planner, native v2 selection, and PRISM with a 15-action returned
plan limit and action replay:

```bash
PYTHONPATH=src python3 -m benchmarks.evaluate_openpsi_fresh \
  --output benchmarks/results/reference/openpsi_fresh_eval.json
```

V1 replayed successfully for **1/21** goals, v2 for **3/21**, and PRISM for
**20/21**. Each goal/mode uses a new PeTTa process and rule space; the two
calls inside that process provide cold and warm timings. Median cold/warm
planner-call times were about `0.423/0.184 ms` (v1), `0.496/0.326 ms` (v2),
and `26.823/3.236 ms` (PRISM). V1's internal search is unbounded, so the
15-action output limit is **not** an equal search-work budget. All 21 goals
still belong to one repository rule graph.

The repository ping-pong test schema, including nested `(ball ...)` goals,
also runs through PeTTa. Both selectors choose the same direct `act-ping`
action, and PRISM falls back to native selection for an unreachable target.
This is a rule-level probe, not a full ping-pong game run. A separate live
negative-compatibility probe loads all 24 repository `metta-trader` rules:
OpenPsi v2 produces no candidates under its different schema, and PRISM
returns no pick. That is **unsupported schema**, not a PRISM task failure.

Finally, `benchmarks.evaluate_openpsi_stochastic` applies explicitly
hypothetical independent action-success rates to the PeTTa-validated plans.
At 90% per-action success and 1,000 seeded episodes per goal, completion was
3.81% (v1), 11.64% (v2), and 49.07% (PRISM); at 70%, it was 2.36%, 7.38%,
and 16.72%. These are simulated outcomes under assumed probabilities, **not**
measured OpenPsi action reliability or field task success. See
`benchmarks/results/reference/openpsi_stochastic_eval.json` and the
workspace's `milestones/openpsi_evaluation.md` for the full protocol.

### Effectful OpenPsi action check

`benchmarks.evaluate_openpsi_action_execution` runs both selectors against
the repository ping-pong game's real `executePlan`/`ping` action functions,
which mutate ball and motivation state. Both select `act-ping`: from motivation
`1.0`, both return the ball and finish at `0.8`; from `0.1`, both miss. PRISM
has **no measured task-outcome advantage** in this actual-action case. The
game's pre-existing `sleep-t` call mismatch was fixed locally to make the
action executable. Run:

```bash
PYTHONPATH=src python3 -m benchmarks.evaluate_openpsi_action_execution \
  --output benchmarks/results/reference/openpsi_action_execution.json
```

This is one turn in one use case. The conversation graph has no action
executor; its replay/demand result remains symbolic, and the stochastic
numbers above remain assumptions rather than observed environment outcomes.
