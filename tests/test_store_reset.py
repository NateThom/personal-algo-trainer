from datetime import datetime, timezone, timedelta

from algotrainer.store import Store


def test_reset_progress_clears_all_learner_tables(tmp_path):
    s = Store(tmp_path / "t.db")
    now = datetime.now(timezone.utc)
    due = now + timedelta(days=1)
    # populate every learner table
    s.save_pattern_card("arrays-hashing", "{}", due)
    aid = s.record_attempt("two-sum", "code", "arrays-hashing", "hm", "O(n)", True, 0, now)
    s.ingest_verdict(aid, "two-sum", 3, "{}", due, "{}", now)
    s.record_graded_attempt(aid, "two-sum", "arrays-hashing", "arrays-hashing",
                            0, True, "good", True, None, now)

    s.reset_progress()

    assert s.get_card("two-sum") is None
    assert s.get_pattern_card("arrays-hashing") is None
    assert s.get_attempt(aid) is None
    assert s.attempt_has_review(aid) is False
    assert s.all_graded_patterns() == []
    assert s.attempted_problem_ids() == set()


def test_reset_progress_is_safe_on_empty_db(tmp_path):
    s = Store(tmp_path / "t.db")
    s.reset_progress()  # must not raise
    assert s.attempted_problem_ids() == set()
