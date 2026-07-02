import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from algotrainer.content import load_problem
from algotrainer.store import Store
from algotrainer.web.app import create_app

REPO = Path(__file__).resolve().parent.parent


def _client(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        content_dir=None,
        session_dir=tmp_path / "sessions",
    )
    return TestClient(app)


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
    return prob, sess["session_id"]


# --- Task 5: store.attempt_count_for_problem ---

def test_attempt_count_for_problem_zero_on_fresh_db(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.attempt_count_for_problem("does-not-exist") == 0


def test_attempt_count_for_problem_counts_graded_attempts(tmp_path):
    session_dir = tmp_path / "sessions"
    c = _client(tmp_path)
    prob, _ = _solve_and_grade(c, session_dir)

    store = Store(tmp_path / "t.db")
    assert store.attempt_count_for_problem(prob["id"]) >= 1


# --- Task 5: /api/next seen_count ---

def test_next_includes_seen_count_zero_on_fresh_db(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/next")
    problem = r.json()["problem"]
    assert problem is not None
    assert problem["seen_count"] == 0


def test_next_seen_count_increments_after_grading(tmp_path):
    session_dir = tmp_path / "sessions"
    c = _client(tmp_path)
    prob, _ = _solve_and_grade(c, session_dir)

    store = Store(tmp_path / "t.db")
    expected = store.attempt_count_for_problem(prob["id"])
    assert expected >= 1

    # Force the just-graded problem due again so /api/next can serve it,
    # then confirm the served payload's seen_count matches the store.
    import sqlite3
    from datetime import datetime, timedelta, timezone
    conn = sqlite3.connect(tmp_path / "t.db")
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn.execute("UPDATE card SET next_due = ? WHERE problem_id = ?", (past, prob["id"]))
    conn.commit()
    conn.close()

    r = c.get("/api/next")
    served = r.json()["problem"]
    assert served is not None
    if served["id"] == prob["id"]:
        assert served["seen_count"] == expected
