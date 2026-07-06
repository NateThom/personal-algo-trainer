import json

import pytest
from pydantic import ValidationError

from algotrainer.handoff.schema import SessionFile
from algotrainer.handoff.files import write_session, read_verdict


def _session(**over):
    base = dict(
        session_id="abc", attempt_id=1, problem={"id": "two-sum"},
        attempt={"code": "x", "judge_passed": True}, recall={"pattern": "arrays-hashing"},
        hints_used=0, request="grade",
    )
    base.update(over)
    return SessionFile(**base)


def test_write_session_creates_file(tmp_path):
    path = write_session(tmp_path, _session())
    assert path.exists()
    assert json.loads(path.read_text())["session_id"] == "abc"


def test_read_valid_verdict(tmp_path):
    (tmp_path / "verdict-abc.json").write_text(json.dumps({
        "session_id": "abc", "attempt_id": 1, "problem_id": "two-sum",
        "grade": "good", "feedback": "Nice, clean hash-map pass.",
    }))
    v = read_verdict(tmp_path, "abc")
    assert v.grade == "good"
    assert v.approach_used is None


def test_missing_verdict_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_verdict(tmp_path, "nope")


def test_malformed_verdict_rejected(tmp_path):
    (tmp_path / "verdict-bad.json").write_text(json.dumps({
        "session_id": "bad", "attempt_id": 1, "problem_id": "two-sum",
        "grade": "brilliant",  # not in the allowed literal set
    }))
    with pytest.raises(ValidationError):
        read_verdict(tmp_path, "bad")


def test_session_request_hint_rejected():
    with pytest.raises(ValidationError):
        _session(request="hint")


def test_session_request_grade_valid():
    assert _session(request="grade").request == "grade"
