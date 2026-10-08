"""Rank OpenPsi-produced successor states without executing or inventing rules.

The input rule atoms and successor pairs come from the live OpenPsi rule space
and its ``applyCurrentActions`` function.  This module only chooses which
already-applicable transition to explore next.
"""

from collections import deque
from math import isfinite
from typing import Any


def _goal_name(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2 and value[0] == "Goal":
        return str(value[1])
    return str(value)


def _transition(rule: Any) -> tuple[str, str] | None:
    """Read the existing OpenPsi cognitive-schema shape; never infer an edge."""
    try:
        schema = rule[0][2][1]
        if schema[0] != "IMPLICATION_LINK":
            return None
        context = schema[1][1][0]
        target = schema[2]
        if context[0] != "Goal" or target[0] != "Goal":
            return None
        return _goal_name(context), _goal_name(target)
    except (IndexError, TypeError, KeyError):
        return None


def _distances(goal: str, rules: Any) -> dict[str, int]:
    reverse: dict[str, set[str]] = {}
    for rule in rules:
        edge = _transition(rule)
        if edge is not None:
            source, target = edge
            reverse.setdefault(target, set()).add(source)
    distances = {goal: 0}
    queue = deque([goal])
    while queue:
        target = queue.popleft()
        for source in reverse.get(target, ()):
            if source not in distances:
                distances[source] = distances[target] + 1
                queue.append(source)
    return distances


def best_successor(successors: Any, goal: Any, rules: Any, visited: Any = ()) -> Any:
    """Return an original ``(action, next-state)`` pair, or ``None``.

    Unreachable candidates are never promoted; the caller then uses OpenPsi's
    original selector.  Stable input order breaks equal-distance ties.
    """
    if not isinstance(successors, (list, tuple)) or not isinstance(rules, (list, tuple)):
        return None
    blocked = {_goal_name(state) for state in visited} if isinstance(visited, (list, tuple)) else set()
    distances = _distances(_goal_name(goal), rules)
    ranked = []
    for index, pair in enumerate(successors):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        distance = distances.get(_goal_name(pair[1]))
        if distance is not None and isfinite(distance) and _goal_name(pair[1]) not in blocked:
            ranked.append((distance, index, pair))
    return min(ranked)[2] if ranked else None
