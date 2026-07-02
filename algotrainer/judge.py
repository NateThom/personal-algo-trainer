import json
import subprocess
import sys
import time
from dataclasses import dataclass

from algotrainer.models import TestCase

# Runner executed in a child process. Reads {code, function_name, tests} as JSON
# on argv[1], prints a JSON result on stdout.
_RUNNER = r'''
import json, sys
payload = json.loads(sys.argv[1])
ns = {}
cases = []
try:
    exec(payload["code"], ns)
    fn = ns[payload["function_name"]]
except Exception as e:  # compile/def error -> whole submission fails
    print(json.dumps({"fatal": f"{type(e).__name__}: {e}"}))
    sys.exit(0)
for tc in payload["tests"]:
    try:
        got = fn(*tc["args"])
        cases.append({"args": tc["args"], "expected": tc["expected"],
                      "got": got, "passed": got == tc["expected"], "error": None})
    except Exception as e:
        cases.append({"args": tc["args"], "expected": tc["expected"],
                      "got": None, "passed": False, "error": f"{type(e).__name__}: {e}"})
print(json.dumps({"cases": cases}))
'''


@dataclass
class CaseResult:
    args: list
    expected: object
    got: object | None
    passed: bool
    error: str | None


@dataclass
class JudgeResult:
    passed: bool
    cases: list[CaseResult]
    error: str | None
    runtime_ms: float


def run_submission(
    code: str, function_name: str, tests: list[TestCase], timeout_s: float = 5.0
) -> JudgeResult:
    payload = json.dumps(
        {
            "code": code,
            "function_name": function_name,
            "tests": [{"args": t.args, "expected": t.expected} for t in tests],
        }
    )
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _RUNNER, payload],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - start) * 1000
        return JudgeResult(False, [], f"Timed out after {timeout_s}s", elapsed)

    elapsed = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        return JudgeResult(False, [], proc.stderr.strip() or "Subprocess crashed", elapsed)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return JudgeResult(False, [], f"Bad runner output: {proc.stdout[:200]}", elapsed)

    if "fatal" in data:
        return JudgeResult(False, [], data["fatal"], elapsed)

    cases = [
        CaseResult(c["args"], c["expected"], c["got"], c["passed"], c["error"])
        for c in data["cases"]
    ]
    return JudgeResult(all(c.passed for c in cases) and bool(cases), cases, None, elapsed)
