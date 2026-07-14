# Bank expansion — portable state (boxed up 2026-07-14)

Working state for the plan in `docs/plans/2026-07-07-bank-expansion.md`, packaged
so work can resume on a different machine. Everything needed is in THIS directory
and git; nothing depends on the original machine's scratchpad or workflow cache.

## Where things stand

- **106 candidate problems** in `pending/` — all pass the mechanical gate
  (`gate.py`, path-independent: run as `.venv/bin/python expansion-staging/gate.py
  expansion-staging/pending/<id>.json`). One syllabus shape (`subarray-sum-equals-k`)
  was renamed to `river-gauge-subarray-sum-k` on id collision; 107 planned, 1 author
  produced under the renamed id → 106 files + existing 73 seeds = 179 total when landed
  (the linked-list syllabus produced one fewer shape; target is >=10/pattern, check
  counts at assembly).
- **84 problems fully accepted**: gate-passed AND adversarially verified
  (2 wrong implementations died, 1 correct alternative survived). Details per
  problem in `state.json` → `accepted_verified`.
- **23 problems authored but NOT verified** — their verifier (or repair) agents hit
  a session limit. Listed in `state.json` → `needs_reverify`, each with its shape
  spec (`canonical_wrong` etc.) needed for the verifier prompt. Two of them
  (`maximize-sum-after-k-negations`, `employee-free-time`) failed one verification
  round and died mid-repair — expect them to need a repair round.
- **Pattern reviews done**: backtracking, bit-manipulation (their file edits are
  already applied in `pending/`). **16 reviews missing** — see `state.json`.
- **0 problems genuinely dropped** so far.
- Model note: authors were a mix of Fable 5 (first 31) and Opus 4.8 (rest); a
  head-to-head on `coin-combination-count` showed no quality difference.
  Remaining agents should run with model `opus` per owner decision.

## Files here

- `pending/` — the 106 candidate problem JSONs (final source of truth; includes
  edits from the two completed pattern reviews).
- `gate.py` — mechanical gate (schema, self-test, id uniqueness vs bank+staging,
  JSON-native outputs, 6–8 tests, exactly 3 hints, starter/signature match).
- `state.json` — machine-readable run state (accepted/needs_reverify/reviews).
- `finish-expansion.js` — continuation Workflow script: verifies the 23 (with up
  to 2 repair rounds each), then runs the 16 missing pattern reviews.
- `finish-args.json` — args for that script; replace `__REPO_PATH__` with the
  repo's absolute path on the new machine.
- `original-workflow.js` — the full original pipeline, for reference only.

## Pickup on the new machine

1. Clone/pull branch `bank-expansion`; `python -m venv .venv && .venv/bin/pip
   install -e ".[dev]"` (editable install is required by the app's path logic).
2. Sanity check: run `gate.py` over a few files in `pending/`.
3. In Claude Code (in the repo), say: *"Finish the bank expansion per
   expansion-staging/STATE.md — run expansion-staging/finish-expansion.js with the
   Workflow tool, args from finish-args.json with __REPO_PATH__ filled in, then do
   final assembly."*
4. Final assembly after the workflow: drop any `flagged_drop` ids, move accepted
   files from `expansion-staging/pending/` into `content/problems/`, run the gate
   over the ENTIRE bank, run `pytest`, write a coverage report
   (problems/difficulty per pattern, tests per problem, wrong-impls-killed,
   drops + reasons) to `docs/reviews/`, delete `expansion-staging/`, commit.
