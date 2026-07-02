import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(session_dir, payload):
    return subprocess.run(
        [sys.executable, "scripts/write_verdict.py", str(session_dir)],
        input=json.dumps(payload), capture_output=True, text=True, cwd=REPO,
    )


def test_writes_valid_verdict(tmp_path):
    payload = {"session_id": "abc", "attempt_id": 1, "problem_id": "two-sum",
               "grade": "good", "error_code": None, "feedback": "clean"}
    r = _run(tmp_path, payload)
    assert r.returncode == 0, r.stderr
    written = json.loads((tmp_path / "verdict-abc.json").read_text())
    assert written["grade"] == "good"


def test_rejects_bad_grade_without_writing(tmp_path):
    payload = {"session_id": "bad", "attempt_id": 1, "problem_id": "two-sum",
               "grade": "spectacular"}
    r = _run(tmp_path, payload)
    assert r.returncode != 0
    assert not (tmp_path / "verdict-bad.json").exists()


def test_rejects_bad_error_code_without_writing(tmp_path):
    payload = {"session_id": "bad2", "attempt_id": 1, "problem_id": "two-sum",
               "grade": "good", "error_code": "nonsense"}
    r = _run(tmp_path, payload)
    assert r.returncode != 0
    assert not (tmp_path / "verdict-bad2.json").exists()
