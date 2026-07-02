import pytest
from pydantic import ValidationError

from algotrainer.handoff.schema import Verdict


def _base(**over):
    d = dict(session_id="s", attempt_id=1, problem_id="two-sum", grade="good")
    d.update(over)
    return d


def test_none_error_code_ok():
    assert Verdict(**_base(error_code=None)).error_code is None


def test_valid_error_code_ok():
    v = Verdict(**_base(error_code="complexity_suboptimal"))
    assert v.error_code == "complexity_suboptimal"


def test_invalid_error_code_rejected():
    with pytest.raises(ValidationError):
        Verdict(**_base(error_code="totally_made_up"))
