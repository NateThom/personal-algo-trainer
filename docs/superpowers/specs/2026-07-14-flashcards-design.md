# Flashcards — Design Document

**Date:** 2026-07-14
**Status:** Approved design, pre-implementation
**Author:** nthom (with Claude)

---

## 1. Purpose

AlgoTrainer's problem-solving loop trains the deep skill (recognize a pattern cold, solve a novel
instance, retain it via spaced repetition). What it doesn't yet cover is the *vocabulary and facts*
that loop assumes you already have: what each pattern's recognition signals are, its time/space
complexity, its code skeleton, its common gotchas. Right now that content only exists as static
reference pages (`/patterns/{id}`) — you can read it, but there's no mechanism forcing you to
retrieve it from memory, and no spaced-repetition schedule keeping it fresh.

This feature adds a flashcard study mode over that existing reference content
(`content/patterns/*.json`), using the same active-recall + FSRS machinery already proven out
elsewhere in the app.

### The one non-negotiable constraint

AlgoTrainer's mastery model (`mastery.py`, `methodology.html` §7) exists specifically to catch and
reject "high solve rate, low pattern-ID accuracy" as **not mastery** — the "memorization trap." A
flashcard mode is, by nature, a memorization/recognition tool. If its review stats fed into the same
`pattern_card` FSRS state that drives the mastery-gate's stability signal, grinding flashcards would
let you *purchase* apparent mastery without ever solving a novel problem — exactly the failure mode
the app is built to prevent.

So: **flashcard review history is a fully separate track.** New table, new FSRS cards, never written
to `pattern_card`, never read by `mastery.py`. Flashcards feed *into* your ability to solve problems
(faster recognition, retained facts); they cannot substitute for the evidence that you did.

---

## 2. Scope

### In scope (v1)
- Four flashcard types per pattern, derived entirely from existing `content/patterns/*.json` docs:
  recognition (MCQ), complexity (flip), template (type-and-diff), gotcha (flip).
- Independent FSRS scheduling per `(pattern, card_type)`, reusing the existing `SrsScheduler`.
- Progressive unlock: a pattern's cards open once you've graded an attempt in it, or it's the next
  pattern up in roadmap order.
- Dedicated `/flashcards` page (global, interleaved study session) + a "Study this pattern" entry
  point from `/patterns/{id}`.
- New nav entry.

### Explicitly out of scope (v1)
- No manual card authoring/editing UI — a pattern doc *is* its flashcard content.
- No dashboard integration — `/dashboard` is untouched.
- No gamification (streaks, XP, badges).
- No cross-device sync/export.

### Rationale for narrow scope
Zero new content debt (all four card types derive from data that already exists), and a tight
boundary against contaminating the mastery model — those two constraints do most of the scoping
work. Everything else (dashboard hooks, authoring UI) is additive and can be layered on later if it
turns out to matter.

---

## 3. Data model

New table in `algotrainer/store.py`:

```sql
CREATE TABLE IF NOT EXISTS flashcard (
    pattern   TEXT NOT NULL,
    card_type TEXT NOT NULL,   -- 'recognition' | 'complexity' | 'template' | 'gotcha'
    card_json TEXT NOT NULL,
    next_due  TEXT NOT NULL,
    PRIMARY KEY (pattern, card_type)
);
```

`Store` gains `get_flashcard(pattern, card_type)`, `save_flashcard(pattern, card_type, card_json,
next_due)`, and `all_flashcard_due(now) -> dict[(pattern, card_type), datetime]`, mirroring the
existing `card`/`pattern_card` accessor pattern exactly (same upsert-on-conflict shape). `flashcard`
is added to the table list `reset_progress()` wipes.

`SrsScheduler` (already a pure `review(card_json, rating, when)` wrapper around the `fsrs` library,
no internal state) is reused unmodified — flashcard reviews just target a different table.

---

## 4. Card types and mechanics

All content is read from the existing `content/patterns/<id>.json` docs (`summary`,
`recognize_when`, `complexity`, `template`, `gotchas`) — no new content files.

