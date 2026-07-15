# Flashcards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a spaced-repetition flashcard study mode over the existing pattern reference docs (recognition/complexity/template/gotcha cards per pattern), scheduled on a track that is fully independent of the mastery gate.

**Architecture:** A new `flashcard` SQLite table + `Store` methods (mirroring the existing `pattern_card` accessor shape) hold FSRS card state per `(pattern, card_type)`. A new pure module `algotrainer/flashcards.py` derives card content from `content/patterns/*.json` docs and contains all card-building/grading logic with zero I/O. Four new/extended FastAPI routes expose due cards and accept reviews, reusing the existing `SrsScheduler`. Two new static pages (`flashcards.html`/`.js`) run the study session client-side; `nav.js` and `patterns_detail.js` get small additive links.

**Tech Stack:** Python 3.10+, FastAPI, SQLite (via the existing `Store` class), the `fsrs` library (via existing `SrsScheduler`), vanilla JS + DOM methods (no framework, matching `patterns.js`/`patterns_detail.js` conventions), pytest + `fastapi.testclient.TestClient`.

Reference spec: `docs/superpowers/specs/2026-07-14-flashcards-design.md`

---

### Task 1: Store layer — `flashcard` table and CRUD

**Files:**
- Modify: `algotrainer/store.py:36-51` (schema), `algotrainer/store.py:171-180` (new methods), `algotrainer/store.py:248-260` (`reset_progress`)
- Test: `tests/test_store.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_store.py` (existing file already has `_store(tmp_path)` helper and the `datetime`/`timezone`/`timedelta` imports at the top — no new imports needed):

```python
def test_flashcard_new_is_none(tmp_path):
    s = _store(tmp_path)
    assert s.get_flashcard("two-pointers", "recognition") is None


def test_flashcard_save_and_get(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_flashcard("two-pointers", "recognition", '{"stability": 2.0}', due)
    assert s.get_flashcard("two-pointers", "recognition") == '{"stability": 2.0}'
    # a different card_type on the same pattern is independent
    assert s.get_flashcard("two-pointers", "template") is None


def test_flashcard_save_overwrites_same_pattern_and_type(tmp_path):
    s = _store(tmp_path)
    due1 = datetime.now(timezone.utc) + timedelta(days=1)
    due2 = datetime.now(timezone.utc) + timedelta(days=5)
    s.save_flashcard("two-pointers", "recognition", '{"stability": 2.0}', due1)
    s.save_flashcard("two-pointers", "recognition", '{"stability": 4.0}', due2)
    assert s.get_flashcard("two-pointers", "recognition") == '{"stability": 4.0}'


def test_all_flashcard_due(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=2)
    s.save_flashcard("two-pointers", "complexity", "{}", due)
    mapping = s.all_flashcard_due(datetime.now(timezone.utc))
    assert ("two-pointers", "complexity") in mapping
    assert isinstance(mapping[("two-pointers", "complexity")], datetime)


def test_reset_progress_clears_flashcards(tmp_path):
    s = _store(tmp_path)
    due = datetime.now(timezone.utc) + timedelta(days=1)
    s.save_flashcard("two-pointers", "gotcha", "{}", due)
    s.reset_progress()
    assert s.get_flashcard("two-pointers", "gotcha") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py -v -k flashcard`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'get_flashcard'`

- [ ] **Step 3: Add the schema and methods**

In `algotrainer/store.py`, the `_SCHEMA` string currently ends with the `graded_attempt` table (lines 36-50) followed by the closing `"""` on line 51:

```python
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
    reviewed_at TEXT NOT NULL,
    approach_used TEXT,
    self_explanation_score INTEGER,
    feedback TEXT NOT NULL DEFAULT ''
);
"""
```

Replace with (adds the `flashcard` table before the closing `"""`):

```python
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
    reviewed_at TEXT NOT NULL,
    approach_used TEXT,
    self_explanation_score INTEGER,
    feedback TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS flashcard (
    pattern   TEXT NOT NULL,
    card_type TEXT NOT NULL,
    card_json TEXT NOT NULL,
    next_due  TEXT NOT NULL,
    PRIMARY KEY (pattern, card_type)
);
"""
```

Then, in `algotrainer/store.py:164-180`, after the existing `save_pattern_card` method:

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
```

