import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from algotrainer.content import load_problem
from algotrainer.web.app import create_app

REPO = Path(__file__).resolve().parent.parent


def _client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.db", content_dir=None,
                                 session_dir=tmp_path / "sessions",
                                 generated_dir=tmp_path / "generated"))


def test_solve_page_has_nav_to_dashboard(tmp_path):
    html = _client(tmp_path).get("/").text
    assert 'href="/dashboard"' in html
    assert 'id="reset-btn"' in html


def test_dashboard_page_served_with_nav_back(tmp_path):
    r = _client(tmp_path).get("/dashboard")
    assert r.status_code == 200
    assert "Dashboard" in r.text
    assert 'href="/"' in r.text  # navigation back to the solve view


def test_nav_and_dashboard_scripts_served(tmp_path):
    c = _client(tmp_path)
    assert c.get("/static/nav.js").status_code == 200
    assert c.get("/static/dashboard.js").status_code == 200


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


def test_reset_clears_progress(tmp_path):
    session_dir = tmp_path / "sessions"
    c = TestClient(create_app(db_path=tmp_path / "t.db", content_dir=None,
                              session_dir=session_dir, generated_dir=tmp_path / "generated"))
    _solve_and_grade(c, session_dir)
    assert c.get("/api/dashboard").json()["patterns"]  # non-empty after grading

    r = c.post("/api/reset")
    assert r.status_code == 200 and r.json() == {"ok": True}

    dash = c.get("/api/dashboard").json()
    assert dash["patterns"] == []  # mastery wiped
    assert dash["due_count"] == dash["total_problems"]  # all problems due again (cards cleared)
