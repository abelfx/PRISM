"""OpenPsi control tests use its actual cognitive-schema term shape."""

from prism.adapters.openpsi.selection import best_successor


def rule(name, source, action, target, weight=1):
    return [
        [
            ":",
            name,
            [
                ["TTV", 1, ["STV", 0.8, 0.7]],
                [
                    "IMPLICATION_LINK",
                    ["AND_LINK", [["Goal", source, 0.9, 0.6], action]],
                    ["Goal", target, 1.0, 1.0],
                ],
            ],
        ],
        weight,
    ]


RULES = [
    rule("decoy", "init", "idle", "deadend", 9),
    rule("first", "init", "explore", "middle", 2),
    rule("second", "middle", "finish", "target", 2),
]


def test_prioritizes_reachable_openpsi_successor():
    candidates = [["idle", "deadend"], ["explore", "middle"]]
    assert best_successor(candidates, "target", RULES) is candidates[1]


def test_never_fabricates_candidate_or_revisits_state():
    candidates = [["idle", "deadend"], ["explore", "middle"]]
    assert best_successor(candidates, "target", RULES, ["middle"]) is None


def test_cycle_terminates_and_selects_shortest_available_path():
    rules = RULES + [rule("loop", "middle", "restart", "init")]
    candidates = [["restart", "init"], ["finish", "target"]]
    assert best_successor(candidates, ["Goal", "target", 1, 1], rules) is candidates[1]


def test_bad_rule_and_bad_successor_fall_back():
    assert best_successor([["idle", "deadend"]], "target", RULES + [["bad"]]) is None
    assert best_successor("invalid", "target", RULES) is None
