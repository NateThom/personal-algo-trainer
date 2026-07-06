from collections import Counter

from algotrainer.content import load_problems, load_problem
from algotrainer.mastery import GATE_BREADTH
from algotrainer.patterns import PATTERNS


def test_loads_all_seed_problems():
    problems = load_problems()
    ids = {p.id for p in problems}
    assert {"two-sum", "valid-anagram", "contains-duplicate",
            "best-time-to-buy-sell-stock"} <= ids


def test_load_single_problem():
    p = load_problem("two-sum")
    assert p.function_name == "two_sum"


def test_every_reference_solution_passes_its_own_tests():
    # loader must validate self-consistency and not raise
    problems = load_problems()
    assert len(problems) >= 4


def test_every_pattern_has_gate_breadth_seed_problems():
    counts = Counter(p.pattern for p in load_problems())
    short = {m.id: counts[m.id] for m in PATTERNS if counts[m.id] < GATE_BREADTH}
    assert not short, f"patterns below gate breadth ({GATE_BREADTH}): {short}"


def test_all_seed_problems_have_unique_ids_and_three_hints():
    problems = load_problems()
    ids = [p.id for p in problems]
    assert len(ids) == len(set(ids))
    no_three = [p.id for p in problems if len(p.hints) != 3]
    assert not no_three, f"problems without exactly 3 hint tiers: {no_three}"
