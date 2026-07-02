import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from algotrainer.content import load_problem
from algotrainer.web.app import create_app

REPO = Path(__file__).resolve().parent.parent


def _client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.db", content_dir=None,
                                 session_dir=tmp_path / "sessions",
                                 generated_dir=tmp_path / "generated"))


def test_reload_returns_count(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/reload")
    assert r.status_code == 200
    assert r.json()["count"] >= 4  # at least the seed problems


def test_next_returns_a_problem_on_fresh_db(tmp_path):
    # With a fresh db nothing is attempted, so /api/next returns some problem.
    c = _client(tmp_path)
    r = c.get("/api/next")
    assert r.json()["problem"] is not None


def _solve_and_grade(c, session_dir):
    prob = c.get("/api/next").json()["problem"]
    code = load_problem(prob["id"]).reference_solution
    judged = c.post("/api/judge", json={"problem_id": prob["id"], "code": code}).json()
    sess = c.post("/api/session", json={
        "problem_id": prob["id"], "code": code,
        "recall": {"pattern": prob["pattern"], "approach": "x", "complexity": "O(n)"},
        "judge_passed": judged["passed"], "hints_used": 0,
    }).json()
    subprocess.run([sys.executable, "scripts/stub_tutor.py", str(session_dir),
                    sess["session_id"]], check=True, cwd=REPO)
    c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]})
    return prob["id"]


def test_next_serves_overdue_review_before_novel(tmp_path):
    # A seen problem that is due (overdue) must be served before never-seen ones,
    # so an endless supply of novel instances can't starve retention reviews.
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir,
                              generated_dir=tmp_path / "generated"))
    solved_id = _solve_and_grade(c, session_dir)
    # Force the solved problem's card overdue.
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE card SET next_due = ? WHERE problem_id = ?", (past, solved_id))
    conn.commit()
    conn.close()
    served = c.get("/api/next").json()["problem"]
    assert served["id"] == solved_id  # the due review, not an unseen novel problem


def test_dashboard_shape(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"due_count", "total_problems", "patterns", "error_counts"}
    assert body["total_problems"] >= 4
    assert isinstance(body["patterns"], list)
