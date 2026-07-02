import subprocess
import sys
from pathlib import Path

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


def test_full_loop_with_stub_tutor(tmp_path):
    session_dir = tmp_path / "sessions"
    app = create_app(db_path=tmp_path / "t.db", content_dir=None, session_dir=session_dir)
    c = TestClient(app)

    prob = c.get("/api/next").json()["problem"]
    code = ("def two_sum(nums, target):\n    seen={}\n"
            "    for i,n in enumerate(nums):\n"
            "        if target-n in seen: return [seen[target-n], i]\n"
            "        seen[n]=i\n") if prob["id"] == "two-sum" else \
        load_default_solution(prob["id"])

    judged = c.post("/api/judge", json={"problem_id": prob["id"], "code": code}).json()
    sess = c.post("/api/session", json={
        "problem_id": prob["id"], "code": code,
        "recall": {"pattern": prob["pattern"], "approach": "x", "complexity": "O(n)"},
        "judge_passed": judged["passed"], "hints_used": 0,
    }).json()

    # Run the stub tutor exactly as the human would run the real tutor skill.
    subprocess.run(
        [sys.executable, "scripts/stub_tutor.py", str(session_dir), sess["session_id"]],
        check=True, cwd=Path(__file__).resolve().parent.parent,
    )

    ingested = c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]}).json()
    assert ingested["grade"] in {"again", "hard", "good", "easy"}
    assert "next_due" in ingested


def load_default_solution(problem_id: str) -> str:
    from algotrainer.content import load_problem
    return load_problem(problem_id).reference_solution
