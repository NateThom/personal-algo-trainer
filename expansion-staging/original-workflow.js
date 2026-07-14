export const meta = {
  name: 'bank-expansion',
  description: 'Author ~107 original problems (6/pattern) with mechanical gate + adversarial verification',
  phases: [
    { title: 'Syllabus', detail: 'one agent per pattern proposes complementary shapes' },
    { title: 'Author', detail: 'one agent per problem writes JSON, iterates until gate passes' },
    { title: 'Verify', detail: 'adversarial: 2 wrong impls must die, 1 correct alternative must survive' },
    { title: 'Review', detail: 'per-pattern dedupe/ambiguity/difficulty/hint review' },
  ],
}

const REPO = '/Users/nthom/personal-algo-trainer'
const PY = '/Users/nthom/personal-algo-trainer/.venv/bin/python'
const EXP = '/private/tmp/claude-503/-Users-nthom-personal-algo-trainer/27c07698-e14d-425b-82d5-c32d6244427c/scratchpad/expansion'
const GATE = EXP + '/gate.py'
const PENDING = EXP + '/pending'

const COMMON_RULES = `
HARD RULES for problem content (the judge compares outputs with exact ==):
- Write ORIGINAL statements. Never copy LeetCode/NeetCode wording. Canonical problem SHAPES are fine; the text, story, and concrete instances must be yours.
- The answer to every test must be UNIQUELY determined by the statement: pin output ordering, tie-breaking, and what to return when there is no solution, explicitly in the statement.
- Outputs must be JSON-native: lists/ints/floats/bools/strings/None. NEVER tuples or sets. args in tests are positional arguments.
- Problem JSON schema (exactly these keys): id (kebab-case, must equal filename stem), pattern, title, difficulty (easy|medium|hard), statement, function_name (snake_case), starter_code (stub def with same signature as reference, body is a comment + pass), reference_solution (correct, canonical for the pattern), tests (list of {"args": [...], "expected": ...}), hints (EXACTLY 3, graduated: 1 = nudge/question toward the pattern, 2 = the key invariant or data structure, 3 = near-solution walkthrough of the step).
- 6-8 tests covering: normal case, boundary (single element / smallest n), empty or degenerate input where the domain allows, the no-solution branch, duplicates/ties, and at least one KILL TEST on which the canonical wrong implementation returns the wrong answer.
- File style: match ${REPO}/content/problems/two-sum.json — 2-space indent, each test object on ONE line.
- expected values MUST be produced by EXECUTING your reference solution (write a throwaway script; run with ${PY}), never computed in your head.`

const parsedArgs = typeof args === 'string' ? JSON.parse(args) : args
const patterns = parsedArgs.patterns
// Problems already authored + gate-passed in a previous (Fable) run: skip their
// author call and go straight to verification. Model for all non-syllabus agents
// is Opus (syllabus opts must stay untouched so cached results replay).
const STAGED = new Set(parsedArgs.staged || [])
const MODEL = 'opus'

const SYLLABUS_SCHEMA = {
  type: 'object', required: ['shapes'], additionalProperties: false,
  properties: { shapes: { type: 'array', items: {
    type: 'object', required: ['slug', 'title', 'difficulty', 'description', 'canonical_wrong', 'sub_technique'],
    additionalProperties: false,
    properties: {
      slug: { type: 'string' }, title: { type: 'string' },
      difficulty: { enum: ['easy', 'medium', 'hard'] },
      description: { type: 'string' }, canonical_wrong: { type: 'string' }, sub_technique: { type: 'string' },
    } } } },
}

