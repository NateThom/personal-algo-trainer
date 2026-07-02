# AlgoTrainer — Plan 3: Learning-Science Depth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Turn the mechanical loop into an actual learning engine: pattern-level FSRS (aggregated from problem outcomes), a per-pattern mastery model with a criterion gate and memorization-trap detection, a session composer that shifts blocked→interleaved as a pattern matures and mixes confusable patterns, and an error-taxonomy journal that reweights what gets scheduled.

**Architecture:** New pure-logic modules — `patterns.py` (taxonomy registry: roadmap order + confusable groups), `mastery.py` (signals → score → gate from graded-attempt rows), `composer.py` (ordered session plan). Persistence gains two new tables (no changes to existing tables): `pattern_card` (pattern-level FSRS) and `graded_attempt` (a denormalized analytics row written at verdict ingestion, carrying grade/complexity/error_code/recall/hints per graded attempt). Verdict ingestion is extended to update the pattern-level card and write a `graded_attempt`. The web app's `/api/next` uses the composer; a new `/api/mastery` exposes the model, surfaced in a small UI panel.

**Tech Stack:** unchanged.

## Global Constraints

- Python **3.11+**; tz-aware UTC datetimes; deterministic FSRS (`enable_fuzzing=False`).
- **No changes to existing tables** (`card`, `attempt`, `review`). Add only new tables (`pattern_card`, `graded_attempt`). The dev `algotrainer.db` is disposable/gitignored; no migration of old rows is required.
- **Pure logic modules take data in, return data out.** `patterns.py`, `mastery.py`, `composer.py` must not import `store`, `web`, or do I/O — they receive plain dicts/lists and return dataclasses/lists, so they are unit-testable in isolation.
- **Mastery is measured on outcomes, never on re-reading.** Transfer breadth counts DISTINCT problems solved unaided (`hints_used == 0`) and correct.
- **Memorization-trap rule:** high solve rate with low pattern-identification accuracy ⇒ flagged, and such a pattern is NOT `mastered` regardless of other signals.
- Mastery gate constants live in `mastery.py` as named module constants (no magic numbers inline).
- Run tests with `.venv/bin/pytest`; lint `.venv/bin/ruff check algotrainer tests scripts`. Pristine output. Commit per task; `git add` only named files.

---

## File Structure

```
algotrainer/
  patterns.py          # NEW: PatternMeta registry, confusable groups, roadmap order
  mastery.py           # NEW: PatternMastery + compute_pattern_mastery()
  composer.py          # NEW: compose_order() session composer
  store.py             # MODIFY: + pattern_card & graded_attempt tables + methods
  web/app.py           # MODIFY: ingest updates pattern card + writes graded_attempt;
                       #         /api/next uses composer; + /api/mastery
  web/static/index.html# MODIFY: + mastery panel
  web/static/app.js    # MODIFY: fetch + render mastery
  web/static/app.css   # MODIFY: mastery panel styling
tests/
  test_patterns.py     # NEW
  test_mastery.py      # NEW
  test_composer.py     # NEW
  test_store_plan3.py  # NEW (pattern_card + graded_attempt)
  test_web_mastery.py  # NEW (/api/mastery + composer-backed /api/next)
```

---

### Task 1: Pattern taxonomy registry

