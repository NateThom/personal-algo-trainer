# Plan: expand the seed bank to ≥10 problems per pattern

Date: 2026-07-07. Status: proposed (prerequisite review fixes applied same day).

## Goal

Grow `content/problems/` from 73 seeds (4–5 per pattern) to **≥10 per pattern**
(≥180 total, ~110 new), with every new problem meeting a higher quality bar than
the original seeds: edge-case-complete tests and at least one test that kills the
canonical wrong implementation for that problem shape. Secondary goal: a richer,
higher-quality seed bank improves the few-shot grounding the tutor skill uses
when generating novel runtime variants.

## Principles (from the 2026-07-07 review + aggregate research)

1. **Author, don't import.** Open aggregates (LeetCodeDataset, TACO,
   code_contests) redistribute copyrighted statements and use foreign formats.
   We use canonical problem lists (NeetCode 150/250 categories = our taxonomy)
   only as a *syllabus* of problem shapes; agents write original statements,
   solutions, tests, and hints in our schema. This keeps the bank cleanly ours.
2. **Discriminative tests are a hard gate, not an aspiration.** 19/73 of the
   original seeds were passed by the canonical wrong implementation. Every new
   problem must ship with a verified kill test (see gates below).
3. **Exact-match-safe by construction.** The judge compares with `==`: unique
   correct answer required; ordering and tie-breaks pinned in the statement;
   JSON-native outputs only (no tuples/sets).

## Target shape per pattern

- ≥10 problems: roughly 3 easy / 5 medium / 2 hard (counting existing seeds).
- Each problem: statement (constraints explicit: emptiness, ranges, ordering,
  ties), starter code, reference solution canonical for the pattern, **6–8
  tests** (normal + boundary + empty/degenerate + no-solution branch + kill
  test), exactly 3 graduated hints (nudge → invariant → near-solution).
- Shapes chosen to complement existing seeds (no re-skins of an existing seed's
  underlying instance) and to cover the pattern's major sub-techniques (e.g.
  binary-search: on index, on answer space, on boundary; dp-2d: grid paths,
  two-sequence alignment, knapsack table).

## Pipeline (one orchestrated run, all 18 patterns in parallel)

Per pattern, a pipelined chain:

1. **Syllabus agent** — reads the pattern doc + existing seeds for that pattern,
   returns a want-list of ~6 problem shapes with difficulty targets and the
   canonical wrong implementation each shape must defeat.
2. **Author agent** (one per problem) — writes the candidate JSON per
   `references/variant.md` (which now encodes the test-quality bar). Must
   execute its own reference solution to produce every `expected` value.
3. **Mechanical gate** (script, not agent) — `validate_problem_dict` + self-test
   execution + id uniqueness + JSON-native outputs + exactly 3 hints +
   starter/function-name consistency.
4. **Adversarial verifier agent** — independently writes 2 canonical wrong
   implementations AND 1 correct alternative implementation; requires every
   wrong impl to fail ≥1 test and the correct alternative to pass all (catches
   both weak tests and multiple-valid-answer hazards). Failures bounce back to
   the author with the diverging input attached; max 2 repair rounds, then drop.
5. **Pattern reviewer agent** — dedupe vs existing bank, statement-ambiguity
   check, difficulty sanity, hint-progression check across the pattern's new
   set.

Bank-level finish: merge all patterns' accepted problems, re-run the full
mechanical validation over the entire bank, run `pytest`, and produce a coverage
report (problems/difficulty per pattern, tests per problem, wrong-impls-killed
per problem, shapes dropped and why — no silent truncation).

## Landing

- New problems land in `content/problems/` as git-tracked, reviewed seeds
  (NOT via `add_variant.py` / `content/generated/`, which stays the runtime
  variant path). Delivered as a single reviewable diff on a branch.
- No code changes required: the app globs `content/problems/` and the mastery
  gate's breadth requirement only benefits from more distinct problems.
- Follow-ups in the same diff: none. Deliberately out of scope: difficulty
  relabels of existing seeds, the `matrix-block-sum`/`alien-dictionary-order`
  id-vs-content mismatches (ids are referenced by DB review history; renaming
  needs a migration).

## Open decisions

1. Hard problems: the bank has only 2 today. Target 2/pattern raises the solve
   ceiling — confirm that's wanted for a daily-practice tool.
2. Whether patterns with natural sub-splits (dp-1d vs dp-2d already split)
   should bias shapes toward interview frequency or uniform sub-technique
   coverage. Default: interview frequency.
3. Cost/scale: ~110 problems × (author + verify + review) ≈ 300–400 agent
   invocations. Fine as an overnight/background run; can halve by batching
   authors per-pattern instead of per-problem.
