export const meta = {
  name: 'finish-bank-expansion',
  description: 'Finish the bank expansion: re-verify 23 problems whose verifier died, then run the 16 missing pattern reviews',
  phases: [
    { title: 'Verify', detail: 'adversarial: 2 wrong impls must die, 1 correct alternative must survive (with repair rounds)' },
    { title: 'Review', detail: 'per-pattern dedupe/ambiguity/difficulty/hint review' },
  ],
}

// args: { repo, py, needs_reverify: [{pattern,id,shape:{slug,canonical_wrong,...}}],
//         reviews_missing: [pattern...], accepted_by_pattern: {pattern: [ids...]} }
const A = typeof args === 'string' ? JSON.parse(args) : args
const REPO = A.repo
const PY = A.py
const STG = REPO + '/expansion-staging'
const GATE = STG + '/gate.py'
const PENDING = STG + '/pending'
const MODEL = 'opus'

const COMMON_RULES = `
HARD RULES for problem content (the judge compares outputs with exact ==):
- Write ORIGINAL statements. Never copy LeetCode/NeetCode wording.
- The answer to every test must be UNIQUELY determined by the statement: pin output ordering, tie-breaking, and what to return when there is no solution, explicitly in the statement.
- Outputs must be JSON-native: lists/ints/floats/bools/strings/None. NEVER tuples or sets.
- 6-8 tests; exactly 3 graduated hints; file style: 2-space indent, each test object on ONE line.
- expected values MUST be produced by EXECUTING the reference solution with ${PY}, never computed in your head.`

