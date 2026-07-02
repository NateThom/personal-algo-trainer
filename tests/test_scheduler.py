from datetime import datetime, timezone, timedelta

from algotrainer.scheduler import SrsScheduler, RATING_BY_NAME


def test_rating_map():
    assert RATING_BY_NAME == {"again": 1, "hard": 2, "good": 3, "easy": 4}


def test_review_new_card_returns_future_due():
    s = SrsScheduler()
    now = datetime.now(timezone.utc)
    card_json, next_due, log_json = s.review(None, RATING_BY_NAME["good"], now)
    assert isinstance(card_json, str) and card_json
    assert next_due > now
    assert isinstance(log_json, str) and log_json


def test_again_schedules_sooner_than_easy():
    s = SrsScheduler()
    now = datetime.now(timezone.utc)
    _, due_again, _ = s.review(None, RATING_BY_NAME["again"], now)
    _, due_easy, _ = s.review(None, RATING_BY_NAME["easy"], now)
    assert due_again < due_easy


def test_due_selection_includes_never_seen_and_overdue():
    s = SrsScheduler()
    now = datetime.now(timezone.utc)
    due_map = {
        "seen-overdue": now - timedelta(days=1),
        "seen-future": now + timedelta(days=5),
    }
    all_ids = ["seen-overdue", "seen-future", "never-seen"]
    due = s.due_problem_ids(due_map, all_ids, now)
    assert due == ["seen-overdue", "never-seen"]