const AUTHOR_SCHEMA = {
  type: 'object', required: ['status', 'id', 'path', 'notes'], additionalProperties: false,
  properties: {
    status: { enum: ['pass', 'fail'] }, id: { type: 'string' }, path: { type: 'string' },
    kill_test_index: { type: 'integer' }, notes: { type: 'string' },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', required: ['pass', 'failures'], additionalProperties: false,
  properties: {
    pass: { type: 'boolean' },
    wrong1_desc: { type: 'string' }, wrong1_killed_by_test: { type: 'integer' },
    wrong2_desc: { type: 'string' }, wrong2_killed_by_test: { type: 'integer' },
    alt_approach: { type: 'string' }, alt_passed: { type: 'boolean' },
    failures: { type: 'array', items: { type: 'object',
      required: ['kind', 'detail'], additionalProperties: false,
      properties: { kind: { enum: ['weak_tests', 'ambiguous_answer', 'wrong_expected', 'other'] },
        detail: { type: 'string' }, diverging_input: { type: 'string' } } } },
  },
}

const REVIEW_SCHEMA = {
  type: 'object', required: ['kept', 'edited', 'flagged_drop', 'summary'], additionalProperties: false,
  properties: {
    kept: { type: 'array', items: { type: 'string' } },
    edited: { type: 'array', items: { type: 'object', required: ['id', 'what'], additionalProperties: false,
      properties: { id: { type: 'string' }, what: { type: 'string' } } } },
    flagged_drop: { type: 'array', items: { type: 'object', required: ['id', 'why'], additionalProperties: false,
      properties: { id: { type: 'string' }, why: { type: 'string' } } } },
    summary: { type: 'string' },
  },
}

function syllabusPrompt(pat) {
  return `You are the syllabus agent for the AlgoTrainer pattern "${pat.pattern}".

Read ${REPO}/content/patterns/${pat.pattern}.json (the teaching doc) and every file in ${REPO}/content/problems/ whose "pattern" field is "${pat.pattern}" (grep for it). Note each existing problem's underlying instance, sub-technique, and difficulty.

Propose EXACTLY ${pat.need} NEW problem shapes for this pattern such that the final set (existing + new) covers the pattern's major sub-techniques and lands near 3 easy / 5 medium / 2 hard overall. Rules:
- No re-skins: a new shape must not share its underlying algorithmic instance with an existing seed (a different story over the same computation is a re-skin).
- Bias toward shapes that appear frequently in real interviews, then fill remaining slots for sub-technique coverage.
- Each shape must be solvable as a single pure function with JSON-native args/output (no class-design problems, no linked-list node objects — linked-list pattern problems here operate on Python lists simulating the technique, see existing seeds).
- slug: a kebab-case id suggestion, descriptive, not colliding with existing problem ids.
- canonical_wrong: describe THE classic wrong implementation a learner writes for this shape (the off-by-one, the missing shrink/backtrack, the greedy shortcut, the set-comparison cheat...). Every shape must have a genuine one — if you cannot name one, pick a different shape.
- description: 2-4 sentences specifying the task precisely enough for an author to write it, including what the function returns and how ties/ordering are resolved.

Return via StructuredOutput. Your final output is data, not prose.`
}

function authorPrompt(pattern, shape) {
  return `You are a problem author for AlgoTrainer. Write ONE new problem for pattern "${pattern}".

Shape spec:
- slug: ${shape.slug}
- title: ${shape.title}
- difficulty: ${shape.difficulty}
- task: ${shape.description}
- sub-technique: ${shape.sub_technique}
- canonical wrong implementation your tests MUST kill: ${shape.canonical_wrong}
${COMMON_RULES}

Process (do all of it, verify by execution, no shortcuts):
1. Read ${REPO}/content/problems/two-sum.json for format, and ${REPO}/content/patterns/${pattern}.json for the pattern's template/gotchas so your reference solution is canonical.
2. Draft the problem. Write your reference solution and a runner script in a scratch dir ${EXP}/scratch/${shape.slug}/; EXECUTE the reference with ${PY} to produce every expected value.
3. ALSO implement the canonical wrong implementation above and run it against your tests: it must fail at least one. If it passes all, find a diverging input and add it as a test.
4. Write the final JSON to ${PENDING}/<id>.json (id = ${shape.slug} unless the gate reports a collision; then choose a new descriptive id and matching filename).
5. Run: ${PY} ${GATE} ${PENDING}/<id>.json — fix and re-run until it prints GATE PASS. Do not stop at fail.
Never modify anything under ${REPO} — you only write in ${EXP}.

Return via StructuredOutput: status ('pass' only if the gate printed GATE PASS), id, path (absolute path of the JSON), kill_test_index (0-based index of a test the wrong impl fails), notes (one sentence: what the kill test catches).`
}

function verifyPrompt(pattern, shape, path) {
  return `You are an ADVERSARIAL VERIFIER for a new AlgoTrainer problem. Do not trust the author. Your job is to prove the test suite is discriminative AND implementation-agnostic.

Problem file: ${path} (pattern "${pattern}"). Read it. Work in ${EXP}/scratch/verify-${shape.slug}/; run everything with ${PY}. Never modify the problem file or anything under ${REPO}.

Do all three checks by ACTUAL EXECUTION:
1. WRONG IMPL #1 — implement the canonical mistake for this shape: "${shape.canonical_wrong}". Run it against every test in the file. It must return a wrong answer on at least one test ("die"). Record which test index kills it.
2. WRONG IMPL #2 — pick a SECOND plausible wrong implementation of your own choosing (a different classic mistake for this problem: off-by-one boundary, missing edge-case branch, greedy shortcut, wrong tie-break...). It must also die. If a wrong impl survives all tests, that is a weak_tests failure: report a concrete diverging input where it returns the wrong answer.
3. CORRECT ALTERNATIVE — write a correct solution using a MATERIALLY different approach than the file's reference_solution (different algorithm or traversal, not a variable rename). It must pass ALL tests ("survive"). If it fails a test while being correct per the statement, that is an ambiguous_answer failure (the tests encode the reference's arbitrary choices): report the diverging input and what the statement fails to pin.
Also sanity-check by hand-reasoning two tests against the statement; if an expected value contradicts the statement, report wrong_expected.

Judge comparison is exact ==. A wrong impl that raises an exception on a test counts as dying on that test only if a correct solution does not also raise there.

Return via StructuredOutput. pass = true only if both wrong impls died, the alternative survived, and no wrong_expected. On failure, failures[] must contain concrete, actionable entries with diverging_input as a Python-literal string.`
}

function repairPrompt(pattern, shape, path, verdict) {
  return `You are repairing an AlgoTrainer problem that FAILED adversarial verification.

Problem file: ${path} (pattern "${pattern}"). Verifier failures:
${JSON.stringify(verdict.failures, null, 2)}
${COMMON_RULES}

Fix the file IN PLACE at ${path}:
- weak_tests: add a test using the diverging input (compute expected by EXECUTING the reference solution with ${PY}); if already at 8 tests, replace the least informative one.
- ambiguous_answer: pin the ordering/tie-break in the statement AND adjust tests/expected so the answer is uniquely determined per the pinned statement (recompute expected by execution). If pinning is impossible for this shape, change inputs so ties cannot occur.
- wrong_expected: fix the reference solution or the statement (whichever is wrong) and regenerate ALL expected values by execution.
Work in ${EXP}/scratch/repair-${shape.slug}/. Then run ${PY} ${GATE} ${path} until GATE PASS. Never modify anything under ${REPO}.

Return via StructuredOutput: status ('pass' only if GATE PASS), id, path, kill_test_index, notes (what you changed).`
}

function reviewPrompt(pattern, accepted) {
  const ids = accepted.map(a => a.id).join(', ')
  return `You are the pattern reviewer for AlgoTrainer pattern "${pattern}". The new candidate problems (already gate-passed and adversarially verified) are these files in ${PENDING}/: ${ids} (files <id>.json).

Read all of them, plus every EXISTING problem in ${REPO}/content/problems/ with "pattern": "${pattern}", plus ${REPO}/content/patterns/${pattern}.json.

Check across the whole new set:
1. Dedupe — no candidate shares its underlying algorithmic instance with an existing seed or another candidate (same computation with a different story = duplicate). Duplicates go in flagged_drop.
2. Statement ambiguity — every statement pins output ordering, tie-breaks, empty/no-solution behavior; constraints explicit. Small wording fixes: edit the file.
3. Difficulty sanity — relabel in the file if clearly wrong (an 'easy' needing a nontrivial invariant, a 'hard' that is a straight template application).
4. Hint progression — exactly 3 graduated hints (nudge that does NOT name the pattern outright, then invariant/data-structure, then near-solution). Hint 1 must not give away what hint 3 gives. Fix by editing.
5. Title/id — descriptive, not leaking the technique in a way the statement should test (e.g. a title literally naming the pattern when recognition is the skill; retitle in-file if so, but NEVER change the id or filename).

You MAY edit candidate files in ${PENDING}/ (never anything under ${REPO}). After editing a file you MUST re-run ${PY} ${GATE} <file> and get GATE PASS; if your edit changes statement semantics, recompute expected values by executing the reference with ${PY}. Do not add/remove tests unless required by an ambiguity fix.

Return via StructuredOutput: kept (ids to keep, including edited ones), edited ([{id, what}]), flagged_drop ([{id, why}] with concrete reasons), summary (2-3 sentences on the pattern's final coverage).`
}

async function authorAndVerify(pattern, shape) {
  let authored
  if (STAGED.has(shape.slug)) {
    authored = { status: 'pass', id: shape.slug, path: `${PENDING}/${shape.slug}.json`, notes: 'pre-staged from earlier run' }
  } else {
    authored = await agent(authorPrompt(pattern, shape), {
      schema: AUTHOR_SCHEMA, phase: 'Author', label: `author:${shape.slug}`, agentType: 'general-purpose', model: MODEL,
    })
  }
  if (!authored || authored.status !== 'pass') {
    return { slug: shape.slug, status: 'dropped', stage: 'author', reason: authored ? authored.notes : 'author agent died' }
  }
  let rounds = 0
  while (true) {
    const v = await agent(verifyPrompt(pattern, shape, authored.path), {
      schema: VERDICT_SCHEMA, phase: 'Verify', label: `verify:${authored.id}`, agentType: 'general-purpose', model: MODEL,
    })
    if (!v) return { slug: shape.slug, id: authored.id, status: 'dropped', stage: 'verify', reason: 'verifier agent died' }
    if (v.pass) {
      return { slug: shape.slug, id: authored.id, path: authored.path, status: 'accepted',
        difficulty: shape.difficulty, repairs: rounds,
        wrong_impls: [v.wrong1_desc, v.wrong2_desc], alt_approach: v.alt_approach }
    }
    rounds += 1
    if (rounds > 2) {
      return { slug: shape.slug, id: authored.id, status: 'dropped', stage: 'verify',
        reason: 'failed adversarial verification after 2 repair rounds', failures: v.failures }
    }
    const repaired = await agent(repairPrompt(pattern, shape, authored.path, v), {
      schema: AUTHOR_SCHEMA, phase: 'Author', label: `repair:${authored.id}(r${rounds})`, agentType: 'general-purpose', model: MODEL,
    })
    if (!repaired || repaired.status !== 'pass') {
      return { slug: shape.slug, id: authored.id, status: 'dropped', stage: 'repair',
        reason: repaired ? repaired.notes : 'repair agent died' }
    }
  }
}

const results = await pipeline(
  patterns,
  pat => agent(syllabusPrompt(pat), {
    schema: SYLLABUS_SCHEMA, phase: 'Syllabus', label: `syllabus:${pat.pattern}`, agentType: 'general-purpose',
  }),
  async (syl, pat) => {
    if (!syl) return { pattern: pat.pattern, outcomes: [], error: 'syllabus agent died' }
    const shapes = syl.shapes.slice(0, pat.need)
    if (syl.shapes.length !== pat.need) log(`${pat.pattern}: syllabus returned ${syl.shapes.length} shapes, wanted ${pat.need}`)
    const outcomes = await parallel(shapes.map(shape => () => authorAndVerify(pat.pattern, shape)))
    return { pattern: pat.pattern, outcomes: outcomes.filter(Boolean) }
  },
  async (res, pat) => {
    const accepted = res.outcomes.filter(o => o.status === 'accepted')
    log(`${pat.pattern}: ${accepted.length}/${pat.need} accepted, ${res.outcomes.length - accepted.length} dropped`)
    if (!accepted.length) return { ...res, review: null }
    const review = await agent(reviewPrompt(pat.pattern, accepted), {
      schema: REVIEW_SCHEMA, phase: 'Review', label: `review:${pat.pattern}`, agentType: 'general-purpose', model: MODEL,
    })
    return { ...res, review }
  },
)

const summary = { patterns: results.filter(Boolean), }
let acc = 0, drop = 0
for (const r of summary.patterns) {
  for (const o of (r.outcomes || [])) { if (o.status === 'accepted') acc += 1; else drop += 1 }
}
log(`TOTAL: ${acc} accepted, ${drop} dropped across ${summary.patterns.length} patterns`)
return summary