const VERDICT_SCHEMA = {
  type: 'object', required: ['pass', 'failures'], additionalProperties: false,
  properties: {
    pass: { type: 'boolean' },
    wrong1_desc: { type: 'string' }, wrong1_killed_by_test: { type: 'integer' },
    wrong2_desc: { type: 'string' }, wrong2_killed_by_test: { type: 'integer' },
    alt_approach: { type: 'string' }, alt_passed: { type: 'boolean' },
    failures: { type: 'array', items: { type: 'object', required: ['kind', 'detail'], additionalProperties: false,
      properties: { kind: { enum: ['weak_tests', 'ambiguous_answer', 'wrong_expected', 'other'] },
        detail: { type: 'string' }, diverging_input: { type: 'string' } } } },
  },
}
const AUTHOR_SCHEMA = {
  type: 'object', required: ['status', 'id', 'path', 'notes'], additionalProperties: false,
  properties: { status: { enum: ['pass', 'fail'] }, id: { type: 'string' }, path: { type: 'string' },
    kill_test_index: { type: 'integer' }, notes: { type: 'string' } },
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

function verifyPrompt(pattern, item) {
  const path = `${PENDING}/${item.id}.json`
  return `You are an ADVERSARIAL VERIFIER for a new AlgoTrainer problem. Do not trust the author. Your job is to prove the test suite is discriminative AND implementation-agnostic.

Problem file: ${path} (pattern "${pattern}"). Read it. Work in a scratch dir you create (e.g. /tmp/verify-${item.id}/); run everything with ${PY}. Never modify the problem file or anything under ${REPO}.

Do all three checks by ACTUAL EXECUTION:
1. WRONG IMPL #1 — implement the canonical mistake for this shape: "${item.shape.canonical_wrong}". Run it against every test in the file. It must return a wrong answer on at least one test ("die"). Record which test index kills it.
2. WRONG IMPL #2 — pick a SECOND plausible wrong implementation of your own choosing (a different classic mistake for this problem). It must also die. If a wrong impl survives all tests, that is a weak_tests failure: report a concrete diverging input where it returns the wrong answer.
3. CORRECT ALTERNATIVE — write a correct solution using a MATERIALLY different approach than the file's reference_solution. It must pass ALL tests ("survive"). If it fails a test while being correct per the statement, that is an ambiguous_answer failure: report the diverging input and what the statement fails to pin.
Also sanity-check by hand-reasoning two tests against the statement; if an expected value contradicts the statement, report wrong_expected.

Judge comparison is exact ==. A wrong impl that raises on a test counts as dying there only if a correct solution does not also raise.

Return via StructuredOutput. pass = true only if both wrong impls died, the alternative survived, and no wrong_expected. On failure, failures[] must contain concrete, actionable entries with diverging_input as a Python-literal string.`
}

function repairPrompt(pattern, item, verdict) {
  const path = `${PENDING}/${item.id}.json`
  return `You are repairing an AlgoTrainer problem that FAILED adversarial verification.

Problem file: ${path} (pattern "${pattern}"). Verifier failures:
${JSON.stringify(verdict.failures, null, 2)}
${COMMON_RULES}

Fix the file IN PLACE at ${path}:
- weak_tests: add a test using the diverging input (compute expected by EXECUTING the reference solution with ${PY}); if already at 8 tests, replace the least informative one.
- ambiguous_answer: pin the ordering/tie-break in the statement AND adjust tests so the answer is uniquely determined (recompute expected by execution). If pinning is impossible, change inputs so ties cannot occur.
- wrong_expected: fix the reference solution or the statement (whichever is wrong) and regenerate ALL expected values by execution.
Then run ${PY} ${GATE} ${path} until GATE PASS. Never modify anything under ${REPO}/content or ${REPO}/algotrainer.

Return via StructuredOutput: status ('pass' only if GATE PASS), id, path, kill_test_index, notes (what you changed).`
}

function reviewPrompt(pattern, ids) {
  return `You are the pattern reviewer for AlgoTrainer pattern "${pattern}". The new candidate problems (already gate-passed and adversarially verified) are these files in ${PENDING}/: ${ids.join(', ')} (files <id>.json).

Read all of them, plus every EXISTING problem in ${REPO}/content/problems/ with "pattern": "${pattern}", plus ${REPO}/content/patterns/${pattern}.json.

Check across the whole new set:
1. Dedupe — no candidate shares its underlying algorithmic instance with an existing seed or another candidate (same computation with a different story = duplicate). Duplicates go in flagged_drop.
2. Statement ambiguity — every statement pins output ordering, tie-breaks, empty/no-solution behavior; constraints explicit. Small wording fixes: edit the file.
3. Difficulty sanity — relabel in the file if clearly wrong.
4. Hint progression — exactly 3 graduated hints (nudge that does NOT name the pattern outright, then invariant/data-structure, then near-solution). Fix by editing.
5. Title/id — retitle in-file if the title leaks the technique the statement should test, but NEVER change the id or filename.

You MAY edit candidate files in ${PENDING}/ (never anything under ${REPO}/content or ${REPO}/algotrainer). After editing a file you MUST re-run ${PY} ${GATE} <file> and get GATE PASS; if your edit changes statement semantics, recompute expected values by executing the reference with ${PY}.

Return via StructuredOutput: kept (ids to keep, including edited ones), edited ([{id, what}]), flagged_drop ([{id, why}] with concrete reasons), summary (2-3 sentences on the pattern's final coverage).`
}

async function verifyWithRepair(item) {
  let rounds = 0
  while (true) {
    const v = await agent(verifyPrompt(item.pattern, item), {
      schema: VERDICT_SCHEMA, phase: 'Verify', label: `verify:${item.id}`, agentType: 'general-purpose', model: MODEL,
    })
    if (!v) return { id: item.id, pattern: item.pattern, status: 'dropped', reason: 'verifier agent died' }
    if (v.pass) return { id: item.id, pattern: item.pattern, status: 'accepted', repairs: rounds,
      wrong_impls: [v.wrong1_desc, v.wrong2_desc], alt_approach: v.alt_approach }
    rounds += 1
    if (rounds > 2) return { id: item.id, pattern: item.pattern, status: 'dropped',
      reason: 'failed adversarial verification after 2 repair rounds', failures: v.failures }
    const r = await agent(repairPrompt(item.pattern, item, v), {
      schema: AUTHOR_SCHEMA, phase: 'Verify', label: `repair:${item.id}(r${rounds})`, agentType: 'general-purpose', model: MODEL,
    })
    if (!r || r.status !== 'pass') return { id: item.id, pattern: item.pattern, status: 'dropped',
      reason: r ? r.notes : 'repair agent died' }
  }
}

const verified = (await parallel(A.needs_reverify.map(item => () => verifyWithRepair(item)))).filter(Boolean)
const okByPattern = {}
for (const v of verified) {
  if (v.status === 'accepted') (okByPattern[v.pattern] = okByPattern[v.pattern] || []).push(v.id)
}
log(`verify: ${verified.filter(v => v.status === 'accepted').length}/${A.needs_reverify.length} accepted`)

const reviews = await parallel(A.reviews_missing.map(pattern => () => {
  const ids = [...(A.accepted_by_pattern[pattern] || []), ...(okByPattern[pattern] || [])]
  if (!ids.length) return Promise.resolve({ pattern, review: null })
  return agent(reviewPrompt(pattern, ids), {
    schema: REVIEW_SCHEMA, phase: 'Review', label: `review:${pattern}`, agentType: 'general-purpose', model: MODEL,
  }).then(review => ({ pattern, review }))
}))

return { verified, reviews: reviews.filter(Boolean) }
