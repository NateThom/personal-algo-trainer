# AlgoTrainer — Plan 1: Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end vertical slice of AlgoTrainer — serve a due problem cold, capture a recall gate, run the learner's Python against tests, hand off a session file, ingest a structured verdict, and update the FSRS schedule — proving every architectural boundary in the design before any component is deepened.

**Architecture:** A FastAPI web app owns all mechanics (SQLite store, code judge, FSRS scheduler, static browser UI with CodeMirror). Tutoring/grading is decoupled behind a file-based handoff: the app writes `session-<id>.json` and reads back a schema-validated `verdict-<id>.json`. In this first plan the verdict is produced by a stub (a fixture file / a trivial CLI), so the full loop closes without the real Claude Code tutor skill — which Plan 2 drops in behind the same contract.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLite (stdlib `sqlite3`), py-fsrs (`fsrs`), Pydantic v2 (validation), pytest, ruff. Frontend: static HTML/CSS/vanilla JS + CodeMirror 5 via CDN (no npm build).

## Global Constraints

- Python **3.11+** (use `from __future__ import annotations` not required; 3.11 syntax allowed).
- **No npm / no frontend build toolchain.** Frontend is static files served by FastAPI; CodeMirror loaded from CDN.
- **All timestamps are timezone-aware UTC** (`datetime.now(timezone.utc)`). Never naive datetimes — py-fsrs requires aware datetimes.
- **FSRS ratings** map exactly: `again=1, hard=2, good=3, easy=4` (matches `fsrs.Rating`).
- **The state-file contract is authoritative.** Any data crossing the tool↔tutor boundary is validated against the Pydantic models in `algotrainer/handoff/schema.py`; malformed verdicts are rejected, never partially applied.
- Package name: `algotrainer`. Source under `algotrainer/`, tests under `tests/`, seed content under `content/`, runtime session files under `sessions/` (gitignored).
- Every multi-write DB update (verdict ingestion) runs inside a single transaction.
- Run tests with `pytest`; lint with `ruff check .`.
- **Front-end assets must not load from a CDN without integrity protection.** Preferred: vendor CodeMirror 5 (`codemirror.min.js`, `codemirror.min.css`, `mode/python/python.min.js`) into `algotrainer/web/static/vendor/` and reference local paths — this removes the CDN-compromise vector and works offline. If a CDN is used instead, every `<script>`/`<link>` must carry `integrity="sha384-…"` + `crossorigin="anonymous"` with hashes fetched at implementation time (never fabricated). The Task-9 `index.html` shows CDN URLs for readability; the implementer applies this constraint (vendor them).

---

## File Structure

```
pyproject.toml                         # deps, pytest, ruff config
algotrainer/
  __init__.py
  models.py            # Problem, TestCase dataclasses (shared domain types)
  content.py           # load seed problems from content/problems/*.json
  store.py             # SQLite schema + Store data-access class
  judge.py             # sandboxed subprocess runner -> JudgeResult
  scheduler.py         # SrsScheduler: py-fsrs wrapper + due-selection
  handoff/
    __init__.py
    schema.py          # Pydantic models: SessionFile, Verdict (the contract)
    files.py           # write_session / read_verdict (schema-validated)
  web/
    __init__.py
    app.py             # FastAPI app + routes + verdict ingestion
    static/
      index.html       # solve view (statement, recall gate, editor, results)
      app.js           # front-end flow (fetch next, judge, session, ingest)
      app.css
content/
  problems/
    two-sum.json
    valid-anagram.json
    contains-duplicate.json
    best-time-to-buy-sell-stock.json
tests/
  test_content.py
  test_store.py
  test_judge.py
  test_scheduler.py
  test_handoff.py
  test_web.py          # route-level + full-loop integration (stub verdict)
scripts/
  stub_tutor.py        # reads a session file, writes a trivial verdict (Plan-1 stand-in for the tutor skill)
```

