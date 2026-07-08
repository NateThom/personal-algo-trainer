# Independent content review — 2026-07-07

Scope: all 73 problem files in `content/problems/`, all 18 pattern docs in
`content/patterns/`, `docs/USING_THE_TUTOR.md`, the `algotrainer-tutor` skill
(SKILL.md + references), and the in-app teaching pages (guide.html,
methodology.html). Method: every reference solution was executed against its own
tests; every suggested test below had its `expected` value verified by running
the reference solution; every "a wrong implementation passes" claim was
demonstrated by executing that wrong implementation against the current suite.

## Headline

- **Mechanically sound**: all 73 reference solutions pass their own tests; all 18
  pattern templates execute correctly; complexity claims in pattern docs are all
  accurate; every problem maps to an existing pattern with ≥4 problems per
  pattern; every problem has exactly 3 hints.
- **One test rejects correct solutions** (task-scheduling-order test 4).
- **18 problems (25% of the bank) have a HIGH-severity edge-case hole**: a
  canonical wrong implementation for that exact problem passes the entire
  current test suite. Each has a one-test verified fix below.
- **Docs**: no README / no install path anywhere (the documented flow starts at
  "activate .venv"); methodology.html §4 contradicts both guide.html and the
  code on review-first serving.

---

## 1. CRITICAL — a correct solution fails

### task-scheduling-order — test 4 contradicts the uniqueness guarantee
Statement guarantees "at every step exactly one task is ready," but test 4
(`[5, [[0,1],[1,2],[1,3],[3,4],[2,4]]]`) has **two** valid topological orders
(`[0,1,2,3,4]` and `[0,1,3,2,4]` — confirmed by brute-force enumeration). A
correct DFS-based topo sort and a correct Kahn-with-stack both return
`[0,1,3,2,4]` and fail the exact-match judge.
**Fix (verified)**: add edge `[2,3]` → `[5, [[0,1],[1,2],[1,3],[3,4],[2,4],[2,3]]]`
has the unique order `[0,1,2,3,4]`.
Also [LOW]: `n=0` returns `[]`, colliding with the cycle sentinel — state `n >= 1`.

## 2. HIGH — canonical wrong implementations that pass the current tests

Each entry: the wrong implementation that passes today, and the single verified
test that catches it.

