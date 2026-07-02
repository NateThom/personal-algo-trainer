# AlgoTrainer — Plan 2: Real Tutor Skill + Hint Ladder

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the Plan-1 stub tutor with a real, version-controlled Claude Code tutor skill that reads a session file, grades the attempt (composite Again/Hard/Good/Easy), classifies the approach, assigns an error-taxonomy code, scores the self-explanation, and writes a schema-valid verdict — plus wire the graduated hint ladder (endpoint + UI) so hints degrade the grade.

**Architecture:** The tutor is a Claude Code skill committed at `.claude/skills/algotrainer-tutor/SKILL.md` (in-repo, so it ships with the project and is auto-discoverable when working in this directory). To guarantee it can never emit a malformed verdict, the skill writes its structured judgment through a validating helper CLI (`scripts/write_verdict.py`) that constructs and validates the `Verdict` Pydantic model before writing `verdict-<id>.json`. Pre-authored tiered hints are served by a new stateless `/api/hint` endpoint; the browser tracks `hints_used` and passes it into the session so grading can penalize hinted solves. The Plan-1 `stub_tutor.py` remains for the automated integration test.

**Tech Stack:** unchanged (Python 3.11+, FastAPI, SQLite, py-fsrs, Pydantic v2, pytest, ruff). New artifact type: a Claude Code SKILL.md (Markdown with YAML frontmatter).

## Global Constraints

- Python **3.11+**; timezone-aware UTC datetimes everywhere.
- **The verdict contract is authoritative.** The tutor skill MUST write verdicts via `scripts/write_verdict.py`, which validates against `algotrainer.handoff.schema.Verdict`. A verdict that fails validation must NOT be written.
- **Error codes are a closed set.** `Verdict.error_code` is either `null` or one of the taxonomy codes in `algotrainer/errors.py`. Grading a clean solve uses `null`.
- **The skill must never reveal the full solution when asked for a hint.** Hints are graduated (category → invariant → pseudocode → single worked step), one tier per request.
- **`hints_used` degrades the grade**: a correct solve with ≥1 hint caps at `hard`; correct with no hints can be `good`/`easy`.
- The skill file lives at `.claude/skills/algotrainer-tutor/SKILL.md` and its frontmatter `name` is `algotrainer-tutor`.
- Run tests with `.venv/bin/pytest`; lint with `.venv/bin/ruff check algotrainer tests scripts`. Test output pristine.
- `git add` only the files each task names; commit after each task.

---

## File Structure

```
algotrainer/
  errors.py            # NEW: ERROR_CODES taxonomy + is_valid_error_code()
  handoff/schema.py    # MODIFY: validate Verdict.error_code against ERROR_CODES
  web/app.py           # MODIFY: add POST /api/hint
  web/static/index.html# MODIFY: add "Get hint" button + hint display
  web/static/app.js    # MODIFY: wire hint button, track hints_used, show tutor command
scripts/
  write_verdict.py     # NEW: validating verdict writer CLI (used by the skill)
.claude/skills/algotrainer-tutor/
  SKILL.md             # NEW: the tutor skill (grade + hint), the core deliverable
  references/
    rubric.md          # NEW: grading rubric + error taxonomy + examples (skill reads on demand)
tests/
  test_errors.py       # NEW
  test_schema_errorcode.py  # NEW (Verdict error_code validation)
  test_write_verdict.py     # NEW
  test_web_hint.py     # NEW (/api/hint)
docs/
  USING_THE_TUTOR.md   # NEW: how to run the tutor skill against a session
```

---

### Task 1: Error taxonomy module

**Files:**
- Create: `algotrainer/errors.py`
- Test: `tests/test_errors.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ERROR_CODES: tuple[str, ...]` = the six taxonomy codes.
  - `is_valid_error_code(code: str | None) -> bool` — True if `code is None` or in `ERROR_CODES`.

- [ ] **Step 1: Write the failing test**

`tests/test_errors.py`:
```python
from algotrainer.errors import ERROR_CODES, is_valid_error_code


def test_taxonomy_members():
    assert ERROR_CODES == (
        "pattern_misidentification",
        "approach_correct_execution_bug",
        "complexity_suboptimal",
        "incomplete_knowledge",
        "got_stuck_no_idea",
        "careless_time_pressure",
    )


def test_none_is_valid():
    assert is_valid_error_code(None) is True


def test_member_is_valid():
    assert is_valid_error_code("complexity_suboptimal") is True


def test_unknown_is_invalid():
    assert is_valid_error_code("made_up") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.errors'`

