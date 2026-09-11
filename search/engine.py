"""
Learned A* Search Engine for PRISM.

Implements agenda-based Best-First / A* inference search over PLN derivation space
using cumulative path uncertainty costs g(n) and inverted Tier 1 heuristic distances h(n).
"""

from dataclasses import dataclass, field
import heapq
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from prism.benchmarks.utils.trace_logger import ProofTraceSession
from prism.core.cache import ScoreCache
from prism.core.config import DEFAULT_CONFIG, SearchConfig, Tier1Config
from prism.search.rules import apply_candidate, generate_forward_candidates
from prism.search.state import (
    SearchNode,
    extract_proof_path,
    hash_belief_state,
    matches_goal,
)
from prism.tier1.heuristic_v1 import compute_v1_score, extract_confidence


@dataclass
class SearchResult:
    """
    Structured outcome of an A* search derivation run.

    Attributes
    ----------
    goal_found : bool
        True if a belief satisfying the query goal was derived.
    final_node : Optional[SearchNode]
        The node at which the goal was derived, or None.
    proof_path : List[SearchNode]
        Reconstructed sequence of ancestor states leading to the goal.
    goal_sentence : Optional[Any]
        The exact derived goal Sentence S-expression.
    steps_expanded : int
        Number of priority queue pop/expansion iterations executed.
    nodes_generated : int
        Total number of state nodes created and pushed to the open queue.
    visited_states_count : int
        Total number of distinct belief states tracked in the closed set.
    wall_clock_seconds : float
        Elapsed search time in seconds.
    stalled : bool
        True if candidate scores fell below the stall threshold during search.
    proof_trace : List[Any]
        Exported proof traces if trace session was active.
    """

    goal_found: bool
    final_node: Optional[SearchNode]
    proof_path: List[SearchNode]
    goal_sentence: Optional[Any]
    steps_expanded: int
    nodes_generated: int
    visited_states_count: int
    wall_clock_seconds: float
    stalled: bool = False
    proof_trace: List[Any] = field(default_factory=list)


