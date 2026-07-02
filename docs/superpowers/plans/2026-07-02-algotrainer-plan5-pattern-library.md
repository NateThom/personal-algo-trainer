# AlgoTrainer — Plan 5: Pattern Reference Library + Progress Signals

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven-development / executing-plans. Checkbox steps.

**Goal:** Give the learner (1) a browsable **pattern reference library** — the canonical set they're choosing from at the recall gate, one page per pattern in the AlgoMonster mould (recognize → complexity → memorizable template → gotchas/examples); (2) a **"New" vs "Review (seen N×)" badge** on every served problem; and (3) **generate-more guidance** — the app tells them when a pattern's unseen pool is empty and when a pattern lacks enough instances to ever reach the mastery gate.

**Architecture:** Expand the `patterns.py` registry to ~18 canonical patterns. Add committed reference content (`content/patterns/<id>.json`) loaded by a new pure `pattern_docs.py` (validated, invalid files skipped). New read-only API (`/api/patterns`, `/api/patterns/{id}`) and two pages (`/patterns` index, `/patterns/{id}` detail, JS-rendered via DOM methods). `/api/next` gains `seen_count` and a `pattern_pool` block; the solve UI renders a badge + a generate-more banner; the dashboard shows per-pattern instance counts and a "needs more" flag.

**Tech Stack:** unchanged.

## Global Constraints
- Python 3.11+; tz-aware UTC. Pure modules (`patterns.py`, `pattern_docs.py`) do no I/O beyond reading their content dir.
- Pattern-doc rendering uses **DOM methods, not innerHTML with file content** (author-provided text/templates are trusted repo content, but avoid an injection habit — build nodes and set `.textContent`).
- The mastery gate breadth is `mastery.GATE_BREADTH` (4). "Needs more instances" = `max(0, GATE_BREADTH - total_instances_of_pattern)`.
- Run tests `.venv/bin/pytest`; lint `.venv/bin/ruff check algotrainer tests scripts`. Pristine. Commit per task; stage only named files.

## Canonical pattern set (registry, ~18)
id / name / order / confusable_with:
1 arrays-hashing / Arrays & Hashing / () ·
2 two-pointers / Two Pointers / (sliding-window) ·
3 sliding-window / Sliding Window / (two-pointers) ·
4 stack / Stack / () ·
5 prefix-sum / Prefix Sum / (sliding-window) ·
6 binary-search / Binary Search / () ·
7 linked-list / Linked List / () ·
8 trees / Trees (BFS/DFS) / (graphs) ·
9 tries / Tries / () ·
10 heaps / Heaps / Top-K / () ·
11 intervals / Intervals / () ·
12 backtracking / Backtracking / (dp-1d) ·
13 graphs / Graphs / (trees, union-find, topological-sort) ·
14 union-find / Union-Find / (graphs) ·
15 topological-sort / Topological Sort / (graphs) ·
16 dp-1d / 1-D DP / (backtracking) ·
17 dp-2d / 2-D DP / (dp-1d) ·
18 bit-manipulation / Bit Manipulation / ()

## Pattern-doc schema (`content/patterns/<id>.json`)
```json
{
  "id": "sliding-window",
  "summary": "1-2 sentence plain-English description of the pattern.",
  "recognize_when": ["signal 1", "signal 2", "signal 3"],
  "complexity": {"time": "O(n)", "space": "O(k)", "notes": "why"},
  "template": "def fn(arr):\n    left = 0\n    ...\n",
  "gotchas": ["common mistake 1", "common mistake 2"],
  "examples": ["Longest Substring Without Repeating Characters", "Best Time to Buy and Sell Stock"]
}
```
`name`/`order`/`confusable` come from the registry (not duplicated in the doc).

---

### Task 1: Expand the pattern registry
**Files:** Modify `algotrainer/patterns.py`; update `tests/test_patterns.py`.
- Add the 5 new `PatternMeta` entries (prefix-sum, intervals, union-find, topological-sort, bit-manipulation) and renumber all orders 1–18 per the canonical list, with the confusable_with declarations above.
- Keep existing helpers unchanged. Existing tests (subset membership, unique/min-1 orders, symmetric confusable, roadmap_order) must still pass; add an assertion that `len(PATTERNS) == 18` and that the 5 new ids are present.
- [ ] Update test → run (fail) → edit registry → run (pass) → commit `feat: expand pattern registry to 18 canonical patterns`.

### Task 2: Pattern-doc loader
**Files:** Create `algotrainer/pattern_docs.py`, `content/patterns/sliding-window.json` (sample), `content/patterns/arrays-hashing.json` (sample); `tests/test_pattern_docs.py`.
**Interfaces:**
- `PATTERN_DOCS_DIR: Path` (repo `content/patterns`).
- `load_pattern_doc(pid, docs_dir=PATTERN_DOCS_DIR) -> dict | None` — returns the validated doc dict or None if missing/invalid.
- `load_all_pattern_docs(docs_dir=PATTERN_DOCS_DIR) -> dict[str, dict]` — id→doc for every valid file (invalid skipped).
- `_valid(doc) -> bool` — requires non-empty `id`, `summary`, `recognize_when` (non-empty list), `complexity` (dict with `time` and `space`), `template` (non-empty str).

