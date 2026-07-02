"""Store for AI-generated problem variants. Every variant is validated (its
reference solution must pass its own tests) before it can be saved or served."""
import json
from pathlib import Path

from algotrainer.models import Problem
from algotrainer.validation import validate_problem_dict

GENERATED_DIR = Path(__file__).resolve().parent.parent / "content" / "generated"


def load_generated(generated_dir: Path = GENERATED_DIR) -> list[Problem]:
    problems: list[Problem] = []
    if not generated_dir.exists():
        return problems
    for path in sorted(generated_dir.glob("*.json")):
        try:
            d = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        ok, _ = validate_problem_dict(d)
        if ok:
            problems.append(Problem.from_dict(d))
    return problems


def save_generated_problem(
    d: dict, existing_ids: set[str], generated_dir: Path = GENERATED_DIR
) -> Path:
    pid = d.get("id")
    if not pid:
        raise ValueError("generated problem missing 'id'")
    if pid in existing_ids:
        raise ValueError(f"id collision: {pid!r} already exists")
    ok, reason = validate_problem_dict(d)
    if not ok:
        raise ValueError(f"invalid generated problem: {reason}")
    generated_dir.mkdir(parents=True, exist_ok=True)
    out = generated_dir / f"{pid}.json"
    if out.exists():
        raise ValueError(f"file already exists for id {pid!r}")
    out.write_text(json.dumps(d, indent=2))
    return out