| Problem | Wrong impl that passes | Verified catch test |
|---|---|---|
| alien-dictionary-order | FIFO Kahn's (no min-heap) — the lexicographic tie-break is never exercised | `{"args": [3, [[1, 0]]], "expected": [1, 0, 2]}` |
| daily-temperatures | pop on `<=` (treats equal temp as warmer) — no test has equal temps | `{"args": [[70, 70]], "expected": [0, 0]}` |
| grid-word-search | never un-marks visited on backtrack (THE classic bug) | `{"args": [[["A","B","C","E"],["S","F","E","S"],["A","D","E","E"]], "ABCESEEEFS"], "expected": true}` |
| is-symmetric-tree | mirror check that ignores node values (all false cases are structurally asymmetric) | `{"args": [[1, 2, 3]], "expected": false}` (also `[[1,2,2,3,4,4,5]] → false`) |
| is-valid-tree-network | `len(edges) == n - 1` alone | `{"args": [4, [[0, 1], [0, 2], [1, 2]]], "expected": false}` |
| k-closest-points-to-origin | sort by distance only — the stated `(x, y)` tie-break is never tested | `{"args": [[[1, 0], [0, 1]], 2], "expected": [[0, 1], [1, 0]]}`; also boundary tie `{"args": [[[1,0],[0,1],[-1,0],[2,0]], 2], "expected": [[-1,0],[0,1]]}` |
| level-order-sums | heap-index leveling (`floor(log2(i+1))`) over the raw array | `{"args": [[1, null, 2, 3, 4, 5]], "expected": [1, 2, 7, 5]}` |
| longest-substring-without-repeating | `left = last_seen[ch] + 1` without the `>= left` guard (the "abba" bug) | `{"args": ["abba"], "expected": 2}` |
| max-depth-of-binary-tree | heap-index (2i+1/2i+2) decoding instead of the stated compact level-order encoding | `{"args": [[1, null, 2, null, 3]], "expected": 3}` |
| merge-intervals | `last[1] = end` instead of `max(last[1], end)` — no fully-nested interval in any test | `{"args": [[[1, 10], [2, 3], [4, 5]]], "expected": [[1, 10]]}` |
| merge-user-account-groups | single greedy left-to-right pass without union-find — transitivity never forced | `{"args": [[["X","a@m.com","b@m.com"],["X","c@m.com","d@m.com"],["X","b@m.com","c@m.com"]]], "expected": [["X","a@m.com","b@m.com","c@m.com","d@m.com"]]}` |
| min-stack | aux-min pushed only on strict `<` (duplicate-minimum bug) | `{"args": [[["push",2],["push",2],["pop"],["getMin"],["push",1],["push",1],["pop"],["getMin"]]], "expected": [2, 1]}` |
| replace-words-with-roots | first `startswith` match in given order — every test's roots list is pre-sorted shortest-first | `{"args": [["abc", "ab"], "abcdef"], "expected": "ab"}` |
| rotting-oranges | BFS from only the first rotten cell — no test has multiple rotten sources | `{"args": [[[2,1,1],[1,1,1],[1,1,2]]], "expected": 2}` |
| shortest-path-unweighted-graph | DFS first-path-found — in every test all routes are equal length | `{"args": [4, [[0,1],[1,2],[2,3],[0,3]], 0, 3], "expected": 1}` |
| valid-anagram | `set(s) == set(t)` | `{"args": ["aab", "abb"], "expected": false}` (also add `["a","ab"] → false`) |
| valid-parentheses | omits final `return not stack` — no test ends with unmatched openers | `{"args": ["("], "expected": false}` (also `["" ] → true`, `[")"] → false`) |
| count-islands *(MEDIUM borderline)* | down/right-neighbors-only flood fill | `{"args": [[[1, 1], [0, 1], [1, 1]]], "expected": 1}` (U-shaped island) |

## 3. MEDIUM — problem-bank findings

- **combination-sum-sorted**: all test inputs pre-sorted; a no-initial-sort impl
  passes. Catch: `{"args": [[7, 3, 2], 7], "expected": [[2, 2, 3], [7]]}`.
- **insert-interval**: touching-on-the-left merge untested. Catch:
  `{"args": [[[1, 5]], [5, 7]], "expected": [[1, 7]]}`.
- **max-overlapping-intervals**: inclusive-endpoint touching case untested.
  Catch: `{"args": [[[1, 3], [3, 5]]], "expected": 2}`.
- **minimum-semesters-to-graduate**: only whole-graph cycles tested; partial-cycle
  catch: `{"args": [4, [[1, 2], [2, 3], [3, 2]]], "expected": -1}`.
- **longest-common-prefix-trie**: no word-is-strict-prefix-of-another case.
  Catch: `{"args": [["flow", "flower"]], "expected": "flow"}`.
- **successor-array-cycle-detection**: no unreachable-cycle case. Catch:
  `{"args": [[-1, 2, 1], 0], "expected": false}`; also self-loop `[[1,1],0] → true`.
- **valid-palindrome**: `isalpha()` (digit-dropping) impl passes. Catch:
  `{"args": ["0P"], "expected": false}`; also `[""] → true`.
- **find-two-non-repeating-numbers**: output ordering never forced
  (`{"args": [[3, 1]], "expected": [1, 3]}`); negative-mix catch
  `{"args": [[-2, 3, -2, -7]], "expected": [-7, 3]}`.
- **middle-of-sequence-fast-slow**: reference **crashes (IndexError) on `[]`**
  and the statement doesn't guarantee non-empty — state `len >= 1`.
