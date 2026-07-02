from algotrainer.judge import run_submission
from algotrainer.models import TestCase


TESTS = [
    TestCase(args=[[2, 7, 11, 15], 9], expected=[0, 1]),
    TestCase(args=[[3, 3], 6], expected=[0, 1]),
]

GOOD = (
    "def two_sum(nums, target):\n"
    "    seen = {}\n"
    "    for i, n in enumerate(nums):\n"
    "        if target - n in seen:\n"
    "            return [seen[target - n], i]\n"
    "        seen[n] = i\n"
    "    return []\n"
)


def test_correct_submission_passes():
    r = run_submission(GOOD, "two_sum", TESTS)
    assert r.passed is True
    assert all(c.passed for c in r.cases)
    assert r.error is None


def test_wrong_submission_fails_with_case_detail():
    bad = "def two_sum(nums, target):\n    return [0, 0]\n"
    r = run_submission(bad, "two_sum", TESTS)
    assert r.passed is False
    assert r.cases[0].got == [0, 0]


def test_runtime_error_is_captured_not_raised():
    boom = "def two_sum(nums, target):\n    raise RuntimeError('boom')\n"
    r = run_submission(boom, "two_sum", TESTS)
    assert r.passed is False
    assert r.error is not None or any(c.error for c in r.cases)


def test_infinite_loop_times_out():
    loop = "def two_sum(nums, target):\n    while True:\n        pass\n"
    r = run_submission(loop, "two_sum", TESTS, timeout_s=1.0)
    assert r.passed is False
    assert r.error is not None


def test_submission_with_print_still_passes():
    noisy = (
        "def two_sum(nums, target):\n"
        "    print('debug')\n"
        "    seen = {}\n"
        "    for i, n in enumerate(nums):\n"
        "        if target - n in seen:\n"
        "            return [seen[target - n], i]\n"
        "        seen[n] = i\n"
        "    return []\n"
    )
    r = run_submission(noisy, "two_sum", TESTS)
    assert r.passed is True
    assert all(c.passed for c in r.cases)
    assert r.error is None