Add immediately after (before `record_graded_attempt`):

```python
    def get_flashcard(self, pattern: str, card_type: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT card_json FROM flashcard WHERE pattern = ? AND card_type = ?",
                (pattern, card_type),
            ).fetchone()
        return row[0] if row else None

    def save_flashcard(
        self, pattern: str, card_type: str, card_json: str, next_due: datetime
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO flashcard(pattern, card_type, card_json, next_due) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(pattern, card_type) DO UPDATE SET "
                "card_json=excluded.card_json, next_due=excluded.next_due",
                (pattern, card_type, card_json, _iso(next_due)),
            )
            self._conn.commit()

    def all_flashcard_due(self, now: datetime) -> dict[tuple[str, str], datetime]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT pattern, card_type, next_due FROM flashcard"
            ).fetchall()
        return {(pat, ctype): datetime.fromisoformat(due) for pat, ctype, due in rows}
```

Finally, update `reset_progress` (`algotrainer/store.py:248-260`) — current code:

```python
    def reset_progress(self) -> None:
        """Wipe all learner progress (cards, attempts, reviews, graded history,
        pattern cards) in one transaction. Leaves the schema intact; problems and
        generated variants live in files, not the db, so they are untouched."""
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                for table in ("card", "attempt", "review", "graded_attempt", "pattern_card"):
                    self._conn.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table names
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
```

Replace with:

```python
    def reset_progress(self) -> None:
        """Wipe all learner progress (cards, attempts, reviews, graded history,
        pattern cards, flashcards) in one transaction. Leaves the schema intact;
        problems and generated variants live in files, not the db, so they are
        untouched."""
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                for table in (
                    "card", "attempt", "review", "graded_attempt", "pattern_card", "flashcard",
                ):
                    self._conn.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table names
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: PASS (all tests in the file, including the pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/store.py tests/test_store.py
git commit -m "feat: add flashcard table and Store CRUD methods"
```

---

### Task 2: Pure flashcard logic module

**Files:**
- Create: `algotrainer/flashcards.py`
- Test: `tests/test_flashcards.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_flashcards.py`:

```python
import random

from algotrainer.flashcards import (
    CARD_TYPES, build_recognition_card, diff_template, grade_recognition, unlocked_patterns,
)
from algotrainer.pattern_docs import load_pattern_doc
from algotrainer.patterns import PATTERNS


def test_card_types_are_the_four_facets():
    assert set(CARD_TYPES) == {"recognition", "complexity", "template", "gotcha"}


def test_unlocked_patterns_empty_history_opens_only_the_first_pattern():
    assert unlocked_patterns(set()) == {"arrays-hashing"}


def test_unlocked_patterns_opens_next_after_attempted():
    assert unlocked_patterns({"arrays-hashing"}) == {"arrays-hashing", "two-pointers"}


def test_unlocked_patterns_all_attempted_returns_all():
    all_ids = {p.id for p in PATTERNS}
    assert unlocked_patterns(all_ids) == all_ids


def test_recognition_card_has_four_unique_options_including_correct():
    doc = load_pattern_doc("two-pointers")
    all_ids = [p.id for p in PATTERNS]
    rng = random.Random(0)
    card = build_recognition_card("two-pointers", doc, all_ids, rng)
    assert len(card["options"]) == 4
    assert len(set(card["options"])) == 4
    assert card["correct"] == "two-pointers"
    assert "two-pointers" in card["options"]
    assert card["signal"] in doc["recognize_when"]


def test_recognition_card_prefers_confusable_distractors():
    doc = load_pattern_doc("sliding-window")
    all_ids = [p.id for p in PATTERNS]
    rng = random.Random(1)
    card = build_recognition_card("sliding-window", doc, all_ids, rng)
    # sliding-window's declared confusable group is {two-pointers, prefix-sum} —
    # both must be offered since the group has fewer than the needed 3 slots
    assert "two-pointers" in card["options"]
    assert "prefix-sum" in card["options"]


def test_recognition_card_pads_from_pool_when_no_confusables():
    # arrays-hashing has an empty confusable_with and nothing points back at
    # it either, so all 3 distractors must come from the random-pool fallback
    doc = load_pattern_doc("arrays-hashing")
    all_ids = [p.id for p in PATTERNS]
    rng = random.Random(2)
    card = build_recognition_card("arrays-hashing", doc, all_ids, rng)
    assert len(card["options"]) == 4
    assert len(set(card["options"])) == 4


def test_grade_recognition_correct_is_good():
    assert grade_recognition("two-pointers", "two-pointers") == 3


def test_grade_recognition_incorrect_is_again():
    assert grade_recognition("sliding-window", "two-pointers") == 1


def test_diff_template_identical_text_is_all_equal():
    ops = diff_template("def f():\n    pass\n", "def f():\n    pass\n")
    assert all(op["op"] == "equal" for op in ops)


def test_diff_template_ignores_whitespace_differences():
    ops = diff_template("def f():\n    pass\n", "def f():\n  pass\n")
    assert all(op["op"] == "equal" for op in ops)


def test_diff_template_flags_real_differences():
    ops = diff_template("left, right = 0, len(arr) - 1\n", "left = 0\n")
    assert any(op["op"] != "equal" for op in ops)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_flashcards.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'algotrainer.flashcards'`