- **min-stack**: empty-stack `top`/`getMin` behavior unspecified (reference
  crashes); statement should guarantee operation validity.
- **two-sum**: index order unspecified but judge is exact-match — a correct
  `[1, 0]` answer fails. State "indices in ascending order."
- **first-bad-version**: `bad == n` boundary untested (`{"args": [5, 5], "expected": 5}`).
- **first-unique-character-index**: empty string untested (`[""] → -1`) and
  non-emptiness unstated.
- **kth-largest-element**: only 3 tests; add k=n (`[[3,2,1,5,6,4], 6] → 1`),
  all-equal (`[[7,7,7], 2] → 7`), negatives (`[[-1,-5,-3], 2] → -3`).
- **last-stone-weight**: statement allows empty but it's untested (`[[]] → 0`).
- **search-insert-position**: empty array (`[[], 5] → 0`) and insert-at-front
  (`[[1,3,5,6], 0] → 0`) untested.
- **rotting-oranges**: fresh-but-no-rotten case untested (`[[[1]]] → -1`).

LOW items (statement-silence on empty inputs, missing boundary tests, difficulty
quibbles, id/content mismatches for `matrix-block-sum` and
`alien-dictionary-order`, vacuous tie-break clause in replace-words-with-roots,
`next` shadowing a builtin in successor-array starter code, edit-distance labeled
hard) are in the per-quarter sections of the reviewer transcripts; the ones with
verified tests: binary-search empty/first/last, find-pivot-index last-index pivot
(`[[1,-1,2]] → 2`), course-schedule self-loop (`[1,[[0,0]]] → false`),
alien-dictionary self-loop (`[2,[[0,0]]] → []`), zero-one-knapsack
item-heavier-than-capacity (`[[10],[100],5] → 0`), unique-permutations empty
(`[[]] → [[]]`) and all-dup (`[[1,1]] → [[1,1]]`), min-days days=1
(`[[1,2,3,4],1] → 10`), prefix-count overshoot (`[["dog"],["dogs"]] → [0]`),
subarray-sum negative k (`[[1,-2,3],-2] → 1`), max-sum-subarray k=len
(`[[4,-1,2,7],4] → 12`), daily-temperatures all-decreasing (`[[90,80,70]] → [0,0,0]`),
first-two-non-repeating both-negative (`[[-3,-5]] → [-5,-3]`).

## 4. Pattern teaching docs

All 18 templates execute correctly; complexity claims verified. Findings:

- **[MEDIUM] graphs**: `recognize_when` includes "need topological order or to
  detect cycles in a directed graph" and "'course schedule' style problems", and
  examples list "Course Schedule" — but this trainer has a separate
  `topological-sort` pattern that owns course-schedule-feasibility. The cues
  route learners to the wrong pattern within the trainer's own taxonomy.
- **[MEDIUM] sliding-window**: lists Best Time to Buy and Sell Stock as an
  example and the bank assigns that seed to sliding-window, but the reference is
  a running-min scan with no window, left pointer, or shrink step — the taught
  template doesn't map onto its own seed problem.
- **[MEDIUM] two-pointers**: template does `arr.sort()` then returns indices —
  indices are meaningless w.r.t. the caller's array (and the input is mutated);
  models the classic sort-loses-indices trap without flagging it. Return values,
  or state a sorted-input precondition.
- [LOW] backtracking: `results` used as an implicit global (state, not a stub
  helper). [LOW] binary-search: "matrix sorted row- and column-wise" cue
  actually describes the staircase-search problem. [LOW] intervals: template
  sorts in place while gotcha 3 warns against input mutation. [LOW] prefix-sum:
  missing the defaultdict mutation-on-read gotcha its own template models; the
  Product-of-Array-Except-Self example is a weak fit. [LOW] sliding-window:
  `O(k)` space with k undefined; missing the negatives-break-sum-windows gotcha
  (the exact prefix-sum discriminator). [LOW] topological-sort: "all valid
  orderings" cue overpromises (that's backtracking). [LOW] "Top K Frequent
  Elements" claimed as an example by both arrays-hashing and heaps.
