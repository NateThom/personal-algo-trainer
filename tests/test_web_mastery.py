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
        "recall": {"pattern": prob["pattern"], "approach": "x", "complexity": "O(n)"},
        "judge_passed": judged["passed"], "hints_used": 0,
    }).json()
    subprocess.run([sys.executable, "scripts/stub_tutor.py", str(session_dir),
                    sess["session_id"]], check=True, cwd=REPO)
    c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]})
    return prob


def test_ingest_writes_graded_attempt_and_pattern_card(tmp_path):
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    prob = _solve_and_grade(c, session_dir, db_path)

    conn = sqlite3.connect(db_path)
    ga = conn.execute("SELECT pattern, grade FROM graded_attempt").fetchall()
    pc = conn.execute("SELECT pattern FROM pattern_card").fetchall()
    conn.close()
    assert len(ga) == 1
    assert ga[0][0] == prob["pattern"]
    assert (prob["pattern"],) in pc
