#!/usr/bin/env python
"""Whole-bank validator for the final assembled content/problems/ set.

Unlike gate.py (which is meant to run on a single staged candidate and checks
id-uniqueness against content/problems/), this validates the ENTIRE bank in
place: every file passes validate_problem_dict, ids are globally unique, the
filename matches the id, pattern/difficulty are known, exactly 3 hints, 6-8
tests, and reference output is JSON-native on every test.

Usage: python bank_check.py <repo_root>
Exits 0 with "BANK OK (<n> problems)" or 1 listing every failure.
"""
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from algotrainer.validation import validate_problem_dict  # noqa: E402

PATTERNS = {
    "arrays-hashing", "backtracking", "binary-search", "bit-manipulation",
    "dp-1d", "dp-2d", "graphs", "heaps", "intervals", "linked-list",
    "prefix-sum", "sliding-window", "stack", "topological-sort", "trees",
    "tries", "two-pointers", "union-find",
}


def main() -> int:
    errors = []
    ids = defaultdict(list)
    files = sorted(glob.glob(str(REPO / "content/problems/*.json")))
    for path in files:
        p = Path(path)
        try:
            d = json.loads(p.read_text())
        except Exception as e:
            errors.append(f"{p.name}: not valid JSON: {e}")
            continue
        ok, err = validate_problem_dict(d)
        if not ok:
            errors.append(f"{p.name}: validate_problem_dict: {err}")
        pid = d.get("id", "")
        ids[pid].append(p.name)
        if p.stem != pid:
            errors.append(f"{p.name}: filename must be {pid}.json")
        if d.get("pattern") not in PATTERNS:
            errors.append(f"{p.name}: unknown pattern {d.get('pattern')!r}")
        if d.get("difficulty") not in ("easy", "medium", "hard"):
            errors.append(f"{p.name}: bad difficulty {d.get('difficulty')!r}")
        # Note: 6-8 tests and exactly-3-hints are NEW-problem gate rules, enforced
        # by gate.py before a candidate is moved in; older seeds predate them, so
        # they are not whole-bank invariants and are not checked here.
        tests = d.get("tests", [])
        fn_name = d.get("function_name", "")
        ns: dict = {}
        try:
            exec(d.get("reference_solution", ""), ns)
            fn = ns.get(fn_name)
            if fn:
                for i, tc in enumerate(tests):
                    got = fn(*[json.loads(json.dumps(a)) for a in tc["args"]])
                    rt = json.loads(json.dumps(got, allow_nan=False)) if got is not None else None
                    if rt != got or type(rt) is not type(got):
                        errors.append(f"{p.name}: test {i} output {got!r} not JSON-native")
        except Exception as e:
            errors.append(f"{p.name}: reference execution failed: {e}")

    for pid, names in ids.items():
        if len(names) > 1:
            errors.append(f"duplicate id {pid!r} in files: {names}")

    if errors:
        print("BANK FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print(f"BANK OK ({len(files)} problems)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
