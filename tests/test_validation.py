from algotrainer.validation import validate_problem_dict

GOOD = {
    "id": "t", "pattern": "arrays-hashing", "title": "T", "difficulty": "easy",
    "statement": "s", "function_name": "f",
    "starter_code": "def f(x):\n    pass\n",
    "reference_solution": "def f(x):\n    return x + 1\n",
    "tests": [{"args": [1], "expected": 2}, {"args": [5], "expected": 6}],
    "hints": [],
}


def test_valid():
    ok, err = validate_problem_dict(GOOD)
    assert ok is True and err is None


def test_wrong_expected_detected():
    bad = {**GOOD, "tests": [{"args": [1], "expected": 999}]}
    ok, err = validate_problem_dict(bad)
    assert ok is False and "mismatch" in err.lower()


def test_runtime_error_detected():
    bad = {**GOOD, "reference_solution": "def f(x):\n    raise ValueError('x')\n"}
    ok, err = validate_problem_dict(bad)
    assert ok is False


def test_bad_shape_detected():
    ok, err = validate_problem_dict({"id": "only"})
    assert ok is False
