# AlgoTrainer Grading Rubric & Error Taxonomy

## Composite grade (map to exactly one FSRS rating)

Consider three signals: correctness (from the judge result in the session file),
complexity optimality, and hints used. (The session file carries no timing data,
so speed is never part of the grade.)

- **again** — did not identify the pattern, OR the judge shows failing tests and
  the approach is fundamentally wrong, OR the learner needed the full worked step
  and still could not finish.
- **hard** — solved (tests pass) but only WITH ≥1 hint, or the solution is
  correct-but-suboptimal in complexity, or it was slow / buggy on the way.
- **good** — solved unaided (0 hints), correct, optimal or near-optimal.
- **easy** — solved unaided, optimal complexity, clean code, and the recall gate
  showed confident, principled understanding.

Hard rule: if `hints_used >= 1` and tests pass, the grade is at most **hard**.
If tests fail, the grade is **again** (never higher).

## approach_used
A short phrase naming the pattern/approach the learner ACTUALLY used (e.g.
"hash map single pass", "brute-force nested loop", "two pointers"). Compare it to
the problem's canonical pattern to decide `pattern_misidentification`.

## error_code (null, or exactly one taxonomy member)
- `null` — clean, optimal, unaided solve.
- `pattern_misidentification` — reached for the wrong schema / recall gate named
  the wrong pattern.
- `approach_correct_execution_bug` — right idea, but off-by-one / base case /
  boundary / wrong return shape caused a failure or near-miss.
- `complexity_suboptimal` — works but not the optimal complexity.
- `incomplete_knowledge` — missing a data structure or API they needed.
- `got_stuck_no_idea` — no viable approach retrieved.
- `careless_time_pressure` — avoidable slip on an otherwise-known approach.

## self_explanation_score (1–5, or null if none given)
Score the learner's recall-gate `approach` + any explanation on whether it cites
the underlying PRINCIPLE/invariant (5) vs. only surface features (1). Null if the
recall fields are empty.

## feedback
2–5 sentences, Socratic and encouraging: name what went well, then the single
highest-leverage thing to improve. (Mid-solve hints are served by the app's own
pre-authored hint ladder — grading is this skill's only request type.)
