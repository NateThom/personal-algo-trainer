"""Plan-1 stand-in for the Claude Code tutor skill. Produces a schema-valid verdict
from mechanical rules so the full loop closes before the real tutor exists (Plan 2)."""
import json
import sys
from pathlib import Path

from algotrainer.handoff.schema import Verdict


def main(session_dir: str, session_id: str) -> None:
    sdir = Path(session_dir)
    session = json.loads((sdir / f"session-{session_id}.json").read_text())
    passed = bool(session["attempt"].get("judge_passed"))
    hints = int(session.get("hints_used", 0))
    if not passed:
        grade = "again"
    elif hints > 0:
        grade = "hard"
    else:
        grade = "good"
    verdict = Verdict(
        session_id=session_id,
        attempt_id=session["attempt_id"],
        problem_id=session["problem"]["id"],
        grade=grade,
        approach_used=session["recall"].get("pattern"),
        complexity_ok=passed,
        feedback=f"[stub tutor] graded '{grade}' from judge result.",
    )
    (sdir / f"verdict-{session_id}.json").write_text(verdict.model_dump_json(indent=2))
    print(f"wrote verdict-{session_id}.json: {grade}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
