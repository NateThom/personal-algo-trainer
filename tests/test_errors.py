from algotrainer.errors import ERROR_CODES, is_valid_error_code


def test_taxonomy_members():
    assert ERROR_CODES == (
        "pattern_misidentification",
        "approach_correct_execution_bug",
        "complexity_suboptimal",
        "incomplete_knowledge",
        "got_stuck_no_idea",
        "careless_time_pressure",
    )


def test_none_is_valid():
    assert is_valid_error_code(None) is True


def test_member_is_valid():
    assert is_valid_error_code("complexity_suboptimal") is True


def test_unknown_is_invalid():
    assert is_valid_error_code("made_up") is False
