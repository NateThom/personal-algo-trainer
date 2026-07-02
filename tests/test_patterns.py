from algotrainer.patterns import (
    PATTERNS, pattern_meta, confusable_group, roadmap_order,
)


def test_seed_patterns_present():
    ids = {p.id for p in PATTERNS}
    assert {"arrays-hashing", "sliding-window", "two-pointers"} <= ids


def test_canonical_taxonomy_of_18():
    ids = {p.id for p in PATTERNS}
    assert len(PATTERNS) == 18
    # the five patterns added to complete the canonical set
    assert {"prefix-sum", "intervals", "union-find",
            "topological-sort", "bit-manipulation"} <= ids


def test_graph_family_confusable_symmetric():
    assert "union-find" in confusable_group("graphs")
    assert "graphs" in confusable_group("union-find")
    assert "topological-sort" in confusable_group("graphs")
    assert "graphs" in confusable_group("topological-sort")


def test_orders_are_unique_and_ascending_start():
    orders = [p.order for p in PATTERNS]
    assert len(orders) == len(set(orders))  # unique
    assert min(orders) == 1


def test_confusable_is_symmetric():
    # sliding-window and two-pointers are declared confusable
    assert "two-pointers" in confusable_group("sliding-window")
    assert "sliding-window" in confusable_group("two-pointers")


def test_group_includes_self():
    assert "arrays-hashing" in confusable_group("arrays-hashing")


def test_roadmap_order_unknown_sentinel():
    assert roadmap_order("does-not-exist") == 10_000
    assert roadmap_order("arrays-hashing") == pattern_meta("arrays-hashing").order
