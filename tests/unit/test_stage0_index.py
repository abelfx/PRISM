"""
Unit tests for PRISM Stage 0 Indexed Premise Pre-Filter.
Verifies concept indexing, candidate/goal lookup, and sound filtering of beliefs.
"""

from prism.stage0.index import PremiseIndex, extract_statement_components


def test_extract_statement_components():
    """Verify extraction of link type and concepts from statement."""
    s1 = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.9]], [1]]
    link, concepts = extract_statement_components(s1)
    assert link == 'Inheritance'
    assert concepts == {'A', 'B'}

    # Nested or malformed
    _link2, concepts2 = extract_statement_components(['Sentence', ['A', ['stv', 1, 1]], [1]])
    assert 'A' in concepts2


def test_index_add_and_lookup():
    """Verify PremiseIndex adds sentences and retrieves by goal concept."""
    idx = PremiseIndex()
    b1 = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.9]], [1]]
    b2 = ['Sentence', [['Inheritance', 'B', 'C'], ['stv', 0.9, 0.9]], [2]]
    b3 = ['Sentence', [['Inheritance', 'X', 'Y'], ['stv', 0.9, 0.9]], [3]]

    idx.add(b1)
    idx.add(b2)
    idx.add(b3)

    # Goal is (Inheritance A C)
    goal = ['Inheritance', 'A', 'C']
    results = idx.lookup_by_goal(goal)
    # b1 has 'A', b2 has 'C' -> both should be returned
    assert b1 in results
    assert b2 in results
    # b3 has 'X' and 'Y' -> should NOT be returned
    assert b3 not in results


def test_filter_beliefs():
    """Verify filter_beliefs includes all candidate-unifiable premises and filters distractors."""
    idx = PremiseIndex()
    cand = ['Sentence', [['Inheritance', 'A', 'B'], ['stv', 0.9, 0.9]], [1]]
    goal = ['Inheritance', 'A', 'F']

    on_path_belief = ['Sentence', [['Inheritance', 'B', 'C'], ['stv', 0.9, 0.9]], [2]]
    distractor_belief = ['Sentence', [['Inheritance', 'Distractor1', 'Distractor2'], ['stv', 0.9, 0.9]], [3]]
    beliefs = [on_path_belief, distractor_belief]

    filtered = idx.filter_beliefs(candidate=cand, goal=goal, beliefs=beliefs)

    # on_path_belief shares 'B' with candidate, so it MUST be included
    assert on_path_belief in filtered
    # distractor_belief shares no concept with candidate or goal -> must be excluded
    assert distractor_belief not in filtered


def test_filter_beliefs_empty_and_fallback():
    """Verify safe fallbacks on empty inputs or no matches."""
    idx = PremiseIndex()
    b1 = ['Sentence', [['Inheritance', 'X', 'Y'], ['stv', 0.9, 0.9]], [1]]

    # Empty beliefs returns empty list
    assert idx.filter_beliefs(candidate=None, goal=None, beliefs=[]) == []

    # Empty goal and empty candidate returns all beliefs unchanged
    assert idx.filter_beliefs(candidate=None, goal=None, beliefs=[b1]) == [b1]

    # No match at all falls back to all beliefs to prevent search halt
    unrelated_cand = ['Sentence', [['Inheritance', 'Q', 'R'], ['stv', 0.9, 0.9]], [2]]
    unrelated_goal = ['Inheritance', 'M', 'N']
    fallback_res = idx.filter_beliefs(candidate=unrelated_cand, goal=unrelated_goal, beliefs=[b1])
    assert fallback_res == [b1]

