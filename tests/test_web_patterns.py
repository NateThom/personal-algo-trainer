from fastapi.testclient import TestClient

from algotrainer.web.app import create_app


def _client(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        content_dir=None,  # use default seed content
        session_dir=tmp_path / "sessions",
    )
    return TestClient(app)


def test_patterns_page_served(tmp_path):
    c = _client(tmp_path)
    r = c.get("/patterns")
    assert r.status_code == 200


def test_patterns_detail_page_served(tmp_path):
    c = _client(tmp_path)
    r = c.get("/patterns/two-pointers")
    assert r.status_code == 200


def test_api_patterns_lists_all_18_sorted_by_order(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/patterns").json()
    patterns = body["patterns"]
    assert len(patterns) == 18
    orders = [p["order"] for p in patterns]
    assert orders == sorted(orders)
    names = {p["name"] for p in patterns}
    assert "Sliding Window" in names
    assert "Two Pointers" in names
    # basic shape
    for p in patterns:
        assert set(p.keys()) >= {"id", "name", "order", "summary", "has_doc", "confusable"}


def test_api_pattern_detail_sliding_window_has_template_and_recognize(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/patterns/sliding-window").json()
    assert body["id"] == "sliding-window"
    assert body["template"].strip() != ""
    assert isinstance(body["recognize_when"], list)
    assert len(body["recognize_when"]) > 0
    assert "two-pointers" in body["confusable"] or "Two Pointers" in body["confusable"]


def test_api_pattern_detail_404_for_unknown(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/patterns/does-not-exist")
    assert r.status_code == 404
