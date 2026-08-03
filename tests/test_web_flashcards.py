from fastapi.testclient import TestClient

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
