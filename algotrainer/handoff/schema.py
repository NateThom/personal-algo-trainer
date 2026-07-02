from typing import Literal

from pydantic import BaseModel


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