**1. Recognition — MCQ, auto-graded**
Front: one signal string randomly chosen from that pattern's `recognize_when` list (varies per rep).
Options: the correct pattern + up to 3 distractors, preferring `confusable_group(pid) - {pid}` first
(the genuinely hard discriminations already used for interleaving — sliding-window vs. two-pointers,
BFS vs. DFS, backtracking vs. DP), padded with random other patterns when the confusable group is
smaller than 3 (several patterns have an empty `confusable_with`). Grading is automatic: correct →
FSRS rating "good" (3), incorrect → "again" (1).

**2. Complexity — flip-card, self-graded**
Front: pattern name only. Flip reveals `complexity.time` / `.space` / `.notes`. You press
Again/Hard/Good/Easy yourself, using the same four-value vocabulary the scheduler already speaks
(`RATING_BY_NAME`) — just user-supplied here instead of tutor-supplied.

**3. Template — type-then-diff, self-graded**
Front: pattern name + an empty code box. You type the template from memory and submit it; the
server whitespace-normalizes both your text and the reference and runs a line-level
`difflib.SequenceMatcher` diff. The frontend renders your version against the reference with
equal/replace/insert/delete highlighting. You self-rate based on how close you were — the diff is a
grading *aid*, not an automatic pass/fail, consistent with how the other flip-card types work.

**4. Gotcha — flip-card, self-graded**
Same shape as complexity: front is the pattern name, flip reveals the `gotchas` list, self-rated.

---

## 5. Pure logic module

New `algotrainer/flashcards.py`, pure functions only (same style as `mastery.py`):

- `unlocked_patterns(graded_patterns: set[str]) -> set[str]` — attempted patterns (from
  `store.all_graded_patterns()`) plus the single next-not-yet-attempted pattern in roadmap order
  (`roadmap_order()` from `patterns.py`).
- MCQ option builder — correct pattern + confusable-group-first distractor selection, described
  above, with the empty-`confusable_with` fallback.
- Diff builder — normalizes whitespace, runs `difflib.SequenceMatcher`, returns aligned line ops.

---

## 6. API surface

Added to `algotrainer/web/app.py`:

- `GET /flashcards` — page.
- `GET /flashcards/{pattern_id}` — page, pattern-scoped session (reuses the same static page, pattern
  passed client-side).
- `GET /api/flashcards/due` — due cards across unlocked patterns, each with its rendered front
  payload (recognition includes pre-shuffled MCQ options; the other three types just need
  `pattern`/`card_type` — the frontend already has pattern-doc content available via the existing
  `/api/patterns/{id}` endpoint).
- `POST /api/flashcards/review` — `{pattern, card_type, rating}` → runs FSRS via `SrsScheduler`,
  writes to `flashcard`. For recognition cards the rating is server-computed from correctness rather
  than client-supplied.
- `POST /api/flashcards/diff` — `{pattern, code}` → diff ops (template card type only).

---

## 7. UI/UX

- New `flashcards.html` + `flashcards.js`, linked from the nav bar (`nav.js`) alongside
  Solve/Dashboard/Patterns/Guide/Methodology. Shows a due-card count and a **Study** button that
  starts a session pulling all due cards across unlocked patterns, shuffled across patterns
  (interleaved, matching the app's existing interleaving philosophy).
- `patterns_detail.html`/`.js` gains a **Study this pattern** link, scoping a session to one
  pattern's due-or-new cards.
- Session UI: one card at a time, type-specific front (MCQ buttons / flip button / code box) →
  reveal → rate → advance. Ends with a plain "N cards studied" summary when the queue empties. No
  gamification.

---

## 8. Testing

Matching existing test-file conventions:

- `tests/test_flashcards.py` — unlock progression, MCQ distractor selection (including the
  empty-`confusable_with` fallback), diff-output shape.
- `tests/test_store.py` — flashcard CRUD + `reset_progress` wipes the new table.
- `tests/test_web_flashcards.py` — due-list endpoint respects unlock gating; the review endpoint
  updates `flashcard` state and provably never touches `pattern_card` or `graded_attempt`.
