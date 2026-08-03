from datetime import datetime, timezone, timedelta

from algotrainer.store import Store


def _store(tmp_path):
    return Store(tmp_path / "t.db")


def test_new_card_is_none(tmp_path):
    s = _store(tmp_path)
    assert s.get_card("two-sum") is None


def test_save_and_get_card(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_card("two-sum", '{"stability": 3.0}', due)
    assert s.get_card("two-sum") == '{"stability": 3.0}'


def test_all_card_due(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=2)
    s.save_card("two-sum", "{}", due)
    mapping = s.all_card_due(datetime.now(timezone.utc))
    assert "two-sum" in mapping
    assert isinstance(mapping["two-sum"], datetime)


def test_ingest_verdict_is_atomic(tmp_path):
    s = _store(tmp_path)
    now = datetime.now(timezone.utc)
    aid = s.record_attempt("two-sum", "code", "arrays-hashing", "hash map", "O(n)",
                           True, 0, now)
    due = now + timedelta(days=1)
    s.ingest_verdict(aid, "two-sum", 3, '{"stability": 3.0}', due, '{"rating": 3}', now)
    assert s.get_card("two-sum") == '{"stability": 3.0}'


def test_flashcard_new_is_none(tmp_path):
    s = _store(tmp_path)
    assert s.get_flashcard("two-pointers", "recognition") is None


def test_flashcard_save_and_get(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_flashcard("two-pointers", "recognition", '{"stability": 2.0}', due)
    assert s.get_flashcard("two-pointers", "recognition") == '{"stability": 2.0}'
    # a different card_type on the same pattern is independent
    assert s.get_flashcard("two-pointers", "template") is None


def test_flashcard_save_overwrites_same_pattern_and_type(tmp_path):
    s = _store(tmp_path)
    due1 = datetime.now(timezone.utc) + timedelta(days=1)
    due2 = datetime.now(timezone.utc) + timedelta(days=5)
    s.save_flashcard("two-pointers", "recognition", '{"stability": 2.0}', due1)
    s.save_flashcard("two-pointers", "recognition", '{"stability": 4.0}', due2)
    assert s.get_flashcard("two-pointers", "recognition") == '{"stability": 4.0}'


def test_all_flashcard_due(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=2)
    s.save_flashcard("two-pointers", "complexity", "{}", due)
    mapping = s.all_flashcard_due(datetime.now(timezone.utc))
    assert ("two-pointers", "complexity") in mapping
    assert isinstance(mapping[("two-pointers", "complexity")], datetime)


def test_reset_progress_clears_flashcards(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_flashcard("two-pointers", "gotcha", "{}", due)
    s.reset_progress()
    assert s.get_flashcard("two-pointers", "gotcha") is None
