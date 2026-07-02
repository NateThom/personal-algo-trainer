from algotrainer.composer import compose_order


def test_empty():
    plan = compose_order([], {}, set(), {})
    assert plan.order == []
    assert plan.blocked_ratio == 0.0


def test_blocked_patterns_grouped_first():
    due = ["a1", "b1", "a2"]           # patterns: a, b, a
    pp = {"a1": "a", "a2": "a", "b1": "b"}
    # 'a' is immature -> its problems blocked (contiguous, first); 'b' interleaved
    plan = compose_order(due, pp, immature={"a"}, error_weight={})
    assert plan.order[:2] == ["a1", "a2"]   # a-block contiguous and first
    assert plan.order[2] == "b1"
    assert plan.blocked_ratio == 2 / 3


def test_weakest_pattern_first_by_error_weight():
    due = ["a1", "b1"]
    pp = {"a1": "a", "b1": "b"}
    # both mature (interleaved); b has more errors -> comes first
    plan = compose_order(due, pp, immature=set(), error_weight={"b": 5, "a": 1})
    assert plan.order[0] == "b1"


def test_interleaving_alternates_patterns():
    due = ["a1", "a2", "b1", "b2"]
    pp = {"a1": "a", "a2": "a", "b1": "b", "b2": "b"}
    plan = compose_order(due, pp, immature=set(), error_weight={})
    # round-robin => patterns alternate, not blocked
    patterns_seq = [pp[x] for x in plan.order]
    assert patterns_seq == ["a", "b", "a", "b"]
    assert plan.blocked_ratio == 0.0