**Files:**
- Create: `algotrainer/patterns.py`
- Test: `tests/test_patterns.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class PatternMeta: id: str; name: str; order: int; confusable_with: tuple[str, ...]`
  - `PATTERNS: tuple[PatternMeta, ...]` — the roadmap (at least the ids used by seed content plus the broader taxonomy).
  - `pattern_meta(pid: str) -> PatternMeta | None`
  - `confusable_group(pid: str) -> set[str]` — `{pid}` unioned with its `confusable_with`, made SYMMETRIC (if A lists B, B's group includes A).
  - `roadmap_order(pid: str) -> int` — the pattern's order, or a large sentinel (`10_000`) if unknown.

- [ ] **Step 1: Write the failing tests**

`tests/test_patterns.py`:
```python
from algotrainer.patterns import (
    PATTERNS, pattern_meta, confusable_group, roadmap_order,
)


def test_seed_patterns_present():
    ids = {p.id for p in PATTERNS}
    assert {"arrays-hashing", "sliding-window", "two-pointers"} <= ids


def test_orders_are_unique_and_ascending_start():
    orders = [p.order for p in PATTERNS]
    assert len(orders) == len(set(orders))  # unique
    assert min(orders) == 1


def test_confusable_is_symmetric():
    # sliding-window and two-pointers are declared confusable
    assert "two-pointers" in confusable_group("sliding-window")
    assert "sliding-window" in confusable_group("two-pointers")


def test_group_includes_self():
    assert "arrays-hashing" in confusable_group("arrays-hashing")


def test_roadmap_order_unknown_sentinel():
    assert roadmap_order("does-not-exist") == 10_000
    assert roadmap_order("arrays-hashing") == pattern_meta("arrays-hashing").order
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_patterns.py -v`
Expected: FAIL — no module `algotrainer.patterns`.

- [ ] **Step 3: Write implementation**

`algotrainer/patterns.py`:
```python
"""The pattern taxonomy: roadmap order + confusable groupings.
Pure metadata; drives the session composer and mastery display."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternMeta:
    id: str
    name: str
    order: int
    confusable_with: tuple[str, ...]


# Dependency-ordered roadmap (subset with seed coverage first, then the broader
# taxonomy as metadata). confusable_with need only be declared one direction;
# confusable_group() makes it symmetric.
PATTERNS: tuple[PatternMeta, ...] = (
    PatternMeta("arrays-hashing", "Arrays & Hashing", 1, ()),
    PatternMeta("two-pointers", "Two Pointers", 2, ("sliding-window",)),
    PatternMeta("sliding-window", "Sliding Window", 3, ("two-pointers",)),
    PatternMeta("stack", "Stack", 4, ()),
    PatternMeta("binary-search", "Binary Search", 5, ()),
    PatternMeta("linked-list", "Linked List", 6, ()),
    PatternMeta("trees", "Trees (BFS/DFS)", 7, ("graphs",)),
    PatternMeta("tries", "Tries", 8, ()),
    PatternMeta("heaps", "Heaps / Top-K", 9, ()),
    PatternMeta("backtracking", "Backtracking", 10, ("dp-1d",)),
    PatternMeta("graphs", "Graphs", 11, ("trees",)),
    PatternMeta("dp-1d", "1-D DP", 12, ("backtracking",)),
    PatternMeta("dp-2d", "2-D DP", 13, ("dp-1d",)),
)

_BY_ID = {p.id: p for p in PATTERNS}


def pattern_meta(pid: str) -> PatternMeta | None:
    return _BY_ID.get(pid)


def confusable_group(pid: str) -> set[str]:
    group = {pid}
    meta = _BY_ID.get(pid)
    if meta:
        group.update(meta.confusable_with)
    # symmetric closure: any pattern that lists pid as confusable
    for p in PATTERNS:
        if pid in p.confusable_with:
            group.add(p.id)
    return group


def roadmap_order(pid: str) -> int:
    meta = _BY_ID.get(pid)
    return meta.order if meta else 10_000
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_patterns.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add algotrainer/patterns.py tests/test_patterns.py
git commit -m "feat: pattern taxonomy registry (roadmap order + confusable groups)"
```

---

### Task 2: Store — pattern cards + graded-attempt analytics table

**Files:**
- Modify: `algotrainer/store.py`
- Test: `tests/test_store_plan3.py`

**Interfaces:**
- Adds to `Store` (existing methods unchanged; new tables created in the schema script):
  - `get_pattern_card(pattern: str) -> str | None`
  - `save_pattern_card(pattern: str, card_json: str, next_due: datetime) -> None`
  - `record_graded_attempt(attempt_id, problem_id, pattern, recall_pattern, hints_used, judge_passed, grade, complexity_ok, error_code, reviewed_at) -> None`
  - `graded_attempts_by_pattern(pattern: str) -> list[dict]` — each dict: `{problem_id, recall_pattern, hints_used, judge_passed, grade, complexity_ok, error_code}` (booleans returned as Python bool).
  - `error_counts_by_pattern() -> dict[str, int]` — pattern → count of graded attempts with a non-null `error_code`.
  - `all_graded_patterns() -> list[str]` — distinct patterns seen in graded_attempt.

- [ ] **Step 1: Write the failing tests**

`tests/test_store_plan3.py`:
```python
from datetime import datetime, timezone, timedelta

from algotrainer.store import Store


def _store(tmp_path):
    return Store(tmp_path / "t.db")


def test_pattern_card_roundtrip(tmp_path):
    s = _store(tmp_path)
    assert s.get_pattern_card("arrays-hashing") is None
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_pattern_card("arrays-hashing", '{"stability": 2.0}', due)
    assert s.get_pattern_card("arrays-hashing") == '{"stability": 2.0}'


def test_record_and_query_graded_attempts(tmp_path):
    s = _store(tmp_path)
    now = datetime.now(timezone.utc)
    s.record_graded_attempt(1, "two-sum", "arrays-hashing", "arrays-hashing",
                            0, True, "good", True, None, now)
    s.record_graded_attempt(2, "contains-duplicate", "arrays-hashing", "sliding-window",
                            1, True, "hard", False, "pattern_misidentification", now)
    rows = s.graded_attempts_by_pattern("arrays-hashing")
    assert len(rows) == 2
    assert rows[0]["judge_passed"] is True
    assert rows[1]["error_code"] == "pattern_misidentification"


def test_error_counts_and_patterns(tmp_path):
    s = _store(tmp_path)
    now = datetime.now(timezone.utc)
    s.record_graded_attempt(1, "two-sum", "arrays-hashing", "arrays-hashing",
                            0, True, "good", True, None, now)
    s.record_graded_attempt(2, "contains-duplicate", "arrays-hashing", "sliding-window",
                            1, True, "hard", False, "pattern_misidentification", now)
    assert s.error_counts_by_pattern() == {"arrays-hashing": 1}
    assert s.all_graded_patterns() == ["arrays-hashing"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_store_plan3.py -v`
Expected: FAIL — new methods/tables absent.

- [ ] **Step 3: Modify the store**

In `algotrainer/store.py`, extend the `_SCHEMA` string (append these two tables to the existing script, before the closing `"""`):
```sql
CREATE TABLE IF NOT EXISTS pattern_card (
    pattern   TEXT PRIMARY KEY,
    card_json TEXT NOT NULL,
    next_due  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graded_attempt (
    attempt_id INTEGER PRIMARY KEY,
    problem_id TEXT NOT NULL,
    pattern TEXT NOT NULL,
    recall_pattern TEXT,
    hints_used INTEGER NOT NULL,
    judge_passed INTEGER NOT NULL,
    grade TEXT NOT NULL,
    complexity_ok INTEGER,
    error_code TEXT,
    reviewed_at TEXT NOT NULL
);
```
Add these methods to the `Store` class (guard each with `self._lock`, follow existing style; `_iso` and `datetime` already imported):
```python
    def get_pattern_card(self, pattern: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT card_json FROM pattern_card WHERE pattern = ?", (pattern,)
            ).fetchone()
            return row[0] if row else None

    def save_pattern_card(self, pattern: str, card_json: str, next_due: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO pattern_card(pattern, card_json, next_due) VALUES(?,?,?) "
                "ON CONFLICT(pattern) DO UPDATE SET card_json=excluded.card_json, "
                "next_due=excluded.next_due",
                (pattern, card_json, _iso(next_due)),
            )
            self._conn.commit()

    def record_graded_attempt(
        self, attempt_id: int, problem_id: str, pattern: str, recall_pattern: str | None,
        hints_used: int, judge_passed: bool, grade: str, complexity_ok: bool | None,
        error_code: str | None, reviewed_at: datetime,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO graded_attempt(attempt_id, problem_id, pattern, recall_pattern, "
                "hints_used, judge_passed, grade, complexity_ok, error_code, reviewed_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(attempt_id) DO NOTHING",
                (attempt_id, problem_id, pattern, recall_pattern, hints_used,
                 int(judge_passed), grade,
                 None if complexity_ok is None else int(complexity_ok),
                 error_code, _iso(reviewed_at)),
            )
            self._conn.commit()

    def graded_attempts_by_pattern(self, pattern: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT problem_id, recall_pattern, hints_used, judge_passed, grade, "
                "complexity_ok, error_code FROM graded_attempt WHERE pattern = ? "
                "ORDER BY attempt_id", (pattern,),
            ).fetchall()
        return [
            {"problem_id": r[0], "recall_pattern": r[1], "hints_used": r[2],
             "judge_passed": bool(r[3]), "grade": r[4],
             "complexity_ok": None if r[5] is None else bool(r[5]), "error_code": r[6]}
            for r in rows
        ]

    def error_counts_by_pattern(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT pattern, COUNT(*) FROM graded_attempt "
                "WHERE error_code IS NOT NULL GROUP BY pattern"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def all_graded_patterns(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT pattern FROM graded_attempt ORDER BY pattern"
            ).fetchall()
        return [r[0] for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_store_plan3.py tests/test_store.py -v`
Expected: PASS (new + existing store tests)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/store.py tests/test_store_plan3.py
git commit -m "feat: pattern_card + graded_attempt persistence"
```

---

### Task 3: Extend verdict ingestion (pattern FSRS + graded_attempt)

**Files:**
- Modify: `algotrainer/web/app.py`
- Test: `tests/test_web_mastery.py` (part 1 — ingestion side effects)

**Interfaces:**
- Consumes: `store` pattern-card + graded-attempt methods; `scheduler.review`; the app's `problems` dict (for the problem's canonical pattern).
- Produces: after a successful (first) verdict ingest, `/api/verdict/ingest` ALSO (a) advances the pattern-level FSRS card using the same rating, and (b) writes a `graded_attempt` row with the problem's canonical pattern, recall pattern, hints_used, judge_passed, grade, complexity_ok, error_code. The already-ingested short-circuit path does none of this (idempotent). Response unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_mastery.py` (part 1; more added in Task 6):
```python
import json
import subprocess
import sys
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from algotrainer.web.app import create_app
from algotrainer.content import load_problem

REPO = Path(__file__).resolve().parent.parent


def _solve_and_grade(c, session_dir, db_path):
    prob = c.get("/api/next").json()["problem"]
    code = load_problem(prob["id"]).reference_solution
    judged = c.post("/api/judge", json={"problem_id": prob["id"], "code": code}).json()
    sess = c.post("/api/session", json={
        "problem_id": prob["id"], "code": code,
        "recall": {"pattern": prob["pattern"], "approach": "x", "complexity": "O(n)"},
        "judge_passed": judged["passed"], "hints_used": 0,
    }).json()
    subprocess.run([sys.executable, "scripts/stub_tutor.py", str(session_dir),
                    sess["session_id"]], check=True, cwd=REPO)
    c.post("/api/verdict/ingest", json={"session_id": sess["session_id"]})
    return prob


def test_ingest_writes_graded_attempt_and_pattern_card(tmp_path):
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    prob = _solve_and_grade(c, session_dir, db_path)

    conn = sqlite3.connect(db_path)
    ga = conn.execute("SELECT pattern, grade FROM graded_attempt").fetchall()
    pc = conn.execute("SELECT pattern FROM pattern_card").fetchall()
    conn.close()
    assert len(ga) == 1
    assert ga[0][0] == prob["pattern"]
    assert (prob["pattern"],) in pc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_web_mastery.py -v`
Expected: FAIL — no graded_attempt/pattern_card rows written by ingest yet.

- [ ] **Step 3: Modify the ingest route**

In `algotrainer/web/app.py`, in the `ingest()` function, on the NORMAL (not already-ingested) success path, after `store.ingest_verdict(...)` and before building the response, add pattern-card + graded-attempt side effects. Use the problem's canonical pattern from `problems`:
```python
        # --- Plan 3: pattern-level FSRS + analytics row ---
        p = problems.get(verdict.problem_id)
        pattern = p.pattern if p else verdict.problem_id
        pcard = store.get_pattern_card(pattern)
        new_pcard, p_next_due, _ = scheduler.review(pcard, rating, now)
        store.save_pattern_card(pattern, new_pcard, p_next_due)
        store.record_graded_attempt(
            attempt_id=verdict.attempt_id, problem_id=verdict.problem_id, pattern=pattern,
            recall_pattern=(attempt or {}).get("recall_pattern"),
            hints_used=(attempt or {}).get("hints_used", 0),
            judge_passed=(attempt or {}).get("judge_passed", False),
            grade=verdict.grade, complexity_ok=verdict.complexity_ok,
            error_code=verdict.error_code, reviewed_at=now,
        )
```
This requires the attempt's `recall_pattern`, `hints_used`, and `judge_passed`. Extend `Store.get_attempt` to return those columns too. In `algotrainer/store.py`, change `get_attempt` to select and return them:
```python
    def get_attempt(self, attempt_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT problem_id, recall_pattern, hints_used, judge_passed "
                "FROM attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
        if row is None:
            return None
        return {"problem_id": row[0], "recall_pattern": row[1],
                "hints_used": row[2], "judge_passed": bool(row[3])}
```
In `ingest()`, the existing cross-check already calls `store.get_attempt(verdict.attempt_id)` into a variable — reuse that variable (named `attempt` here). If the current code names it differently or doesn't retain it, capture it: `attempt = store.get_attempt(verdict.attempt_id)` (it's already fetched for the cross-check; reuse the same variable rather than querying twice).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_web_mastery.py tests/test_web.py tests/test_store.py -v`
Expected: PASS (ingestion side effects present; existing tests still pass — the double-ingest test still shows no second advance because the graded_attempt uses `ON CONFLICT DO NOTHING` and the pattern side-effects are on the non-short-circuit path only)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/web/app.py algotrainer/store.py tests/test_web_mastery.py
git commit -m "feat: ingest updates pattern-level FSRS + records graded_attempt"
```

