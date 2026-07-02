from fastapi.testclient import TestClient

from algotrainer.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.db", content_dir=None,
                                 session_dir=tmp_path / "sessions"))


def test_first_hint(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/hint", json={"problem_id": "two-sum", "tier": 0})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["hint"], str) and body["hint"]
    assert body["has_more"] is True


def test_out_of_range_tier(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/hint", json={"problem_id": "two-sum", "tier": 99})
    assert r.json()["hint"] is None
    assert r.json()["has_more"] is False


def test_unknown_problem_404(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/hint", json={"problem_id": "nope", "tier": 0})
    assert r.status_code == 404