- [ ] **Step 3: Implement `algotrainer/flashcards.py`**

Create `algotrainer/flashcards.py`:

```python
"""Pure flashcard logic: which patterns are unlocked for study, how a
recognition card's MCQ options are built, how it's graded, and how a typed
template compares to the reference. No I/O — the web layer wires this to
Store and the pattern-doc loader."""
import difflib
import random

from algotrainer.patterns import PATTERNS, confusable_group
from algotrainer.scheduler import RATING_BY_NAME

CARD_TYPES: tuple[str, ...] = ("recognition", "complexity", "template", "gotcha")


def unlocked_patterns(graded_patterns: set[str]) -> set[str]:
    """Patterns whose flashcards are open: any pattern with at least one graded
    attempt, plus the single next pattern in roadmap order — so you can study
    ahead of practicing it, without every pattern being available day one."""
    unlocked = set(graded_patterns)
    remaining = sorted(
        (p for p in PATTERNS if p.id not in graded_patterns), key=lambda p: p.order
    )
    if remaining:
        unlocked.add(remaining[0].id)
    return unlocked


def build_recognition_card(
    pattern_id: str, doc: dict, all_pattern_ids: list[str], rng: random.Random
) -> dict:
    """A recognition MCQ: a randomly-chosen recognize_when signal for
    pattern_id, plus 3 distractor pattern ids (preferring the declared
    confusable group, padded with random other patterns when that group is
    smaller than 3), shuffled into a 4-option list."""
    signal = rng.choice(doc["recognize_when"])
    distractors = sorted(confusable_group(pattern_id) - {pattern_id})
    rng.shuffle(distractors)
    distractors = distractors[:3]
    if len(distractors) < 3:
        pool = [pid for pid in all_pattern_ids if pid != pattern_id and pid not in distractors]
        rng.shuffle(pool)
        distractors += pool[: 3 - len(distractors)]
    options = [pattern_id] + distractors
    rng.shuffle(options)
    return {"signal": signal, "options": options, "correct": pattern_id}


def grade_recognition(selected: str, correct: str) -> int:
    """MCQ correctness maps directly to an FSRS rating: correct -> good,
    incorrect -> again. No partial credit."""
    return RATING_BY_NAME["good"] if selected == correct else RATING_BY_NAME["again"]


def diff_template(reference: str, typed: str) -> list[dict]:
    """Line-level diff between the reference template and what was typed, both
    whitespace-normalized (collapsed internal whitespace, stripped
    leading/trailing newlines) so indentation differences don't dominate."""
    def _norm_lines(text: str) -> list[str]:
        return [" ".join(line.split()) for line in text.strip("\n").splitlines()]

    ref_lines = _norm_lines(reference)
    typed_lines = _norm_lines(typed)
    matcher = difflib.SequenceMatcher(a=ref_lines, b=typed_lines, autojunk=False)
    return [
        {"op": tag, "reference": ref_lines[i1:i2], "typed": typed_lines[j1:j2]}
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_flashcards.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/flashcards.py tests/test_flashcards.py
git commit -m "feat: add pure flashcard logic (unlock, MCQ builder, diff)"
```

---

### Task 3: API — pages and the due-cards endpoint

