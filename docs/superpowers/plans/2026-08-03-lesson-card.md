# Lesson Field + Lesson Flashcard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `lesson` field (a short, plain-language teaching paragraph) to all 18 pattern reference docs, and surface it as a fifth flashcard type in the existing FSRS-scheduled flashcard system, plus as reference prose on the pattern detail page.

**Architecture:** `content/patterns/*.json` gains a `lesson` string field, validated as required by `pattern_docs.py`. `algotrainer/flashcards.py`'s `CARD_TYPES` tuple grows from 4 to 5 entries; because `/api/flashcards/due` and `/api/flashcards/review` in `algotrainer/web/app.py` already iterate `CARD_TYPES` generically, no route changes are needed. `flashcards.js` gets one new reveal function and a dispatch branch (mirrors the existing `complexity`/`gotcha` flip cards exactly). `patterns_detail.js` renders the lesson paragraph as prose. The scratchpad Anki export script gets a matching fifth note type.

**Tech Stack:** Python 3.10+, pytest, vanilla JS + DOM methods (no framework, matching existing `flashcards.js`/`patterns_detail.js` conventions).

Reference spec: `docs/superpowers/specs/2026-08-03-lesson-card-design.md`

## Global Constraints

- `lesson` text: 3–5 sentences, plain language, assumes no prior familiarity with the pattern — distinct from the existing terse `summary` field (do not duplicate its wording).
- No DB schema migration — `flashcard` table's `card_type` column is unconstrained `TEXT`.
- No new API routes — `CARD_TYPES` is the only integration point for the due/review endpoints.

---

### Task 1: `lesson` field — validation + content for all 18 patterns

**Files:**
- Modify: `algotrainer/pattern_docs.py:10` (`_REQUIRED` tuple)
- Modify: `tests/test_pattern_docs.py` (`VALID` fixture, new test)
- Modify: all 18 files in `content/patterns/*.json` (add `lesson` field)
- Create (temporary, deleted before commit): `scripts/_add_lesson_field.py`

**Interfaces:**
- Produces: every `content/patterns/*.json` doc now has a `"lesson"` key (string); `load_pattern_doc`/`load_all_pattern_docs` in `algotrainer/pattern_docs.py` reject any doc missing it. `GET /api/patterns/{id}` does **not** yet expose it — that response is hand-built field-by-field in `algotrainer/web/app.py:236-244`, not a passthrough of the doc dict — so Task 3 adds `lesson` to that response before any frontend task can read `doc.lesson`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_pattern_docs.py`, the current `VALID` fixture (top of file) is:

```python
VALID = {
    "id": "x", "summary": "s", "recognize_when": ["a"],
    "complexity": {"time": "O(n)", "space": "O(1)", "notes": "n"},
    "template": "def f():\n    pass\n", "gotchas": ["g"], "examples": ["e"],
}
```

Replace it with (adds `"lesson": "l"` so the existing tests that rely on `VALID` loading successfully keep passing once `lesson` becomes required):

```python
VALID = {
    "id": "x", "summary": "s", "lesson": "l", "recognize_when": ["a"],
    "complexity": {"time": "O(n)", "space": "O(1)", "notes": "n"},
    "template": "def f():\n    pass\n", "gotchas": ["g"], "examples": ["e"],
}
```

Then append a new test to the same file:

```python
def test_doc_without_lesson_is_invalid(tmp_path):
    missing_lesson = {k: v for k, v in VALID.items() if k != "lesson"}
    (tmp_path / "no-lesson.json").write_text(json.dumps(missing_lesson))
    assert load_pattern_doc("no-lesson", tmp_path) is None
