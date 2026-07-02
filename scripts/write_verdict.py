"""Validating verdict writer — the sanctioned channel for the tutor skill.
Reads a JSON object of Verdict fields on stdin, validates, writes verdict-<id>.json.
Exits nonzero without writing if validation fails, so a bad verdict never lands."""
import json
import sys
from pathlib import Path

from algotrainer.handoff.schema import Verdict


def main(session_dir: str) -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(f"invalid JSON on stdin: {e}", file=sys.stderr)
        return 2
    try:
        verdict = Verdict(**payload)
    except Exception as e:  # pydantic ValidationError or bad kwargs
        print(f"verdict validation failed: {e}", file=sys.stderr)
        return 1
    out = Path(session_dir) / f"verdict-{verdict.session_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(verdict.model_dump_json(indent=2))
    print(str(out))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: write_verdict.py <session_dir>  (verdict JSON on stdin)", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