Implementation:
```python
import json
from pathlib import Path

PATTERN_DOCS_DIR = Path(__file__).resolve().parent.parent / "content" / "patterns"

_REQUIRED = ("id", "summary", "recognize_when", "complexity", "template")


def _valid(doc: dict) -> bool:
    if not all(doc.get(k) for k in _REQUIRED):
        return False
    if not isinstance(doc.get("recognize_when"), list) or not doc["recognize_when"]:
        return False
    c = doc.get("complexity")
    if not isinstance(c, dict) or not c.get("time") or not c.get("space"):
        return False
    return isinstance(doc.get("template"), str) and bool(doc["template"].strip())


def load_pattern_doc(pid: str, docs_dir: Path = PATTERN_DOCS_DIR) -> dict | None:
    path = docs_dir / f"{pid}.json"
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return doc if _valid(doc) else None


def load_all_pattern_docs(docs_dir: Path = PATTERN_DOCS_DIR) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not docs_dir.exists():
        return out
    for path in sorted(docs_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if _valid(doc):
            out[doc["id"]] = doc
    return out
```
Author `sliding-window.json` and `arrays-hashing.json` as the quality bar (complete, accurate).
Tests: valid sample loads; a fabricated invalid doc (missing template) returns None; load_all skips invalid.
- [ ] TDD → commit `feat: pattern-doc loader + sample reference pages`.

### Task 3: Author the remaining pattern reference docs (FAN-OUT)
**Files:** Create `content/patterns/<id>.json` for the other 16 patterns.
- Each doc follows the schema, accurate for the canonical pattern: crisp summary, 3–5 recognition signals, correct characteristic time/space complexity with a short why, a correct memorizable Python template (a real starting skeleton), 2–3 gotchas, 2–3 named example problems.
- Acceptance: `load_all_pattern_docs()` returns a doc for ALL 18 registry patterns; a test asserts coverage.
- [ ] Author (fan-out) → add coverage test → run → commit `feat: complete pattern reference library (all 18 patterns)`.

### Task 4: Pattern-library API + pages
**Files:** Modify `algotrainer/web/app.py`; create `web/static/patterns.html`, `patterns_detail.html`, `patterns.js`, `patterns_detail.js`; modify `index.html` (recall-gate link), `app.css`, `nav.js` (add "Patterns" nav link).
**Interfaces:**
- `GET /api/patterns` → `{"patterns": [{id, name, order, summary, has_doc, confusable}]}` for ALL registry patterns (summary from doc if present else ""), sorted by roadmap order.
- `GET /api/patterns/{pattern_id}` → registry name/order + doc fields + `confusable` (names) + `seed_examples` (problem ids in the pool for that pattern); 404 if the id is not a registry pattern.
- `GET /patterns` → patterns.html; `GET /patterns/{pattern_id}` → patterns_detail.html (JS reads the id from `location.pathname`).
- Add "Patterns" to `nav.js` NAV_PAGES (after Methodology). Add a recall-gate hint on the solve page: "Not sure? Browse the Pattern Library" linking `/patterns`.
- Pages render with DOM methods (textContent), not innerHTML of doc text.
- [ ] TDD (routes serve; /api/patterns lists 18; detail 404 for junk) → commit `feat: pattern library API + browsable pages`.

### Task 5: "New" vs "Review" badge
**Files:** Modify `algotrainer/store.py` (+ `attempt_count_for_problem(problem_id) -> int` from graded_attempt), `algotrainer/web/app.py` (`/api/next` adds `seen_count`), `web/static/index.html` + `app.js` (badge), `app.css`.
- `/api/next` problem payload gains `seen_count` (graded attempts for that id). UI shows "🆕 New" when 0 else "🔁 Review · seen N×".
- [ ] TDD (store count; /api/next includes seen_count; after grading a problem and forcing it due, seen_count>=1) → commit `feat: new/review badge on served problems`.

### Task 6: Generate-more guidance
**Files:** Modify `algotrainer/web/app.py` (`/api/next` adds `pattern_pool`; `/api/dashboard` adds per-pattern instance info), `web/static/app.js` (banner), `web/static/dashboard.js` (column + hint), `app.css`.
- Compute for a pattern: `total` = problems in the pool with that pattern; `seen` = distinct graded problem ids of that pattern; `unseen = total - seen`; `needs_more = max(0, GATE_BREADTH - total)`.
- `/api/next` adds `pattern_pool: {pattern, total, unseen, needs_more}` for the served problem's pattern. Solve UI shows a banner when `unseen == 0` ("You've seen all N {name} problems — ask the tutor to generate a variant to keep progressing") and/or when `needs_more > 0` ("This pattern needs {needs_more} more instance(s) to be masterable — generate variants").
- `/api/dashboard` mastery rows gain `instances` (total) and `needs_more`; dashboard.js adds an "Instances" column and a "⚙ generate more" flag when `needs_more > 0` or the pattern is tracked but has no unseen left.
- [ ] TDD (pattern_pool present + correct on /api/next; dashboard exposes instances/needs_more) → commit `feat: generate-more guidance on solve page + dashboard`.

### Task 7: Verify + review
- [ ] Full suite green + ruff clean; manual: browse /patterns, open a detail page, confirm badge + banner on solve page and dashboard indicators.

## Self-Review (against this plan)
- Pattern library (recognize/complexity/template/gotchas/examples) — Tasks 1–4 ✓
- Seen/new labeling — Task 5 ✓
- Generate-more guidance incl. the "gate needs 4 but seed has fewer" reality — Task 6 ✓