class AStarSearchEngine:
    """
    Learned A* Best-First Search engine for PLN derivation spaces.

    Inputs:
        config (SearchConfig): Search hyperparameters (beam width, max steps, costs).
        tier1_config (Tier1Config): Heuristic scoring parameters.
        cache (Optional[ScoreCache]): Cache for candidate heuristic scores.

    Outputs:
        SearchResult dataclass containing derived proof path and search telemetry.

    What it does NOT handle:
        Does not perform backward abduction or call Tier 2 LLMs (handled in Week 8).
    """

    def __init__(
        self,
        config: Optional[SearchConfig] = None,
        tier1_config: Optional[Tier1Config] = None,
        cache: Optional[ScoreCache] = None,
    ) -> None:
        self.config = config or DEFAULT_CONFIG.search
        self.tier1_config = tier1_config or DEFAULT_CONFIG.tier1
        self.cache = cache or ScoreCache()

    def search(
        self,
        initial_tasks: Sequence[Any],
        initial_beliefs: Sequence[Any],
        goal: Any,
        candidate_generator: Optional[
            Callable[[Sequence[Any], Sequence[Any]], List[Any]]
        ] = None,
        trace_session: Optional[ProofTraceSession] = None,
    ) -> SearchResult:
        """
        Execute learned A* search from initial knowledge to derive target goal.

        Parameters
        ----------
        initial_tasks : Sequence[Any]
            Initial set of task sentences.
        initial_beliefs : Sequence[Any]
            Initial belief buffer (axioms).
        goal : Any
            Target statement, e.g. ['Inheritance', 'A', 'Z'] or '(Inheritance A Z)'.
        candidate_generator : Optional[Callable]
            Custom candidate generation function (defaults to generate_forward_candidates).
        trace_session : Optional[ProofTraceSession]
            Optional telemetry session to record and label proof traces.

        Returns
        -------
        SearchResult
            Complete execution results and reconstructed proof path.
        """
        t0 = time.perf_counter()
        generator = candidate_generator or generate_forward_candidates

        node_registry: Dict[int, SearchNode] = {}
        open_queue: List[SearchNode] = []
        visited_states: Set[str] = set()

        state_counter = 1
        steps_expanded = 0
        nodes_generated = 1
        search_stalled = False

        # Compute initial heuristic cost
        if self.config.guided:
            initial_h = 1.0
            for b in initial_beliefs:
                s = self.cache.get_or_compute(
                    b, goal, lambda c, g: compute_v1_score(c, g, self.tier1_config)
                )
                initial_h = min(initial_h, max(0.0, 1.0 - s))
        else:
            initial_h = 0.0

        root_node = SearchNode(
            state_id=state_counter,
            tasks=list(initial_tasks),
            beliefs=list(initial_beliefs),
            g_cost=0.0,
            h_cost=initial_h,
            f_cost=initial_h,
            depth=0,
            parent_id=None,
            action=None,
            step_created=0,
        )

        heapq.heappush(open_queue, root_node)
        node_registry[root_node.state_id] = root_node

        if self.config.deduplicate_beliefs:
            visited_states.add(hash_belief_state(initial_beliefs))

        while open_queue and steps_expanded < self.config.max_steps:
            current_node = heapq.heappop(open_queue)
            steps_expanded += 1

            # 1. Goal satisfaction check
            for belief in current_node.beliefs:
                if matches_goal(belief, goal):
                    proof = extract_proof_path(current_node, node_registry)
                    final_stamp: Optional[List[str]] = None
                    if isinstance(belief, (list, tuple)) and len(belief) >= 3:
                        raw_stamp = belief[2]
                        if isinstance(raw_stamp, (list, tuple)):
                            final_stamp = [str(x) for x in raw_stamp]
                    if trace_session:
                        trace_session.finalize(final_stamp)

                    elapsed = time.perf_counter() - t0
                    return SearchResult(
                        goal_found=True,
                        final_node=current_node,
                        proof_path=proof,
                        goal_sentence=belief,
                        steps_expanded=steps_expanded,
                        nodes_generated=nodes_generated,
                        visited_states_count=len(visited_states),
                        wall_clock_seconds=round(elapsed, 4),
                        stalled=search_stalled,
                        proof_trace=trace_session.steps if trace_session else [],
                    )

            # 2. Candidate generation
            candidates = generator(current_node.tasks, current_node.beliefs)
            if not candidates:
                continue

            # 3. Score and prioritize candidates
            if self.config.guided:
                scored_candidates = []
                for candidate in candidates:
                    score = self.cache.get_or_compute(
                        candidate,
                        goal,
                        lambda c, g: compute_v1_score(c, g, self.tier1_config),
                    )
                    scored_candidates.append((score, candidate))

                # Sort descending by score
                scored_candidates.sort(key=lambda x: -x[0])

                # Check stall condition
                top_score = scored_candidates[0][0] if scored_candidates else 0.0
                if top_score < self.config.stall_threshold:
                    search_stalled = True

                top_k = scored_candidates[: self.config.beam_width]
            else:
                top_k = [(0.0, c) for c in candidates[: self.config.beam_width]]

            # 4. Expand top-k beam candidates
            for score, candidate in top_k:
                if trace_session:
                    trace_session.record_step(
                        step=steps_expanded,
                        sentence_expr=candidate,
                        candidate_pool_size=len(candidates),
                    )

                new_tasks, new_beliefs = apply_candidate(
                    candidate, current_node.tasks, current_node.beliefs
                )

                # Closed set check
                if self.config.deduplicate_beliefs:
                    b_hash = hash_belief_state(new_beliefs)
                    if b_hash in visited_states:
                        continue
                    visited_states.add(b_hash)

                # Action cost computation
                conf = extract_confidence(candidate, self.tier1_config.default_confidence)
                step_cost = max(
                    self.config.min_step_cost,
                    (1.0 - conf) * self.config.cost_confidence_weight,
                )

                new_g = current_node.g_cost + step_cost
                new_h = max(0.0, 1.0 - score) if self.config.guided else 0.0
                new_f = new_g + new_h

                state_counter += 1
                nodes_generated += 1

                successor = SearchNode(
                    state_id=state_counter,
                    tasks=new_tasks,
                    beliefs=new_beliefs,
                    g_cost=round(new_g, 4),
                    h_cost=round(new_h, 4),
                    f_cost=round(new_f, 4),
                    depth=current_node.depth + 1,
                    parent_id=current_node.state_id,
                    action=candidate,
                    step_created=steps_expanded,
                )

                node_registry[successor.state_id] = successor
                heapq.heappush(open_queue, successor)

        elapsed = time.perf_counter() - t0
        if trace_session:
            trace_session.finalize(None)

        return SearchResult(
            goal_found=False,
            final_node=None,
            proof_path=[],
            goal_sentence=None,
            steps_expanded=steps_expanded,
            nodes_generated=nodes_generated,
            visited_states_count=len(visited_states),
            wall_clock_seconds=round(elapsed, 4),
            stalled=search_stalled,
            proof_trace=trace_session.steps if trace_session else [],
        )