- Cross-refs clean: 0 orphaned pattern assignments; 48/67 example names have no
  exact bank counterpart but the app serves `examples` (display-only) separately
  from `seed_examples`, so nothing is broken.

## 5. Documentation & tutor skill

- **[HIGH] No install path anywhere.** `docs/USING_THE_TUTOR.md:8` starts at
  "Activate `.venv`" but nothing documents creating it (`python -m venv .venv &&
  pip install -e ".[dev]"`). Editable install is functionally **required**:
  `__main__.py` derives DB/sessions/generated paths from `Path(__file__)`, so a
  plain `pip install .` would silently relocate them into site-packages.
- **[HIGH] No top-level README** — nothing at the repo root points to
  USING_THE_TUTOR.md or the in-app guide (which is only visible after the app
  runs).
- **[MEDIUM] methodology.html §4 is wrong and contradicts guide.html**: it says
  "when a pattern comes due, the tool prefers a problem you haven't seen," but
  `/api/next` deliberately serves due reviews of already-seen problems before
  novel ones (web/app.py:141-146). guide.html states the real behavior.
- **[MEDIUM] rubric.md weighs signals that don't exist**: "time-to-solve"
  ("slow", "fast", "first try") — the session file carries no timing or
  attempt-count data. Drop the signal or add `seen_count`/duration to the
  session file (the app already computes seen_count for the UI).
- **[MEDIUM] SKILL.md's session field list omits top-level `attempt_id`** while
  step 4 says attempt_id "comes from the session file."
- **[MEDIUM] Skill scripts assume the venv python**: SKILL.md says bare
  `python scripts/write_verdict.py` — ImportError outside the venv; say
  `.venv/bin/python` or "with the venv active."
- [LOW] rubric.md's "when asked for a HINT" paragraph is a dead branch
  (`request` is `Literal["grade"]`); stale text that could tempt ad-hoc hinting.
- [LOW] variant.md implies difficulty enum and 3–4 hints are validated —
  they aren't (`Problem.from_dict` accepts any difficulty; hints default `[]`).
- [LOW] guide.html calls the judge "sandboxed" — it's a subprocess with a 5s
  timeout, no fs/network isolation. [LOW] methodology §3 says FSRS schedules
  "each pattern"; scheduling is per-problem (pattern cards feed mastery only).
- [LOW] "The app opens at" — it serves; nothing opens a browser. No `--port`
  override exists if 8000 is taken.
- Judge semantics worth documenting for authors: exact `==` comparison (tuple ≠
  list; a returned set → non-serializable → cryptic "Bad runner output"), and
  `judge_passed` in the session is client-supplied, not re-verified server-side.
- Fresh-machine gap list: install/venv, README, DB/sessions auto-creation note,
  venv-python for skill scripts, how to run tests, port override.

## 6. Bank-shape stats

73 problems; tests-per-problem: 3×14, 4×18, 5×32, 6×9; no duplicate test args in
any problem; difficulty mix 34 easy / 37 medium / 2 hard; per-pattern counts:
bit-manipulation 5, all others exactly 4.

## Recommended order of work

1. Fix task-scheduling-order test 4 (rejects correct solutions).
2. Add the 18 verified HIGH catch tests (§2 table) — each is one test.
3. Add the MEDIUM catch tests and the statement clarifications (two-sum ordering,
   min-stack/middle-of-sequence non-empty guarantees).
4. Resolve the three pattern-doc MEDIUMs (graphs/topo cue collision,
   sliding-window seed, two-pointers template).
5. Write a README with install steps (mandating `pip install -e`); fix
   methodology.html §4; align rubric.md with the actual session schema.
