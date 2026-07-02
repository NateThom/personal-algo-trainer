# AlgoTrainer — Plan 4: Content Scale + AI Variants + Dashboards

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Complete the design's vision: (1) an AI-variant pipeline so reviews draw *novel* instances — the tutor skill generates a fresh problem for a pattern, and a validating CLI accepts it only if its reference solution passes its own tests before it can ever be served; (2) the web app prefers never-seen instances so a pattern review isn't a re-solve of the same problem; (3) a real dashboard (due, mastery, error trends); (4) a moderate expansion of the vetted seed bank across more patterns.

**Architecture:** A reusable `validation.py` (single source of the "reference solution must pass its own tests" rule, which `content.py` is refactored to use) underpins a `generated.py` store that loads/saves validated generated problems under `content/generated/` (runtime, gitignored). `scripts/add_variant.py` is the sanctioned channel the tutor skill uses to persist a generated problem — it validates and rejects invalid or id-colliding candidates. The app merges seed + generated problems, exposes `POST /api/reload` to pick up new variants without a restart, and `/api/next` prefers unseen problems (novel instances). A new `GET /api/dashboard` aggregates due count, per-pattern mastery, and error-taxonomy trends behind a dashboard UI.

**Tech Stack:** unchanged.

## Global Constraints

- Python **3.11+**; tz-aware UTC; deterministic FSRS.
- **One validation rule, one place.** `validation.validate_problem_dict` is the single implementation of "reference solution must pass every one of its own tests"; `content.py` and `generated.py` both use it. No duplicated exec-and-compare logic.
- **Generated problems are never served unless valid.** `add_variant.py` / `save_generated_problem` must reject (nonzero / raise) a candidate whose reference solution fails its tests, whose shape is bad, or whose `id` collides with an existing seed or generated problem — WITHOUT writing a file.
- **Novel-instance principle:** `/api/next` prefers a due problem that has NO prior graded attempt over one already attempted.
- `content/generated/` is runtime, per-learner, gitignored (like `algotrainer.db`). Seed problems under `content/problems/` remain committed and vetted.
- Run tests `.venv/bin/pytest`; lint `.venv/bin/ruff check algotrainer tests scripts`. Pristine. Commit per task; stage only named files.

---

## File Structure

```
algotrainer/
  validation.py         # NEW: validate_problem_dict (single source of the self-consistency rule)
  content.py            # MODIFY: use validation.validate_problem_dict
  generated.py          # NEW: load_generated / save_generated_problem (validated)
  web/app.py            # MODIFY: merge generated pool, /api/reload, novel-instance next, /api/dashboard
  web/static/index.html # MODIFY: dashboard section
  web/static/app.js     # MODIFY: render dashboard
  web/static/app.css    # MODIFY: dashboard styling
scripts/
  add_variant.py        # NEW: validating generated-problem writer (used by the tutor skill)
content/
  generated/            # NEW dir (gitignored); .gitkeep committed
  problems/             # + expanded seed problems
.claude/skills/algotrainer-tutor/
  SKILL.md              # MODIFY: add "generate a variant" mode
  references/variant.md # NEW: variant authoring spec
tests/
  test_validation.py    # NEW
  test_generated.py     # NEW
  test_add_variant.py   # NEW
  test_web_variants.py  # NEW (reload + novel-instance + dashboard)
docs/USING_THE_TUTOR.md # MODIFY: variant workflow
```

---

### Task 1: Validation module + content refactor

**Files:**
- Create: `algotrainer/validation.py`
- Modify: `algotrainer/content.py` (use the new module; behavior preserved)
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `validate_problem_dict(d: dict) -> tuple[bool, str | None]` — `(True, None)` if the dict builds a `Problem` AND its `reference_solution` returns each test's `expected`; else `(False, reason)`. Never raises.
- `content._run_reference` is reimplemented to call `validate_problem_dict` and raise `ValueError(reason)` on failure (so `load_problem(s)` behavior is unchanged).

