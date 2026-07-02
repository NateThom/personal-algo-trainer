# AlgoTrainer — Plan 6: Audit Fixes + Full Seed Bank

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Address the accepted findings of `docs/reviews/2026-07-02-product-review.md`: stop the recall-gate pattern leak, harden the API, persist verdict fields, delete the dead skill hint mode, make the tutor handoff lossless (localStorage + verdict polling + pending sweep), freshen the dashboard, fix hygiene items, and expand the seed bank so **every one of the 18 patterns has ≥ 4 seed problems** (the mastery-gate breadth).

**Architecture:** All changes are small, local edits to existing modules; no new modules except two tiny read-only endpoints. Content expansion is committed seed JSON under `content/problems/`, gated by the existing reference-solution validator and a new coverage test.

**Tech Stack:** unchanged (FastAPI, SQLite, vanilla JS).

## Global Constraints
- Python 3.11+; tz-aware UTC everywhere; `.venv/bin/pytest` green and `.venv/bin/ruff check algotrainer tests scripts` clean after EVERY task.
- **The recall gate must not reveal the pattern**: nothing served before verdict ingest (API payload or visible UI text) may contain the problem's pattern id or name (audit 1.1; design §5 step 2, §7 signal 3).
- `GATE_BREADTH` is 4 (`algotrainer/mastery.py`). Seed target is ≥ 4 problems per registry pattern.
- Judge contract: problems are a single pure function; `tests[].args` / `expected` are plain JSON values compared by equality. **No custom classes in test IO** — represent linked lists/trees/graphs as JSON (arrays, adjacency lists, level-order arrays with `null`).
- Frontend: DOM methods / `textContent` for any dynamic text; no new dependencies; no CDN.
- Commit per task; stage only named files.

---

### Task 1: Stop the recall-gate pattern leak (audit 1.1)
**Files:** Modify `algotrainer/web/app.py`, `algotrainer/web/static/app.js`, `algotrainer/web/static/index.html`; update tests in `tests/` that assert `pattern` in the `/api/next` payload.

