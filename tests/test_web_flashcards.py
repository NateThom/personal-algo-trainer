from fastapi.testclient import TestClient

from algotrainer.store import Store
from algotrainer.web.app import create_app


def _client(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        content_dir=None,  # use default seed content
        session_dir=tmp_path / "sessions",
    )
    return TestClient(app)


def test_flashcards_page_served(tmp_path):
    c = _client(tmp_path)
    assert c.get("/flashcards").status_code == 200


def test_flashcards_pattern_page_served(tmp_path):
    c = _client(tmp_path)
    assert c.get("/flashcards/two-pointers").status_code == 200


def test_due_cards_include_all_patterns_regardless_of_attempts(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    patterns_present = {card["pattern"] for card in body["cards"]}
    # nothing attempted yet, and nothing is gated: all 18 patterns show up
    assert len(patterns_present) == 18


def test_due_cards_include_far_future_roadmap_pattern(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    patterns_present = {card["pattern"] for card in body["cards"]}
    # dp-2d is last in roadmap order (order 17 of 18) — still available day one
    assert "dp-2d" in patterns_present


def test_due_cards_include_all_four_types_for_a_pattern(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    types_seen = {
        card["card_type"] for card in body["cards"] if card["pattern"] == "arrays-hashing"
    }
    assert types_seen == {"recognition", "complexity", "template", "gotcha"}


def test_recognition_card_has_four_options_including_self(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    rec = next(
        card for card in body["cards"]
        if card["pattern"] == "arrays-hashing" and card["card_type"] == "recognition"
    )
    assert len(rec["options"]) == 4
    ids = {opt["id"] for opt in rec["options"]}
    assert "arrays-hashing" in ids
    assert all(opt["name"] for opt in rec["options"])


def test_review_recognition_correct_is_marked_correct(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition", "selected": "arrays-hashing",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["next_due"] is not None


def test_review_recognition_incorrect_is_marked_incorrect(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition", "selected": "two-pointers",
    })
    assert r.status_code == 200
    assert r.json()["correct"] is False


def test_review_recognition_without_selected_is_400(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition",
    })
    assert r.status_code == 400


def test_review_flip_card_requires_rating(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "complexity",
    })
    assert r.status_code == 400


def test_review_flip_card_with_rating_reschedules(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "complexity", "rating": 3,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["next_due"] is not None
    assert body["correct"] is None


def test_review_unknown_card_type_is_404(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "nonsense", "rating": 3,
    })
    assert r.status_code == 404


def test_review_does_not_touch_mastery_or_pattern_card(tmp_path):
    c = _client(tmp_path)
    c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition", "selected": "arrays-hashing",
    })
    dash = c.get("/api/dashboard").json()
    # no graded_attempt rows were written by the flashcard review, so the
    # mastery table (which reads graded_attempt) stays empty
    assert dash["patterns"] == []
    # nor did the review write a pattern_card row: that table feeds the
    # mastery gate's stability signal, and flashcard reviews must never be
    # able to "purchase apparent mastery" through it (design doc §1, §8)
    store = Store(tmp_path / "t.db")
    assert store.get_pattern_card("arrays-hashing") is None


def test_review_flip_card_with_out_of_range_rating_is_400(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "complexity", "rating": 99,
    })
    assert r.status_code == 400


def test_diff_endpoint_returns_ops(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/diff", json={"pattern": "two-pointers", "code": "left = 0"})
    assert r.status_code == 200
    ops = r.json()["ops"]
    assert isinstance(ops, list)
    assert len(ops) > 0


def test_diff_endpoint_404_for_unknown_pattern(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/diff", json={"pattern": "does-not-exist", "code": ""})
    assert r.status_code == 404
