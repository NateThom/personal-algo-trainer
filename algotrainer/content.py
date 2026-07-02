import json
from pathlib import Path

from algotrainer.models import Problem

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "problems"


def _run_reference(problem: Problem) -> None:
    """Execute the reference solution against the problem's own tests in-process.
    Raises ValueError if any test fails — guarantees seed content is self-consistent."""
    namespace: dict = {}
    exec(problem.reference_solution, namespace)  # noqa: S102 - trusted repo content
    fn = namespace[problem.function_name]
    for tc in problem.tests:
        got = fn(*tc.args)
        if got != tc.expected:
            raise ValueError(
                f"Problem {problem.id}: reference solution returned {got!r} "
                f"for args {tc.args!r}, expected {tc.expected!r}"
            )


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