---

### Task 4: Mastery model

**Files:**
- Create: `algotrainer/mastery.py`
- Test: `tests/test_mastery.py`

**Interfaces:**
- Consumes: plain lists of graded-attempt dicts (from `store.graded_attempts_by_pattern`) + a stability float. No I/O.
- Produces:
  - Module constants: `GATE_BREADTH = 4`, `GATE_ID_ACCURACY = 0.9`, `GATE_STABILITY = 7.0`, `TRAP_SOLVE_RATE = 0.8`, `TRAP_ID_ACCURACY = 0.6`, `TRAP_MIN_ATTEMPTS = 3`.
  - `@dataclass class PatternMastery: pattern; attempts; transfer_breadth; solve_rate; pattern_id_accuracy; optimal_rate; stability; memorization_trap; mastery_score; mastered`
  - `compute_pattern_mastery(pattern: str, rows: list[dict], stability: float) -> PatternMastery`

Definitions (all guard against division by zero → 0.0):
- `solve_rate` = passed / attempts.
- `transfer_breadth` = number of DISTINCT `problem_id` with `judge_passed and hints_used == 0`.
- `pattern_id_accuracy` = fraction of rows with `recall_pattern == pattern`.
- `optimal_rate` = fraction of PASSED rows with `complexity_ok is True`.
- `memorization_trap` = `attempts >= TRAP_MIN_ATTEMPTS and solve_rate >= TRAP_SOLVE_RATE and pattern_id_accuracy < TRAP_ID_ACCURACY`.
- `mastery_score` = `0.4*min(transfer_breadth/GATE_BREADTH,1) + 0.3*pattern_id_accuracy + 0.2*optimal_rate + 0.1*min(stability/GATE_STABILITY,1)`, rounded to 3 dp.
- `mastered` = `transfer_breadth >= GATE_BREADTH and pattern_id_accuracy >= GATE_ID_ACCURACY and stability >= GATE_STABILITY and not memorization_trap`.