- [ ] **Step 1: Write the failing tests**

`tests/test_validation.py`:
```python
from algotrainer.validation import validate_problem_dict

GOOD = {
    "id": "t", "pattern": "arrays-hashing", "title": "T", "difficulty": "easy",
    "statement": "s", "function_name": "f",
    "starter_code": "def f(x):\n    pass\n",
    "reference_solution": "def f(x):\n    return x + 1\n",
    "tests": [{"args": [1], "expected": 2}, {"args": [5], "expected": 6}],
    "hints": [],
}


def test_valid():
    ok, err = validate_problem_dict(GOOD)
    assert ok is True and err is None


def test_wrong_expected_detected():
    bad = {**GOOD, "tests": [{"args": [1], "expected": 999}]}
    ok, err = validate_problem_dict(bad)
    assert ok is False and "mismatch" in err.lower()


def test_runtime_error_detected():
    bad = {**GOOD, "reference_solution": "def f(x):\n    raise ValueError('x')\n"}
    ok, err = validate_problem_dict(bad)
    assert ok is False


def test_bad_shape_detected():
    ok, err = validate_problem_dict({"id": "only"})
    assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_validation.py -v`
Expected: FAIL — no module `algotrainer.validation`.

- [ ] **Step 3: Write the validation module**

`algotrainer/validation.py`:
```python
"""Single source of the problem self-consistency rule: a problem's reference
solution must return each test's expected value. Used by seed loading and by
AI-variant acceptance."""
from algotrainer.models import Problem


def validate_problem_dict(d: dict) -> tuple[bool, str | None]:
    try:
        p = Problem.from_dict(d)
    except Exception as e:  # missing keys / bad shape
        return False, f"bad problem shape: {e}"
    namespace: dict = {}
    try:
        exec(p.reference_solution, namespace)  # noqa: S102 - trusted/generated content, validated here
    except Exception as e:
        return False, f"reference_solution failed to define: {e}"
    fn = namespace.get(p.function_name)
    if fn is None:
        return False, f"reference_solution does not define {p.function_name!r}"
    for tc in p.tests:
        try:
            got = fn(*tc.args)
        except Exception as e:
            return False, f"reference_solution raised on args {tc.args!r}: {e}"
        if got != tc.expected:
            return False, f"mismatch on args {tc.args!r}: got {got!r}, expected {tc.expected!r}"
    return True, None
```

- [ ] **Step 4: Refactor content.py to use it**

