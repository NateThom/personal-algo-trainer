import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from algotrainer.content import load_problem
from algotrainer.handoff.schema import Verdict
from algotrainer.web.app import create_app


def _client(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        content_dir=None,  # use default seed content
        session_dir=tmp_path / "sessions",
    )
    return TestClient(app)


def _run_full_loop_up_to_ingest(tmp_path):
    """Shared setup: drive the app through judge/session/stub-tutor, stopping
    just before the (first) call to /api/verdict/ingest. Returns (client, sess, db_path)."""
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    app = create_app(db_path=db_path, content_dir=None, session_dir=session_dir)
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
        "recall": {"pattern": load_problem(prob["id"]).pattern, "approach": "x", "complexity": "O(n)"},
        "judge_passed": judged["passed"], "hints_used": 0,
    }).json()

    subprocess.run(
        [sys.executable, "scripts/stub_tutor.py", str(session_dir), sess["session_id"]],
        check=True, cwd=Path(__file__).resolve().parent.parent,
    )
    return c, sess, session_dir, db_path


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


def test_next_does_not_leak_pattern(tmp_path):
    c = _client(tmp_path)
    p = c.get("/api/next").json()["problem"]
    assert "pattern" not in p
    assert "pattern" not in p["pattern_pool"]


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
        "recall": {"pattern": load_problem(prob["id"]).pattern, "approach": "x", "complexity": "O(n)"},
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


def test_double_ingest_does_not_advance_twice(tmp_path):
    c, sess, session_dir, db_path = _run_full_loop_up_to_ingest(tmp_path)

    first = c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]}).json()
    assert first["already_ingested"] is False
    first_next_due = first["next_due"]

    second = c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]}).json()
    assert second["already_ingested"] is True
    assert second["next_due"] is None
    assert second["grade"] == first["grade"]

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM review WHERE attempt_id = ?", (sess["attempt_id"],)
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1
    assert first_next_due is not None


def test_ingest_rejects_session_mismatch(tmp_path):
    c, sess, session_dir, db_path = _run_full_loop_up_to_ingest(tmp_path)

    verdict_path = session_dir / f"verdict-{sess['session_id']}.json"
    verdict = Verdict.model_validate_json(verdict_path.read_text())
    tampered = verdict.model_copy(update={"session_id": "some-other-session"})
    verdict_path.write_text(tampered.model_dump_json(indent=2))

    r = c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]})
    assert r.status_code == 400


def load_default_solution(problem_id: str) -> str:
    from algotrainer.content import load_problem
    return load_problem(problem_id).reference_solution
