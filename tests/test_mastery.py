from algotrainer.mastery import compute_pattern_mastery, GATE_BREADTH


def _row(pid, recall, hints, passed, grade="good", complexity_ok=True, err=None):
    return {"problem_id": pid, "recall_pattern": recall, "hints_used": hints,
            "judge_passed": passed, "grade": grade, "complexity_ok": complexity_ok,
            "error_code": err}


def test_empty_is_zeroed():
    m = compute_pattern_mastery("arrays-hashing", [], 0.0)
    assert m.attempts == 0
    assert m.mastery_score == 0.0
    assert m.mastered is False


def test_transfer_breadth_counts_distinct_unaided_correct():
    rows = [
        _row("p1", "arrays-hashing", 0, True),
        _row("p1", "arrays-hashing", 0, True),   # duplicate problem, not counted twice
        _row("p2", "arrays-hashing", 1, True),   # hinted, doesn't count
        _row("p3", "arrays-hashing", 0, False),  # failed, doesn't count
    ]
    m = compute_pattern_mastery("arrays-hashing", rows, 1.0)
    assert m.transfer_breadth == 1


def test_pattern_id_accuracy():
    rows = [
        _row("p1", "arrays-hashing", 0, True),
        _row("p2", "sliding-window", 0, True),  # wrong pattern named
    ]
    m = compute_pattern_mastery("arrays-hashing", rows, 1.0)
    assert m.pattern_id_accuracy == 0.5


def test_memorization_trap_flagged():
    # solves everything but keeps naming the wrong pattern
    rows = [_row(f"p{i}", "sliding-window", 0, True) for i in range(4)]
    m = compute_pattern_mastery("arrays-hashing", rows, 20.0)
    assert m.solve_rate == 1.0
    assert m.pattern_id_accuracy == 0.0
    assert m.memorization_trap is True
    assert m.mastered is False  # trap blocks mastery even with high stability/breadth


def test_mastered_when_all_gates_met():
    rows = [_row(f"p{i}", "arrays-hashing", 0, True) for i in range(GATE_BREADTH)]
    m = compute_pattern_mastery("arrays-hashing", rows, 10.0)
    assert m.transfer_breadth == GATE_BREADTH
    assert m.pattern_id_accuracy == 1.0
    assert m.mastered is True
