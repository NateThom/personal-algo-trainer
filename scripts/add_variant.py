"""Validating writer for AI-generated problem variants — the sanctioned channel
the tutor skill uses. Reads a candidate problem JSON on stdin; saves it only if
it validates and its id is unique across seed + generated. Fails closed."""
import json
import sys

from algotrainer.content import load_problems
from algotrainer.generated import load_generated, save_generated_problem


def main() -> int:
    try:
        cand = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(f"invalid JSON on stdin: {e}", file=sys.stderr)
        return 2
    existing = {p.id for p in load_problems()} | {p.id for p in load_generated()}
    try:
        path = save_generated_problem(cand, existing_ids=existing)
    except ValueError as e:
        print(f"rejected: {e}", file=sys.stderr)
        return 1
    print(str(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
