"""
Bidirectional A* Search Engine Subsystem for PRISM (§9).

Maintains dual search frontiers:
  - Forward Frontier: expands known premises toward the derivation goal via forward deduction rules.
  - Backward Frontier: expands required subgoals backward from the goal toward base premises via rule inversion.

Interleaves frontier expansions, detects meet-in-the-middle convergence via check_connection,
and stitches dual proof paths into a unified, forward-executable PLN proof trace.
"""

from collections import deque
import heapq
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from prism.core.config import (
    DEFAULT_CONFIG,
    BidirectionalConfig,
    SearchConfig,
    Tier1Config,
)
from prism.search.backward import (
    backward_step,
    check_connection,
    compute_backward_score,
)
from prism.search.engine import SearchResult
from prism.search.rules import (
    apply_candidate,
    generate_forward_candidates,
    parse_sentence,
)
from prism.adapters.petta.runtime import apply_pln_sentences, infer_concept_stvs
from prism.search.state import (
    BidirectionalSearchNode,
    BidirectionalSearchResult,
    SearchNode,
    extract_proof_path,
    extract_statement_term,
    hash_belief_state,
    matches_goal,
    normalize_term_str,
)
from prism.core.cache import ScoreCache
from prism.tier1.heuristic_v1 import compute_v1_score, extract_confidence
from prism.tier2.reasoner import Tier2Reasoner


