import subprocess
import sys
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from algotrainer.web.app import create_app
from algotrainer.content import load_problem

REPO = Path(__file__).resolve().parent.parent


def _solve_and_grade(c, session_dir, db_path):
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


def test_ingest_writes_graded_attempt_and_pattern_card(tmp_path):
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    prob, _ = _solve_and_grade(c, session_dir, db_path)

    conn = sqlite3.connect(db_path)
    ga = conn.execute("SELECT pattern, grade FROM graded_attempt").fetchall()
    pc = conn.execute("SELECT pattern FROM pattern_card").fetchall()
    conn.close()
    assert len(ga) == 1
    assert ga[0][0] == load_problem(prob["id"]).pattern
    assert (load_problem(prob["id"]).pattern,) in pc


def test_mastery_endpoint_reports_pattern(tmp_path):
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    prob, _ = _solve_and_grade(c, session_dir, db_path)

    r = c.get("/api/mastery")
    assert r.status_code == 200
    pats = {p["pattern"]: p for p in r.json()["patterns"]}
    expected_pattern = load_problem(prob["id"]).pattern
    assert expected_pattern in pats
    entry = pats[expected_pattern]
    assert entry["attempts"] >= 1
    assert "mastery_score" in entry and "mastered" in entry
    assert entry["transfer_breadth"] >= 1  # solved unaided


def test_next_uses_composer_without_crashing(tmp_path):
    # smoke: after grading one problem, /api/next still returns a due problem or null
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    _solve_and_grade(c, session_dir, db_path)
    r = c.get("/api/next")
    assert r.status_code == 200
    assert "problem" in r.json()


def test_double_ingest_does_not_double_write_plan3_tables(tmp_path):
    # A re-ingest (idempotent short-circuit) must not advance the pattern card
    # or add a second graded_attempt row.
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    _prob, session_id = _solve_and_grade(c, session_dir, db_path)

    conn = sqlite3.connect(db_path)
    ga_before = conn.execute("SELECT COUNT(*) FROM graded_attempt").fetchone()[0]
    pc_before = conn.execute("SELECT pattern, card_json, next_due FROM pattern_card").fetchall()
    conn.close()

    r = c.post("/api/verdict/ingest", json={"session_id": session_id})
    assert r.json().get("already_ingested") is True

    conn = sqlite3.connect(db_path)
    ga_after = conn.execute("SELECT COUNT(*) FROM graded_attempt").fetchone()[0]
    pc_after = conn.execute("SELECT pattern, card_json, next_due FROM pattern_card").fetchall()
    conn.close()
    assert ga_after == ga_before  # no duplicate graded_attempt
    assert pc_after == pc_before  # pattern card unchanged (not re-advanced)