**Responsibility boundaries:** `models`/`content` = domain + seed data; `store` = persistence only; `judge` = code execution only; `scheduler` = FSRS logic only (no I/O beyond what's passed in); `handoff` = the tool↔tutor contract; `web` = HTTP + UI glue. Each is independently testable.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `algotrainer/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable `algotrainer` package; `pytest` and `ruff` runnable.

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import algotrainer

    assert algotrainer.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer'`

- [ ] **Step 3: Create pyproject and package**

`pyproject.toml`:
```toml
[project]
name = "algotrainer"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pydantic>=2.6",
    "fsrs>=5.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27", "ruff>=0.4"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py311"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["algotrainer*"]
```

`algotrainer/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: (empty file)

- [ ] **Step 4: Install and run**

Run: `python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
Then: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml algotrainer/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: project scaffold with pytest and ruff"
```

---

### Task 2: Domain models

**Files:**
- Create: `algotrainer/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `@dataclass(frozen=True) class TestCase: args: list; expected: object`
  - `@dataclass(frozen=True) class Problem: id: str; pattern: str; title: str; difficulty: str; statement: str; function_name: str; starter_code: str; reference_solution: str; tests: list[TestCase]; hints: list[str]`
  - `Problem.from_dict(d: dict) -> Problem`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from algotrainer.models import Problem, TestCase


def test_problem_from_dict_builds_testcases():
    d = {
        "id": "two-sum",
        "pattern": "arrays-hashing",
        "title": "Two Sum",
        "difficulty": "easy",
        "statement": "Return indices of the two numbers that add to target.",
        "function_name": "two_sum",
        "starter_code": "def two_sum(nums, target):\n    pass\n",
        "reference_solution": "def two_sum(nums, target):\n    seen={}\n    for i,n in enumerate(nums):\n        if target-n in seen:\n            return [seen[target-n], i]\n        seen[n]=i\n",
        "tests": [{"args": [[2, 7, 11, 15], 9], "expected": [0, 1]}],
        "hints": ["Which pattern maps input to O(1) lookups?"],
    }
    p = Problem.from_dict(d)
    assert p.id == "two-sum"
    assert isinstance(p.tests[0], TestCase)
    assert p.tests[0].args == [[2, 7, 11, 15], 9]
    assert p.tests[0].expected == [0, 1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.models'`

- [ ] **Step 3: Write implementation**

`algotrainer/models.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TestCase:
    args: list
    expected: object


@dataclass(frozen=True)
class Problem:
    id: str
    pattern: str
    title: str
    difficulty: str
    statement: str
    function_name: str
    starter_code: str
    reference_solution: str
    tests: list[TestCase]
    hints: list[str]

    @classmethod
    def from_dict(cls, d: dict) -> "Problem":
        tests = [TestCase(args=t["args"], expected=t["expected"]) for t in d["tests"]]
        return cls(
            id=d["id"],
            pattern=d["pattern"],
            title=d["title"],
            difficulty=d["difficulty"],
            statement=d["statement"],
            function_name=d["function_name"],
            starter_code=d["starter_code"],
            reference_solution=d["reference_solution"],
            tests=tests,
            hints=list(d.get("hints", [])),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add algotrainer/models.py tests/test_models.py
git commit -m "feat: domain models Problem and TestCase"
```

---

### Task 3: Seed content + loader

**Files:**
- Create: `content/problems/two-sum.json`
- Create: `content/problems/valid-anagram.json`
- Create: `content/problems/contains-duplicate.json`
- Create: `content/problems/best-time-to-buy-sell-stock.json`
- Create: `algotrainer/content.py`
- Test: `tests/test_content.py`

**Interfaces:**
- Consumes: `algotrainer.models.Problem`.
- Produces:
  - `load_problems(content_dir: Path = DEFAULT_CONTENT_DIR) -> list[Problem]`
  - `load_problem(problem_id: str, content_dir: Path = DEFAULT_CONTENT_DIR) -> Problem`
  - `DEFAULT_CONTENT_DIR: Path` (points at repo `content/problems`)
  - **Validation:** loader raises `ValueError` if any problem's `reference_solution` fails its own `tests` (self-consistency guarantee — the same rule reused for AI variants in Plan 4).

- [ ] **Step 1: Author two seed problems (two patterns)**

`content/problems/two-sum.json` (pattern `arrays-hashing`):
```json
{
  "id": "two-sum",
  "pattern": "arrays-hashing",
  "title": "Two Sum",
  "difficulty": "easy",
  "statement": "Given an integer array nums and an integer target, return the indices of the two numbers such that they add up to target. Exactly one solution exists; you may not use the same element twice.",
  "function_name": "two_sum",
  "starter_code": "def two_sum(nums, target):\n    # your code here\n    pass\n",
  "reference_solution": "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n    return []\n",
  "tests": [
    {"args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
    {"args": [[3, 2, 4], 6], "expected": [1, 2]},
    {"args": [[3, 3], 6], "expected": [0, 1]}
  ],
  "hints": [
    "Which pattern turns a repeated 'have I seen X?' question into O(1) lookups?",
    "Keep a hash map from value -> index as you scan once.",
    "For each n, check if (target - n) is already in the map before inserting n."
  ]
}
```

`content/problems/contains-duplicate.json` (pattern `arrays-hashing`):
```json
{
  "id": "contains-duplicate",
  "pattern": "arrays-hashing",
  "title": "Contains Duplicate",
  "difficulty": "easy",
  "statement": "Given an integer array nums, return True if any value appears at least twice, and False if every element is distinct.",
  "function_name": "contains_duplicate",
  "starter_code": "def contains_duplicate(nums):\n    # your code here\n    pass\n",
  "reference_solution": "def contains_duplicate(nums):\n    seen = set()\n    for n in nums:\n        if n in seen:\n            return True\n        seen.add(n)\n    return False\n",
  "tests": [
    {"args": [[1, 2, 3, 1]], "expected": true},
    {"args": [[1, 2, 3, 4]], "expected": false},
    {"args": [[]], "expected": false}
  ],
  "hints": [
    "Same family as Two Sum: fast membership checks.",
    "A set gives O(1) membership; add as you go.",
    "Return True the first time you re-encounter a value."
  ]
}
```

`content/problems/valid-anagram.json` (pattern `arrays-hashing`):
```json
{
  "id": "valid-anagram",
  "pattern": "arrays-hashing",
  "title": "Valid Anagram",
  "difficulty": "easy",
  "statement": "Given two strings s and t, return True if t is an anagram of s, and False otherwise.",
  "function_name": "is_anagram",
  "starter_code": "def is_anagram(s, t):\n    # your code here\n    pass\n",
  "reference_solution": "def is_anagram(s, t):\n    if len(s) != len(t):\n        return False\n    from collections import Counter\n    return Counter(s) == Counter(t)\n",
  "tests": [
    {"args": ["anagram", "nagaram"], "expected": true},
    {"args": ["rat", "car"], "expected": false},
    {"args": ["", ""], "expected": true}
  ],
  "hints": [
    "Counting characters is a hashing problem.",
    "Compare frequency maps of both strings.",
    "Early-exit on unequal lengths."
  ]
}
```

`content/problems/best-time-to-buy-sell-stock.json` (pattern `sliding-window`):
```json
{
  "id": "best-time-to-buy-sell-stock",
  "pattern": "sliding-window",
  "title": "Best Time to Buy and Sell Stock",
  "difficulty": "easy",
  "statement": "You are given an array prices where prices[i] is the price of a stock on day i. Maximize profit by choosing a day to buy and a later day to sell. Return the max profit, or 0 if no profit is possible.",
  "function_name": "max_profit",
  "starter_code": "def max_profit(prices):\n    # your code here\n    pass\n",
  "reference_solution": "def max_profit(prices):\n    best = 0\n    lo = float('inf')\n    for p in prices:\n        lo = min(lo, p)\n        best = max(best, p - lo)\n    return best\n",
  "tests": [
    {"args": [[7, 1, 5, 3, 6, 4]], "expected": 5},
    {"args": [[7, 6, 4, 3, 1]], "expected": 0},
    {"args": [[1]], "expected": 0}
  ],
  "hints": [
    "Think of a window whose left edge is the cheapest price so far.",
    "Track the running minimum price as you scan.",
    "Profit at day i = price[i] - min_price_so_far; keep the max."
  ]
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_content.py`:
```python
from algotrainer.content import load_problems, load_problem


def test_loads_all_seed_problems():
    problems = load_problems()
    ids = {p.id for p in problems}
    assert {"two-sum", "valid-anagram", "contains-duplicate",
            "best-time-to-buy-sell-stock"} <= ids


def test_load_single_problem():
    p = load_problem("two-sum")
    assert p.function_name == "two_sum"


def test_every_reference_solution_passes_its_own_tests():
    # loader must validate self-consistency and not raise
    problems = load_problems()
    assert len(problems) >= 4
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_content.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.content'`

- [ ] **Step 4: Write implementation**

`algotrainer/content.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_content.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add content/problems/*.json algotrainer/content.py tests/test_content.py
git commit -m "feat: seed problem bank + self-validating loader"
```

---

### Task 4: Code judge

**Files:**
- Create: `algotrainer/judge.py`
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: `algotrainer.models.Problem`, `TestCase`.
- Produces:
  - `@dataclass class CaseResult: args: list; expected: object; got: object | None; passed: bool; error: str | None`
  - `@dataclass class JudgeResult: passed: bool; cases: list[CaseResult]; error: str | None; runtime_ms: float`
  - `run_submission(code: str, function_name: str, tests: list[TestCase], timeout_s: float = 5.0) -> JudgeResult`
  - Runs learner code in a **separate subprocess** with a wall-clock timeout; a timeout or crash yields `JudgeResult(passed=False, error=...)` — never hangs or raises to the caller.

- [ ] **Step 1: Write the failing tests**

`tests/test_judge.py`:
```python
from algotrainer.judge import run_submission
from algotrainer.models import TestCase


TESTS = [
    TestCase(args=[[2, 7, 11, 15], 9], expected=[0, 1]),
    TestCase(args=[[3, 3], 6], expected=[0, 1]),
]

GOOD = (
    "def two_sum(nums, target):\n"
    "    seen = {}\n"
    "    for i, n in enumerate(nums):\n"
    "        if target - n in seen:\n"
    "            return [seen[target - n], i]\n"
    "        seen[n] = i\n"
    "    return []\n"
)


def test_correct_submission_passes():
    r = run_submission(GOOD, "two_sum", TESTS)
    assert r.passed is True
    assert all(c.passed for c in r.cases)
    assert r.error is None


def test_wrong_submission_fails_with_case_detail():
    bad = "def two_sum(nums, target):\n    return [0, 0]\n"
    r = run_submission(bad, "two_sum", TESTS)
    assert r.passed is False
    assert r.cases[0].got == [0, 0]


def test_runtime_error_is_captured_not_raised():
    boom = "def two_sum(nums, target):\n    raise RuntimeError('boom')\n"
    r = run_submission(boom, "two_sum", TESTS)
    assert r.passed is False
    assert r.error is not None or any(c.error for c in r.cases)


def test_infinite_loop_times_out():
    loop = "def two_sum(nums, target):\n    while True:\n        pass\n"
    r = run_submission(loop, "two_sum", TESTS, timeout_s=1.0)
    assert r.passed is False
    assert r.error is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.judge'`

- [ ] **Step 3: Write implementation**

`algotrainer/judge.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_judge.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/judge.py tests/test_judge.py
git commit -m "feat: sandboxed subprocess code judge"
```

---

### Task 5: SQLite store

**Files:**
- Create: `algotrainer/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: nothing (stores primitive/JSON values).
- Produces a `Store` class opened on a db path:
  - `Store(db_path: str | Path)` — creates schema on first open (idempotent).
  - `get_card(problem_id: str) -> str | None` — returns stored py-fsrs Card JSON, or None if new.
  - `save_card(problem_id: str, card_json: str, next_due: datetime) -> None`
  - `all_card_due(now: datetime) -> dict[str, datetime]` — problem_id -> next_due for every stored card.
  - `record_attempt(problem_id, code, recall_pattern, recall_approach, recall_complexity, judge_passed, hints_used, created_at) -> int` (returns attempt_id)
  - `record_review(attempt_id, problem_id, rating, review_log_json, reviewed_at) -> None`
  - `ingest_verdict(attempt_id, problem_id, rating, card_json, next_due, review_log_json, reviewed_at) -> None` — saves card + records review in ONE transaction.
  - `close() -> None`
- Tables: `card(problem_id PK, card_json, next_due)`, `attempt(id PK, ...)`, `review(id PK, attempt_id, problem_id, rating, review_log_json, reviewed_at)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py`:
```python
from datetime import datetime, timezone, timedelta

from algotrainer.store import Store


def _store(tmp_path):
    return Store(tmp_path / "t.db")


def test_new_card_is_none(tmp_path):
    s = _store(tmp_path)
    assert s.get_card("two-sum") is None


def test_save_and_get_card(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_card("two-sum", '{"stability": 3.0}', due)
    assert s.get_card("two-sum") == '{"stability": 3.0}'


def test_all_card_due(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=2)
    s.save_card("two-sum", "{}", due)
    mapping = s.all_card_due(datetime.now(timezone.utc))
    assert "two-sum" in mapping
    assert isinstance(mapping["two-sum"], datetime)


def test_ingest_verdict_is_atomic(tmp_path):
    s = _store(tmp_path)
    now = datetime.now(timezone.utc)
    aid = s.record_attempt("two-sum", "code", "arrays-hashing", "hash map", "O(n)",
                           True, 0, now)
    due = now + timedelta(days=1)
    s.ingest_verdict(aid, "two-sum", 3, '{"stability": 3.0}', due, '{"rating": 3}', now)
    assert s.get_card("two-sum") == '{"stability": 3.0}'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.store'`

- [ ] **Step 3: Write implementation**

`algotrainer/store.py`:
```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS card (
    problem_id TEXT PRIMARY KEY,
    card_json  TEXT NOT NULL,
    next_due   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id TEXT NOT NULL,
    code TEXT NOT NULL,
    recall_pattern TEXT,
    recall_approach TEXT,
    recall_complexity TEXT,
    judge_passed INTEGER NOT NULL,
    hints_used INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    rating INTEGER NOT NULL,
    review_log_json TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def get_card(self, problem_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT card_json FROM card WHERE problem_id = ?", (problem_id,)
        ).fetchone()
        return row[0] if row else None

    def save_card(self, problem_id: str, card_json: str, next_due: datetime) -> None:
        self._conn.execute(
            "INSERT INTO card(problem_id, card_json, next_due) VALUES(?,?,?) "
            "ON CONFLICT(problem_id) DO UPDATE SET card_json=excluded.card_json, "
            "next_due=excluded.next_due",
            (problem_id, card_json, _iso(next_due)),
        )
        self._conn.commit()

    def all_card_due(self, now: datetime) -> dict[str, datetime]:
        rows = self._conn.execute("SELECT problem_id, next_due FROM card").fetchall()
        return {pid: datetime.fromisoformat(due) for pid, due in rows}

    def record_attempt(
        self, problem_id, code, recall_pattern, recall_approach, recall_complexity,
        judge_passed, hints_used, created_at,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO attempt(problem_id, code, recall_pattern, recall_approach, "
            "recall_complexity, judge_passed, hints_used, created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (problem_id, code, recall_pattern, recall_approach, recall_complexity,
             int(judge_passed), hints_used, _iso(created_at)),
        )
        self._conn.commit()
        return cur.lastrowid

    def record_review(self, attempt_id, problem_id, rating, review_log_json, reviewed_at):
        self._conn.execute(
            "INSERT INTO review(attempt_id, problem_id, rating, review_log_json, reviewed_at) "
            "VALUES(?,?,?,?,?)",
            (attempt_id, problem_id, rating, review_log_json, _iso(reviewed_at)),
        )
        self._conn.commit()

    def ingest_verdict(
        self, attempt_id, problem_id, rating, card_json, next_due, review_log_json, reviewed_at,
    ) -> None:
        try:
            self._conn.execute("BEGIN")
            self._conn.execute(
                "INSERT INTO card(problem_id, card_json, next_due) VALUES(?,?,?) "
                "ON CONFLICT(problem_id) DO UPDATE SET card_json=excluded.card_json, "
                "next_due=excluded.next_due",
                (problem_id, card_json, _iso(next_due)),
            )
            self._conn.execute(
                "INSERT INTO review(attempt_id, problem_id, rating, review_log_json, reviewed_at) "
                "VALUES(?,?,?,?,?)",
                (attempt_id, problem_id, rating, review_log_json, _iso(reviewed_at)),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/store.py tests/test_store.py
git commit -m "feat: SQLite store with atomic verdict ingestion"
```

---

### Task 6: FSRS scheduler wrapper

**Files:**
- Create: `algotrainer/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: py-fsrs (`fsrs.Scheduler`, `fsrs.Card`, `fsrs.Rating`).
- Produces:
  - `RATING_BY_NAME: dict[str, int] = {"again": 1, "hard": 2, "good": 3, "easy": 4}`
  - `class SrsScheduler:`
    - `new_card_json() -> str` — a fresh serialized Card (due now).
    - `review(card_json: str | None, rating: int, when: datetime) -> tuple[str, datetime, str]` — returns `(updated_card_json, next_due, review_log_json)`. `card_json=None` starts a new card.
    - `due_problem_ids(due_map: dict[str, datetime], all_ids: list[str], now: datetime) -> list[str]` — problems whose stored due ≤ now, plus never-seen problems (not in due_map), preserving `all_ids` order.

- [ ] **Step 1: Write the failing tests**

`tests/test_scheduler.py`:
```python
from datetime import datetime, timezone, timedelta

from algotrainer.scheduler import SrsScheduler, RATING_BY_NAME


def test_rating_map():
    assert RATING_BY_NAME == {"again": 1, "hard": 2, "good": 3, "easy": 4}


def test_review_new_card_returns_future_due():
    s = SrsScheduler()
    now = datetime.now(timezone.utc)
    card_json, next_due, log_json = s.review(None, RATING_BY_NAME["good"], now)
    assert isinstance(card_json, str) and card_json
    assert next_due > now
    assert isinstance(log_json, str) and log_json


def test_again_schedules_sooner_than_easy():
    s = SrsScheduler()
    now = datetime.now(timezone.utc)
    _, due_again, _ = s.review(None, RATING_BY_NAME["again"], now)
    _, due_easy, _ = s.review(None, RATING_BY_NAME["easy"], now)
    assert due_again < due_easy


def test_due_selection_includes_never_seen_and_overdue():
    s = SrsScheduler()
    now = datetime.now(timezone.utc)
    due_map = {
        "seen-overdue": now - timedelta(days=1),
        "seen-future": now + timedelta(days=5),
    }
    all_ids = ["seen-overdue", "seen-future", "never-seen"]
    due = s.due_problem_ids(due_map, all_ids, now)
    assert due == ["seen-overdue", "never-seen"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.scheduler'`

- [ ] **Step 3: Write implementation**

`algotrainer/scheduler.py`:
```python
from datetime import datetime

from fsrs import Card, Rating, Scheduler

RATING_BY_NAME: dict[str, int] = {"again": 1, "hard": 2, "good": 3, "easy": 4}


class SrsScheduler:
    def __init__(self) -> None:
        # Deterministic scheduling (no fuzz) so tests and intervals are reproducible.
        self._scheduler = Scheduler(enable_fuzzing=False)

    def new_card_json(self) -> str:
        return Card().to_json()

    def review(
        self, card_json: str | None, rating: int, when: datetime
    ) -> tuple[str, datetime, str]:
        card = Card.from_json(card_json) if card_json else Card()
        card, review_log = self._scheduler.review_card(
            card=card, rating=Rating(rating), review_datetime=when
        )
        return card.to_json(), card.due, review_log.to_json()

    def due_problem_ids(
        self, due_map: dict[str, datetime], all_ids: list[str], now: datetime
    ) -> list[str]:
        out = []
        for pid in all_ids:
            due = due_map.get(pid)
            if due is None or due <= now:
                out.append(pid)
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/scheduler.py tests/test_scheduler.py
git commit -m "feat: FSRS scheduler wrapper + due selection"
```

---

### Task 7: Handoff contract (schema + files)

**Files:**
- Create: `algotrainer/handoff/__init__.py`
- Create: `algotrainer/handoff/schema.py`
- Create: `algotrainer/handoff/files.py`
- Test: `tests/test_handoff.py`

**Interfaces:**
- Consumes: Pydantic v2.
- Produces:
  - `schema.SessionFile` (Pydantic model): `session_id: str`, `attempt_id: int`, `problem: dict`, `attempt: dict`, `recall: dict`, `hints_used: int`, `request: str` (`"grade"` in Plan 1).
  - `schema.Verdict` (Pydantic model): `session_id: str`, `attempt_id: int`, `problem_id: str`, `grade: Literal["again","hard","good","easy"]`, `approach_used: str | None = None`, `error_code: str | None = None`, `complexity_ok: bool | None = None`, `self_explanation_score: int | None = None`, `feedback: str = ""`.
  - `files.write_session(session_dir: Path, session: SessionFile) -> Path` — writes `sessions/session-<id>.json`.
  - `files.read_verdict(session_dir: Path, session_id: str) -> Verdict` — reads/validates `sessions/verdict-<id>.json`; raises `FileNotFoundError` if absent, `pydantic.ValidationError` if malformed.

- [ ] **Step 1: Write the failing tests**

`tests/test_handoff.py`:
```python
import json

import pytest
from pydantic import ValidationError

from algotrainer.handoff.schema import SessionFile, Verdict
from algotrainer.handoff.files import write_session, read_verdict


def _session(**over):
    base = dict(
        session_id="abc", attempt_id=1, problem={"id": "two-sum"},
        attempt={"code": "x", "judge_passed": True}, recall={"pattern": "arrays-hashing"},
        hints_used=0, request="grade",
    )
    base.update(over)
    return SessionFile(**base)


def test_write_session_creates_file(tmp_path):
    path = write_session(tmp_path, _session())
    assert path.exists()
    assert json.loads(path.read_text())["session_id"] == "abc"


def test_read_valid_verdict(tmp_path):
    (tmp_path / "verdict-abc.json").write_text(json.dumps({
        "session_id": "abc", "attempt_id": 1, "problem_id": "two-sum",
        "grade": "good", "feedback": "Nice, clean hash-map pass.",
    }))
    v = read_verdict(tmp_path, "abc")
    assert v.grade == "good"
    assert v.approach_used is None


def test_missing_verdict_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_verdict(tmp_path, "nope")


def test_malformed_verdict_rejected(tmp_path):
    (tmp_path / "verdict-bad.json").write_text(json.dumps({
        "session_id": "bad", "attempt_id": 1, "problem_id": "two-sum",
        "grade": "brilliant",  # not in the allowed literal set
    }))
    with pytest.raises(ValidationError):
        read_verdict(tmp_path, "bad")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_handoff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.handoff'`

- [ ] **Step 3: Write implementation**

`algotrainer/handoff/__init__.py`: (empty file)

`algotrainer/handoff/schema.py`:
```python
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
```

`algotrainer/handoff/files.py`:
```python
from pathlib import Path

from algotrainer.handoff.schema import SessionFile, Verdict


def write_session(session_dir: Path, session: SessionFile) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"session-{session.session_id}.json"
    path.write_text(session.model_dump_json(indent=2))
    return path


def read_verdict(session_dir: Path, session_id: str) -> Verdict:
    path = session_dir / f"verdict-{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No verdict at {path}")
    return Verdict.model_validate_json(path.read_text())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_handoff.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/handoff tests/test_handoff.py
git commit -m "feat: tool<->tutor handoff contract (schema + files)"
```

---

### Task 8: Stub tutor (Plan-1 stand-in)

**Files:**
- Create: `scripts/stub_tutor.py`
- Test: covered by the integration test in Task 10.

**Interfaces:**
- Consumes: `algotrainer.handoff` (SessionFile/Verdict), `algotrainer.judge` result semantics via the session's `attempt`.
- Produces: a CLI `python scripts/stub_tutor.py <session_dir> <session_id>` that reads the session file and writes a valid `verdict-<id>.json`. Grade rule: `good` if `attempt.judge_passed` is true and `hints_used == 0`; `hard` if passed with hints; `again` if not passed. This mimics the real tutor's output shape so the loop closes in Plan 1.

- [ ] **Step 1: Write implementation**

`scripts/stub_tutor.py`:
```python
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
```

- [ ] **Step 2: Smoke-run it manually (optional sanity)**

(Deferred to the Task 10 integration test, which drives this script end-to-end.)

- [ ] **Step 3: Commit**

```bash
git add scripts/stub_tutor.py
git commit -m "feat: stub tutor stand-in producing schema-valid verdicts"
```

---

### Task 9: Web app — routes + static solve view

**Files:**
- Create: `algotrainer/web/__init__.py`
- Create: `algotrainer/web/app.py`
- Create: `algotrainer/web/static/index.html`
- Create: `algotrainer/web/static/app.js`
- Create: `algotrainer/web/static/app.css`
- Test: `tests/test_web.py` (routes; full loop added in Task 10)

**Interfaces:**
- Consumes: `content.load_problems/load_problem`, `judge.run_submission`, `scheduler.SrsScheduler`, `store.Store`, `handoff` (schema + files).
- Produces a FastAPI app via `create_app(db_path, content_dir, session_dir) -> FastAPI` with routes:
  - `GET /` → serves `index.html`.
  - `GET /api/next` → `{problem: {id,title,pattern,difficulty,statement,function_name,starter_code}}` for the next due problem (reference_solution/tests/hints **omitted** so the client never sees the answer). 404-safe: returns `{problem: null}` if none.
  - `POST /api/judge` body `{problem_id, code}` → runs judge, returns `{passed, cases:[{args,expected,got,passed,error}], error, runtime_ms}`.
  - `POST /api/session` body `{problem_id, code, recall:{pattern,approach,complexity}, judge_passed, hints_used}` → records attempt, writes session file, returns `{session_id, attempt_id}`.
  - `POST /api/verdict/ingest` body `{session_id}` → reads verdict, runs scheduler.review, ingests atomically, returns `{grade, next_due, feedback}`.

- [ ] **Step 1: Write the failing route tests**

`tests/test_web.py`:
```python
from fastapi.testclient import TestClient

from algotrainer.web.app import create_app


def _client(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        content_dir=None,  # use default seed content
        session_dir=tmp_path / "sessions",
    )
    return TestClient(app)


def test_index_served(tmp_path):
    c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "AlgoTrainer" in r.text


def test_next_returns_problem_without_solution(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/next")
    assert r.status_code == 200
    prob = r.json()["problem"]
    assert prob is not None
    assert "reference_solution" not in prob
    assert "tests" not in prob


def test_judge_endpoint_runs_code(tmp_path):
    c = _client(tmp_path)
    code = ("def two_sum(nums, target):\n    seen={}\n"
            "    for i,n in enumerate(nums):\n"
            "        if target-n in seen: return [seen[target-n], i]\n"
            "        seen[n]=i\n")
    r = c.post("/api/judge", json={"problem_id": "two-sum", "code": code})
    assert r.status_code == 200
    assert r.json()["passed"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_web.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.web.app'`

- [ ] **Step 3: Write the FastAPI app**

`algotrainer/web/__init__.py`: (empty file)

`algotrainer/web/app.py`:
```python
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from algotrainer.content import DEFAULT_CONTENT_DIR, load_problem, load_problems
from algotrainer.handoff.files import read_verdict, write_session
from algotrainer.handoff.schema import SessionFile
from algotrainer.judge import run_submission
from algotrainer.scheduler import RATING_BY_NAME, SrsScheduler
from algotrainer.store import Store

_STATIC = Path(__file__).resolve().parent / "static"


class JudgeBody(BaseModel):
    problem_id: str
    code: str


class SessionBody(BaseModel):
    problem_id: str
    code: str
    recall: dict
    judge_passed: bool
    hints_used: int = 0


class IngestBody(BaseModel):
    session_id: str


def create_app(db_path, content_dir, session_dir) -> FastAPI:
    content_dir = content_dir or DEFAULT_CONTENT_DIR
    session_dir = Path(session_dir)
    app = FastAPI(title="AlgoTrainer")
    store = Store(db_path)
    scheduler = SrsScheduler()
    problems = {p.id: p for p in load_problems(content_dir)}

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    @app.get("/api/next")
    def next_problem():
        now = datetime.now(timezone.utc)
        due_map = store.all_card_due(now)
        ids = scheduler.due_problem_ids(due_map, list(problems), now)
        if not ids:
            return {"problem": None}
        p = problems[ids[0]]
        return {"problem": {
            "id": p.id, "title": p.title, "pattern": p.pattern,
            "difficulty": p.difficulty, "statement": p.statement,
            "function_name": p.function_name, "starter_code": p.starter_code,
        }}

    @app.post("/api/judge")
    def judge(body: JudgeBody):
        p = problems[body.problem_id]
        r = run_submission(body.code, p.function_name, p.tests)
        return {
            "passed": r.passed, "error": r.error, "runtime_ms": r.runtime_ms,
            "cases": [
                {"args": c.args, "expected": c.expected, "got": c.got,
                 "passed": c.passed, "error": c.error} for c in r.cases
            ],
        }

    @app.post("/api/session")
    def session(body: SessionBody):
        now = datetime.now(timezone.utc)
        attempt_id = store.record_attempt(
            body.problem_id, body.code, body.recall.get("pattern"),
            body.recall.get("approach"), body.recall.get("complexity"),
            body.judge_passed, body.hints_used, now,
        )
        sid = uuid.uuid4().hex[:12]
        p = problems[body.problem_id]
        sf = SessionFile(
            session_id=sid, attempt_id=attempt_id,
            problem={"id": p.id, "title": p.title, "pattern": p.pattern,
                     "statement": p.statement, "reference_solution": p.reference_solution},
            attempt={"code": body.code, "judge_passed": body.judge_passed},
            recall=body.recall, hints_used=body.hints_used, request="grade",
        )
        write_session(session_dir, sf)
        return {"session_id": sid, "attempt_id": attempt_id}

    @app.post("/api/verdict/ingest")
    def ingest(body: IngestBody):
        try:
            verdict = read_verdict(session_dir, body.session_id)
        except FileNotFoundError:
            return JSONResponse({"error": "verdict not found yet"}, status_code=409)
        now = datetime.now(timezone.utc)
        rating = RATING_BY_NAME[verdict.grade]
        card_json = store.get_card(verdict.problem_id)
        new_card_json, next_due, log_json = scheduler.review(card_json, rating, now)
        store.ingest_verdict(
            verdict.attempt_id, verdict.problem_id, rating,
            new_card_json, next_due, log_json, now,
        )
        return {"grade": verdict.grade, "next_due": next_due.isoformat(),
                "feedback": verdict.feedback}

    return app
```

- [ ] **Step 4: Write the static front end**

`algotrainer/web/static/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AlgoTrainer</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css" />
  <link rel="stylesheet" href="/static/app.css" />
</head>
<body>
  <header><h1>AlgoTrainer</h1><span id="pattern-badge"></span></header>
  <main>
    <section id="problem">
      <h2 id="title">Loading…</h2>
      <p id="statement"></p>
    </section>
    <section id="recall">
      <h3>Before you code — recall gate</h3>
      <label>Which pattern is this? <input id="r-pattern" /></label>
      <label>Approach (2–4 sentences): <textarea id="r-approach"></textarea></label>
      <label>Predicted time/space complexity: <input id="r-complexity" /></label>
    </section>
    <section id="editor-wrap">
      <textarea id="editor"></textarea>
      <div class="actions">
        <button id="run">Run tests</button>
        <button id="handoff" disabled>Send to tutor</button>
        <button id="ingest" disabled>Ingest verdict</button>
      </div>
      <pre id="results"></pre>
    </section>
  </main>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>
```

`algotrainer/web/static/app.css`:
```css
body { font-family: system-ui, sans-serif; margin: 0; color: #1a1a2e; }
header { background: #16213e; color: #fff; padding: 12px 20px; display: flex;
  justify-content: space-between; align-items: center; }
main { max-width: 900px; margin: 20px auto; padding: 0 16px; display: grid; gap: 20px; }
section { border: 1px solid #ddd; border-radius: 8px; padding: 16px; }
label { display: block; margin: 8px 0; }
input, textarea { width: 100%; padding: 6px; font: inherit; }
.CodeMirror { border: 1px solid #ccc; height: 320px; }
.actions { margin: 12px 0; display: flex; gap: 8px; }
button { padding: 8px 16px; cursor: pointer; }
#results { background: #0f0f23; color: #6be675; padding: 12px; min-height: 40px;
  white-space: pre-wrap; border-radius: 6px; }
</style>
```

`algotrainer/web/static/app.js`:
```javascript
let current = null;      // current problem
let sessionId = null;    // last handoff session
let hintsUsed = 0;
let editor = null;

async function loadNext() {
  const r = await fetch("/api/next");
  const { problem } = await r.json();
  current = problem;
  if (!problem) {
    document.getElementById("title").textContent = "Nothing due — you're caught up!";
    document.getElementById("statement").textContent = "";
    return;
  }
  document.getElementById("title").textContent = problem.title;
  document.getElementById("statement").textContent = problem.statement;
  document.getElementById("pattern-badge").textContent = "";  // pattern hidden on purpose
  editor.setValue(problem.starter_code);
  document.getElementById("results").textContent = "";
  document.getElementById("handoff").disabled = true;
  document.getElementById("ingest").disabled = true;
  hintsUsed = 0;
}

async function runTests() {
  const r = await fetch("/api/judge", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_id: current.id, code: editor.getValue() }),
  });
  const res = await r.json();
  window._lastPassed = res.passed;
  document.getElementById("results").textContent =
    (res.passed ? "ALL TESTS PASSED\n\n" : "SOME TESTS FAILED\n\n") +
    (res.error ? "Error: " + res.error + "\n" : "") +
    res.cases.map((c, i) =>
      `#${i + 1} ${c.passed ? "ok" : "FAIL"} args=${JSON.stringify(c.args)} ` +
      `expected=${JSON.stringify(c.expected)} got=${JSON.stringify(c.got)}` +
      (c.error ? " err=" + c.error : "")).join("\n");
  document.getElementById("handoff").disabled = false;
}

async function handoff() {
  const recall = {
    pattern: document.getElementById("r-pattern").value,
    approach: document.getElementById("r-approach").value,
    complexity: document.getElementById("r-complexity").value,
  };
  const r = await fetch("/api/session", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      problem_id: current.id, code: editor.getValue(), recall,
      judge_passed: !!window._lastPassed, hints_used: hintsUsed,
    }),
  });
  const { session_id } = await r.json();
  sessionId = session_id;
  document.getElementById("results").textContent +=
    `\n\nSession written: sessions/session-${session_id}.json\n` +
    `In Claude Code, run the tutor on this session, then click "Ingest verdict".`;
  document.getElementById("ingest").disabled = false;
}

