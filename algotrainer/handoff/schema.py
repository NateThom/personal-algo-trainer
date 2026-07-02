from typing import Literal

from pydantic import BaseModel, field_validator

from algotrainer.errors import is_valid_error_code


class SessionFile(BaseModel):
    session_id: str
    attempt_id: int
    problem: dict
    attempt: dict
    recall: dict
    hints_used: int = 0
    request: str = "grade"


class Verdict(BaseModel):
    session_id: str
    attempt_id: int
    problem_id: str
    grade: Literal["again", "hard", "good", "easy"]
    approach_used: str | None = None
    error_code: str | None = None
    complexity_ok: bool | None = None
    self_explanation_score: int | None = None
    feedback: str = ""

    @field_validator("error_code")
    @classmethod
    def _check_error_code(cls, v: str | None) -> str | None:
        if not is_valid_error_code(v):
            raise ValueError(f"unknown error_code: {v!r}")
        return v
