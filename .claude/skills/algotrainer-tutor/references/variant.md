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
the reason, fix, and resubmit. Cover normal, boundary, and empty/edge cases in
`tests`.