def stitch_proof_traces(
    forward_path: List[SearchNode],
    backward_leaf_id: int,
    backward_nodes: Dict[int, SearchNode],
    backward_decompositions: Dict[int, Tuple[Any, Tuple[Any, ...], Tuple[Any, ...]]],
    goal: Any,
    concept_stvs: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Tuple[List[SearchNode], Optional[Any]]:
    """
    Stitch a forward derivation path with an inverted backward path (§9.3).

    Takes the forward path reaching meeting lemma M and forward-executes the
    backward reductions that led from G down to M.

    Parameters
    ----------
    forward_path : List[SearchNode]
        Derivation path from root premises to the meeting node.
    backward_leaf_id : int
        state_id of the backward node where connection was established.
    backward_nodes : Dict[int, SearchNode]
        Registry of all backward search nodes.
    backward_decompositions : Dict[int, Tuple[Any, Tuple[Any, ...], Tuple[Any, ...]]]
        Mapping: child_state_id -> (target_subgoal, available_premises, missing_premises).
    goal : Any
        The original query goal.

    Returns
    -------
    Tuple[List[SearchNode], Optional[Any]]
        (stitched_path, final_goal_sentence).
    """
    if not forward_path:
        return [], None

    stitched_path: List[SearchNode] = list(forward_path)
    current_node = forward_path[-1]

    # Reconstruct backward chain from meeting node up to backward root
    bwd_chain_up: List[int] = []
    curr_id: Optional[int] = backward_leaf_id
    while curr_id is not None and curr_id in backward_nodes:
        bwd_chain_up.append(curr_id)
        node = backward_nodes[curr_id]
        if node.parent_id is None:
            break
        curr_id = node.parent_id

    # If the backward root is itself the meeting node (or no backward steps were taken)
    if len(bwd_chain_up) <= 1 and not backward_decompositions:
        # Check if the last forward node already contains the goal
        for b in current_node.beliefs:
            if matches_goal(b, goal):
                return stitched_path, b
        return stitched_path, current_node.action

    # Reverse to go from meeting point toward goal:
    # bwd_chain_up is [leaf, parent, ..., root].
    # Reversing gives [root, ..., parent, leaf].
    # But for forward execution, we want child -> parent transitions:
    # Leaf was reduced from its parent, which was reduced from its grandparent...
    # So we walk backwards from leaf to root:
    # child = bwd_chain_up[0] (leaf), parent = bwd_chain_up[1], etc.
    active_lemma = current_node.action
    if active_lemma is None and current_node.beliefs:
        active_lemma = current_node.beliefs[-1]

    state_id_alloc = max([n.state_id for n in stitched_path], default=1000) + 1

    for child_id in bwd_chain_up:
        if child_id not in backward_decompositions:
            continue
        parent_subgoal, available_premises, missing_premises = backward_decompositions[child_id]

        parsed_lemma = parse_sentence(active_lemma)
        if not parsed_lemma:
            continue

        derived_step = None
        for avail in available_premises:
            derived = apply_pln_sentences(active_lemma, avail, concept_stvs)
            if not derived:
                derived = apply_pln_sentences(avail, active_lemma, concept_stvs)
            if derived:
                derived_step = derived
                break

        if not derived_step:
            # Illegal PLN step: do not adopt an unproven parent subgoal.
            continue

        active_lemma = derived_step
        new_tasks, new_beliefs = apply_candidate(
            derived_step, current_node.tasks, current_node.beliefs
        )

        conf = extract_confidence(derived_step, DEFAULT_CONFIG.tier1.default_confidence)
        step_cost = max(0.01, (1.0 - conf))

        new_node = SearchNode(
            state_id=state_id_alloc,
            tasks=new_tasks,
            beliefs=new_beliefs,
            g_cost=round(current_node.g_cost + step_cost, 4),
            h_cost=0.0,
            f_cost=round(current_node.g_cost + step_cost, 4),
            depth=current_node.depth + 1,
            parent_id=current_node.state_id,
            action=derived_step,
            step_created=current_node.step_created + 1,
        )
        state_id_alloc += 1
        stitched_path.append(new_node)
        current_node = new_node

    # Find the matching goal sentence in the final node beliefs
    goal_sentence = None
    for b in current_node.beliefs:
        if matches_goal(b, goal):
            goal_sentence = b
            break
    if goal_sentence is None:
        goal_sentence = current_node.action

    return stitched_path, goal_sentence


class BidirectionalSearchEngine:
    """
    Bidirectional A* Search Engine with dual-frontier interleaving.

    Attributes
    ----------
    config : BidirectionalConfig
        Bidirectional control hyperparameters.
    search_config : SearchConfig
        Underlying A* search settings.
    tier1_config : Tier1Config
        Heuristic scoring weights and defaults.
    tier2_reasoner : Optional[Tier2Reasoner]
        Strategic LLM reasoner for stall recovery.
    cache : ScoreCache
        Memoization cache for forward and backward heuristic evaluations.
    """

    def __init__(
        self,
        config: Optional[BidirectionalConfig] = None,
        search_config: Optional[SearchConfig] = None,
        tier1_config: Optional[Tier1Config] = None,
        tier2_reasoner: Optional[Tier2Reasoner] = None,
        cache_size: int = 5000,
    ) -> None:
        self.config = config or DEFAULT_CONFIG.bidirectional
        self.search_config = search_config or DEFAULT_CONFIG.search
        self.tier1_config = tier1_config or DEFAULT_CONFIG.tier1
        self.tier2_reasoner = tier2_reasoner
        self.cache = ScoreCache()

    def search(
        self,
        goal: Any,
        beliefs: Sequence[Any],
        tasks: Optional[Sequence[Any]] = None,
        max_steps: Optional[int] = None,
        concept_stvs: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> BidirectionalSearchResult:
        """
        Execute dual-frontier bidirectional A* search toward goal (§9.1).

        Parameters
        ----------
        goal : Any
            Target statement to derive (e.g. ['Inheritance', 'A', 'Z']).
        beliefs : Sequence[Any]
            Initial known facts and axioms.
        tasks : Optional[Sequence[Any]]
            Active candidate tasks (defaults to beliefs).
        max_steps : Optional[int]
            Maximum combined derivation steps budget.

        Returns
        -------
        BidirectionalSearchResult
            Detailed derivation result with meeting lemma and stitched proof trace.
        """
        start_time = time.perf_counter()
        step_budget = max_steps or self.config.max_steps

        initial_beliefs = list(beliefs)
        initial_tasks = list(tasks) if tasks is not None else list(beliefs)
        stvs = dict(concept_stvs or {})
        inferred = infer_concept_stvs(initial_beliefs + initial_tasks)
        for name, tv in inferred.items():
            stvs.setdefault(name, tv)
        self._concept_stvs = stvs

        # 0. Immediate goal check in initial beliefs
        for b in initial_beliefs:
            if matches_goal(b, goal):
                elapsed = time.perf_counter() - start_time
                root_node = SearchNode(
                    state_id=0,
                    tasks=initial_tasks,
                    beliefs=initial_beliefs,
                    g_cost=0.0,
                    h_cost=0.0,
                    f_cost=0.0,
                    depth=0,
                )
                return BidirectionalSearchResult(
                    goal_found=True,
                    meeting_point=b,
                    proof_path=[root_node],
                    goal_sentence=b,
                    steps_expanded=0,
                    forward_steps=0,
                    backward_steps=0,
                    nodes_generated=1,
                    visited_states_count=1,
                    wall_clock_seconds=round(elapsed, 4),
                    stalled=False,
                )

        # 1. Initialize Forward Frontier
        forward_open: List[SearchNode] = []
        forward_nodes: Dict[int, SearchNode] = {}
        forward_visited: Set[str] = set()

        root_fwd = SearchNode(
            state_id=0,
            tasks=initial_tasks,
            beliefs=initial_beliefs,
            g_cost=0.0,
            h_cost=1.0,
            f_cost=1.0,
            depth=0,
        )
        heapq.heappush(forward_open, root_fwd)
        forward_nodes[0] = root_fwd
        forward_visited.add(hash_belief_state(initial_beliefs))

        # 2. Initialize Backward Frontier
        backward_open: List[SearchNode] = []
        backward_nodes: Dict[int, SearchNode] = {}
        backward_visited: Set[str] = set()
        subgoals_by_state: Dict[int, List[Any]] = {}
        backward_decompositions: Dict[int, Tuple[Any, Tuple[Any, ...], Tuple[Any, ...]]] = {}

        initial_bwd_score = compute_backward_score(goal, initial_beliefs, self.tier1_config)
        root_bwd = SearchNode(
            state_id=1,
            tasks=[],
            beliefs=initial_beliefs,
            g_cost=0.0,
            h_cost=round(max(0.0, 1.0 - initial_bwd_score), 4),
            f_cost=round(max(0.0, 1.0 - initial_bwd_score), 4),
            depth=0,
            action=goal,
        )
        heapq.heappush(backward_open, root_bwd)
        backward_nodes[1] = root_bwd
        subgoals_by_state[1] = [goal]
        backward_visited.add(normalize_term_str(extract_statement_term(goal)))

        state_counter = 1
        steps_expanded = 0
        forward_steps = 0
        backward_steps = 0
        nodes_generated = 2
        search_stalled = False
        subgoals_proposed: List[Any] = []

        # Interleaving turn counter (ratio of forward to backward)
        fwd_turns = 0
        bwd_turns = 0

        # 3. Dual-Frontier Search Loop
        while (forward_open or backward_open) and steps_expanded < step_budget:
            # Decide search direction based on forward_backward_ratio
            expand_forward = True
            if forward_open and backward_open:
                target_ratio = self.config.forward_backward_ratio
                current_ratio = fwd_turns / max(1, bwd_turns)
                expand_forward = current_ratio < target_ratio
            elif backward_open:
                expand_forward = False

            # ==========================================
            # A. FORWARD EXPANSION STEP
            # ==========================================
            if expand_forward and forward_open:
                current_fwd = heapq.heappop(forward_open)
                steps_expanded += 1
                forward_steps += 1
                fwd_turns += 1
                check_meet = self._should_check_connection(steps_expanded)

                # Generate forward candidate deductions
                candidates = generate_forward_candidates(
                    current_fwd.tasks,
                    current_fwd.beliefs,
                    goal=goal,
                    use_stage0=self.config.use_stage0_filter,
                    task_selection_k=self.search_config.task_selection_k,
                    concept_stvs=self._concept_stvs,
                )

                if not candidates:
                    if self.tier2_reasoner and self.tier2_reasoner.check_stall(
                        0.0, current_depth=current_fwd.depth
                    ):
                        search_stalled = True
                        subgoal_res = self._invoke_tier2(goal, current_fwd, subgoals_proposed)
                        if subgoal_res:
                            # Seed both frontiers
                            injected = self._seed_waypoint(
                                subgoal_res,
                                forward_open,
                                backward_open,
                                forward_nodes,
                                backward_nodes,
                                subgoals_by_state,
                                current_fwd,
                                initial_beliefs,
                            )
                            if injected:
                                candidates = [injected]
                    if not candidates:
                        continue

                # Score candidates with Tier 1
                scored_candidates = []
                for cand in candidates:
                    score = self.cache.get_or_compute(
                        cand,
                        goal,
                        lambda c, g: compute_v1_score(c, g, self.tier1_config),
                    )
                    scored_candidates.append((score, cand))

                scored_candidates.sort(key=lambda x: -x[0])

                # Check stall condition
                top_score = scored_candidates[0][0] if scored_candidates else 0.0
                if top_score < self.search_config.stall_threshold:
                    search_stalled = True
                    if self.tier2_reasoner and self.tier2_reasoner.check_stall(
                        top_score, current_depth=current_fwd.depth
                    ):
                        subgoal_res = self._invoke_tier2(goal, current_fwd, subgoals_proposed)
                        if subgoal_res:
                            self._seed_waypoint(
                                subgoal_res,
                                forward_open,
                                backward_open,
                                forward_nodes,
                                backward_nodes,
                                subgoals_by_state,
                                current_fwd,
                                initial_beliefs,
                            )

                # Expand top candidates
                for score, cand in scored_candidates[: self.search_config.beam_width]:
                    # 1. Direct Goal Satisfaction Check
                    if matches_goal(cand, goal):
                        new_tasks, new_beliefs = apply_candidate(
                            cand, current_fwd.tasks, current_fwd.beliefs
                        )
                        state_counter += 1
                        nodes_generated += 1
                        goal_node = SearchNode(
                            state_id=state_counter,
                            tasks=new_tasks,
                            beliefs=new_beliefs,
                            g_cost=round(current_fwd.g_cost + 0.01, 4),
                            h_cost=0.0,
                            f_cost=round(current_fwd.g_cost + 0.01, 4),
                            depth=current_fwd.depth + 1,
                            parent_id=current_fwd.state_id,
                            action=cand,
                            step_created=steps_expanded,
                        )
                        forward_nodes[state_counter] = goal_node
                        fwd_path = extract_proof_path(goal_node, forward_nodes)
                        elapsed = time.perf_counter() - start_time
                        return BidirectionalSearchResult(
                            goal_found=True,
                            meeting_point=cand,
                            proof_path=fwd_path,
                            goal_sentence=cand,
                            steps_expanded=steps_expanded,
                            forward_steps=forward_steps,
                            backward_steps=backward_steps,
                            nodes_generated=nodes_generated,
                            visited_states_count=len(forward_visited) + len(backward_visited),
                            wall_clock_seconds=round(elapsed, 4),
                            stalled=search_stalled,
                            subgoals_proposed=subgoals_proposed,
                        )

                    # 2. Check Connection with Active Backward Subgoals
                    connection_found = None
                    matched_bwd_id = None
                    if check_meet:
                        for bwd_id, subgoals in subgoals_by_state.items():
                            conn = check_connection([cand], subgoals)
                            if conn:
                                connection_found = conn
                                matched_bwd_id = bwd_id
                                break

                    if connection_found and matched_bwd_id is not None:
                        meeting_belief, matched_subgoal = connection_found
                        new_tasks, new_beliefs = apply_candidate(
                            cand, current_fwd.tasks, current_fwd.beliefs
                        )
                        state_counter += 1
                        nodes_generated += 1
                        meeting_node = SearchNode(
                            state_id=state_counter,
                            tasks=new_tasks,
                            beliefs=new_beliefs,
                            g_cost=round(current_fwd.g_cost + 0.01, 4),
                            h_cost=0.0,
                            f_cost=round(current_fwd.g_cost + 0.01, 4),
                            depth=current_fwd.depth + 1,
                            parent_id=current_fwd.state_id,
                            action=cand,
                            step_created=steps_expanded,
                        )
                        forward_nodes[state_counter] = meeting_node
                        fwd_path = extract_proof_path(meeting_node, forward_nodes)

                        stitched, final_goal_sent = stitch_proof_traces(
                            fwd_path,
                            matched_bwd_id,
                            backward_nodes,
                            backward_decompositions,
                            goal,
                            concept_stvs=self._concept_stvs,
                        )
                        elapsed = time.perf_counter() - start_time
                        return BidirectionalSearchResult(
                            goal_found=True,
                            meeting_point=cand,
                            proof_path=stitched,
                            goal_sentence=final_goal_sent,
                            steps_expanded=steps_expanded,
                            forward_steps=forward_steps,
                            backward_steps=backward_steps,
                            nodes_generated=nodes_generated,
                            visited_states_count=len(forward_visited) + len(backward_visited),
                            wall_clock_seconds=round(elapsed, 4),
                            stalled=search_stalled,
                            subgoals_proposed=subgoals_proposed,
                        )

                    # Form forward child node
                    new_tasks, new_beliefs = apply_candidate(
                        cand, current_fwd.tasks, current_fwd.beliefs
                    )
                    b_hash = hash_belief_state(new_beliefs)
                    if b_hash in forward_visited:
                        continue
                    forward_visited.add(b_hash)

                    conf = extract_confidence(cand, self.tier1_config.default_confidence)
                    step_cost = max(
                        self.search_config.min_step_cost,
                        (1.0 - conf) * self.search_config.cost_confidence_weight,
                    )
                    new_g = current_fwd.g_cost + step_cost
                    new_h = max(0.0, 1.0 - score)
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
                        depth=current_fwd.depth + 1,
                        parent_id=current_fwd.state_id,
                        action=cand,
                        step_created=steps_expanded,
                    )
                    forward_nodes[state_counter] = successor
                    heapq.heappush(forward_open, successor)

            # ==========================================
            # B. BACKWARD EXPANSION STEP
            # ==========================================
            elif backward_open:
                current_bwd = heapq.heappop(backward_open)
                if current_bwd.depth >= self.config.max_backward_depth:
                    continue
                steps_expanded += 1
                backward_steps += 1
                bwd_turns += 1
                check_meet = self._should_check_connection(steps_expanded)

                active_subgoals = subgoals_by_state.get(current_bwd.state_id, [])
                if not active_subgoals:
                    continue

                for sg in active_subgoals:
                    # Decompose subgoal via rule inversion
                    bwd_candidates = backward_step(sg, initial_beliefs)
                    if not bwd_candidates:
                        continue

                    # The forward frontier already grows outward from the
                    # query subject. Keep the backward frontier directional:
                    # regress the target object toward that subject instead
                    # of duplicating forward-prefix exploration.
                    parsed_target = parse_sentence(sg)
                    if parsed_target:
                        regressive = [
                            candidate
                            for candidate in bwd_candidates
                            if any(
                                (parsed_missing := parse_sentence(missing)) is not None
                                and parsed_missing.subject == parsed_target.subject
                                for missing in candidate.missing_premises
                            )
                        ]
                        if regressive:
                            bwd_candidates = regressive

                    # Sort by completeness and heuristic score
                    for b_cand in bwd_candidates[: self.config.backward_beam_width]:
                        if not b_cand.missing_premises:
                            # Subgoal is already completely supported by available premises
                            continue

                        # Each missing premise forms a new subgoal state
                        for missing in b_cand.missing_premises:
                            missing_term = normalize_term_str(extract_statement_term(missing))
                            if missing_term in backward_visited:
                                continue
                            backward_visited.add(missing_term)

                            new_depth = current_bwd.depth + 1
                            if new_depth > self.config.max_backward_depth:
                                continue

                            # Check if forward frontier already derived this missing premise
                            conn_found = None
                            matched_fwd_node = None
                            if check_meet:
                                for fwd_id, fwd_node in forward_nodes.items():
                                    conn = check_connection(fwd_node.beliefs, [missing])
                                    if conn:
                                        conn_found = conn
                                        matched_fwd_node = fwd_node
                                        break

                            state_counter += 1
                            nodes_generated += 1
                            bwd_score = compute_backward_score(
                                missing, initial_beliefs, self.tier1_config, depth=new_depth
                            )
                            step_cost = 0.10 * (1.0 - b_cand.completeness)
                            bwd_g = current_bwd.g_cost + step_cost
                            bwd_h = max(0.0, 1.0 - bwd_score)
                            bwd_f = bwd_g + bwd_h

                            bwd_child = SearchNode(
                                state_id=state_counter,
                                tasks=[],
                                beliefs=initial_beliefs,
                                g_cost=round(bwd_g, 4),
                                h_cost=round(bwd_h, 4),
                                f_cost=round(bwd_f, 4),
                                depth=new_depth,
                                parent_id=current_bwd.state_id,
                                action=missing,
                                step_created=steps_expanded,
                            )
                            backward_nodes[state_counter] = bwd_child
                            subgoals_by_state[state_counter] = [missing]
                            backward_decompositions[state_counter] = (
                                sg,
                                b_cand.available_premises,
                                b_cand.missing_premises,
                            )

                            if conn_found and matched_fwd_node is not None:
                                # Connection detected!
                                meeting_belief, _ = conn_found
                                fwd_path = extract_proof_path(matched_fwd_node, forward_nodes)
                                stitched, final_goal_sent = stitch_proof_traces(
                                    fwd_path,
                                    state_counter,
                                    backward_nodes,
                                    backward_decompositions,
                                    goal,
                                    concept_stvs=self._concept_stvs,
                                )
                                elapsed = time.perf_counter() - start_time
                                return BidirectionalSearchResult(
                                    goal_found=True,
                                    meeting_point=meeting_belief,
                                    proof_path=stitched,
                                    goal_sentence=final_goal_sent,
                                    steps_expanded=steps_expanded,
                                    forward_steps=forward_steps,
                                    backward_steps=backward_steps,
                                    nodes_generated=nodes_generated,
                                    visited_states_count=len(forward_visited) + len(backward_visited),
                                    wall_clock_seconds=round(elapsed, 4),
                                    stalled=search_stalled,
                                    subgoals_proposed=subgoals_proposed,
                                )

                            heapq.heappush(backward_open, bwd_child)

        elapsed = time.perf_counter() - start_time
        return BidirectionalSearchResult(
            goal_found=False,
            meeting_point=None,
            proof_path=[],
            goal_sentence=None,
            steps_expanded=steps_expanded,
            forward_steps=forward_steps,
            backward_steps=backward_steps,
            nodes_generated=nodes_generated,
            visited_states_count=len(forward_visited) + len(backward_visited),
            wall_clock_seconds=round(elapsed, 4),
            stalled=search_stalled,
            subgoals_proposed=subgoals_proposed,
        )

    def _should_check_connection(self, steps_expanded: int) -> bool:
        interval = max(1, int(self.config.connection_check_interval))
        return steps_expanded % interval == 0

    def _invoke_tier2(
        self,
        goal: Any,
        node: SearchNode,
        subgoals_proposed: List[Any],
    ) -> Optional[Any]:
        """Invoke Tier 2 reasoner to generate intermediate bridging subgoal."""
        if not self.tier2_reasoner:
            return None

        from prism.stage0.index import extract_concepts

        domain_concepts = set()
        for b in node.beliefs:
            domain_concepts |= extract_concepts(b)
        domain_concepts |= extract_concepts(goal)

        res = self.tier2_reasoner.propose_subgoal(
            goal=goal,
            beliefs=node.beliefs,
            recent_derivations=[node.action] if node.action else None,
            domain_concepts=domain_concepts,
        )
        if res:
            subgoals_proposed.append(res)
        return res

    def _seed_waypoint(
        self,
        subgoal_res: Any,
        forward_open: List[SearchNode],
        backward_open: List[SearchNode],
        forward_nodes: Dict[int, SearchNode],
        backward_nodes: Dict[int, SearchNode],
        subgoals_by_state: Dict[int, List[Any]],
        current_fwd: SearchNode,
        initial_beliefs: List[Any],
    ) -> Optional[Any]:
        """Seed the backward frontier with a subgoal. Derive via PLN only if premises exist."""
        derived_sentence = None
        target = subgoal_res.subgoal
        if target:
            state_id = len(forward_nodes) + len(backward_nodes) + 1000
            bwd_node = SearchNode(
                state_id=state_id,
                tasks=[],
                beliefs=list(current_fwd.beliefs),
                g_cost=current_fwd.g_cost + 0.05,
                h_cost=0.5,
                f_cost=current_fwd.g_cost + 0.55,
                depth=current_fwd.depth + 1,
                parent_id=current_fwd.state_id,
                action=target,
            )
            backward_nodes[state_id] = bwd_node
            subgoals_by_state[state_id] = [target]
            heapq.heappush(backward_open, bwd_node)

            for decomp in backward_step(target, current_fwd.beliefs):
                if decomp.completeness < 1.0 or len(decomp.available_premises) < 2:
                    continue
                derived_sentence = apply_pln_sentences(
                    decomp.available_premises[0],
                    decomp.available_premises[1],
                    getattr(self, "_concept_stvs", None),
                )
                if derived_sentence:
                    break

        return derived_sentence