**Files:**
- Modify: `algotrainer/web/app.py` (imports, page routes, `/api/flashcards/due`)
- Test: `tests/test_web_flashcards.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_flashcards.py`:

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


def test_flashcards_page_served(tmp_path):
    c = _client(tmp_path)
    assert c.get("/flashcards").status_code == 200


def test_flashcards_pattern_page_served(tmp_path):
    c = _client(tmp_path)
    assert c.get("/flashcards/two-pointers").status_code == 200


def test_due_cards_only_include_unlocked_patterns(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    patterns_present = {card["pattern"] for card in body["cards"]}
    # nothing attempted yet: only the first roadmap pattern is unlocked
    assert patterns_present == {"arrays-hashing"}


def test_due_cards_include_all_four_types_for_unlocked_pattern(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    types_seen = {
        card["card_type"] for card in body["cards"] if card["pattern"] == "arrays-hashing"
    }
    assert types_seen == {"recognition", "complexity", "template", "gotcha"}


def test_recognition_card_has_four_options_including_self(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    rec = next(
        card for card in body["cards"]
        if card["pattern"] == "arrays-hashing" and card["card_type"] == "recognition"
    )
    assert len(rec["options"]) == 4
    ids = {opt["id"] for opt in rec["options"]}
    assert "arrays-hashing" in ids
    assert all(opt["name"] for opt in rec["options"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_web_flashcards.py -v`
Expected: FAIL — `404 Not Found` for `/flashcards` (route doesn't exist yet)

- [ ] **Step 3: Add imports, models, and routes to `algotrainer/web/app.py`**

At `algotrainer/web/app.py:1-3`, current:

```python
import uuid
from datetime import datetime, timezone
from pathlib import Path
```

Replace with:

```python
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
```

At `algotrainer/web/app.py:12-13`, current:

```python
from algotrainer.content import DEFAULT_CONTENT_DIR, load_problems
from algotrainer.generated import GENERATED_DIR, load_generated
```

Replace with:

```python
from algotrainer.content import DEFAULT_CONTENT_DIR, load_problems
from algotrainer.flashcards import (
    CARD_TYPES, build_recognition_card, diff_template, grade_recognition, unlocked_patterns,
)
from algotrainer.generated import GENERATED_DIR, load_generated
```

At `algotrainer/web/app.py:44-47`, current (the last Pydantic body class):

```python
class HintBody(BaseModel):
    problem_id: str
    tier: int
```

Add immediately after it (still before `def create_app`):

```python
class HintBody(BaseModel):
    problem_id: str
    tier: int


class FlashcardReviewBody(BaseModel):
    pattern: str
    card_type: str
    rating: int | None = None
    selected: str | None = None


class FlashcardDiffBody(BaseModel):
    pattern: str
    code: str
```

At `algotrainer/web/app.py:110-112`, current:

```python
    @app.get("/patterns/{pattern_id}")
    def patterns_detail_page(pattern_id: str):
        return FileResponse(_STATIC / "patterns_detail.html")
```

Add immediately after:

```python
    @app.get("/patterns/{pattern_id}")
    def patterns_detail_page(pattern_id: str):
        return FileResponse(_STATIC / "patterns_detail.html")

    @app.get("/flashcards")
    def flashcards_page():
        return FileResponse(_STATIC / "flashcards.html")

    @app.get("/flashcards/{pattern_id}")
    def flashcards_pattern_page(pattern_id: str):
        return FileResponse(_STATIC / "flashcards.html")
```

At `algotrainer/web/app.py:198-222`, immediately after the `pattern_detail` handler (which ends right before `@app.get("/api/dashboard")`), insert:

```python
    @app.get("/api/flashcards/due")
    def flashcards_due():
        now = datetime.now(timezone.utc)
        docs = load_all_pattern_docs()
        unlocked = unlocked_patterns(set(store.all_graded_patterns())) & docs.keys()
        due_map = store.all_flashcard_due(now)
        rng = random.Random()
        out = []
        for pattern in sorted(unlocked):
            doc = docs[pattern]
            meta = pattern_meta(pattern)
            for card_type in CARD_TYPES:
                due = due_map.get((pattern, card_type))
                if due is not None and due > now:
                    continue
                card = {
                    "pattern": pattern, "card_type": card_type,
                    "pattern_name": meta.name if meta else pattern,
                }
                if card_type == "recognition":
                    rc = build_recognition_card(pattern, doc, list(docs.keys()), rng)
                    card["signal"] = rc["signal"]
                    card["options"] = [
                        {"id": pid, "name": pattern_meta(pid).name if pattern_meta(pid) else pid}
                        for pid in rc["options"]
                    ]
                out.append(card)
        rng.shuffle(out)
        return {"cards": out}
```

(This sits right before the existing `@app.get("/api/dashboard")` handler — do not reorder or remove anything else in the file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web_flashcards.py -v`
Expected: PASS (5 tests)

Also run the full suite to confirm nothing else broke:

Run: `pytest -v`
Expected: PASS (all tests, including pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/web/app.py tests/test_web_flashcards.py
git commit -m "feat: add flashcard pages and due-cards API endpoint"
```

---

### Task 4: API — review and diff endpoints

**Files:**
- Modify: `algotrainer/web/app.py` (append to the routes added in Task 3)
- Test: `tests/test_web_flashcards.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_flashcards.py`:

```python
def test_review_recognition_correct_is_marked_correct(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition", "selected": "arrays-hashing",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["next_due"] is not None


def test_review_recognition_incorrect_is_marked_incorrect(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition", "selected": "two-pointers",
    })
    assert r.status_code == 200
    assert r.json()["correct"] is False


def test_review_recognition_without_selected_is_400(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition",
    })
    assert r.status_code == 400


def test_review_flip_card_requires_rating(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "complexity",
    })
    assert r.status_code == 400


def test_review_flip_card_with_rating_reschedules(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "complexity", "rating": 3,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["next_due"] is not None
    assert body["correct"] is None


def test_review_unknown_card_type_is_404(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "nonsense", "rating": 3,
    })
    assert r.status_code == 404


def test_review_does_not_touch_mastery_or_pattern_card(tmp_path):
    c = _client(tmp_path)
    c.post("/api/flashcards/review", json={
        "pattern": "arrays-hashing", "card_type": "recognition", "selected": "arrays-hashing",
    })
    dash = c.get("/api/dashboard").json()
    # no graded_attempt rows were written by the flashcard review, so the
    # mastery table (which reads graded_attempt) stays empty
    assert dash["patterns"] == []


def test_diff_endpoint_returns_ops(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/diff", json={"pattern": "two-pointers", "code": "left = 0"})
    assert r.status_code == 200
    ops = r.json()["ops"]
    assert isinstance(ops, list)
    assert len(ops) > 0


def test_diff_endpoint_404_for_unknown_pattern(tmp_path):
    c = _client(tmp_path)
    r = c.post("/api/flashcards/diff", json={"pattern": "does-not-exist", "code": ""})
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_web_flashcards.py -v -k "review or diff_endpoint"`
Expected: FAIL — `404 Not Found` (routes don't exist yet)

- [ ] **Step 3: Add the review and diff routes**

In `algotrainer/web/app.py`, immediately after the `flashcards_due` handler added in Task 3 (still before `@app.get("/api/dashboard")`), add:

```python
    @app.post("/api/flashcards/review")
    def flashcard_review(body: FlashcardReviewBody):
        if body.card_type not in CARD_TYPES:
            raise HTTPException(status_code=404, detail="unknown card type")
        if body.card_type == "recognition":
            if body.selected is None:
                raise HTTPException(
                    status_code=400, detail="selected is required for recognition cards"
                )
            rating = grade_recognition(body.selected, body.pattern)
            correct = body.selected == body.pattern
        else:
            if body.rating is None:
                raise HTTPException(status_code=400, detail="rating is required")
            rating = body.rating
            correct = None
        now = datetime.now(timezone.utc)
        card_json = store.get_flashcard(body.pattern, body.card_type)
        new_card_json, next_due, _ = scheduler.review(card_json, rating, now)
        store.save_flashcard(body.pattern, body.card_type, new_card_json, next_due)
        return {"next_due": next_due.isoformat(), "correct": correct}

    @app.post("/api/flashcards/diff")
    def flashcard_diff(body: FlashcardDiffBody):
        doc = load_pattern_doc(body.pattern)
        if doc is None:
            raise HTTPException(status_code=404, detail="unknown pattern")
        return {"ops": diff_template(doc["template"], body.code)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web_flashcards.py -v`
Expected: PASS (14 tests total in the file)

Run the full suite:

Run: `pytest -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/web/app.py tests/test_web_flashcards.py
git commit -m "feat: add flashcard review and template-diff endpoints"
```

---

### Task 5: Frontend — flashcards page and study session

**Files:**
- Create: `algotrainer/web/static/flashcards.html`
- Create: `algotrainer/web/static/flashcards.js`

No automated test for this task (no JS test runner in this project — `patterns.js`/`dashboard.js` are likewise untested). Verification is manual, via the dev server, in Task 7.

- [ ] **Step 1: Create `algotrainer/web/static/flashcards.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AlgoTrainer — Flashcards</title>
  <link rel="stylesheet" href="/static/app.css" />
</head>
<body>
  <header><h1>Flashcards</h1><span id="due-count"></span></header>
  <main class="doc">
    <p class="lede" id="empty-note" hidden>No flashcards due right now.</p>
    <button id="start-btn" type="button" hidden>Study</button>
    <p id="session-progress"></p>
    <section id="session-body"></section>
  </main>
  <script src="/static/nav.js"></script>
  <script src="/static/flashcards.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `algotrainer/web/static/flashcards.js`**

```javascript
// Flashcard study session: fetches due cards, runs one at a time (MCQ /
// flip-and-rate / type-and-diff depending on card_type), submits reviews.
// Built with DOM methods (textContent) for anything derived from pattern-doc
// free text — same convention as patterns_detail.js.
let queue = [];
const docCache = new Map(); // pattern id -> full /api/patterns/<id> doc

function patternIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.length > 1 ? parts[parts.length - 1] : null;
}

async function fetchDoc(pattern) {
  if (!docCache.has(pattern)) {
    const doc = await (await fetch(`/api/patterns/${encodeURIComponent(pattern)}`)).json();
    docCache.set(pattern, doc);
  }
  return docCache.get(pattern);
}

function clearBody() {
  const body = document.getElementById("session-body");
  body.textContent = "";
  return body;
}

function ratingRow(onRate) {
  const row = document.createElement("div");
  row.className = "rating-row";
  for (const [label, value] of [["Again", 1], ["Hard", 2], ["Good", 3], ["Easy", 4]]) {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.addEventListener("click", () => onRate(value));
    row.appendChild(btn);
  }
  return row;
}

async function submitReview(card, payload) {
  const res = await fetch("/api/flashcards/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern: card.pattern, card_type: card.card_type, ...payload }),
  });
  return res.json();
}

function renderRecognition(card, body) {
  const q = document.createElement("p");
  q.className = "lede";
  q.textContent = card.signal;
  body.appendChild(q);

  const options = document.createElement("div");
  options.className = "mcq-options";
  for (const opt of card.options) {
    const btn = document.createElement("button");
    btn.textContent = opt.name;
    btn.addEventListener("click", async () => {
      [...options.children].forEach((b) => (b.disabled = true));
      const result = await submitReview(card, { selected: opt.id });
      const feedback = document.createElement("p");
      feedback.className = result.correct ? "note" : "note mtrap";
      feedback.textContent = result.correct
        ? "Correct."
        : `Not quite — this was ${card.pattern_name}.`;
      body.appendChild(feedback);
      const next = document.createElement("button");
      next.textContent = "Next";
      next.addEventListener("click", advance);
      body.appendChild(next);
    });
    options.appendChild(btn);
  }
  body.appendChild(options);
}

function revealComplexity(doc, body) {
  const p = document.createElement("p");
  p.textContent = `Time: ${doc.complexity.time || "?"}  ·  Space: ${doc.complexity.space || "?"}`;
  body.appendChild(p);
  if (doc.complexity.notes) {
    const notes = document.createElement("p");
    notes.className = "note";
    notes.textContent = doc.complexity.notes;
    body.appendChild(notes);
  }
}

function revealGotchas(doc, body) {
  const ul = document.createElement("ul");
  for (const g of doc.gotchas) {
    const li = document.createElement("li");
    li.textContent = g;
    ul.appendChild(li);
  }
  body.appendChild(ul);
}

function renderFlipCard(card, body, reveal) {
  const front = document.createElement("p");
  front.className = "lede";
  front.textContent = card.pattern_name;
  body.appendChild(front);

  const show = document.createElement("button");
  show.textContent = "Show answer";
  show.addEventListener("click", async () => {
    show.remove();
    const doc = await fetchDoc(card.pattern);
    reveal(doc, body);
    body.appendChild(ratingRow(async (rating) => {
      await submitReview(card, { rating });
      advance();
    }));
  });
  body.appendChild(show);
}

function renderDiff(ops) {
  const pre = document.createElement("pre");
  pre.className = "diff-view";
  for (const op of ops) {
    for (const line of op.reference) {
      const div = document.createElement("div");
      div.className = `diff-line diff-${op.op === "equal" ? "equal" : "reference"}`;
      div.textContent = (op.op === "equal" ? "  " : "- ") + line;
      pre.appendChild(div);
    }
    if (op.op !== "equal") {
      for (const line of op.typed) {
        const div = document.createElement("div");
        div.className = "diff-line diff-typed";
        div.textContent = "+ " + line;
        pre.appendChild(div);
      }
    }
  }
  return pre;
}

function renderTemplate(card, body) {
  const front = document.createElement("p");
  front.className = "lede";
  front.textContent = `${card.pattern_name} — type the template from memory`;
  body.appendChild(front);

  const box = document.createElement("textarea");
  box.className = "flashcard-code";
  box.rows = 12;
  body.appendChild(box);

  const check = document.createElement("button");
  check.textContent = "Check";
  check.addEventListener("click", async () => {
    check.disabled = true;
    const res = await fetch("/api/flashcards/diff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pattern: card.pattern, code: box.value }),
    });
    const { ops } = await res.json();
    box.remove();
    check.remove();
    body.appendChild(renderDiff(ops));
    body.appendChild(ratingRow(async (rating) => {
      await submitReview(card, { rating });
      advance();
    }));
  });
  body.appendChild(check);
}

function renderCard(card) {
  const body = clearBody();
  document.getElementById("session-progress").textContent =
    `${queue.length + 1} card${queue.length === 0 ? "" : "s"} remaining`;
  if (card.card_type === "recognition") {
    renderRecognition(card, body);
  } else if (card.card_type === "complexity") {
    renderFlipCard(card, body, revealComplexity);
  } else if (card.card_type === "gotcha") {
    renderFlipCard(card, body, revealGotchas);
  } else if (card.card_type === "template") {
    renderTemplate(card, body);
  }
}

function advance() {
  const card = queue.shift();
  if (!card) {
    const body = clearBody();
    const done = document.createElement("p");
    done.className = "lede";
    done.textContent = "Session complete.";
    body.appendChild(done);
    document.getElementById("session-progress").textContent = "";
    return;
  }
  renderCard(card);
}

async function startSession() {
  const filterPattern = patternIdFromPath();
  const { cards } = await (await fetch("/api/flashcards/due")).json();
  queue = filterPattern ? cards.filter((c) => c.pattern === filterPattern) : cards;
  document.getElementById("due-count").textContent = `${queue.length} due`;
  document.getElementById("start-btn").hidden = queue.length === 0;
  document.getElementById("empty-note").hidden = queue.length > 0;
}

function wireStart() {
  document.getElementById("start-btn").addEventListener("click", () => {
    document.getElementById("start-btn").hidden = true;
    advance();
  });
}

window.addEventListener("DOMContentLoaded", () => {
  wireStart();
  startSession();
});
```

- [ ] **Step 3: Commit**

```bash
git add algotrainer/web/static/flashcards.html algotrainer/web/static/flashcards.js
git commit -m "feat: add flashcard study session page"
```

---

### Task 6: Frontend — nav link, pattern-detail link, styling

**Files:**
- Modify: `algotrainer/web/static/nav.js:3-10`
- Modify: `algotrainer/web/static/patterns_detail.js:37-42`
- Modify: `algotrainer/web/static/app.css` (append)

- [ ] **Step 1: Add the nav entry**

In `algotrainer/web/static/nav.js`, current lines 3-10:

```javascript
const NAV_PAGES = [
  { href: "/", label: "Solve" },
  { href: "/guide", label: "Guide" },
  { href: "/methodology", label: "Methodology" },
  { href: "/patterns", label: "Patterns" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/docs", label: "API Docs ↗", external: true },
];
```

Replace with:

```javascript
const NAV_PAGES = [
  { href: "/", label: "Solve" },
  { href: "/guide", label: "Guide" },
  { href: "/methodology", label: "Methodology" },
  { href: "/patterns", label: "Patterns" },
  { href: "/flashcards", label: "Flashcards" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/docs", label: "API Docs ↗", external: true },
];
```

- [ ] **Step 2: Add the "Study this pattern" link**

In `algotrainer/web/static/patterns_detail.js`, current lines 37-42:

```javascript
  const summary = document.createElement("p");
  summary.className = "lede";
  summary.textContent = p.summary || "No reference doc has been written for this pattern yet.";
  body.appendChild(summary);

  if (p.recognize_when.length) {
```

Replace with:

```javascript
  const summary = document.createElement("p");
  summary.className = "lede";
  summary.textContent = p.summary || "No reference doc has been written for this pattern yet.";
  body.appendChild(summary);

  const studyLink = document.createElement("p");
  const studyA = document.createElement("a");
  studyA.href = `/flashcards/${p.id}`;
  studyA.textContent = "Study this pattern with flashcards →";
  studyLink.appendChild(studyA);
  body.appendChild(studyLink);

  if (p.recognize_when.length) {
```

- [ ] **Step 3: Add flashcard styles**

Append to `algotrainer/web/static/app.css`:

```css
/* --- flashcards --- */
.mcq-options { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.rating-row { display: flex; gap: 8px; margin: 12px 0; }
.flashcard-code { width: 100%; font-family: ui-monospace, monospace; padding: 8px; }
.diff-view { background: #0f0f23; color: #eee; padding: 12px 14px; border-radius: 6px;
  font-family: ui-monospace, monospace; overflow-x: auto; white-space: pre; margin: 10px 0; }
.diff-line.diff-equal { color: #9aa0c3; }
.diff-line.diff-reference { color: #ff8a80; }
.diff-line.diff-typed { color: #6be675; }
#session-progress { font-size: 0.85rem; color: #666; }
```

- [ ] **Step 4: Commit**

```bash
git add algotrainer/web/static/nav.js algotrainer/web/static/patterns_detail.js algotrainer/web/static/app.css
git commit -m "feat: link flashcards from nav and pattern detail pages"
```

---

### Task 7: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full automated test suite**

Run: `pytest -v`
Expected: PASS — every test in `tests/`, including all `test_flashcards.py`, `test_store.py`, and `test_web_flashcards.py` cases added above.

- [ ] **Step 2: Start the dev server**

Run: `algotrainer` (or `python -m algotrainer`)
Expected: Server starts, logs listening on `http://127.0.0.1:8000`.

- [ ] **Step 3: Manually exercise the feature in a browser**

Visit `http://127.0.0.1:8000/flashcards`:
- Confirm the due count shows `1 due` or more and the page lists only `arrays-hashing` cards (nothing has been attempted yet in a fresh db, so per `unlocked_patterns`, only the first roadmap pattern is unlocked).
- Click **Study**. Step through at least one card of each type:
  - **Recognition**: click an option, confirm correct/incorrect feedback appears, click Next.
  - **Complexity**: click "Show answer", confirm time/space text renders, click a rating button.
  - **Gotcha**: same flip flow, confirm the gotcha list renders.
  - **Template**: type a few lines of Python into the box, click Check, confirm the diff view renders with colored lines, then rate.
- Confirm the session ends with "Session complete." once the queue is empty.
- Visit `http://127.0.0.1:8000/patterns/two-pointers`, confirm the "Study this pattern with flashcards →" link appears and navigates to `/flashcards/two-pointers`.
- Confirm the "Flashcards" link appears in the top nav on every page and highlights as active on `/flashcards`.
- Visit `http://127.0.0.1:8000/dashboard` and confirm nothing changed there — no flashcard due-count, mastery table unaffected (this confirms the isolation from the mastery gate holds in the running app, not just in tests).

- [ ] **Step 4: Stop the dev server**

Interrupt the running `algotrainer` process (Ctrl-C in that terminal, or the equivalent for however it was started).

No commit for this task — it's verification only.