- In `_pattern_pool` (app.py:79-88): remove the `"pattern": pattern` key from the returned dict.
- In `/api/next` (app.py:148-154): remove `"pattern": p.pattern` from the problem payload. Keep everything else (`seen_count`, `pattern_pool` counts don't name the pattern).
- In `app.js`: delete the `pattern-badge` assignment line (`document.getElementById("pattern-badge")...`); in `index.html` delete the corresponding `pattern-badge` element. In `renderPoolBanner`, reword the exhausted-pool message to avoid the pattern name:

```js
if (pool.unseen === 0) {
  parts.push(
    `You've seen every problem in this problem's pattern pool (${pool.total} total) — ` +
    `ask the Claude tutor to generate a variant (see the Guide), then click Reload problems.`
  );
}
```

- [ ] **Step 1: Write/adjust the failing test** in the existing web-app test module (follow its fixture style):

```python
def test_next_does_not_leak_pattern(client):
    p = client.get("/api/next").json()["problem"]
    assert "pattern" not in p
    assert "pattern" not in p["pattern_pool"]
```

- [ ] Step 2: run → FAIL. Step 3: implement. Step 4: run full suite → PASS (fix any existing tests that asserted the old payload — they must now assert absence).
- [ ] Step 5: commit `fix: stop leaking pattern before the recall gate`

### Task 2: 404 guards on /api/judge and /api/session (audit 1.4)
**Files:** Modify `algotrainer/web/app.py`; test in the web-app test module.

Both handlers currently do `problems[body.problem_id]` → KeyError → 500. Apply the same guard `/api/hint` uses:

```python
p = problems.get(body.problem_id)
if p is None:
    raise HTTPException(status_code=404, detail="unknown problem")
```

- [ ] Test first:

```python
def test_judge_unknown_problem_404(client):
    r = client.post("/api/judge", json={"problem_id": "nope", "code": "x = 1"})
    assert r.status_code == 404

def test_session_unknown_problem_404(client):
    r = client.post("/api/session", json={
        "problem_id": "nope", "code": "x", "recall": {}, "judge_passed": False})
    assert r.status_code == 404
```

- [ ] TDD cycle → commit `fix: 404 instead of 500 on unknown problem_id`

### Task 3: Persist approach_used / self_explanation_score / feedback (audit 1.3)
**Files:** Modify `algotrainer/store.py`, `algotrainer/web/app.py`; tests in `tests/test_store*.py` (follow existing style).

- Add three columns to the `graded_attempt` CREATE TABLE in `_SCHEMA`: `approach_used TEXT`, `self_explanation_score INTEGER`, `feedback TEXT NOT NULL DEFAULT ''`.
- Migrate existing DBs in `Store.__init__` right after `executescript`:

```python
for stmt in (
    "ALTER TABLE graded_attempt ADD COLUMN approach_used TEXT",
    "ALTER TABLE graded_attempt ADD COLUMN self_explanation_score INTEGER",
    "ALTER TABLE graded_attempt ADD COLUMN feedback TEXT NOT NULL DEFAULT ''",
):
    try:
        self._conn.execute(stmt)
    except sqlite3.OperationalError:
        pass  # column already exists
self._conn.commit()
```

- Extend `record_graded_attempt` with keyword params `approach_used: str | None`, `self_explanation_score: int | None`, `feedback: str = ""` and include them in the INSERT.
- Extend `graded_attempts_by_pattern` SELECT + returned dicts with the three fields.
- In `app.py` ingest (the `record_graded_attempt` call), pass `approach_used=verdict.approach_used, self_explanation_score=verdict.self_explanation_score, feedback=verdict.feedback`.
- [ ] Test first: record a graded attempt with the three fields set, read back via `graded_attempts_by_pattern`, assert values; plus a migration test — create a `Store`, close it, reopen the same path (exercises the ALTER path on an existing file) and assert a write with the new fields succeeds.
- [ ] TDD cycle → commit `feat: persist approach_used, self_explanation_score, feedback on ingest`

### Task 4: Delete the dead skill hint request mode (audit 1.2, decision: delete)
**Files:** Modify `algotrainer/handoff/schema.py`, `.claude/skills/algotrainer-tutor/SKILL.md`, `docs/USING_THE_TUTOR.md`; adjust any test referencing `request="hint"`.

- `schema.py`: change `request: str = "grade"` → `request: Literal["grade"] = "grade"`.
- `SKILL.md`: remove the `## If request is "hint"` section and the `"hint"` option in the request-field description; update the frontmatter `description` to drop "or gives the next graduated hint". Grade and generate-variant modes stay.
- `USING_THE_TUTOR.md`: remove the "Get an adaptive hint" section; note under grading that mid-solve hints are the app's **Get hint** ladder.
- [ ] Test: `SessionFile(request="hint", ...)` now raises `ValidationError`; `request="grade"` still valid. TDD cycle → commit `refactor: remove dead tutor hint request mode`

### Task 5: Hygiene — unused dep, dead code, atomic reload (audit 4.1, 4.2, 4.3)
**Files:** Modify `pyproject.toml`, `algotrainer/store.py`, `algotrainer/scheduler.py`, `algotrainer/web/app.py`, `tests/test_store_reset.py`.

- `pyproject.toml`: delete the `python-multipart>=0.0.9` line.
- `store.py`: delete `record_review` (production path is `ingest_verdict`). In `tests/test_store_reset.py` replace the `s.record_review(...)` call with `s.ingest_verdict(aid, "two-sum", 3, "{}", due, "{}", now)` and delete the now-redundant `s.save_card(...)` line above it (ingest_verdict upserts the card itself).
- `scheduler.py`: delete `new_card_json`.
- `app.py` `_reload_problems`: rebind atomically instead of mutating in place:

```python
def _reload_problems() -> int:
    nonlocal problems
    new_map = {p.id: p for p in load_problems(content_dir)}
    for p in load_generated(generated_dir):
        # seed ids win over generated on collision (setdefault keeps the seed)
        new_map.setdefault(p.id, p)
    problems = new_map
    return len(problems)
```

(All closures share the enclosing cell, so `nonlocal` rebinding is visible everywhere; declare `problems: dict = {}` before the def as now.)
- [ ] Full suite green (no new tests needed; test_store_reset edit is the coverage fold-in) → commit `chore: drop unused dep and dead code; atomic problem reload`

### Task 6: Session persistence + copy-tutor-command button (audit 2.1, 2.2)
**Files:** Modify `algotrainer/web/static/app.js`, `algotrainer/web/static/index.html`, `algotrainer/web/static/app.css` (if a style hook is needed).

- In `handoff()` after `sessionId = session_id;` add `localStorage.setItem("algotrainer.sessionId", session_id);`.
- On `DOMContentLoaded`, restore: `sessionId = localStorage.getItem("algotrainer.sessionId"); if (sessionId) document.getElementById("ingest").disabled = false;`.
- In `ingest()` on success (non-409, after reading the JSON): `localStorage.removeItem("algotrainer.sessionId"); sessionId = null;`. On 409 re-enable the button (`document.getElementById("ingest").disabled = false;`) so retry stays possible.
- Add a `Copy tutor command` button next to Ingest in `index.html` (`id="copy-cmd"`, initially `disabled`). Enable it wherever ingest gets enabled. Click handler:

```js
async function copyTutorCommand() {
  await navigator.clipboard.writeText(
    `Use the algotrainer-tutor skill to grade session ${sessionId}.`);
  const b = document.getElementById("copy-cmd");
  b.textContent = "Copied!";
  setTimeout(() => { b.textContent = "Copy tutor command"; }, 1500);
}
```

- [ ] Manual check via TestClient is N/A (pure JS); verify by serving and exercising in a browser once at Task 12. Suite green → commit `feat: persist session id across reloads + copy tutor command`

### Task 7: Verdict-ready polling (audit 3.1)
**Files:** Modify `algotrainer/web/app.py`, `algotrainer/web/static/app.js`; test in the web-app test module.

- New endpoint:

```python
@app.get("/api/verdict/status")
def verdict_status(session_id: str):
    return {"ready": (session_dir / f"verdict-{session_id}.json").exists()}
```

- `app.js`: keep a module-level `let pollTimer = null;`. After a successful handoff (and on load-restore of a stored sessionId), start `pollTimer = setInterval(checkVerdict, 5000);` where:

```js
async function checkVerdict() {
  if (!sessionId) { clearInterval(pollTimer); return; }
  const r = await fetch(`/api/verdict/status?session_id=${sessionId}`);
  const { ready } = await r.json();
  if (ready) {
    clearInterval(pollTimer);
    const b = document.getElementById("ingest");
    b.disabled = false;
    b.textContent = "Verdict ready — ingest";
  }
}
```

  Reset the button text to `Ingest verdict` in `loadNext()`; clear the timer in `ingest()` on success and in `loadNext()`.
- [ ] Test first: status returns `{"ready": false}` for a fresh session id; write a verdict file (use the existing verdict-writing test helper/stub pattern) and assert `{"ready": true}`. TDD cycle → commit `feat: verdict-ready polling`

### Task 8: Pending-verdict sweep (audit 2-M / 3.2)
**Files:** Modify `algotrainer/web/app.py`, `algotrainer/web/static/app.js`, `algotrainer/web/static/index.html`, `app.css`; test in the web-app test module.

- New endpoint — verdict files on disk whose attempts were never ingested:

```python
@app.get("/api/verdicts/pending")
def verdicts_pending():
    out = []
    for path in sorted(session_dir.glob("verdict-*.json")):
        sid = path.stem.removeprefix("verdict-")
        try:
            v = read_verdict(session_dir, sid)
        except Exception:
            continue  # malformed file: not ingestable, skip
        if not store.attempt_has_review(v.attempt_id):
            out.append({"session_id": sid, "problem_id": v.problem_id, "grade": v.grade})
    return {"pending": out}
```

  (Guard `session_dir.glob` with `if session_dir.exists()` — the dir is only created on first handoff.)
- UI: add `<div id="pending-verdicts" hidden></div>` near the top of the solve column in `index.html`. On `DOMContentLoaded` call `loadPending()`: fetch the endpoint; if non-empty, unhide and DOM-build one row per item — `textContent` label `Un-ingested verdict for <problem_id> (grade <grade>)` plus an `Ingest` button that POSTs `/api/verdict/ingest` with that `session_id`, then re-runs `loadPending()`, `loadMastery()`, `loadDashboard()`. Also clear the matching localStorage id if it was just ingested.
- [ ] Test first: with an ingested and a non-ingested verdict on disk, `/api/verdicts/pending` lists only the non-ingested one; empty session dir → `{"pending": []}`. TDD cycle → commit `feat: pending-verdict sweep with one-click ingest`

### Task 9: Dashboard freshness (audit 3.3, 3.4)
**Files:** Modify `algotrainer/web/app.py`, `algotrainer/web/static/app.js`, `algotrainer/web/static/dashboard.js`; test in the web-app test module.

- `/api/dashboard` gains `next_review_due` from data it already loads:

```python
"next_review_due": min(due_map.values()).isoformat() if due_map else None,
```

- `dashboard.js`: add a tile `Next review due` rendering the value (or `—` when null) formatted via `new Date(v).toLocaleString()`.
- Both `app.js` and `dashboard.js`: `setInterval(loadDashboard, 60_000);` after the initial load.
- [ ] Test first: after ingesting one verdict, `/api/dashboard` includes a parseable `next_review_due`; with a fresh DB it is `None`. TDD cycle → commit `feat: next-review tile + auto-refreshing stats`

### Task 10: Console script + run docs (audit 2.4)
**Files:** Modify `algotrainer/__main__.py`, `pyproject.toml`, `docs/USING_THE_TUTOR.md`.

- `__main__.py`: wrap the uvicorn call:

```python
def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
```

- `pyproject.toml`: add

```toml
[project.scripts]
algotrainer = "algotrainer.__main__:main"
```

- `USING_THE_TUTOR.md`: add a `## Run it` section at the top: activate `.venv`, then `algotrainer` (or `python -m algotrainer`), app at `http://127.0.0.1:8000`.
- [ ] Verify: `.venv/bin/pip install -e . >/dev/null && .venv/bin/algotrainer --help 2>/dev/null; true` — simplest check is `python -c "from algotrainer.__main__ import main"`. Suite green → commit `feat: algotrainer console script + run docs`

### Task 11: Seed-bank expansion to 4 problems per pattern (audit 1.5) — FAN-OUT
**Files:** Create ~60 files under `content/problems/`; add coverage test to `tests/test_content.py` (or the existing content test module).

Current per-pattern counts: arrays-hashing 3 · two-pointers 2 · binary-search 2 · stack 2 · heaps 2 · sliding-window 1 · the other 12 patterns 0. Author enough new problems to bring **every registry pattern to exactly 4** (61 → author 49… compute precisely: 4×18 = 72 target − 12 existing = **60 new problems**).

Every problem follows the existing seed schema (see `content/problems/binary-search.json`): `id` (kebab-case, unique across seed+generated, matches filename), `pattern` (registry id), `title`, `difficulty` (`easy|medium|hard` — mostly easy/medium, ≥1 medium per pattern), `statement` (self-contained, no images), `function_name`, `starter_code` (def + `# your code here` + `pass`), `reference_solution` (correct AND at the pattern's optimal complexity), `tests` (≥3 cases including at least one edge case; plain-JSON args/expected), `hints` (exactly 3 tiers: category-level nudge → key invariant → near-pseudocode).

**JSON-IO constraint (binding):** linked-list problems operate on Python lists (exercise fast/slow-pointer or in-place-reversal ideas on arrays); trees passed as level-order arrays with `null` for missing nodes; graphs as edge lists or adjacency lists; no custom classes anywhere in args/expected.

**Fan-out:** dispatch parallel author subagents with disjoint pattern assignments (e.g., 6 agents × 3 patterns). Each agent must validate every problem it writes by running it through the existing gate:

```bash
.venv/bin/python - <<'EOF'
import json, sys
from algotrainer.validation import validate_problem_dict
for f in [<its files>]:
    ok, err = validate_problem_dict(json.load(open(f)))
    assert ok, f"{f}: {err}"
print("all valid")
EOF
```

Coverage + validity tests (add after fan-out completes):

```python
def test_every_pattern_has_gate_breadth_seed_problems():
    from collections import Counter
    counts = Counter(p.pattern for p in load_problems())
    short = {m.id: counts[m.id] for m in PATTERNS if counts[m.id] < GATE_BREADTH}
    assert not short, f"patterns below gate breadth: {short}"

def test_all_seed_problems_have_unique_ids_and_three_hints():
    probs = load_problems()
    ids = [p.id for p in probs]
    assert len(ids) == len(set(ids))
    assert all(len(p.hints) == 3 for p in probs)
```

(If `load_problems` already executes reference solutions on load, these tests inherit that gate; otherwise add one test iterating `validate_problem_dict` over every file.)
- [ ] Fan out authors → validate → add tests → full suite green → commit `feat: seed bank covers all 18 patterns at gate breadth (4 each)`

### Task 12: Verify + final review
- [ ] Full suite green; ruff clean. Manual browser pass: no pattern visible pre-verdict; 404s behave; copy button; reload page mid-handoff and confirm Ingest still enabled; verdict polling flips the button; pending sweep lists an orphan; dashboard next-review tile; `algotrainer` entry point runs.
- [ ] Whole-branch review (most capable model) → fix findings → merge per finishing-a-development-branch.

## Self-Review (against audit + decisions)
- 1.1 leak ✓ T1 · 1.2 delete ✓ T4 · 1.3 persist ✓ T3 · 1.4 404 ✓ T2 · 1.5 full 4/pattern ✓ T11
- 2.1 copy ✓ T6 · 2.2 localStorage ✓ T6 · 2.4 run docs ✓ T10 · 2-M sweep ✓ T8
- 3.1 polling ✓ T7 · 3.2 sweep ✓ T8 · 3.3 refresh ✓ T9 · 3.4 next-due tile ✓ T9
- 4.1 dep ✓ T5 · 4.2 dead code ✓ T5 · 4.3 atomic reload ✓ T5
- Audit "skip" items (push notifications, pinning, plan pruning, pooling) intentionally not addressed.
