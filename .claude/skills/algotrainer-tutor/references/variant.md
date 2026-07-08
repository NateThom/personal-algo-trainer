# Variant authoring spec

Produce a NOVEL problem for a given pattern — same underlying schema, different
surface (different story, inputs, sizes) — never a copy of a seed problem.

The candidate is a JSON object with exactly these keys:
- `id`: kebab-case, unique, suffixed to signal generation, e.g. `arrays-hashing-gen-<short>`
- `pattern`: the target pattern id (e.g. `arrays-hashing`)
- `title`, `difficulty` (`easy|medium|hard`), `statement`
- `function_name`: snake_case
- `starter_code`: a stub `def <function_name>(...):` with `pass`
- `reference_solution`: a CORRECT solution defining `function_name`
- `tests`: a list of `{"args": [...], "expected": ...}` — args are the positional
  arguments; `expected` must be JSON-native (list/number/bool/string, not tuple/set)
- `hints`: 3–4 graduated hints (category → invariant → pseudocode → worked step)

Correctness bar: your `reference_solution`, run on each test's `args`, MUST return
that test's `expected`. `add_variant.py` re-checks this and REJECTS the candidate
if any test fails — so verify mentally before submitting, and if rejected, read
the reason, fix, and resubmit. (Only shape and the self-test are machine-checked;
difficulty and hint quality are on you.)

Test-quality bar (as important as correctness):
- Cover normal, boundary, and empty/edge cases: empty input, single element,
  all-equal values, ties/duplicates, the no-solution branch, negatives/zero where
  the domain allows them.
- Include at least one test that KILLS the canonical wrong implementation for
  this problem shape (the off-by-one, the missing shrink/backtrack step, the
  greedy shortcut, the set-comparison cheat). Write that wrong implementation
  mentally, find an input where it diverges, and make that a test.
- The answer must be uniquely determined: pin output ordering and tie-breaking
  in the statement, since the judge compares with exact `==` (and tuple != list;
  return lists, never tuples or sets).
