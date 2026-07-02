import json
from pathlib import Path

from algotrainer.models import Problem
from algotrainer.validation import validate_problem_dict

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "problems"


def _run_reference(problem: Problem) -> None:
    """Execute the reference solution against the problem's own tests in-process.
    Raises ValueError if any test fails — guarantees seed content is self-consistent."""
    ok, reason = validate_problem_dict(
        {
            "id": problem.id, "pattern": problem.pattern, "title": problem.title,
            "difficulty": problem.difficulty, "statement": problem.statement,
            "function_name": problem.function_name, "starter_code": problem.starter_code,
            "reference_solution": problem.reference_solution,
            "tests": [{"args": t.args, "expected": t.expected} for t in problem.tests],
            "hints": list(problem.hints),
        }
    )
    if not ok:
        raise ValueError(f"Problem {problem.id}: {reason}")


def load_problem(problem_id: str, content_dir: Path = DEFAULT_CONTENT_DIR) -> Problem:
    path = content_dir / f"{problem_id}.json"
    data = json.loads(path.read_text())
    problem = Problem.from_dict(data)
    _run_reference(problem)
    return problem


def load_problems(content_dir: Path = DEFAULT_CONTENT_DIR) -> list[Problem]:
    problems = []
    for path in sorted(content_dir.glob("*.json")):
        data = json.loads(path.read_text())
        problem = Problem.from_dict(data)
        _run_reference(problem)
        problems.append(problem)
    return problems