In `algotrainer/content.py`, replace the body of `_run_reference` so it delegates (keep the raising contract):
```python
from algotrainer.validation import validate_problem_dict


def _run_reference(problem: Problem) -> None:
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
```
(Remove the now-unused old exec logic. `load_problem`/`load_problems` are otherwise unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_validation.py tests/test_content.py -v`
Expected: PASS (validation tests + existing content tests still pass)

- [ ] **Step 6: Commit**

```bash
git add algotrainer/validation.py algotrainer/content.py tests/test_validation.py
git commit -m "feat: single-source problem validation; content uses it"
```

---

### Task 2: Generated-problem store

**Files:**
- Create: `algotrainer/generated.py`
- Create: `content/generated/.gitkeep`
- Modify: `.gitignore` (ignore `content/generated/*.json`)
- Test: `tests/test_generated.py`

**Interfaces:**
- Produces:
  - `GENERATED_DIR: Path` (repo `content/generated`).
  - `load_generated(generated_dir=GENERATED_DIR) -> list[Problem]` — loads every `*.json`, validating each; a file that fails validation is SKIPPED (not raised) so one bad variant can't break startup.
  - `save_generated_problem(d: dict, existing_ids: set[str], generated_dir=GENERATED_DIR) -> Path` — validates via `validate_problem_dict`; raises `ValueError` if invalid, if `d["id"]` is in `existing_ids`, or if a file for that id already exists; otherwise writes `<id>.json` and returns the path.

- [ ] **Step 1: Write the failing tests**

`tests/test_generated.py`:
```python
import pytest

from algotrainer.generated import load_generated, save_generated_problem

CAND = {
    "id": "two-sum-var1", "pattern": "arrays-hashing", "title": "Two Sum Variant",
    "difficulty": "easy", "statement": "s", "function_name": "f",
    "starter_code": "def f(x):\n    pass\n",
    "reference_solution": "def f(x):\n    return x * 2\n",
    "tests": [{"args": [2], "expected": 4}],
    "hints": ["hint"],
}


def test_save_then_load(tmp_path):
    save_generated_problem(CAND, existing_ids=set(), generated_dir=tmp_path)
    probs = load_generated(tmp_path)
    assert [p.id for p in probs] == ["two-sum-var1"]


def test_reject_invalid_without_writing(tmp_path):
    bad = {**CAND, "tests": [{"args": [2], "expected": 999}]}
    with pytest.raises(ValueError):
        save_generated_problem(bad, existing_ids=set(), generated_dir=tmp_path)
    assert list(tmp_path.glob("*.json")) == []


def test_reject_id_collision(tmp_path):
    with pytest.raises(ValueError):
        save_generated_problem(CAND, existing_ids={"two-sum-var1"}, generated_dir=tmp_path)


def test_load_skips_invalid_file(tmp_path):
    (tmp_path / "broken.json").write_text('{"id": "broken"}')  # bad shape
    save_generated_problem(CAND, existing_ids=set(), generated_dir=tmp_path)
    ids = {p.id for p in load_generated(tmp_path)}
    assert ids == {"two-sum-var1"}  # broken skipped, valid loaded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_generated.py -v`
Expected: FAIL — no module `algotrainer.generated`.

- [ ] **Step 3: Write implementation**

`algotrainer/generated.py`:
```python
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
```

- [ ] **Step 4: Create the dir + gitignore**

Create `content/generated/.gitkeep` (empty). Append to `.gitignore`:
```
content/generated/*.json
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_generated.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add algotrainer/generated.py content/generated/.gitkeep .gitignore tests/test_generated.py
git commit -m "feat: validated generated-problem store"
```

---

### Task 3: add_variant CLI

**Files:**
- Create: `scripts/add_variant.py`
- Test: `tests/test_add_variant.py`

**Interfaces:**
- Produces: `python scripts/add_variant.py` reads a candidate problem JSON on **stdin**, computes existing ids from BOTH seed (`content.load_problems`) and generated (`generated.load_generated`), calls `save_generated_problem`, prints the written path on success (exit 0), or prints the rejection reason to stderr and exits nonzero WITHOUT writing.

- [ ] **Step 1: Write the failing tests**

`tests/test_add_variant.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CAND = {
    "id": "plan4-add-variant-test", "pattern": "arrays-hashing", "title": "V",
    "difficulty": "easy", "statement": "s", "function_name": "f",
    "starter_code": "def f(x):\n    pass\n",
    "reference_solution": "def f(x):\n    return x\n",
    "tests": [{"args": [3], "expected": 3}], "hints": [],
}


def _run(payload):
    return subprocess.run([sys.executable, "scripts/add_variant.py"],
                          input=json.dumps(payload), capture_output=True, text=True, cwd=REPO)


def test_rejects_invalid(tmp_path):
    bad = {**CAND, "id": "plan4-invalid-x", "tests": [{"args": [3], "expected": 4}]}
    r = _run(bad)
    assert r.returncode != 0
    assert not (REPO / "content" / "generated" / "plan4-invalid-x.json").exists()


def test_rejects_seed_id_collision():
    clash = {**CAND, "id": "two-sum"}  # collides with a seed problem id
    r = _run(clash)
    assert r.returncode != 0


def test_accepts_valid_then_cleanup():
    out = REPO / "content" / "generated" / "plan4-add-variant-test.json"
    try:
        r = _run(CAND)
        assert r.returncode == 0, r.stderr
        assert out.exists()
    finally:
        if out.exists():
            out.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_add_variant.py -v`
Expected: FAIL — `scripts/add_variant.py` does not exist.

- [ ] **Step 3: Write implementation**

`scripts/add_variant.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_add_variant.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/add_variant.py tests/test_add_variant.py
git commit -m "feat: add_variant CLI (validated, unique-id generated problems)"
```

---

### Task 4: App integration — merge generated, reload, novel-instance next

**Files:**
- Modify: `algotrainer/web/app.py`
- Test: `tests/test_web_variants.py` (part 1)

**Interfaces:**
- `create_app` builds `problems` from `load_problems(content_dir)` PLUS `load_generated()`; a `_reload_problems()` inner helper re-scans and updates the in-memory dict.
- `POST /api/reload` → `{"count": <n>}` re-scans seed+generated and returns the problem count.
- `/api/next`: among the composer-ordered due ids, prefer the first whose problem has NO prior graded attempt (novel instance); fall back to the composer's first if all have been attempted. Use a new `store.attempted_problem_ids() -> set[str]`.

- [ ] **Step 1: Add the store helper + test (part 1)**

Add to `algotrainer/store.py`:
```python
    def attempted_problem_ids(self) -> set[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT problem_id FROM graded_attempt"
            ).fetchall()
        return {r[0] for r in rows}
```

Create `tests/test_web_variants.py`:
```python
import json

from fastapi.testclient import TestClient

from algotrainer.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.db", content_dir=None,
                                 session_dir=tmp_path / "sessions"))


def test_reload_returns_count(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/reload")
    assert r.status_code == 200
    assert r.json()["count"] >= 4  # at least the seed problems


def test_next_prefers_unseen(tmp_path, monkeypatch):
    # With a fresh db nothing is attempted, so /api/next returns some problem.
    c = _client(tmp_path)
    r = c.get("/api/next")
    assert r.json()["problem"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_web_variants.py -v`
Expected: FAIL — no `/api/reload`.

- [ ] **Step 3: Modify the app**

In `algotrainer/web/app.py`:
- Add import: `from algotrainer.generated import load_generated`.
- Replace the `problems = {...}` construction with a reload helper:
```python
    problems: dict = {}

    def _reload_problems() -> int:
        problems.clear()
        for p in load_problems(content_dir):
            problems[p.id] = p
        for p in load_generated():
            problems[p.id] = p
        return len(problems)

    _reload_problems()
```
- Add the reload route:
```python
    @app.post("/api/reload")
    def reload():
        return {"count": _reload_problems()}
```
- In `next_problem()`, after computing `plan = compose_order(...)`, choose a novel instance:
```python
        attempted = store.attempted_problem_ids()
        pid = next((x for x in plan.order if x not in attempted), plan.order[0])
```
(replace the previous `pid = plan.order[0]`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_web_variants.py tests/test_web.py tests/test_web_mastery.py -v`
Expected: PASS (reload works; novel-instance selection doesn't break existing flows)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/web/app.py algotrainer/store.py tests/test_web_variants.py
git commit -m "feat: merge generated problems, /api/reload, novel-instance selection"
```

---

### Task 5: Variant-generation mode in the tutor skill

**Files:**
- Modify: `.claude/skills/algotrainer-tutor/SKILL.md`
- Create: `.claude/skills/algotrainer-tutor/references/variant.md`
- Modify: `docs/USING_THE_TUTOR.md`
- Test: `tests/test_skill_variant.py`

**Interfaces:**
- The skill gains a "generate a variant" mode: given a pattern id and a target difficulty, author a NOVEL problem for that pattern (statement, function_name, starter_code, reference_solution, tests, tiered hints), then persist it via `python scripts/add_variant.py` (stdin JSON). Never serve/keep a variant the CLI rejects — fix and retry.

- [ ] **Step 1: Write the structural test**

`tests/test_skill_variant.py`:
```python
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "algotrainer-tutor"


def test_variant_reference_exists():
    assert (BASE / "references" / "variant.md").exists()


def test_skill_documents_variant_mode():
    text = (BASE / "SKILL.md").read_text().lower()
    assert "add_variant.py" in text
    assert "variant" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_skill_variant.py -v`
Expected: FAIL — variant.md absent / SKILL.md lacks the mode.

- [ ] **Step 3: Write the variant reference**

`.claude/skills/algotrainer-tutor/references/variant.md`:
```markdown
# Variant authoring spec

Produce a NOVEL problem for a given pattern — same underlying schema, different
surface (different story, inputs, sizes) — never a copy of a seed problem.

The candidate is a JSON object with exactly these keys:
- `id`: kebab-case, unique, suffixed to signal generation, e.g. `arrays-hashing-gen-<short>`
- `pattern`: the target pattern id (e.g. `arrays-hashing`)
- `title`, `difficulty` (`easy|medium|hard`), `statement`
- `function_name`: snake_case
- `starter_code`: a stub `def <function_name>(...):` with `pass`
- `reference_solution`: a CORRECT solution defining `function_name`
- `tests`: a list of `{"args": [...], "expected": ...}` — args are the positional
  arguments; `expected` must be JSON-native (list/number/bool/string, not tuple/set)
- `hints`: 3–4 graduated hints (category → invariant → pseudocode → worked step)

Correctness bar: your `reference_solution`, run on each test's `args`, MUST return
that test's `expected`. `add_variant.py` re-checks this and REJECTS the candidate
if any test fails — so verify mentally before submitting, and if rejected, read
the reason, fix, and resubmit. Cover normal, boundary, and empty/edge cases in
`tests`.
```

- [ ] **Step 4: Add the variant mode to SKILL.md**

Append a new section to `.claude/skills/algotrainer-tutor/SKILL.md` (before "## Principles"):
```markdown
## If asked to generate a variant

When asked to create a new practice problem / variant for a pattern (e.g. "generate
an arrays-hashing variant, medium"):
1. Read `references/variant.md` for the exact candidate schema and correctness bar.
2. Author a NOVEL problem for that pattern at the requested difficulty — new surface,
   same underlying schema; never copy a seed problem.
3. Persist it ONLY through the validating CLI (run from the repo root):
   ```bash
   echo '<candidate-json>' | python scripts/add_variant.py
   ```
   If it exits non-zero, read the rejection reason (a failing self-test, an id
   collision, or bad shape), fix the candidate, and retry until accepted.
4. Tell the learner the new problem id and that they can click "Reload problems"
   in the app (or restart) to have it enter rotation.
```

- [ ] **Step 5: Document it**

Append to `docs/USING_THE_TUTOR.md`:
```markdown
## Generate a novel variant
Ask: **"Use the algotrainer-tutor skill to generate an arrays-hashing variant
(medium)."** The skill authors a fresh problem and saves it via
`scripts/add_variant.py` (which rejects it unless its reference solution passes its
own tests). Click **Reload problems** in the app to bring new variants into rotation.
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_skill_variant.py tests/test_skill_present.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/algotrainer-tutor docs/USING_THE_TUTOR.md tests/test_skill_variant.py
git commit -m "feat: variant-generation mode in the tutor skill"
```

---

### Task 6: Seed content expansion

**Files:**
- Create seed problems for four more patterns under `content/problems/` (two each):
  - `valid-palindrome.json` + `two-sum-ii-sorted.json` → pattern `two-pointers`
  - `binary-search.json` + `search-insert-position.json` → pattern `binary-search`
  - `valid-parentheses.json` + `min-stack.json` → pattern `stack` (use a function-style API for min-stack, see note)
  - `kth-largest-element.json` + `last-stone-weight.json` → pattern `heaps`
- Test: covered by existing `tests/test_content.py::test_every_reference_solution_passes_its_own_tests` (the loader validates all).

**Interfaces:** each JSON follows the seed schema (id, pattern, title, difficulty, statement, function_name, starter_code, reference_solution, tests, hints). Every reference solution MUST pass its own tests (the loader enforces this — a bad one fails the suite).

- [ ] **Step 1: Author the eight problems**

Author each with a correct `reference_solution` and tests whose `expected` are JSON-native. Keep functions pure (args in, value out). Example shape for `valid-palindrome.json` (pattern `two-pointers`):
```json
{
  "id": "valid-palindrome",
  "pattern": "two-pointers",
  "title": "Valid Palindrome",
  "difficulty": "easy",
  "statement": "Given a string s, return True if it is a palindrome considering only alphanumeric characters and ignoring case.",
  "function_name": "is_palindrome",
  "starter_code": "def is_palindrome(s):\n    # your code here\n    pass\n",
  "reference_solution": "def is_palindrome(s):\n    t = [c.lower() for c in s if c.isalnum()]\n    return t == t[::-1]\n",
  "tests": [
    {"args": ["A man, a plan, a canal: Panama"], "expected": true},
    {"args": ["race a car"], "expected": false},
    {"args": [" "], "expected": true}
  ],
  "hints": [
    "Two pointers from both ends, skipping non-alphanumeric.",
    "Compare lowercased characters as the pointers converge.",
    "Or filter to alphanumeric lowercase and compare with its reverse."
  ]
}
```
Author the remaining seven analogously. For `min-stack`, model it as a function that replays a list of operations so it stays pure, e.g. `function_name: "min_stack_ops"` taking a list of ops like `[["push",5],["push",3],["getMin"],["pop"],["getMin"]]` and returning the list of results from query ops (`[3, 5]`); write a reference solution and tests consistent with that contract. Ensure every reference solution returns exactly the declared `expected` for every test.

- [ ] **Step 2: Validate by loading**

Run: `.venv/bin/pytest tests/test_content.py -v`
Expected: PASS — `test_every_reference_solution_passes_its_own_tests` and `test_loads_all_seed_problems` now cover the new files (if any reference solution is wrong, this FAILS with the mismatch; fix until green).

- [ ] **Step 3: Commit**

```bash
git add content/problems/valid-palindrome.json content/problems/two-sum-ii-sorted.json \
  content/problems/binary-search.json content/problems/search-insert-position.json \
  content/problems/valid-parentheses.json content/problems/min-stack.json \
  content/problems/kth-largest-element.json content/problems/last-stone-weight.json
git commit -m "feat: expand seed bank (two-pointers, binary-search, stack, heaps)"
```

---

### Task 7: Dashboard endpoint + UI

**Files:**
- Modify: `algotrainer/web/app.py`
- Modify: `algotrainer/web/static/index.html`
- Modify: `algotrainer/web/static/app.js`
- Modify: `algotrainer/web/static/app.css`
- Test: `tests/test_web_variants.py` (part 2)

**Interfaces:**
- `GET /api/dashboard` → `{"due_count": int, "total_problems": int, "patterns": [<mastery entries, same shape as /api/mastery>], "error_counts": {pattern: count}}`. `due_count` = number of due problem ids now; `total_problems` = size of the problem pool.

- [ ] **Step 1: Write the failing test (part 2)**

Append to `tests/test_web_variants.py`:
```python
def test_dashboard_shape(tmp_path):
    c = _client(tmp_path)
    r = c.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"due_count", "total_problems", "patterns", "error_counts"}
    assert body["total_problems"] >= 4
    assert isinstance(body["patterns"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_web_variants.py::test_dashboard_shape -v`
Expected: FAIL — no `/api/dashboard`.

- [ ] **Step 3: Add the dashboard route**

In `algotrainer/web/app.py`, factor the mastery list out of the `/api/mastery` handler into an inner helper `_mastery_list()` that returns the sorted list (so both routes share it), then:
```python
    @app.get("/api/dashboard")
    def dashboard():
        now = datetime.now(timezone.utc)
        due_map = store.all_card_due(now)
        due = scheduler.due_problem_ids(due_map, list(problems), now)
        return {
            "due_count": len(due),
            "total_problems": len(problems),
            "patterns": _mastery_list(),
            "error_counts": store.error_counts_by_pattern(),
        }
```
Update `/api/mastery` to `return {"patterns": _mastery_list()}`.

- [ ] **Step 4: Add a dashboard header to the UI**

In `algotrainer/web/static/index.html`, add a compact stats bar inside `<header>` (after the `<h1>`):
```html
    <span id="stats"></span>
```
In `app.js`, add:
```javascript
async function loadDashboard() {
  const r = await fetch("/api/dashboard");
  const d = await r.json();
  const mastered = d.patterns.filter(p => p.mastered).length;
  document.getElementById("stats").textContent =
    `${d.due_count} due · ${d.total_problems} problems · ${mastered}/${d.patterns.length} patterns mastered`;
}
```
Call `loadDashboard()` at the end of `DOMContentLoaded` and inside `ingest()` next to `loadMastery()`.

- [ ] **Step 5: Style the stats bar**

Append to `algotrainer/web/static/app.css`:
```css
#stats { font-size: 0.9rem; opacity: 0.9; }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_web_variants.py tests/test_web_mastery.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add algotrainer/web/app.py algotrainer/web/static/index.html algotrainer/web/static/app.js algotrainer/web/static/app.css tests/test_web_variants.py
git commit -m "feat: dashboard endpoint + header stats"
```

---

### Task 8: Full-suite + lint gate

- [ ] **Step 1:** Run `.venv/bin/pytest -q` — all pass, pristine.
- [ ] **Step 2:** Run `.venv/bin/ruff check algotrainer tests scripts` — clean.
- [ ] **Step 3 (optional manual):** `python -m algotrainer`; in Claude Code, ask the tutor skill to generate a variant for `arrays-hashing`; click **Reload problems**; confirm the variant enters rotation and the dashboard counts update.
- [ ] **Step 4:** No commit (verification only).

---

## Self-Review (against the Plan 4 roadmap)

- Full-roadmap-thin seed expansion — Task 6 (four more patterns; framework + AI variants supply the rest) ✓
- AI variant generation via the tutor skill, validated by the self-consistency rule before serving — Tasks 1,2,3,5 ✓ (validation is single-sourced and reused; `add_variant`/`save_generated_problem` fail closed)
- Novel-instance serving — Task 4 (`/api/next` prefers unseen) ✓
- Dashboards — Task 7 (`/api/dashboard` + header stats; mastery panel from Plan 3) ✓

**Placeholder scan:** none (Task 6 requires authoring eight concrete problems; the loader test is the acceptance gate). **Type consistency:** `validate_problem_dict` return tuple consumed by content/generated/add_variant consistently; `save_generated_problem(d, existing_ids, generated_dir)` signature matches the CLI call; `attempted_problem_ids` set used in novel-instance selection; `_mastery_list` shared by mastery + dashboard routes.

## Completion
With Plan 4 merged, AlgoTrainer realizes the full design: a closed learning loop (cold problem → recall gate → judge → tutor grade/hint via the in-repo skill → FSRS reschedule), pattern-level spaced repetition serving novel instances, a mastery model with the memorization-trap guard driving blocked→interleaved scheduling, an error-taxonomy journal, AI-generated validated variants, and dashboards — all for the DSA track, with the engine cleanly separable so SQL/stats/ML tracks can be added later.
