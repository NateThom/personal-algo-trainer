# Bank expansion coverage report (2026-07-14)

Completes the plan in `docs/plans/2026-07-07-bank-expansion.md`. Bank grows from
73 to **178 problems** (105 net new; 106 authored, 1 dropped as a duplicate).

## Per-pattern coverage

| Pattern | Total | Easy | Medium | Hard | Tests (min/avg/max) |
|---|---|---|---|---|---|
| arrays-hashing | 10 | 4 | 5 | 1 | 3/6.3/8 |
| backtracking | 10 | 2 | 6 | 2 | 4/6.3/8 |
| binary-search | 10 | 3 | 5 | 2 | 5/6.7/8 |
| bit-manipulation | 10 | 3 | 5 | 2 | 5/7.0/8 |
| dp-1d | 11 | 3 | 7 | 1 | 5/6.7/8 |
| dp-2d | **9** | 3 | 4 | 2 | 5/6.6/8 |
| graphs | 10 | 3 | 5 | 2 | 4/7.1/8 |
| heaps | **9** | 3 | 4 | 2 | 4/6.7/8 |
| intervals | 10 | 3 | 5 | 2 | 6/7.2/8 |
| linked-list | 10 | 3 | 5 | 2 | 5/7.0/8 |
| prefix-sum | 10 | 3 | 5 | 2 | 4/7.0/8 |
| sliding-window | 10 | 3 | 5 | 2 | 4/6.7/8 |
| stack | 10 | 3 | 5 | 2 | 4/6.8/8 |
| topological-sort | 10 | 3 | 5 | 2 | 5/7.2/8 |
| trees | 10 | 3 | 5 | 2 | 6/7.2/8 |
| tries | **9** | 3 | 4 | 2 | 4/6.6/8 |
| two-pointers | 10 | 3 | 5 | 2 | 3/6.4/8 |
| union-find | 10 | 3 | 5 | 2 | 3/6.4/8 |
| **Total** | **178** | | | | |

Three patterns (**dp-2d, heaps, tries**) land at 9, one short of the >=10
target set in the original plan — each lost a candidate to a legitimate drop
during review (see below) and no replacement was authored. Flagging as a known
gap rather than closing it with a fresh authoring round, since that's outside
this pass's scope.

## Verification (adversarial: 2 wrong impls must die, 1 correct alternative must survive)

- **84 problems** verified in the original authoring session (see prior
  `docs/plans/2026-07-07-bank-expansion.md` run); per-problem rationale not
  retained past that session.
- **23 problems** re-verified in this session after their original verifier/repair
  agent hit a session limit. All 23 passed: 21 on the first attempt, 2 needed one
  repair round (`shortest-unique-prefixes` — a test's expected value violated the
  problem's own no-prefix-collision precondition; `network-connectivity-queries`
  — the canonical-wrong test suite was too weak to kill `parent[a]==parent[b]`
  on a chain topology, fixed by adding a discriminating test).
- **0 problems dropped** for failing verification.

## Pattern reviews (dedupe, ambiguity, difficulty, hint progression, title leaks)

All 18 patterns reviewed: `backtracking` and `bit-manipulation` in the original
session; the remaining 16 in this session. Reviews collectively:

- **Edited ~25 files** — mostly stripping statement/hint text that leaked the
  intended technique (e.g. a hint naming "binary search" outright, or a
  statement spelling out "build a trie..."), a few difficulty relabels, and one
  title rewrite that named the exact algorithm.
- **Dropped 1 candidate**: `maximum-xor-pair` (tries) — verified to be an exact
  duplicate of the already-accepted `max-pairwise-xor` (bit-manipulation): same
  LC 421 computation, same input/output shape, only the taught technique
  (binary trie vs. greedy bitmask) differs. Kept the bit-manipulation copy.
- **Reconciled two review-run disagreements** by direct inspection rather than
  trusting either agent verdict outright (the pattern-review stage for
  `dp-2d`/`tries` partially re-ran after a mid-session usage-limit interruption,
  producing two independent verdicts on the same candidates):
  - `triangle-minimum-total` was flagged as a duplicate of `minimum-path-sum` by
    one review pass, kept by the other. Read both files: `minimum-path-sum` is
    a true 2-D table over a rectangle with distinct first-row/first-column
    boundary handling; `triangle-minimum-total`'s own reference solution never
    builds a 2-D table at all (pure bottom-up 1-D roll, uniform recurrence, no
    boundary special-casing). Different lesson despite a similar-looking
    recurrence — **kept**.
  - `coin-combination-count` was flagged as "wrong pattern, not dp-2d" by both
    review passes — correct, since the file's own `"pattern"` field says
    `dp-1d` and it was only in the dp-2d review batch due to a bookkeeping slip
    in the original run's candidate grouping. Compared against the existing
    `coin-change` seed: different problem (count combinations vs. minimize coin
    count), different recurrence, different core lesson (loop-order-matters for
    combinations vs. permutations) — **kept**, correctly filed as dp-1d.

## Validation

- `gate.py` (schema, self-test, id uniqueness, JSON-native outputs, 6-8 tests,
  exactly 3 hints, starter/signature match): all 106 authored files passed
  before assembly; the 105 moved files still on disk all pass.
- Whole-bank check (`expansion-staging/bank_check.py`, written for this
  assembly since `gate.py` assumes staged candidates and self-collides once
  files live in `content/problems/`): **BANK OK (178 problems)** — schema
  valid, ids globally unique, filenames match ids, JSON-native reference output
  on every test, for the entire bank including the pre-existing 73 seeds.
- `pytest`: **128 passed**, 0 failed (app-logic suite; doesn't scale with
  problem count since per-problem correctness is gate/verification's job, not
  pytest's).

## Drops (bank-wide)

| id | pattern | reason |
|---|---|---|
| `maximum-xor-pair` | tries | exact duplicate of `max-pairwise-xor` (bit-manipulation) |

No problems were dropped for failing verification.
