import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from algotrainer import mastery as mastery_mod
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
        "recall": {"pattern": load_problem(prob["id"]).pattern, "approach": "x", "complexity": "O(n)"},
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


# --- Task 6: pattern_pool on /api/next ---

def test_next_includes_pattern_pool_with_expected_keys(tmp_path):
    c = _client(tmp_path)
    problem = c.get("/api/next").json()["problem"]
    assert problem is not None
    pool = problem["pattern_pool"]
    assert set(pool.keys()) == {"total", "unseen", "needs_more"}
    assert pool["total"] >= 1
    assert pool["unseen"] == pool["total"]  # nothing attempted yet
    assert pool["needs_more"] == max(0, mastery_mod.GATE_BREADTH - pool["total"])


def test_next_pattern_pool_unseen_decreases_after_grading(tmp_path):
    session_dir = tmp_path / "sessions"
    c = _client(tmp_path)
    prob, _ = _solve_and_grade(c, session_dir)

    r = c.get("/api/next")
    problem = r.json()["problem"]
    if problem is not None and load_problem(problem["id"]).pattern == load_problem(prob["id"]).pattern:
        pool = problem["pattern_pool"]
        assert pool["unseen"] == pool["total"] - 1


# --- Task 6: /api/dashboard instances / needs_more ---

def test_dashboard_patterns_include_instances_and_needs_more(tmp_path):
    session_dir = tmp_path / "sessions"
    c = _client(tmp_path)
    prob, _ = _solve_and_grade(c, session_dir)

    r = c.get("/api/dashboard")
    assert r.status_code == 200
    pats = {p["pattern"]: p for p in r.json()["patterns"]}
    expected_pattern = load_problem(prob["id"]).pattern
    assert expected_pattern in pats
    entry = pats[expected_pattern]
    assert "instances" in entry
    assert "needs_more" in entry
    assert entry["instances"] >= 1
    assert entry["needs_more"] == max(0, mastery_mod.GATE_BREADTH - entry["instances"])