- [ ] **Step 3: Write implementation**

`algotrainer/errors.py`:
```python
"""The error taxonomy that codes why an attempt was less than perfect.
Drives remediation/scheduling in later plans; here it constrains verdicts."""

ERROR_CODES: tuple[str, ...] = (
    "pattern_misidentification",       # reached for the wrong schema
    "approach_correct_execution_bug",  # right idea, off-by-one / base case / boundary
    "complexity_suboptimal",           # worked but not optimal
    "incomplete_knowledge",            # missing a data structure / API
    "got_stuck_no_idea",               # no retrieval at all
    "careless_time_pressure",          # avoidable slip
)


def is_valid_error_code(code: str | None) -> bool:
    return code is None or code in ERROR_CODES
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add algotrainer/errors.py tests/test_errors.py
git commit -m "feat: error taxonomy module"
```

---

### Task 2: Validate Verdict.error_code against the taxonomy

**Files:**
- Modify: `algotrainer/handoff/schema.py`
- Test: `tests/test_schema_errorcode.py`

**Interfaces:**
- Consumes: `algotrainer.errors.ERROR_CODES`.
- Produces: `Verdict` now rejects an `error_code` that is neither `None` nor a taxonomy member (raises `pydantic.ValidationError`). All other fields unchanged.

- [ ] **Step 1: Write the failing test**

`tests/test_schema_errorcode.py`:
```python
import pytest
from pydantic import ValidationError

from algotrainer.handoff.schema import Verdict


def _base(**over):
    d = dict(session_id="s", attempt_id=1, problem_id="two-sum", grade="good")
    d.update(over)
    return d


def test_none_error_code_ok():
    assert Verdict(**_base(error_code=None)).error_code is None


def test_valid_error_code_ok():
    v = Verdict(**_base(error_code="complexity_suboptimal"))
    assert v.error_code == "complexity_suboptimal"


def test_invalid_error_code_rejected():
    with pytest.raises(ValidationError):
        Verdict(**_base(error_code="totally_made_up"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_schema_errorcode.py -v`
Expected: FAIL — the invalid code is currently accepted (`error_code` is a plain `str | None`).

- [ ] **Step 3: Modify the schema**