async function ingest() {
  const r = await fetch("/api/verdict/ingest", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (r.status === 409) {
    document.getElementById("results").textContent += "\n\nNo verdict yet — run the tutor first.";
    return;
  }
  const res = await r.json();
  document.getElementById("results").textContent +=
    `\n\nGRADE: ${res.grade}\nNext due: ${res.next_due}\nTutor: ${res.feedback}`;
  setTimeout(loadNext, 1500);
}

window.addEventListener("DOMContentLoaded", () => {
  editor = CodeMirror.fromTextArea(document.getElementById("editor"),
    { mode: "python", lineNumbers: true, indentUnit: 4 });
  document.getElementById("run").addEventListener("click", runTests);
  document.getElementById("handoff").addEventListener("click", handoff);
  document.getElementById("ingest").addEventListener("click", ingest);
  loadNext();
});
```

- [ ] **Step 5: Run route tests to verify they pass**

Run: `pytest tests/test_web.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add algotrainer/web tests/test_web.py
git commit -m "feat: FastAPI app + static solve view (editor, recall gate, judge, handoff)"
```

---

### Task 10: Full-loop integration test + run entrypoint

**Files:**
- Modify: `tests/test_web.py` (append the integration test)
- Create: `algotrainer/__main__.py` (uvicorn entrypoint)
- Test: the appended integration test.

**Interfaces:**
- Consumes: all prior tasks + `scripts/stub_tutor.py`.
- Produces: `python -m algotrainer` launches the server on `http://127.0.0.1:8000`.

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_web.py`:
```python
import subprocess
import sys
from pathlib import Path


def test_full_loop_with_stub_tutor(tmp_path):
    session_dir = tmp_path / "sessions"
    app = create_app(db_path=tmp_path / "t.db", content_dir=None, session_dir=session_dir)
    c = TestClient(app)

    prob = c.get("/api/next").json()["problem"]
    code = ("def two_sum(nums, target):\n    seen={}\n"
            "    for i,n in enumerate(nums):\n"
            "        if target-n in seen: return [seen[target-n], i]\n"
            "        seen[n]=i\n") if prob["id"] == "two-sum" else \
        load_default_solution(prob["id"])

    judged = c.post("/api/judge", json={"problem_id": prob["id"], "code": code}).json()
    sess = c.post("/api/session", json={
        "problem_id": prob["id"], "code": code,
        "recall": {"pattern": prob["pattern"], "approach": "x", "complexity": "O(n)"},
        "judge_passed": judged["passed"], "hints_used": 0,
    }).json()

    # Run the stub tutor exactly as the human would run the real tutor skill.
    subprocess.run(
        [sys.executable, "scripts/stub_tutor.py", str(session_dir), sess["session_id"]],
        check=True, cwd=Path(__file__).resolve().parent.parent,
    )

    ingested = c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]}).json()
    assert ingested["grade"] in {"again", "hard", "good", "easy"}
    assert "next_due" in ingested


