from algotrainer.models import Problem, TestCase


def test_problem_from_dict_builds_testcases():
    d = {
        "id": "two-sum",
        "pattern": "arrays-hashing",
        "title": "Two Sum",
        "difficulty": "easy",
        "statement": "Return indices of the two numbers that add to target.",
        "function_name": "two_sum",
        "starter_code": "def two_sum(nums, target):\n    pass\n",
        "reference_solution": "def two_sum(nums, target):\n    seen={}\n    for i,n in enumerate(nums):\n        if target-n in seen:\n            return [seen[target-n], i]\n        seen[n]=i\n",
        "tests": [{"args": [[2, 7, 11, 15], 9], "expected": [0, 1]}],
        "hints": ["Which pattern maps input to O(1) lookups?"],
    }
    p = Problem.from_dict(d)
    assert p.id == "two-sum"
    assert isinstance(p.tests[0], TestCase)
    assert p.tests[0].args == [[2, 7, 11, 15], 9]
    assert p.tests[0].expected == [0, 1]