In `algotrainer/handoff/schema.py`, add the import and a field validator on `Verdict`:
```python
from pydantic import BaseModel, field_validator

from algotrainer.errors import is_valid_error_code
```
Add inside `class Verdict`:
```python
    @field_validator("error_code")
    @classmethod
    def _check_error_code(cls, v: str | None) -> str | None:
        if not is_valid_error_code(v):
            raise ValueError(f"unknown error_code: {v!r}")
        return v
```
(Keep the existing `error_code: str | None = None` field declaration; the validator runs on it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_schema_errorcode.py tests/test_handoff.py -v`
Expected: PASS (new tests pass, existing handoff tests still pass)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/handoff/schema.py tests/test_schema_errorcode.py
git commit -m "feat: validate Verdict.error_code against taxonomy"
```

---

### Task 3: Validating verdict writer CLI

**Files:**
- Create: `scripts/write_verdict.py`
- Test: `tests/test_write_verdict.py`

**Interfaces:**
- Consumes: `algotrainer.handoff.schema.Verdict`.
- Produces: a CLI `python scripts/write_verdict.py <session_dir>` that reads a JSON object of verdict fields from **stdin**, validates it by constructing `Verdict(**payload)`, and writes `verdict-<session_id>.json` (pretty-printed) into `<session_dir>`. On validation failure it prints the error to stderr and exits non-zero WITHOUT writing a file. On success it prints the written path and exits 0. This is the ONLY sanctioned way for the tutor skill to emit a verdict.

- [ ] **Step 1: Write the failing tests**

`tests/test_write_verdict.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(session_dir, payload):
    return subprocess.run(
        [sys.executable, "scripts/write_verdict.py", str(session_dir)],
        input=json.dumps(payload), capture_output=True, text=True, cwd=REPO,
    )


def test_writes_valid_verdict(tmp_path):
    payload = {"session_id": "abc", "attempt_id": 1, "problem_id": "two-sum",
               "grade": "good", "error_code": None, "feedback": "clean"}
    r = _run(tmp_path, payload)
    assert r.returncode == 0, r.stderr
    written = json.loads((tmp_path / "verdict-abc.json").read_text())
    assert written["grade"] == "good"


def test_rejects_bad_grade_without_writing(tmp_path):
    payload = {"session_id": "bad", "attempt_id": 1, "problem_id": "two-sum",
               "grade": "spectacular"}
    r = _run(tmp_path, payload)
    assert r.returncode != 0
    assert not (tmp_path / "verdict-bad.json").exists()


def test_rejects_bad_error_code_without_writing(tmp_path):
    payload = {"session_id": "bad2", "attempt_id": 1, "problem_id": "two-sum",
               "grade": "good", "error_code": "nonsense"}
    r = _run(tmp_path, payload)
    assert r.returncode != 0
    assert not (tmp_path / "verdict-bad2.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_write_verdict.py -v`
Expected: FAIL — `scripts/write_verdict.py` does not exist (nonzero return, no file).

- [ ] **Step 3: Write implementation**

`scripts/write_verdict.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_write_verdict.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/write_verdict.py tests/test_write_verdict.py
git commit -m "feat: validating verdict writer CLI for the tutor skill"
```

---

### Task 4: Hint endpoint

**Files:**
- Modify: `algotrainer/web/app.py`
- Test: `tests/test_web_hint.py`

**Interfaces:**
- Consumes: the app's in-memory `problems` dict (each `Problem` has `.hints: list[str]`).
- Produces: `POST /api/hint` body `{problem_id: str, tier: int}` → `{hint: str | None, tier: int, has_more: bool}`. `tier` is 0-based; if `tier` is out of range, `hint` is `null` and `has_more` is `false`. `has_more` is true when a further tier exists. Unknown `problem_id` → HTTP 404.

- [ ] **Step 1: Write the failing tests**

`tests/test_web_hint.py`:
```python
from fastapi.testclient import TestClient

from algotrainer.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.db", content_dir=None,
                                 session_dir=tmp_path / "sessions"))


def test_first_hint(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/hint", json={"problem_id": "two-sum", "tier": 0})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["hint"], str) and body["hint"]
    assert body["has_more"] is True


def test_out_of_range_tier(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/hint", json={"problem_id": "two-sum", "tier": 99})
    assert r.json()["hint"] is None
    assert r.json()["has_more"] is False


def test_unknown_problem_404(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/hint", json={"problem_id": "nope", "tier": 0})
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_web_hint.py -v`
Expected: FAIL — no `/api/hint` route (404 for the valid case, or KeyError).

- [ ] **Step 3: Modify the app**

In `algotrainer/web/app.py`, add near the other Pydantic bodies:
```python
class HintBody(BaseModel):
    problem_id: str
    tier: int
```
Add `from fastapi import HTTPException` to the FastAPI import line. Add this route inside `create_app` (alongside the others):
```python
    @app.post("/api/hint")
    def hint(body: HintBody):
        p = problems.get(body.problem_id)
        if p is None:
            raise HTTPException(status_code=404, detail="unknown problem")
        hints = p.hints
        if body.tier < 0 or body.tier >= len(hints):
            return {"hint": None, "tier": body.tier, "has_more": False}
        return {"hint": hints[body.tier], "tier": body.tier,
                "has_more": body.tier + 1 < len(hints)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_web_hint.py tests/test_web.py -v`
Expected: PASS (new hint tests pass; existing web tests still pass)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/web/app.py tests/test_web_hint.py
git commit -m "feat: /api/hint serves graduated tiered hints"
```

---

### Task 5: Wire the hint ladder into the UI

**Files:**
- Modify: `algotrainer/web/static/index.html`
- Modify: `algotrainer/web/static/app.js`
- Test: manual (front end); route behavior covered by Task 4.

**Interfaces:**
- Consumes: `POST /api/hint`.
- Produces: a "Get hint" button that reveals the next tier on each click, appends it to a hints panel, increments the `hintsUsed` counter (already sent to `/api/session`), and disables itself when `has_more` is false. `hintsUsed` resets to 0 on each new problem.

- [ ] **Step 1: Add the hint UI to index.html**

In `algotrainer/web/static/index.html`, inside `<section id="editor-wrap">`, add a hint button to the `.actions` div (before `#run`) and a hints panel after `#results`:
```html
        <button id="hint">Get hint</button>
```
And after the `<pre id="results"></pre>` line:
```html
      <div id="hints"></div>
```

- [ ] **Step 2: Wire the hint button in app.js**

In `algotrainer/web/static/app.js`, add a `nextHintTier` module variable next to the others:
```javascript
let nextHintTier = 0;
```
In `loadNext()`, after `hintsUsed = 0;` add:
```javascript
  nextHintTier = 0;
  document.getElementById("hints").innerHTML = "";
  document.getElementById("hint").disabled = false;
```
Add a `getHint` function:
```javascript
async function getHint() {
  const r = await fetch("/api/hint", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_id: current.id, tier: nextHintTier }),
  });
  const { hint, has_more } = await r.json();
  if (hint == null) { document.getElementById("hint").disabled = true; return; }
  const div = document.createElement("div");
  div.className = "hint-item";
  div.textContent = `Hint ${nextHintTier + 1}: ${hint}`;
  document.getElementById("hints").appendChild(div);
  nextHintTier += 1;
  hintsUsed += 1;
  if (!has_more) document.getElementById("hint").disabled = true;
}
```
In the `DOMContentLoaded` handler, register it:
```javascript
  document.getElementById("hint").addEventListener("click", getHint);
```

- [ ] **Step 3: Add minimal styling for hints in app.css**

Append to `algotrainer/web/static/app.css`:
```css
#hints { margin-top: 10px; display: grid; gap: 6px; }
.hint-item { background: #fff8e1; border-left: 3px solid #ffb300; padding: 8px; border-radius: 4px; }
```

- [ ] **Step 4: Manual smoke (optional)**

Run `python -m algotrainer`, open the app, click **Get hint** repeatedly on a problem; confirm hints appear one tier at a time and the button disables after the last tier, and that solving after hints reports `hints_used > 0` in the session file.

- [ ] **Step 5: Commit**

```bash
git add algotrainer/web/static/index.html algotrainer/web/static/app.js algotrainer/web/static/app.css
git commit -m "feat: graduated hint ladder in the solve UI"
```

---

### Task 6: The tutor skill (SKILL.md + rubric reference)

**Files:**
- Create: `.claude/skills/algotrainer-tutor/SKILL.md`
- Create: `.claude/skills/algotrainer-tutor/references/rubric.md`
- Create: `docs/USING_THE_TUTOR.md`
- Test: `tests/test_skill_present.py` (structural checks only — the skill's reasoning is reviewed by a human/subagent, not unit-tested)

**Interfaces:**
- Consumes: `scripts/write_verdict.py`, the session file schema, the error taxonomy, the FSRS grade names.
- Produces: an invocable Claude Code skill named `algotrainer-tutor` that, given a session directory and session id, reads `session-<id>.json`, grades/classifies/codes/scores, and writes the verdict via `write_verdict.py`. Also supports producing a single graduated hint when the session's `request` is `hint`.

- [ ] **Step 1: Write the structural test**

`tests/test_skill_present.py`:
```python
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "algotrainer-tutor" / "SKILL.md"


def test_skill_file_exists():
    assert SKILL.exists()


def test_skill_frontmatter_name():
    text = SKILL.read_text()
    assert text.startswith("---")
    assert "name: algotrainer-tutor" in text


def test_skill_references_write_verdict_and_grades():
    text = SKILL.read_text().lower()
    assert "write_verdict.py" in text
    # the four FSRS grade names must be documented
    for g in ("again", "hard", "good", "easy"):
        assert g in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_skill_present.py -v`
Expected: FAIL — SKILL.md does not exist.

- [ ] **Step 3: Write the rubric reference**

`.claude/skills/algotrainer-tutor/references/rubric.md`:
```markdown
# AlgoTrainer Grading Rubric & Error Taxonomy

## Composite grade (map to exactly one FSRS rating)

Consider four signals: correctness (from the judge result in the session file),
complexity optimality, time-to-solve, and hints used.

- **again** — did not identify the pattern, OR the judge shows failing tests and
  the approach is fundamentally wrong, OR the learner needed the full worked step
  and still could not finish.
- **hard** — solved (tests pass) but only WITH ≥1 hint, or the solution is
  correct-but-suboptimal in complexity, or it was slow / buggy on the way.
- **good** — solved unaided (0 hints), correct, optimal or near-optimal, time
  reasonable.
- **easy** — solved unaided, first try, optimal complexity, clean and fast.

Hard rule: if `hints_used >= 1` and tests pass, the grade is at most **hard**.
If tests fail, the grade is **again** (never higher).

## approach_used
A short phrase naming the pattern/approach the learner ACTUALLY used (e.g.
"hash map single pass", "brute-force nested loop", "two pointers"). Compare it to
the problem's canonical pattern to decide `pattern_misidentification`.

## error_code (null, or exactly one taxonomy member)
- `null` — clean, optimal, unaided solve.
- `pattern_misidentification` — reached for the wrong schema / recall gate named
  the wrong pattern.
- `approach_correct_execution_bug` — right idea, but off-by-one / base case /
  boundary / wrong return shape caused a failure or near-miss.
- `complexity_suboptimal` — works but not the optimal complexity.
- `incomplete_knowledge` — missing a data structure or API they needed.
- `got_stuck_no_idea` — no viable approach retrieved.
- `careless_time_pressure` — avoidable slip on an otherwise-known approach.

## self_explanation_score (1–5, or null if none given)
Score the learner's recall-gate `approach` + any explanation on whether it cites
the underlying PRINCIPLE/invariant (5) vs. only surface features (1). Null if the
recall fields are empty.

## feedback
2–5 sentences, Socratic and encouraging: name what went well, then the single
highest-leverage thing to improve. When asked for a HINT instead of a grade, give
ONLY the next tier and never the full solution.
```

- [ ] **Step 4: Write the SKILL.md**

`.claude/skills/algotrainer-tutor/SKILL.md`:
```markdown
---
name: algotrainer-tutor
description: Use when tutoring or grading an AlgoTrainer practice session — reads a session-<id>.json the web app wrote, then either grades the attempt (writing a schema-valid verdict) or gives the next graduated hint. Invoke with the session id (and session dir if not ./sessions).
---

# AlgoTrainer Tutor

You are a Socratic coding-interview tutor operating on one practice session at a
time. The AlgoTrainer web app writes a session file; you read it, do your work,
and (for grading) write a verdict file the app ingests to update the learner's
spaced-repetition schedule.

## Inputs

- Session directory: `sessions/` at the repo root unless told otherwise.
- Session id: given by the user (e.g. "grade session a1b2c3d4e5f6").
- Read `sessions/session-<id>.json`. Its fields:
  - `problem`: `{id, title, pattern, statement, reference_solution}`
  - `attempt`: `{code, judge_passed}` (the learner's code and whether tests passed)
  - `recall`: `{pattern, approach, complexity}` (what the learner stated BEFORE coding)
  - `hints_used`: integer
  - `request`: `"grade"` (default) or `"hint"`

Load the grading rubric and error taxonomy from `references/rubric.md` in this
skill directory before grading — follow it exactly.

## If request is "grade" (the default)

1. Read the session file and the rubric.
2. Compare the learner's `attempt.code` and `recall` to the `reference_solution`
   and the canonical `pattern`.
3. Decide, per the rubric:
   - `grade`: one of `again` | `hard` | `good` | `easy` (respect the hard rules:
     tests failing ⇒ `again`; `hints_used >= 1` with passing tests ⇒ at most `hard`).
   - `approach_used`: short phrase for what they actually did.
   - `error_code`: `null` or exactly one taxonomy member.
   - `complexity_ok`: true/false vs. the optimal complexity.
   - `self_explanation_score`: 1–5 or null.
   - `feedback`: 2–5 Socratic sentences.
4. Write the verdict — ALWAYS through the validating writer, never by hand:
   ```bash
   echo '{"session_id":"<id>","attempt_id":<n>,"problem_id":"<pid>","grade":"<g>","approach_used":"<...>","error_code":<null-or-"code">,"complexity_ok":<bool>,"self_explanation_score":<null-or-int>,"feedback":"<...>"}' \
     | python scripts/write_verdict.py sessions
   ```
   (`attempt_id` and `problem_id` come from the session file; `problem_id` is
   `problem.id`.) If the writer exits non-zero, read its error, fix your JSON, and
   retry — a malformed verdict must never be left unwritten-around.
5. Tell the learner their grade and feedback in the chat, and remind them to click
   "Ingest verdict" in the web app.

## If request is "hint"

Give ONLY the next graduated hint tier — category → invariant → pseudocode →
single worked step — based on `hints_used` (which tells you how many tiers they
have already seen). NEVER reveal the full solution. Do not write a verdict for a
hint request; just respond in the chat.

## Principles

- Be encouraging and specific. Name one highest-leverage improvement, not ten.
- Diagnose the misconception; prefer a guiding question over handing the answer.
- The verdict JSON is machine-read — keep `feedback` plain text, no newlines that
  would break the one-line echo (use short sentences).
```

- [ ] **Step 5: Write the usage doc**

`docs/USING_THE_TUTOR.md`:
```markdown
# Using the AlgoTrainer tutor

The tutor is a Claude Code skill committed at `.claude/skills/algotrainer-tutor/`.
When you work in this repo with Claude Code, it is auto-discoverable.

## Grade a session
1. In the web app: solve a problem, click **Run tests**, then **Send to tutor**.
   Note the session id shown in the results pane (e.g. `a1b2c3d4e5f6`).
2. In Claude Code (in this repo), say: **"Use the algotrainer-tutor skill to grade
   session a1b2c3d4e5f6."** The skill reads `sessions/session-a1b2c3d4e5f6.json`,
   grades it, and writes `sessions/verdict-a1b2c3d4e5f6.json`.
3. Back in the web app, click **Ingest verdict** to update your schedule.

## Get an adaptive hint
Ask: **"Use the algotrainer-tutor skill to hint session <id>."** It gives the next
tier only, never the full solution. (For quick pre-authored hints, use the
**Get hint** button in the app instead.)

## Offline / automated fallback
`scripts/stub_tutor.py <session_dir> <session_id>` writes a mechanical verdict
(used by the test suite and when you're away from Claude Code).
```

- [ ] **Step 6: Run the structural test**

Run: `.venv/bin/pytest tests/test_skill_present.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/algotrainer-tutor docs/USING_THE_TUTOR.md tests/test_skill_present.py
git commit -m "feat: in-repo Claude Code tutor skill (grade + hint) with rubric"
```

---

### Task 7: Full-suite + lint gate

**Files:**
- Test: whole suite.

- [ ] **Step 1: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all tests pass, output pristine.

- [ ] **Step 2: Lint**

Run: `.venv/bin/ruff check algotrainer tests scripts`
Expected: All checks passed.

- [ ] **Step 3: Manual end-to-end with the REAL tutor (optional but recommended)**

Start `python -m algotrainer`, solve Two Sum (optionally take a hint or two), **Send to tutor**, then in Claude Code run the `algotrainer-tutor` skill on the printed session id, confirm `sessions/verdict-<id>.json` appears and is schema-valid, click **Ingest verdict**, and confirm the grade reflects hint usage (≥1 hint ⇒ at most `hard`).

- [ ] **Step 4: No commit needed** (verification only).

---

## Self-Review (against the roadmap for Plan 2)

- Real in-repo tutor skill replacing the stub — Task 6 ✓ (stub retained for tests/fallback)
- Socratic hint ladder + grading/approach-classification/error-coding — Tasks 4,5,6 + rubric ✓
- Graduated hint endpoint + UI (`request:"hint"` supported by the skill; pre-authored tiers in the app) — Tasks 4,5,6 ✓
- Verdict always schema-valid (skill writes via validating CLI) — Task 3 ✓
- Error taxonomy is a closed set enforced on the contract — Tasks 1,2 ✓
- `hints_used` degrades the grade (hard rule in rubric) — Task 6 ✓

**Placeholder scan:** none. **Type consistency:** `Verdict` fields unchanged except the new validator; `HintBody`/`/api/hint` response shape matches the app.js consumer; `write_verdict.py` constructs `Verdict(**payload)` with the same field names the skill emits.

## Next: Plan 3 — Learning-science depth (pattern-level FSRS, session composer with blocked→interleaved, mastery model + gate + memorization-trap detection, error-taxonomy journal that reweights scheduling).