- [ ] **Step 1: Write the failing tests**

`tests/test_mastery.py`:
```python
from algotrainer.mastery import compute_pattern_mastery, GATE_BREADTH


def _row(pid, recall, hints, passed, grade="good", complexity_ok=True, err=None):
    return {"problem_id": pid, "recall_pattern": recall, "hints_used": hints,
            "judge_passed": passed, "grade": grade, "complexity_ok": complexity_ok,
            "error_code": err}


def test_empty_is_zeroed():
    m = compute_pattern_mastery("arrays-hashing", [], 0.0)
    assert m.attempts == 0
    assert m.mastery_score == 0.0
    assert m.mastered is False


def test_transfer_breadth_counts_distinct_unaided_correct():
    rows = [
        _row("p1", "arrays-hashing", 0, True),
        _row("p1", "arrays-hashing", 0, True),   # duplicate problem, not counted twice
        _row("p2", "arrays-hashing", 1, True),   # hinted, doesn't count
        _row("p3", "arrays-hashing", 0, False),  # failed, doesn't count
    ]
    m = compute_pattern_mastery("arrays-hashing", rows, 1.0)
    assert m.transfer_breadth == 1


def test_pattern_id_accuracy():
    rows = [
        _row("p1", "arrays-hashing", 0, True),
        _row("p2", "sliding-window", 0, True),  # wrong pattern named
    ]
    m = compute_pattern_mastery("arrays-hashing", rows, 1.0)
    assert m.pattern_id_accuracy == 0.5


def test_memorization_trap_flagged():
    # solves everything but keeps naming the wrong pattern
    rows = [_row(f"p{i}", "sliding-window", 0, True) for i in range(4)]
    m = compute_pattern_mastery("arrays-hashing", rows, 20.0)
    assert m.solve_rate == 1.0
    assert m.pattern_id_accuracy == 0.0
    assert m.memorization_trap is True
    assert m.mastered is False  # trap blocks mastery even with high stability/breadth


def test_mastered_when_all_gates_met():
    rows = [_row(f"p{i}", "arrays-hashing", 0, True) for i in range(GATE_BREADTH)]
    m = compute_pattern_mastery("arrays-hashing", rows, 10.0)
    assert m.transfer_breadth == GATE_BREADTH
    assert m.pattern_id_accuracy == 1.0
    assert m.mastered is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mastery.py -v`