def load_default_solution(problem_id: str) -> str:
    from algotrainer.content import load_problem
    return load_problem(problem_id).reference_solution
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py::test_full_loop_with_stub_tutor -v`
Expected: FAIL (until `scripts/stub_tutor.py` from Task 8 is present and importable — if Task 8 is done, this should surface any wiring gaps first).

- [ ] **Step 3: Write the entrypoint**

`algotrainer/__main__.py`:
```python
from pathlib import Path

import uvicorn

from algotrainer.web.app import create_app

_ROOT = Path(__file__).resolve().parent.parent

app = create_app(
    db_path=_ROOT / "algotrainer.db",
    content_dir=None,
    session_dir=_ROOT / "sessions",
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: PASS (all tests)

- [ ] **Step 5: Manual end-to-end smoke**

Run: `python -m algotrainer`
Then open `http://127.0.0.1:8000`, solve Two Sum, click **Run tests** → **Send to tutor**, then in a terminal:
`python scripts/stub_tutor.py sessions <session_id>` (id shown in the results pane), then click **Ingest verdict**.
Expected: a grade + next-due appears; the next due problem loads.

- [ ] **Step 6: Commit**

```bash
git add algotrainer/__main__.py tests/test_web.py
git commit -m "feat: full-loop integration test + uvicorn entrypoint"
```

---

## Self-Review (against the spec)

**Spec coverage (Plan 1 slice):**
- Closed loop cold-problem → recall gate → judge → handoff → verdict → FSRS update — Tasks 3,4,6,7,9,10 ✓
- Pattern-hidden serving (§5 "shown cold") — `/api/next` omits pattern badge + solution ✓
- FSRS scheduling at problem level — Task 6 ✓ (pattern-level scheduling is Plan 3)
- File-based handoff contract, schema-validated, no partial application — Tasks 5 (atomic ingest) + 7 ✓
- Seed content + self-consistency validation (reused for AI variants later) — Task 3 ✓
- Judge sandbox with timeout — Task 4 ✓
- Zero-API-cost tutor boundary — stub in Plan 1 (Task 8), real skill in Plan 2 ✓

**Deferred to later plans (by design, tracked in the roadmap below):** pattern-level FSRS + session composer/interleaving (Plan 3), mastery model + gate + error journal driving scheduling (Plan 3), the real Claude Code tutor skill + hint ladder (Plan 2), AI variant generation (Plan 4), dashboards + full roadmap seed (Plan 4).

**Placeholder scan:** none — every code step is complete.

**Type consistency:** `Problem`/`TestCase` fields consistent across content/judge/web; `SrsScheduler.review` signature `(card_json|None, rating:int, when)` matches its call in `app.ingest`; `RATING_BY_NAME` keys match `Verdict.grade` literals; `Store.ingest_verdict` args match the `app.ingest` call site; `write_session`/`read_verdict` signatures match `app` usage.

---

## Roadmap: subsequent plans

Each is its own spec-covered plan producing working software, built behind the same interfaces this skeleton establishes:

- **Plan 2 — Real tutor skill + hint ladder.** Replace the stub with an in-repo Claude Code skill + slash command that reads `session-<id>.json`, runs the Socratic hint ladder and grading/approach-classification/error-coding, and writes `verdict-<id>.json`. Add the graduated hint endpoint + UI (`request:"hint"`).
- **Plan 3 — Learning-science depth.** Pattern-level FSRS (aggregate from problem outcomes), session composer with maturity-driven blocked→interleaved ratio and confusable-pattern mixing, mastery model + criterion gate + memorization-trap detection, error-taxonomy journal that reweights scheduling.
- **Plan 4 — Content scale + AI variants + dashboards.** Full ~22–24 pattern roadmap seeded thin, AI variant generation via the tutor skill (validated by the Task-3 self-consistency rule before serving), and mastery/due/error dashboards.
