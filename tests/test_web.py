from fastapi.testclient import TestClient

from algotrainer.web.app import create_app


def _client(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        content_dir=None,  # use default seed content
        session_dir=tmp_path / "sessions",
    )
    return TestClient(app)


def test_index_served(tmp_path):
    c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "AlgoTrainer" in r.text


def test_next_returns_problem_without_solution(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/next")
    assert r.status_code == 200
    prob = r.json()["problem"]
    assert prob is not None
    assert "reference_solution" not in prob
    assert "tests" not in prob


def test_judge_endpoint_runs_code(tmp_path):
    c = _client(tmp_path)
    code = ("def two_sum(nums, target):\n    seen={}\n"
            "    for i,n in enumerate(nums):\n"
            "        if target-n in seen: return [seen[target-n], i]\n"
            "        seen[n]=i\n")
    r = c.post("/api/judge", json={"problem_id": "two-sum", "code": code})
    assert r.status_code == 200
    assert r.json()["passed"] is True