Expected: FAIL — no module `algotrainer.mastery`.

- [ ] **Step 3: Write implementation**

`algotrainer/mastery.py`:
```python
"""Per-pattern mastery model. Pure functions over graded-attempt rows.
Mastery is measured on outcomes (distinct unaided-correct solves, pattern-ID
accuracy, optimality, retention), never on re-reading; the memorization trap
(high solve rate + low pattern-ID accuracy) blocks mastery."""
from dataclasses import dataclass

GATE_BREADTH = 4
GATE_ID_ACCURACY = 0.9
GATE_STABILITY = 7.0
TRAP_SOLVE_RATE = 0.8
TRAP_ID_ACCURACY = 0.6
TRAP_MIN_ATTEMPTS = 3


@dataclass
class PatternMastery:
    pattern: str
    attempts: int
    transfer_breadth: int
    solve_rate: float
    pattern_id_accuracy: float
    optimal_rate: float
    stability: float
    memorization_trap: bool
    mastery_score: float
    mastered: bool


def _frac(num: int, den: int) -> float:
    return num / den if den else 0.0


def compute_pattern_mastery(pattern: str, rows: list[dict], stability: float) -> PatternMastery:
    attempts = len(rows)
    passed = [r for r in rows if r["judge_passed"]]
    unaided_correct = {
        r["problem_id"] for r in rows if r["judge_passed"] and r["hints_used"] == 0
    }
    transfer_breadth = len(unaided_correct)
    solve_rate = _frac(len(passed), attempts)
    pattern_id_accuracy = _frac(
        sum(1 for r in rows if r["recall_pattern"] == pattern), attempts
    )
    optimal_rate = _frac(
        sum(1 for r in passed if r["complexity_ok"] is True), len(passed)
    )
    memorization_trap = (
        attempts >= TRAP_MIN_ATTEMPTS
        and solve_rate >= TRAP_SOLVE_RATE
        and pattern_id_accuracy < TRAP_ID_ACCURACY
    )
    mastery_score = round(
        0.4 * min(transfer_breadth / GATE_BREADTH, 1.0)
        + 0.3 * pattern_id_accuracy
        + 0.2 * optimal_rate
        + 0.1 * min(stability / GATE_STABILITY, 1.0),
        3,
    )
    mastered = (
        transfer_breadth >= GATE_BREADTH
        and pattern_id_accuracy >= GATE_ID_ACCURACY
        and stability >= GATE_STABILITY
        and not memorization_trap
    )
    return PatternMastery(
        pattern=pattern, attempts=attempts, transfer_breadth=transfer_breadth,
        solve_rate=round(solve_rate, 3), pattern_id_accuracy=round(pattern_id_accuracy, 3),
        optimal_rate=round(optimal_rate, 3), stability=round(stability, 3),
        memorization_trap=memorization_trap, mastery_score=mastery_score, mastered=mastered,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_mastery.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/mastery.py tests/test_mastery.py
git commit -m "feat: per-pattern mastery model with memorization-trap guard"
```