```

- [ ] **Step 2: Run tests to verify the new test fails**

Run: `pytest tests/test_pattern_docs.py -v -k lesson`
Expected: FAIL — `test_doc_without_lesson_is_invalid` fails because `pattern_docs.py` doesn't require `lesson` yet, so the doc loads successfully instead of returning `None`.

- [ ] **Step 3: Require `lesson` in `pattern_docs.py`**

In `algotrainer/pattern_docs.py`, current line 10:

```python
_REQUIRED = ("id", "summary", "recognize_when", "complexity", "template")
```

Replace with:

```python
_REQUIRED = ("id", "summary", "lesson", "recognize_when", "complexity", "template")
```

- [ ] **Step 4: Run tests to verify the new test passes (real docs will still fail)**

Run: `pytest tests/test_pattern_docs.py -v`
Expected: `test_doc_without_lesson_is_invalid` now PASSES, but `test_every_registry_pattern_has_a_valid_doc` FAILS — none of the 18 real `content/patterns/*.json` docs have a `lesson` field yet. This is expected at this point in the task; Step 5 fixes it.

- [ ] **Step 5: Write the content-insertion script**

Create `scripts/_add_lesson_field.py` (temporary — deleted in Step 8):

```python
"""One-off: insert the "lesson" field into every content/patterns/*.json doc,
immediately after "summary", preserving each file's existing formatting."""
import json
import re
from pathlib import Path

LESSONS = {
    "arrays-hashing": (
        "A hash map (or hash set) is a lookup table: it lets you ask \"have I seen this "
        "before?\" or \"what index did this appear at?\" in constant time, instead of "
        "scanning the whole array again. The core trick is trading memory for speed -- you "
        "spend O(n) space remembering what you've seen so you never have to re-scan. That "
        "turns problems that look like they need nested loops (compare every pair) into a "
        "single pass: for each element, check the map before adding to it. It's the workhorse "
        "pattern for counting, deduplication, and complement-lookup problems like Two Sum."
    ),
    "backtracking": (
        "Backtracking explores a decision tree by making a choice, recursing into the "
        "consequences of that choice, and then undoing the choice before trying the next one "
        "-- the \"choose, explore, un-choose\" cycle. It's how you systematically generate "
        "every valid combination, permutation, or configuration without missing any or "
        "repeating any. The \"un-choose\" step is what makes it different from plain "
        "recursion: it resets shared state (a path list, a visited set) so the next branch "
        "starts clean. Pruning -- bailing out early when a partial choice already can't lead "
        "to a valid answer -- is what keeps the exponential search tree small enough to run "
        "in practice."
    ),
    "binary-search": (
        "Binary search works on any answer space where you can ask a yes/no question and the "
        "answers are monotonic -- all the \"no\"s come before all the \"yes\"es (or vice "
        "versa). Instead of checking every candidate, you check the midpoint and use its "
        "answer to throw away half the remaining space, repeating until one candidate "
        "remains. This is why it isn't limited to \"find X in a sorted array\" -- any problem "
        "where you can binary-search on the answer itself (like \"the minimum capacity that "
        "lets you finish shipping in D days\") fits the same shape. Each halving takes it from "
        "O(n) linear scanning down to O(log n)."
    ),
    "bit-manipulation": (
        "Every integer is already a sequence of bits, so bitwise operators let you inspect or "
        "transform that structure directly instead of building an auxiliary data structure. "
        "XOR is the standout trick: it cancels a value with itself (a ^ a = 0) and is "
        "commutative, so XOR-ing a list where everything appears in pairs except one element "
        "isolates that unpaired element for free. AND/OR/shift operations let you test, set, "
        "clear, or count individual bits in O(1). The appeal is almost always space: where a "
        "hash set solution needs O(n) extra memory, the bit trick often needs none."
    ),
    "dp-1d": (
        "Dynamic programming exists because some recursive problems keep re-solving the exact "
        "same smaller subproblem over and over -- naive Fibonacci recomputes fib(n-2) "
        "exponentially many times. 1-D DP fixes this by storing each subproblem's answer in a "
        "table indexed by a single position (dp[i]), and filling that table from the smallest "
        "index up, so each entry is computed once from a few already-known earlier entries. "
        "You've turned exponential recursion into a linear pass. The pattern to look for is a "
        "recurrence: can you describe the answer at position i purely in terms of answers at "
        "smaller positions?"
    ),
    "dp-2d": (
        "2-D DP is the same idea as 1-D DP, but the state needs two coordinates instead of one "
        "-- most often because you're comparing two sequences (dp[i][j] = best answer using "
        "the first i characters of A and the first j characters of B) or moving through a "
        "grid. Each cell is filled from a small number of neighboring cells (usually the cell "
        "above, to the left, or diagonally up-left), so once the first row and column are "
        "seeded, the rest fills in one pass. This is the pattern behind \"align these two "
        "strings\" problems like edit distance and longest common subsequence, and grid-path "
        "problems like counting unique paths. The mental model: if a single index doesn't "
        "fully describe \"where you are\" in the problem, you probably need a second one."
    ),
    "graphs": (
        "Graphs generalize trees: nodes connect to other nodes via edges, and there's no "
        "single root or hierarchy to lean on. The two traversal strategies you reach for are "
        "BFS, which explores level by level using a queue and is what you want whenever you "
        "need the shortest path in an unweighted graph, and DFS, which dives as deep as "
        "possible using recursion or a stack and is what you want for connectivity, cycle "
        "detection, or exhaustively exploring every path. Grids (like an \"islands\" problem) "
        "are graphs in disguise -- each cell is a node connected to its neighbors. The main "
        "design decision on any graph problem is simply: BFS or DFS, and which one the "
        "question is actually asking for."
    ),
    "heaps": (
        "A heap (priority queue) keeps its smallest (or largest) element accessible in O(1) "
        "while still supporting O(log n) insertion and removal -- it's the data structure for "
        "\"give me the next-most-important item\" without paying for a full sort. That makes "
        "it the natural fit whenever a problem asks for the top-K, K-th largest, or repeatedly "
        "needs the current minimum/maximum as new elements stream in over time. Merging K "
        "sorted lists is a heap problem in disguise: keep one candidate from each list in the "
        "heap and always pull the smallest. The key efficiency win over sorting is that a heap "
        "only pays O(log k) per operation for a heap of size k, rather than O(n log n) to sort "
        "everything up front."
    ),
    "intervals": (
        "Interval problems become easy once you sort by start time -- after that, checking "
        "whether two intervals overlap or merging a run of overlapping intervals is just a "
        "single left-to-right sweep. The core comparison is: does this interval's start fall "
        "before (or at) the end of the interval you're currently building? If so, extend the "
        "current interval's end; if not, start a new one. Because the hard part (establishing "
        "an order) is handled by the sort, the sweep itself only needs to look at the interval "
        "immediately before it -- no backtracking required. This is why interval problems "
        "(merging, inserting, meeting-room conflicts) all end up with roughly the same shape: "
        "sort, then one pass."
    ),
    "linked-list": (
        "A linked list has no indices -- only pointers -- so problems here are about "
        "manipulating those pointers directly rather than array positions. Common techniques "
        "include the fast/slow pointer pair (fast moves two nodes per step, slow moves one; "
        "when fast reaches the end, slow is at the midpoint -- and if there's a cycle, they "
        "eventually meet), and using a dummy head node so you never need special-case logic "
        "for \"the answer's first node might change.\" Because you can't jump backward, most "
        "operations (reversal, merging) are done by carefully re-wiring .next pointers while "
        "walking forward once. The payoff for this extra care is O(1) space -- no array copy "
        "needed to reorder or transform the list."
    ),
    "prefix-sum": (
        "If you're going to ask \"what's the sum of this subrange\" many times over an array "
        "that doesn't change, it's wasteful to re-add the same numbers on every query. Prefix "
        "sum precomputes a running total once, so the sum of any subrange becomes a single "
        "subtraction: sum(i, j) = prefix[j] - prefix[i]. The same idea generalizes to "
        "counting: if you're looking for subarrays that sum to a target, you can reframe the "
        "condition as \"has this exact prefix value occurred before,\" and answer it with a "
        "hashmap in one pass instead of checking every subarray. It trades one O(n) setup pass "
        "for O(1) answers afterward."
    ),
    "sliding-window": (
        "Sliding window is for problems about a contiguous run of a sequence -- a substring or "
        "subarray -- where a brute-force solution would recheck the same overlapping range "
        "again and again. Instead of restarting from scratch for every possible window, you "
        "keep one window with a left and right edge: expand the right edge to bring in new "
        "elements, and only shrink from the left when the window becomes invalid. Because each "
        "element enters and leaves the window at most once, this turns an O(n^2) \"check every "
        "subarray\" approach into O(n). The technique only works when the window's validity is "
        "monotonic in size -- once it stops being valid, shrinking is guaranteed to help, "
        "which is why it breaks down on inputs like negative numbers in a sum-based window."
    ),
    "stack": (
        "A stack is useful whenever the thing you need to resolve later is \"whatever is most "
        "recently still open\" -- an unmatched opening bracket, the last unresolved "
        "comparison, the most recent unfinished operation. You push items as you encounter "
        "them and pop them off once the matching condition arrives, so each item is handled in "
        "the reverse order it was seen (LIFO). The monotonic stack variant takes this further: "
        "by only keeping elements on the stack that could still be useful (discarding anything "
        "a new, better element makes irrelevant), you can answer \"next greater element\" "
        "style questions for the whole array while still only pushing and popping each element "
        "once -- giving amortized O(n) despite the nested-looking while loop."
    ),
    "topological-sort": (
        "Topological sort answers \"in what order can these tasks happen, given that some must "
        "come before others?\" It only works on a directed acyclic graph, because a cycle "
        "would mean two tasks depend on each other, which has no valid order. Kahn's algorithm "
        "builds the order by repeatedly picking off any node with zero remaining prerequisites "
        "(in-degree zero), removing its outgoing edges, and repeating -- nodes that become "
        "prerequisite-free as a result get added to the queue next. If you run out of nodes to "
        "process before every node is ordered, that's proof a cycle exists somewhere in the "
        "remaining graph."
    ),
    "trees": (
        "Trees are graphs with a fixed hierarchy (a single root, no cycles), which means most "
        "tree problems decompose naturally: the answer for a node is defined in terms of the "
        "answers for its children. That's why recursive DFS (compute left, compute right, "
        "combine) is the default tool -- height, sum, balance, and lowest-common-ancestor "
        "problems all follow this same \"solve the subtree, combine with the current node\" "
        "shape. BFS (level order, via a queue) is what you reach for instead whenever the "
        "question is actually about levels or \"shortest path\" in an unweighted tree, since "
        "DFS doesn't naturally expose that structure."
    ),
    "tries": (
        "A trie stores a set of strings as a tree of characters, where any two words sharing a "
        "prefix also share the tree nodes for that prefix. Looking up a word or checking "
        "whether any word starts with a given prefix costs only O(L), where L is the length of "
        "the word or prefix being checked -- completely independent of how many words are "
        "stored, unlike scanning a word list. This makes it the right structure whenever a "
        "problem needs repeated prefix queries (autocomplete, dictionary word search) against "
        "a fixed or growing set of strings. The key structural detail is the is_word flag on "
        "each node -- it's what distinguishes \"this prefix exists\" from \"this exact word "
        "was inserted.\""
    ),
    "two-pointers": (
        "Two pointers replaces a nested-loop pairwise check with two indices that walk through "
        "the data together, using the fact that the data is sorted (or has some other "
        "structural property) to know which pointer to move next without ever backtracking. "
        "In the classic \"pointers moving toward each other\" form, comparing the sum at both "
        "ends against a target tells you unambiguously whether to move the left pointer up or "
        "the right pointer down -- you never need to reconsider a pair you've already ruled "
        "out. The fast/slow variant (both pointers moving forward at different speeds) is the "
        "same underlying idea applied to linked lists, for finding midpoints or detecting "
        "cycles. Either way, the win is turning an O(n^2) pairwise scan into a single O(n) "
        "pass."
    ),
    "union-find": (
        "Union-Find (Disjoint Set Union) tracks a collection of elements as they get grouped "
        "together over time, answering two questions efficiently: \"are these two elements in "
        "the same group?\" and \"merge these two groups into one.\" Each element points toward "
        "a representative \"root\" for its group, and two optimizations -- path compression "
        "(flattening the pointer chain every time you look something up) and union by rank "
        "(always attaching the smaller tree under the bigger one) -- keep those operations "
        "nearly O(1) even after many merges. It's the natural fit whenever connectivity is "
        "being built incrementally from a stream of edges or relations, rather than given all "
        "at once as a graph to traverse -- think \"redundant connection\" or counting "
        "provinces as friendships are added one by one."
    ),
}

DIR = Path("content/patterns")
SUMMARY_LINE = re.compile(r'("summary":\s*"(?:[^"\\]|\\.)*",\n)')

for pattern_id, lesson in LESSONS.items():
    path = DIR / f"{pattern_id}.json"
    text = path.read_text()
    lesson_line = f'  "lesson": {json.dumps(lesson)},\n'
    new_text, n = SUMMARY_LINE.subn(lambda m: m.group(1) + lesson_line, text, count=1)
    assert n == 1, f"no summary line matched in {path}"
    path.write_text(new_text)

print(f"inserted lesson field into {len(LESSONS)} files")
```

- [ ] **Step 6: Run the script**

Run: `python scripts/_add_lesson_field.py`
Expected output: `inserted lesson field into 18 files`

- [ ] **Step 7: Run the full test suite to verify everything passes**

Run: `pytest tests/test_pattern_docs.py -v`
Expected: PASS (all tests, including `test_every_registry_pattern_has_a_valid_doc`)

Run: `python -c "import json; from pathlib import Path; [json.loads(p.read_text()) for p in Path('content/patterns').glob('*.json')]"`
Expected: no output, no exception (confirms every file is still valid JSON after the regex edit)

- [ ] **Step 8: Delete the temporary script**

```bash
rm scripts/_add_lesson_field.py
rmdir scripts 2>/dev/null || true
```

- [ ] **Step 9: Commit**

```bash
git add algotrainer/pattern_docs.py tests/test_pattern_docs.py content/patterns/*.json
git commit -m "feat: add lesson field to all pattern docs"
```

---

### Task 2: `lesson` card type in the flashcard system

**Files:**
- Modify: `algotrainer/flashcards.py:12` (`CARD_TYPES` tuple)
- Modify: `tests/test_flashcards.py` (rename/update the card-types test)
- Modify: `tests/test_web_flashcards.py` (rename/update the four-types test)

**Interfaces:**
- Consumes: `content/patterns/*.json` docs' `lesson` field, guaranteed present by Task 1.
- Produces: `CARD_TYPES = ("lesson", "recognition", "complexity", "template", "gotcha")` — later tasks (frontend) dispatch on `card.card_type == "lesson"`.

- [ ] **Step 1: Write the failing test**

In `tests/test_flashcards.py`, current:

```python
def test_card_types_are_the_four_facets():
    assert set(CARD_TYPES) == {"recognition", "complexity", "template", "gotcha"}
```

Replace with:

```python
def test_card_types_are_the_five_facets():
    assert set(CARD_TYPES) == {"lesson", "recognition", "complexity", "template", "gotcha"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_flashcards.py -v -k five_facets`
Expected: FAIL — `CARD_TYPES` currently has only 4 members.

- [ ] **Step 3: Update `CARD_TYPES`**

In `algotrainer/flashcards.py`, current line 12:

```python
CARD_TYPES: tuple[str, ...] = ("recognition", "complexity", "template", "gotcha")
```

Replace with:

```python
CARD_TYPES: tuple[str, ...] = ("lesson", "recognition", "complexity", "template", "gotcha")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_flashcards.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Update the web due-cards test**

In `tests/test_web_flashcards.py`, current:

```python
def test_due_cards_include_all_four_types_for_a_pattern(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    types_seen = {
        card["card_type"] for card in body["cards"] if card["pattern"] == "arrays-hashing"
    }
    assert types_seen == {"recognition", "complexity", "template", "gotcha"}
```

Replace with:

```python
def test_due_cards_include_all_five_types_for_a_pattern(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/flashcards/due").json()
    types_seen = {
        card["card_type"] for card in body["cards"] if card["pattern"] == "arrays-hashing"
    }
    assert types_seen == {"lesson", "recognition", "complexity", "template", "gotcha"}
```

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: PASS — every test, including the two updated above. No `app.py` changes were needed: `/api/flashcards/due` and `/api/flashcards/review` already iterate `CARD_TYPES` generically (confirmed at `algotrainer/web/app.py:258` and `:279`).

- [ ] **Step 7: Commit**

```bash
git add algotrainer/flashcards.py tests/test_flashcards.py tests/test_web_flashcards.py
git commit -m "feat: add lesson as a fifth flashcard type"
```

---

### Task 3: Backend — expose `lesson` via the pattern detail API

**Files:**
- Modify: `algotrainer/web/app.py:236-244` (`pattern_detail` handler)
- Test: `tests/test_web_patterns.py` (append)

**Interfaces:**
- Consumes: `doc["lesson"]` from `load_pattern_doc`, guaranteed present by Task 1.
- Produces: `GET /api/patterns/{id}` response gains a `"lesson"` key — Tasks 4 and 5 (frontend) both read `doc.lesson` / `p.lesson` from this endpoint's JSON.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_patterns.py`:

```python
def test_api_pattern_detail_includes_lesson(tmp_path):
    c = _client(tmp_path)
    body = c.get("/api/patterns/sliding-window").json()
    assert isinstance(body["lesson"], str)
    assert body["lesson"].strip() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_patterns.py -v -k includes_lesson`
Expected: FAIL — `KeyError: 'lesson'`, since the response dict doesn't include that key yet.

- [ ] **Step 3: Add `lesson` to the response**

In `algotrainer/web/app.py`, current (lines 236–244):

```python
        return {
            "id": meta.id, "name": meta.name, "order": meta.order,
            "summary": doc["summary"] if doc else "",
            "recognize_when": doc["recognize_when"] if doc else [],
            "complexity": doc["complexity"] if doc else {},
            "template": doc["template"] if doc else "",
            "gotchas": doc.get("gotchas", []) if doc else [],
            "examples": doc.get("examples", []) if doc else [],
            "confusable": confusable_names,
```

Replace with:

```python
        return {
            "id": meta.id, "name": meta.name, "order": meta.order,
            "summary": doc["summary"] if doc else "",
            "lesson": doc["lesson"] if doc else "",
            "recognize_when": doc["recognize_when"] if doc else [],
            "complexity": doc["complexity"] if doc else {},
            "template": doc["template"] if doc else "",
            "gotchas": doc.get("gotchas", []) if doc else [],
            "examples": doc.get("examples", []) if doc else [],
            "confusable": confusable_names,
```

(This is a partial excerpt — the `return` statement has more keys after `"confusable"`, e.g. `seed_examples`; leave everything after `"confusable": confusable_names,` untouched.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web_patterns.py -v`
Expected: PASS (all tests in the file)

Run the full suite to confirm nothing else broke:

Run: `pytest -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add algotrainer/web/app.py tests/test_web_patterns.py
git commit -m "feat: expose lesson field on the pattern detail API"
```

---

### Task 4: Frontend — lesson flip card in the study session

**Files:**
- Modify: `algotrainer/web/static/flashcards.js`

No automated test for this task (no JS test runner in this project — matches the convention already used for `flashcards.js`/`patterns_detail.js`). Verified manually in Task 6.

**Interfaces:**
- Consumes: `card.card_type === "lesson"` (from Task 2), `doc.lesson` (the pattern doc fetched via the existing `fetchDoc(card.pattern)` helper already in this file, which calls `GET /api/patterns/{id}` — only exposes `lesson` once Task 3 lands).

- [ ] **Step 1: Add `revealLesson`**

In `algotrainer/web/static/flashcards.js`, immediately after the existing `revealComplexity` function (currently lines 85–95) and before `revealGotchas`, add:

```javascript
function revealLesson(doc, body) {
  const p = document.createElement("p");
  p.textContent = doc.lesson;
  body.appendChild(p);
}
```

- [ ] **Step 2: Wire it into `renderCard`'s dispatch**

Current `renderCard` (around line 183):

```javascript
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
```

Replace with:

```javascript
function renderCard(card) {
  const body = clearBody();
  document.getElementById("session-progress").textContent =
    `${queue.length + 1} card${queue.length === 0 ? "" : "s"} remaining`;
  if (card.card_type === "recognition") {
    renderRecognition(card, body);
  } else if (card.card_type === "lesson") {
    renderFlipCard(card, body, revealLesson);
  } else if (card.card_type === "complexity") {
    renderFlipCard(card, body, revealComplexity);
  } else if (card.card_type === "gotcha") {
    renderFlipCard(card, body, revealGotchas);
  } else if (card.card_type === "template") {
    renderTemplate(card, body);
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add algotrainer/web/static/flashcards.js
git commit -m "feat: render lesson flashcards in the study session"
```

---

### Task 5: Pattern detail page — show the lesson as reference prose

**Files:**
- Modify: `algotrainer/web/static/patterns_detail.js`

No automated test for this task (same convention as Task 4). Verified manually in Task 6.

**Interfaces:**
- Consumes: `p.lesson` on the object returned by `GET /api/patterns/{id}`, exposed by Task 3.

- [ ] **Step 1: Render the lesson paragraph**

In `algotrainer/web/static/patterns_detail.js`, current (lines 38–49):

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
```

Replace with:

```javascript
  const summary = document.createElement("p");
  summary.className = "lede";
  summary.textContent = p.summary || "No reference doc has been written for this pattern yet.";
  body.appendChild(summary);

  if (p.lesson) {
    const lesson = document.createElement("p");
    lesson.textContent = p.lesson;
    body.appendChild(lesson);
  }

  const studyLink = document.createElement("p");
  const studyA = document.createElement("a");
  studyA.href = `/flashcards/${p.id}`;
  studyA.textContent = "Study this pattern with flashcards →";
  studyLink.appendChild(studyA);
  body.appendChild(studyLink);
```

- [ ] **Step 2: Commit**

```bash
git add algotrainer/web/static/patterns_detail.js
git commit -m "feat: show the pattern lesson on the pattern detail page"
```

---

### Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full automated test suite**

Run: `pytest -v`
Expected: PASS — every test in `tests/`.

- [ ] **Step 2: Start the dev server**

Run: `algotrainer` (or `python -m algotrainer`)
Expected: server starts, logs listening on `http://127.0.0.1:8000`.

- [ ] **Step 3: Manually exercise the feature in a browser**

Visit `http://127.0.0.1:8000/flashcards`:
- Confirm the due count shows `90 due` (18 patterns × 5 card types) on a fresh db.
- Click **Study**. Step through at least one **lesson** card: confirm the front shows the pattern name, "Show answer" reveals the lesson paragraph, and rating buttons advance to the next card.
- Confirm the other four card types (recognition/complexity/template/gotcha) still work exactly as before.

Visit `http://127.0.0.1:8000/patterns/dp-1d` (or any pattern):
- Confirm a lesson paragraph now renders between the summary and the "Study this pattern with flashcards →" link.

- [ ] **Step 4: Stop the dev server**

Interrupt the running `algotrainer` process (Ctrl-C in that terminal).

No commit for this task — it's verification only.

---

### Task 7: Update the standalone Anki export (optional, not part of the repo)

**Files:**
- Modify (outside the repo, in the session scratchpad): `build_anki_deck.py`

This script pushes pattern content into a local Anki collection via AnkiConnect; it mirrors the four flashcard facets today and should mirror all five once `lesson` exists. It is not committed to `personal-algo-trainer` — this task only applies if the user still has that script and an Anki instance running.

- [ ] **Step 1: Add a fifth note-emission block**

After the existing `gotcha_html` note-append block (and before the `template` block, to match `CARD_TYPES` order) in `build_anki_deck.py`'s `main()` loop, add:

```python
        notes.append({
            "deckName": deck,
            "modelName": "Basic",
            "fields": {
                "Front": f"{html_escape(name)} &mdash; what is this pattern?",
                "Back": f"<p>{html_escape(doc['lesson'])}</p>",
            },
            "tags": ["algotrainer", pattern_id, "lesson"],
            "options": {"allowDuplicate": False},
        })
```

- [ ] **Step 2: Re-run the script**

Run: `python build_anki_deck.py` (with Anki open and AnkiConnect listening on `localhost:8765`)
Expected output includes `notes added: 18` for the new lesson notes (the previously-pushed recognition/complexity/gotcha/template notes are skipped as duplicates, per `allowDuplicate: False`).

No commit for this task — the script lives outside the repository.
