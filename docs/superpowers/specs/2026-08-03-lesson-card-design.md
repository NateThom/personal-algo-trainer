# Lesson Field + Lesson Flashcard — Design Document

**Date:** 2026-08-03
**Status:** Approved design, pre-implementation
**Author:** nthom (with Claude)

---

## 1. Purpose

Every pattern doc (`content/patterns/*.json`) already carries a `summary` field, but it's written
for someone who already knows the pattern — a terse, technical one-liner (e.g. "Build a bottom-up
1-D table where each entry is computed from a small fixed number of previous entries..."). There is
no field aimed at someone encountering the pattern for the first time: a short, plain-language
explanation of *what the pattern is and why it works*, the kind of thing you'd want to read before
the recognition/complexity/template/gotcha drill material makes sense.

This feature adds that content (`lesson`) to every pattern doc, and — since the app already has a
flashcard study system (`docs/superpowers/specs/2026-07-14-flashcards-design.md`) covering
recognition/complexity/template/gotcha — surfaces it as a fifth flashcard type in that same system,
plus as reference prose on the existing `/patterns/{id}` page.

---

## 2. Scope

### In scope
- New `lesson` field (string, 3–5 sentence teaching paragraph) added to all 18
  `content/patterns/*.json` docs, written by hand per pattern (not derived from existing fields).
- `lesson` promoted to a required field in `pattern_docs.py` validation (all 18 docs get it in the
  same change, so this doesn't break anything mid-flight).
- New `lesson` flashcard type in the existing FSRS-scheduled flashcard system
  (`algotrainer/flashcards.py`, `flashcard` table, `/flashcards` study session), using the same
  flip-card mechanic already used by `complexity`/`gotcha`: front = pattern name, "Show answer"
  reveals the lesson paragraph, self-rated Again/Hard/Good/Easy.
- Lesson paragraph also rendered as prose on `/patterns/{id}` (`patterns_detail.js`), near the
  existing summary — useful as reference reading, not just quiz content.
- The standalone Anki export script (scratchpad `build_anki_deck.py`, not part of the repo) updated
  to emit a lesson note per pattern and re-run, so the Anki deck stays a mirror of the in-app deck.

### Explicitly out of scope
- No changes to the recognition/complexity/template/gotcha card types or their content.
- No new API routes and no changes to `/api/flashcards/due` or `/api/flashcards/review` — both
  already iterate `CARD_TYPES` generically and only need the tuple extended (see §4). One existing
  route's response shape does change: `GET /api/patterns/{id}` gains a `lesson` key (see §5).
- No DB schema migration — `flashcard` is keyed by `(pattern, card_type)` as free-text `TEXT`
  columns; a new `card_type` value needs no table change.
- No gating/ordering changes to how patterns become available (unchanged: all 18 patterns' cards
  are available from day one, per the original flashcards design).

---

## 3. Data model

`content/patterns/<id>.json` gains one field, alongside the existing ones:

```json
{
  "id": "dp-1d",
  "summary": "...",
  "lesson": "A short paragraph (3-5 sentences) explaining what the pattern is, in plain language, for someone seeing it for the first time.",
  "recognize_when": [...],
  "complexity": {...},
  "template": "...",
  "gotchas": [...],
  "examples": [...]
}
```

`algotrainer/pattern_docs.py`'s `_REQUIRED` tuple changes from
`("id", "summary", "recognize_when", "complexity", "template")` to
`("id", "summary", "lesson", "recognize_when", "complexity", "template")`, with the same
"non-empty string" validation already applied to `summary`/`template`.

No changes to `algotrainer/store.py` — the `flashcard` table already has no `CHECK` constraint on
`card_type`, so a new value flows through the existing `get_flashcard`/`save_flashcard`/
`all_flashcard_due` methods unmodified.

---

## 4. Card type and mechanics

`algotrainer/flashcards.py`'s `CARD_TYPES` tuple changes from

```python
CARD_TYPES: tuple[str, ...] = ("recognition", "complexity", "template", "gotcha")
```

to

```python
CARD_TYPES: tuple[str, ...] = ("lesson", "recognition", "complexity", "template", "gotcha")
```

`lesson` is ordered first: pedagogically, you read the concept before drilling recognition signals,
complexity, or gotchas for it.

No new pure-logic function is needed. `lesson` is a flip card with the same shape as `complexity`
and `gotcha` — no MCQ options to build (that's only `recognition`), no diff to compute (that's only
`template`). The existing `/api/flashcards/due` handler already builds a bare
`{pattern, card_type, pattern_name}` card dict for any type that isn't `recognition`, and the
existing `/api/flashcards/review` handler already routes any non-`recognition` type through the
"rating is required" flip-card path. Both pick up `lesson` automatically once it's in `CARD_TYPES` —
no route changes.

---

## 5. API

`GET /api/patterns/{id}` (`algotrainer/web/app.py`, `pattern_detail` handler) builds its response as
a hand-picked field-by-field dict, not a passthrough of the doc — so it does *not* automatically
expose new doc keys the way `/api/flashcards/due` does. It needs one added line,
`"lesson": doc["lesson"] if doc else ""`, alongside the existing `"summary"` line. Both consumers in
§6 below (`flashcards.js`'s `fetchDoc`, and `patterns_detail.js`) read `lesson` through this same
endpoint, so this is a prerequisite for both.

`/api/flashcards/due` and `/api/flashcards/review` need no changes — confirmed in §4, they already
iterate `CARD_TYPES` generically.

---

## 6. UI/UX

**Flashcard session (`flashcards.js`):** add `revealLesson(doc, body)`, mirroring the existing
`revealComplexity`/`revealGotchas` functions — renders `doc.lesson` as a single paragraph. Add a
`card.card_type === "lesson"` branch in `renderCard`'s dispatch, wired to `renderFlipCard(card, body,
revealLesson)` exactly like the `complexity`/`gotcha` branches.

**Pattern detail page (`patterns_detail.js`):** render `p.lesson` as a prose paragraph immediately
after the existing summary `<p class="lede">`, before the "Study this pattern with flashcards →"
link and the `recognize_when` list.

No new styling needed — reuses existing `.lede`/paragraph/flip-card CSS.

---

## 7. Content authoring

The bulk of this change is writing 18 lesson paragraphs, one per `content/patterns/*.json`. Each
should:
- Be 3–5 sentences, plain language, assuming no prior familiarity with the pattern.
- Explain the core idea/mechanism (not just "when to use it" — that's what `recognize_when`
  already covers).
- Avoid duplicating the `summary` field's wording — summary is the terse technical reminder,
  lesson is the teaching explanation.

Drafted by Claude from each doc's existing `summary`/`recognize_when`/`gotchas`/`examples`/
`template` content, then spot-checked for accuracy against the pattern's actual mechanics.

---

## 8. Anki export

The scratchpad `build_anki_deck.py` script (not committed to the repo — a one-off AnkiConnect
pusher) gains a fifth note-emission block, mirroring the existing `complexity`/`gotcha`/`template`
blocks:

```python
notes.append({
    "deckName": deck,
    "modelName": "Basic",
    "fields": {
        "Front": f"{html_escape(name)} — what is this pattern?",
        "Back": f"<p>{html_escape(doc['lesson'])}</p>",
    },
    "tags": ["algotrainer", pattern_id, "lesson"],
    "options": {"allowDuplicate": False},
})
```

Re-run after the content change lands, so the Anki deck (which already has all 18 pattern subdecks)
picks up the new lesson notes. `allowDuplicate: False` means re-running the whole script is safe —
it won't duplicate the recognition/complexity/gotcha/template notes already pushed.

---

## 9. Testing

Matching existing test-file conventions:

- `tests/test_pattern_docs.py` — `VALID` fixture gains `"lesson"`; new test asserts a doc missing
  `lesson` is rejected by `load_pattern_doc`.
- `tests/test_flashcards.py` — `test_card_types_are_the_four_facets` updated to assert the full
  5-member set (`{"lesson", "recognition", "complexity", "template", "gotcha"}`); rename to
  `test_card_types_are_the_five_facets`.
- `tests/test_web_flashcards.py` — `test_due_cards_include_all_four_types_for_a_pattern` updated to
  expect 5 types and renamed accordingly; due-count comment in the design/plan docs (72 = 18×4)
  becomes 90 = 18×5 wherever it's asserted or documented.
- `tests/test_web_patterns.py` — new test asserting `GET /api/patterns/{id}` includes a non-empty
  `lesson` string (see §5).
- No new test file — `lesson` reuses existing flip-card code paths, so it's covered by extending the
  existing parametrized-style assertions rather than adding new test functions.
