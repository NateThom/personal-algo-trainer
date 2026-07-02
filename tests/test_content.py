from algotrainer.content import load_problems, load_problem


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
