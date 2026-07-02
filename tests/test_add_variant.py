import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CAND = {
    "id": "plan4-add-variant-test", "pattern": "arrays-hashing", "title": "V",
    "difficulty": "easy", "statement": "s", "function_name": "f",
    "starter_code": "def f(x):\n    pass\n",
    "reference_solution": "def f(x):\n    return x\n",
    "tests": [{"args": [3], "expected": 3}], "hints": [],
}


def _run(payload):
    return subprocess.run([sys.executable, "scripts/add_variant.py"],
                          input=json.dumps(payload), capture_output=True, text=True, cwd=REPO)


def test_rejects_invalid(tmp_path):
    bad = {**CAND, "id": "plan4-invalid-x", "tests": [{"args": [3], "expected": 4}]}
    r = _run(bad)
    assert r.returncode != 0
    assert not (REPO / "content" / "generated" / "plan4-invalid-x.json").exists()


def test_rejects_seed_id_collision():
    clash = {**CAND, "id": "two-sum"}  # collides with a seed problem id
    r = _run(clash)
    assert r.returncode != 0


def test_accepts_valid_then_cleanup():
    out = REPO / "content" / "generated" / "plan4-add-variant-test.json"
    try:
        r = _run(CAND)
        assert r.returncode == 0, r.stderr
        assert out.exists()
    finally:
        if out.exists():
            out.unlink()
