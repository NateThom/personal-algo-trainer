from datetime import datetime, timezone, timedelta

from algotrainer.store import Store


def _store(tmp_path):
    return Store(tmp_path / "t.db")


def test_pattern_card_roundtrip(tmp_path):
    s = _store(tmp_path)
    assert s.get_pattern_card("arrays-hashing") is None
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_pattern_card("arrays-hashing", '{"stability": 2.0}', due)
    assert s.get_pattern_card("arrays-hashing") == '{"stability": 2.0}'


def test_record_and_query_graded_attempts(tmp_path):
    s = _store(tmp_path)
    now = datetime.now(timezone.utc)
    s.record_graded_attempt(1, "two-sum", "arrays-hashing", "arrays-hashing",
                            0, True, "good", True, None, now)
    s.record_graded_attempt(2, "contains-duplicate", "arrays-hashing", "sliding-window",
                            1, True, "hard", False, "pattern_misidentification", now)
    rows = s.graded_attempts_by_pattern("arrays-hashing")
    assert len(rows) == 2
    assert rows[0]["judge_passed"] is True
    assert rows[1]["error_code"] == "pattern_misidentification"


def test_error_counts_and_patterns(tmp_path):
    s = _store(tmp_path)
    now = datetime.now(timezone.utc)
    s.record_graded_attempt(1, "two-sum", "arrays-hashing", "arrays-hashing",
                            0, True, "good", True, None, now)
    s.record_graded_attempt(2, "contains-duplicate", "arrays-hashing", "sliding-window",
                            1, True, "hard", False, "pattern_misidentification", now)
    assert s.error_counts_by_pattern() == {"arrays-hashing": 1}
    assert s.all_graded_patterns() == ["arrays-hashing"]
