from fastapi.testclient import TestClient

from algotrainer.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.db", content_dir=None,
                                 session_dir=tmp_path / "sessions"))


def test_reload_returns_count(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/reload")
    assert r.status_code == 200
    assert r.json()["count"] >= 4  # at least the seed problems


def test_next_prefers_unseen(tmp_path, monkeypatch):
    # With a fresh db nothing is attempted, so /api/next returns some problem.
    c = _client(tmp_path)
    r = c.get("/api/next")
    assert r.json()["problem"] is not None
