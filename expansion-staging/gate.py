#!/usr/bin/env python
"""Mechanical gate for new AlgoTrainer bank problems.

Usage: /Users/nthom/personal-algo-trainer/.venv/bin/python gate.py <candidate.json>
Exits 0 with "GATE PASS" on success; exits 1 printing every failure otherwise.

Checks (plan docs/plans/2026-07-07-bank-expansion.md step 3):
  - loads as JSON, validate_problem_dict (shape + reference passes own tests)
  - id: kebab-case, unique vs content/problems/ AND other staged candidates
  - pattern is one of the 18 known patterns; difficulty easy|medium|hard
  - exactly 3 hints, all non-empty strings
  - 6-8 tests; expected values JSON-native and reference output round-trips
    (kills tuple/set returns even when == would hide them... it wouldn't, but
    belt and braces)
  - starter_code defines function_name with the same arg signature as the
    reference solution and body is a stub (contains pass, no return of logic)
  - statement mentions nothing empty: minimal length sanity only
"""
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from algotrainer.validation import validate_problem_dict  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
STAGING = Path(__file__).parent / "pending"
PATTERNS = {
    "arrays-hashing", "backtracking", "binary-search", "bit-manipulation",
    "dp-1d", "dp-2d", "graphs", "heaps", "intervals", "linked-list",
    "prefix-sum", "sliding-window", "stack", "topological-sort", "trees",
    "tries", "two-pointers", "union-find",
}


def arg_names(src: str, fn: str):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn:
            return [a.arg for a in node.args.args]
    return None


def main(path: str) -> int:
    errors = []
    p = Path(path)
    try:
        d = json.loads(p.read_text())
    except Exception as e:
        print(f"FAIL: not valid JSON: {e}")
        return 1

    ok, err = validate_problem_dict(d)
    if not ok:
        errors.append(f"validate_problem_dict: {err}")

    pid = d.get("id", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", pid):
        errors.append(f"id not kebab-case: {pid!r}")
    existing = {json.loads(f.read_text())["id"] for f in (REPO / "content/problems").glob("*.json")}
    if pid in existing:
        errors.append(f"id collides with existing bank problem: {pid}")
    for f in STAGING.glob("*.json"):
        if f.resolve() == p.resolve():
            continue
        try:
            other = json.loads(f.read_text())
        except Exception:
            continue
        if other.get("id") == pid:
            errors.append(f"id collides with staged candidate {f.name}")
    if p.stem != pid:
        errors.append(f"filename {p.name} must be <id>.json ({pid}.json)")

    if d.get("pattern") not in PATTERNS:
        errors.append(f"unknown pattern: {d.get('pattern')!r}")
    if d.get("difficulty") not in ("easy", "medium", "hard"):
        errors.append(f"bad difficulty: {d.get('difficulty')!r}")

    hints = d.get("hints", [])
    if not (isinstance(hints, list) and len(hints) == 3 and all(isinstance(h, str) and h.strip() for h in hints)):
        errors.append(f"need exactly 3 non-empty string hints, got {len(hints) if isinstance(hints, list) else type(hints)}")

    tests = d.get("tests", [])
    if not (6 <= len(tests) <= 8):
        errors.append(f"need 6-8 tests, got {len(tests)}")

    # JSON-native round-trip of actual reference output on each test
    fn_name = d.get("function_name", "")
    ns: dict = {}
    try:
        exec(d.get("reference_solution", ""), ns)
        fn = ns.get(fn_name)
        if fn:
            for i, tc in enumerate(tests):
                got = fn(*[json.loads(json.dumps(a)) for a in tc["args"]])
                round_tripped = json.loads(json.dumps(got, allow_nan=False)) if got is not None else None
                if round_tripped != got or type(round_tripped) is not type(got):
                    errors.append(f"test {i}: reference output {got!r} is not JSON-native")
    except Exception as e:
        errors.append(f"reference execution for JSON-native check failed: {e}")

    ref_args = arg_names(d.get("reference_solution", ""), fn_name)
    try:
        starter_args = arg_names(d.get("starter_code", ""), fn_name)
    except SyntaxError as e:
        starter_args = None
        errors.append(f"starter_code does not parse: {e}")
    if starter_args is None:
        errors.append(f"starter_code does not define {fn_name!r}")
    elif ref_args is not None and starter_args != ref_args:
        errors.append(f"starter args {starter_args} != reference args {ref_args}")
    if starter_args is not None and "pass" not in d.get("starter_code", ""):
        errors.append("starter_code should be a stub containing pass")

    if len(d.get("statement", "")) < 80:
        errors.append("statement suspiciously short (<80 chars)")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", fn_name or ""):
        errors.append(f"function_name not snake_case: {fn_name!r}")

    if errors:
        print("GATE FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("GATE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