---

### Task 5: Session composer

**Files:**
- Create: `algotrainer/composer.py`
- Test: `tests/test_composer.py`

**Interfaces:**
- Consumes: plain data (due ids, a problem→pattern map, a set of immature patterns, an error-weight map, a confusable-group function). No I/O.
- Produces:
  - `@dataclass class SessionPlan: order: list[str]; blocked_ratio: float`
  - `compose_order(due: list[str], problem_pattern: dict[str, str], immature: set[str], error_weight: dict[str, int], confusable_of=None) -> SessionPlan`

Rules (deterministic):
1. Partition `due` into **blocked** (problem's pattern ∈ `immature`) and **interleaved** (rest), preserving input order within each.
2. Order patterns by descending `error_weight` (default 0), tie-broken by pattern name — weakest-first (deliberate practice targets weaknesses).
3. **Blocked section first:** emit blocked problems grouped contiguously by pattern, patterns in the weakest-first order. (Acquire a schema in a block before mixing.)
4. **Interleaved section next:** round-robin one problem at a time across the interleaved patterns (weakest-first order), so patterns alternate. When a just-emitted pattern has a confusable counterpart also present, prefer that counterpart next (train discrimination). `confusable_of(pid)` returns a set; if `None`, skip the confusable preference.
5. `blocked_ratio = len(blocked) / len(due)` (0.0 if due empty).

- [ ] **Step 1: Write the failing tests**

`tests/test_composer.py`:
```python
from algotrainer.composer import compose_order


def test_empty():
    plan = compose_order([], {}, set(), {})
    assert plan.order == []
    assert plan.blocked_ratio == 0.0


def test_blocked_patterns_grouped_first():
    due = ["a1", "b1", "a2"]           # patterns: a, b, a
    pp = {"a1": "a", "a2": "a", "b1": "b"}
    # 'a' is immature -> its problems blocked (contiguous, first); 'b' interleaved
    plan = compose_order(due, pp, immature={"a"}, error_weight={})
    assert plan.order[:2] == ["a1", "a2"]   # a-block contiguous and first
    assert plan.order[2] == "b1"
    assert plan.blocked_ratio == 2 / 3


def test_weakest_pattern_first_by_error_weight():
    due = ["a1", "b1"]
    pp = {"a1": "a", "b1": "b"}
    # both mature (interleaved); b has more errors -> comes first
    plan = compose_order(due, pp, immature=set(), error_weight={"b": 5, "a": 1})
    assert plan.order[0] == "b1"


def test_interleaving_alternates_patterns():
    due = ["a1", "a2", "b1", "b2"]
    pp = {"a1": "a", "a2": "a", "b1": "b", "b2": "b"}
    plan = compose_order(due, pp, immature=set(), error_weight={})
    # round-robin => patterns alternate, not blocked
    patterns_seq = [pp[x] for x in plan.order]
    assert patterns_seq == ["a", "b", "a", "b"]
    assert plan.blocked_ratio == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_composer.py -v`
Expected: FAIL — no module `algotrainer.composer`.

- [ ] **Step 3: Write implementation**

`algotrainer/composer.py`:
```python
"""Session composer. Blocked practice while a pattern is immature, interleaved
(with confusable patterns adjacent) once it matures; weakest patterns first."""
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class SessionPlan:
    order: list[str]
    blocked_ratio: float


def _patterns_weakest_first(patterns: set[str], error_weight: dict[str, int]) -> list[str]:
    return sorted(patterns, key=lambda p: (-error_weight.get(p, 0), p))


def compose_order(
    due: list[str],
    problem_pattern: dict[str, str],
    immature: set[str],
    error_weight: dict[str, int],
    confusable_of=None,
) -> SessionPlan:
    if not due:
        return SessionPlan(order=[], blocked_ratio=0.0)

    blocked_ids = [pid for pid in due if problem_pattern.get(pid) in immature]
    interleaved_ids = [pid for pid in due if problem_pattern.get(pid) not in immature]

    # --- blocked section: contiguous by pattern, weakest-first ---
    blocked_by_pat: dict[str, list[str]] = defaultdict(list)
    for pid in blocked_ids:
        blocked_by_pat[problem_pattern[pid]].append(pid)
    blocked_order: list[str] = []
    for pat in _patterns_weakest_first(set(blocked_by_pat), error_weight):
        blocked_order.extend(blocked_by_pat[pat])

    # --- interleaved section: round-robin across patterns, confusable-adjacent ---
    inter_by_pat: dict[str, list[str]] = defaultdict(list)
    for pid in interleaved_ids:
        inter_by_pat[problem_pattern[pid]].append(pid)
    remaining = _patterns_weakest_first(set(inter_by_pat), error_weight)
    inter_order: list[str] = []
    last_pat: str | None = None
    while remaining:
        # prefer a confusable counterpart of the last-emitted pattern
        pick = None
        if last_pat is not None and confusable_of is not None:
            group = confusable_of(last_pat) - {last_pat}
            for cand in remaining:
                if cand in group:
                    pick = cand
                    break
        if pick is None:
            pick = remaining[0]
        inter_order.append(inter_by_pat[pick].pop(0))
        last_pat = pick
        if not inter_by_pat[pick]:
            remaining.remove(pick)

    order = blocked_order + inter_order
    return SessionPlan(order=order, blocked_ratio=len(blocked_ids) / len(due))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_composer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/composer.py tests/test_composer.py
git commit -m "feat: session composer (blocked->interleaved, confusable mixing, weakest-first)"
```

---

### Task 6: Wire composer + mastery into the app and UI

**Files:**
- Modify: `algotrainer/web/app.py`
- Modify: `algotrainer/web/static/index.html`
- Modify: `algotrainer/web/static/app.js`
- Modify: `algotrainer/web/static/app.css`
- Test: `tests/test_web_mastery.py` (part 2)

**Interfaces:**
- Consumes: `composer.compose_order`, `mastery.compute_pattern_mastery`, `patterns.confusable_group`, and store queries.
- Produces:
  - `/api/next` orders the due problems via `compose_order` (immature = patterns whose `transfer_breadth < mastery.GATE_BREADTH`; error_weight from `store.error_counts_by_pattern()`; confusable via `patterns.confusable_group`) and serves the first.
  - New `GET /api/mastery` → `{"patterns": [ {pattern, name, attempts, transfer_breadth, solve_rate, pattern_id_accuracy, optimal_rate, stability, memorization_trap, mastery_score, mastered}, ... ]}` for every pattern seen in `graded_attempt`, ordered by roadmap order.
  - A "Mastery" panel in the UI that fetches `/api/mastery` on load and after each ingest and renders one row per pattern (score, breadth, a trap warning if flagged).

- [ ] **Step 1: Write the failing test (part 2)**

Append to `tests/test_web_mastery.py`:
```python
def test_mastery_endpoint_reports_pattern(tmp_path):
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    prob = _solve_and_grade(c, session_dir, db_path)

    r = c.get("/api/mastery")
    assert r.status_code == 200
    pats = {p["pattern"]: p for p in r.json()["patterns"]}
    assert prob["pattern"] in pats
    entry = pats[prob["pattern"]]
    assert entry["attempts"] >= 1
    assert "mastery_score" in entry and "mastered" in entry
    assert entry["transfer_breadth"] >= 1  # solved unaided


def test_next_uses_composer_without_crashing(tmp_path):
    # smoke: after grading one problem, /api/next still returns a due problem or null
    session_dir = tmp_path / "sessions"
    db_path = tmp_path / "t.db"
    c = TestClient(create_app(db_path=db_path, content_dir=None, session_dir=session_dir))
    _solve_and_grade(c, session_dir, db_path)
    r = c.get("/api/next")
    assert r.status_code == 200
    assert "problem" in r.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_web_mastery.py -v`
Expected: FAIL — no `/api/mastery` route.

- [ ] **Step 3: Modify the app**

In `algotrainer/web/app.py`:
- Add imports:
```python
from algotrainer import mastery as mastery_mod
from algotrainer.composer import compose_order
from algotrainer.patterns import confusable_group, pattern_meta, roadmap_order
```
- Add a helper inside `create_app` (after `problems` is built) to compute per-pattern graded rows + stability, and reuse it in both routes:
```python
    def _pattern_stability(pattern: str) -> float:
        from fsrs import Card
        cj = store.get_pattern_card(pattern)
        return Card.from_json(cj).stability if cj else 0.0

    def _mastery_for(pattern: str):
        rows = store.graded_attempts_by_pattern(pattern)
        return mastery_mod.compute_pattern_mastery(pattern, rows, _pattern_stability(pattern))
```
- Replace the body of `next_problem()` so it orders via the composer:
```python
    @app.get("/api/next")
    def next_problem():
        now = datetime.now(timezone.utc)
        due_map = store.all_card_due(now)
        ids = scheduler.due_problem_ids(due_map, list(problems), now)
        if not ids:
            return {"problem": None}
        problem_pattern = {pid: problems[pid].pattern for pid in ids}
        immature = {
            pat for pat in set(problem_pattern.values())
            if _mastery_for(pat).transfer_breadth < mastery_mod.GATE_BREADTH
        }
        plan = compose_order(
            ids, problem_pattern, immature, store.error_counts_by_pattern(),
            confusable_of=confusable_group,
        )
        pid = plan.order[0]
        p = problems[pid]
        return {"problem": {
            "id": p.id, "title": p.title, "pattern": p.pattern,
            "difficulty": p.difficulty, "statement": p.statement,
            "function_name": p.function_name, "starter_code": p.starter_code,
        }}
```
- Add the mastery route:
```python
    @app.get("/api/mastery")
    def mastery():
        out = []
        for pat in store.all_graded_patterns():
            m = _mastery_for(pat)
            meta = pattern_meta(pat)
            out.append({
                "pattern": pat, "name": meta.name if meta else pat,
                "attempts": m.attempts, "transfer_breadth": m.transfer_breadth,
                "solve_rate": m.solve_rate, "pattern_id_accuracy": m.pattern_id_accuracy,
                "optimal_rate": m.optimal_rate, "stability": m.stability,
                "memorization_trap": m.memorization_trap,
                "mastery_score": m.mastery_score, "mastered": m.mastered,
            })
        out.sort(key=lambda e: roadmap_order(e["pattern"]))
        return {"patterns": out}
```

- [ ] **Step 4: Add the mastery panel to the UI**

In `algotrainer/web/static/index.html`, add a panel after the `<section id="editor-wrap">` closing tag (still inside `<main>`):
```html
    <section id="mastery">
      <h3>Pattern mastery</h3>
      <div id="mastery-body">No data yet — solve a problem.</div>
    </section>
```
In `algotrainer/web/static/app.js`, add a render function and call it on load and after ingest:
```javascript
async function loadMastery() {
  const r = await fetch("/api/mastery");
  const { patterns } = await r.json();
  const body = document.getElementById("mastery-body");
  if (!patterns.length) { body.textContent = "No data yet — solve a problem."; return; }
  body.innerHTML = patterns.map(p =>
    `<div class="mrow${p.mastered ? " mastered" : ""}">` +
    `<span class="mname">${p.name}</span>` +
    `<span class="mscore">score ${p.mastery_score.toFixed(2)}</span>` +
    `<span class="mbreadth">breadth ${p.transfer_breadth}</span>` +
    (p.memorization_trap ? `<span class="mtrap">⚠ memorizing, not recognizing</span>` : "") +
    (p.mastered ? `<span class="mgate">✓ mastered</span>` : "") +
    `</div>`).join("");
}
```
Call `loadMastery()` at the end of the `DOMContentLoaded` handler, and add `loadMastery();` inside `ingest()` right after the results are shown (before the `setTimeout(loadNext, ...)`).

- [ ] **Step 5: Style the panel**

Append to `algotrainer/web/static/app.css`:
```css
#mastery .mrow { display: flex; gap: 14px; padding: 6px 0; border-bottom: 1px solid #eee; align-items: center; }
#mastery .mname { font-weight: 600; min-width: 160px; }
#mastery .mtrap { color: #c62828; }
#mastery .mgate { color: #2e7d32; font-weight: 600; }
#mastery .mrow.mastered { background: #f1f8e9; }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_web_mastery.py tests/test_web.py tests/test_web_hint.py -v`
Expected: PASS (mastery endpoint + composer-backed next work; existing web tests still pass)

- [ ] **Step 7: Commit**

```bash
git add algotrainer/web/app.py algotrainer/web/static/index.html algotrainer/web/static/app.js algotrainer/web/static/app.css tests/test_web_mastery.py
git commit -m "feat: composer-driven scheduling + mastery endpoint and panel"
```

---

### Task 7: Full-suite + lint gate

- [ ] **Step 1:** Run `.venv/bin/pytest -q` — all pass, pristine.
- [ ] **Step 2:** Run `.venv/bin/ruff check algotrainer tests scripts` — clean.
- [ ] **Step 3 (optional manual):** `python -m algotrainer`; solve problems and watch the mastery panel populate; deliberately name the wrong pattern on the recall gate a few times and confirm the trap warning appears.
- [ ] **Step 4:** No commit (verification only).

---

## Self-Review (against the Plan 3 roadmap)

- Pattern-level FSRS aggregated from problem outcomes — Task 2 (storage) + Task 3 (update on ingest) ✓
- Session composer, maturity-driven blocked→interleaved + confusable mixing — Tasks 1,5,6 ✓
- Mastery model + criterion gate + memorization-trap detection — Task 4 ✓
- Error-taxonomy journal reweights scheduling — Task 2 (`error_counts_by_pattern`) + Task 5/6 (error_weight → weakest-first) ✓

**Placeholder scan:** none. **Type consistency:** `graded_attempts_by_pattern` dict keys match `compute_pattern_mastery` row access; `compose_order` signature matches the `/api/next` call; `mastery_mod.GATE_BREADTH` used for immaturity threshold matches the model. Pure modules do no I/O per constraints.

## Next: Plan 4 — Content scale + AI variants + dashboards (full ~22-24 pattern seed thin, AI variant generation via the tutor skill validated by the Task-3 self-consistency rule, richer dashboards).
