# AlgoTrainer Product Review — 2026-07-02

Independent review of the implemented app against the five design plans in
`docs/superpowers/plans/`. Full loop was exercised end-to-end (TestClient:
next → judge → session → stub verdict → ingest → mastery). All 111 tests pass.
Findings cite `file:line`; each section ends with scoped suggestions
(S = small, ≤1 hr; M = medium, an evening; L = larger, only if the pain is real).

---

## 1. Purpose — designed intent vs. delivered loop

**Design (plans):** pattern-mastery interview trainer where Claude Code is the
tutor. Plan 1 (`walking-skeleton.md:5`) defines the loop: serve due problem cold
→ recall gate → judge → session-file handoff → verdict ingest → FSRS update.
Plans 2–5 add tutor skill + hint ladder, pattern-level FSRS / mastery gate /
memorization trap / composer, AI variants + dashboard, pattern library + signals.

**Verified working:**
- Due selection with reviews-before-novel and blocked→interleaved composition
  (`algotrainer/web/app.py:119-154`, `algotrainer/composer.py:22`).
- Judge in a subprocess, stdout-safe, 5 s timeout (`algotrainer/judge.py:54-95`).
- Handoff → validated verdict → idempotent, transactional ingest that updates
  problem card, pattern card, and analytics row (`app.py:279-324`,
  `algotrainer/store.py:139-159`).
- Mastery model with gate + memorization trap (`algotrainer/mastery.py:32-70`).

**The loop closes.** The weak links are at the seams:

| # | Finding | Evidence |
|---|---------|----------|
| 1.1 | **Recall gate leaks its own answer.** `/api/next` returns `"pattern"` in the payload, and the pool banner prints the pattern name in visible UI text — while `app.js` comments "pattern hidden on purpose". Pattern-ID accuracy is 30% of the mastery score. | `app.py:149`, `static/app.js` (`renderPoolBanner`) |
| 1.2 | **Skill "hint" request mode is dead wiring.** Schema and SKILL.md support `request:"hint"`, but the app always writes `request="grade"`, and a session file only exists *after* "Send to tutor" — so adaptive hints mid-solve are impossible via the documented path. | `handoff/schema.py:15`, `SKILL.md:52-57`, `app.py:263` |
| 1.3 | **Verdict fields dropped on ingest.** `approach_used`, `self_explanation_score`, `feedback` are validated but never persisted — `graded_attempt` has no columns. Plan 2's self-explanation scoring is write-only. | `handoff/schema.py:23-27`, `store.py:36-47` |
| 1.4 | Unknown `problem_id` → raw `KeyError` → 500 in `/api/judge` and `/api/session`; only `/api/hint` 404s properly. | `app.py:238,257` vs `app.py:270-272` |
| 1.5 | **Seed bank far below plan.** 12 problems across 6 of 18 patterns; `content/generated/` empty. With `GATE_BREADTH = 4`, no pattern is masterable out of the box; 12 patterns have zero problems. Plan 4's "moderate expansion of the vetted seed bank" was not delivered. | `content/problems/`, `mastery.py:7` |

**Suggestions**
- (S) 1.1: strip `pattern` and `pattern_pool.pattern` from the `/api/next`
  payload until after handoff; reword the exhausted-pool banner to avoid the
  pattern name ("You've seen every problem in this pattern's pool…") and move
  the named version to post-ingest feedback.
- (S) 1.4: wrap both handlers with the same 404 guard `/api/hint` uses.
- (S) 1.3: either add the three columns to `graded_attempt` (SQLite `ALTER TABLE
  ADD COLUMN`, no migration framework needed) or delete the fields from
  `Verdict` and the rubric — don't validate what you throw away. Persisting
  `feedback` also fixes "feedback is shown once then lost".
- (M) 1.2: pick one. Simplest honest fix: delete `request:"hint"` from the
  schema/SKILL.md and document that mid-solve hints are the pre-authored
  `/api/hint` ladder only. Fuller fix: a "Request tutor hint" button that writes
  a session file with `request:"hint"` pre-judging.
- (M/L) 1.5: author ~2 seed problems for each of the 12 empty patterns (the
  variant validator already enforces correctness, so Claude can draft and
  `scripts/add_variant.py` gates them). This is the highest-leverage content
  work in the repo; everything downstream (mastery, composer, library) is
  already built and waiting for it.

---

## 2. Tools available

**Inventory (all verified rendering / responding):**
- Pages: `/` (Solve), `/dashboard`, `/guide`, `/methodology`, `/patterns`,
  `/patterns/{id}`, `/docs` (FastAPI).
- Buttons: Get hint, Run tests, Send to tutor, Ingest verdict (`index.html`);
  Reload problems, Reset progress (shared nav, `nav.js`).
- API: `next`, `judge`, `session`, `hint`, `verdict/ingest`, `mastery`,
  `dashboard`, `patterns[/{id}]`, `reload`, `reset`.
- Skill: `algotrainer-tutor` (grade / hint / generate-variant) with rubric +
  variant references; validating writers `scripts/write_verdict.py`,
  `scripts/add_variant.py`; offline fallback `scripts/stub_tutor.py`.

| # | Finding | Evidence |
|---|---------|----------|
| 2.1 | **Session id is the load-bearing hinge and it's fragile.** It appears only as text in the results `<pre>`; the user retypes it into Claude Code. No copy button, no "latest session" affordance. | `app.js` (`handoff()`), `docs/USING_THE_TUTOR.md:8-12` |
| 2.2 | **Page reload strands a graded session.** `sessionId` lives only in JS memory; after reload the Ingest button is disabled forever and there is no UI to enter an id. The verdict sits orphaned on disk. | `app.js:2` (`let sessionId = null`) |
| 2.3 | Two hint systems with different UX; the skill path is unusable mid-solve (see 1.2). | — |
| 2.4 | App startup (`python -m algotrainer`) is undocumented in USING_THE_TUTOR.md; no console script in pyproject. | `algotrainer/__main__.py:16`, `pyproject.toml` |
| 2.5 | Variant generation is three manual hops (notice banner → ask Claude → click Reload), though each is signposted. | `app.js` banner, `SKILL.md:59-74` |

**Suggestions**
- (S) 2.2: persist `sessionId` to `localStorage` on handoff and restore on load;
  enable Ingest whenever a stored id exists. This is ~10 lines and removes the
  worst failure mode.
- (S) 2.1: add a "Copy tutor command" button that puts
  `grade session <id>` on the clipboard.
- (S) 2.4: add a `[project.scripts] algotrainer = ...` entry or a one-line
  "Run it" section at the top of USING_THE_TUTOR.md.
- (M) 2.2/2.1 together: an ingest-sweep — on page load, `GET /api/verdicts/pending`
  listing verdict files whose attempts lack reviews, with one-click ingest.
  Kills both the copy-paste round-trip's tail risk and orphaned verdicts.

---

## 3. Notifications / action signals

**Exists (all pull-based, in-app — appropriate for a local single-user tool):**
- Header stats "N due · M problems · K/18 mastered" (`app.js` `loadDashboard`);
  dashboard tiles (`dashboard.js`).
- 🆕 New / 🔁 Review·seen N× badge per problem (`app.py:152`).
- Pool banner: exhausted-pool → "ask the tutor for a variant"; `needs_more`
  count (`app.py:79-88`); dashboard "⚙ generate more" markers.
- Memorization-trap warning "⚠ memorizing, not recognizing" (`mastery.py:47-51`).
- Post-handoff instructions; ingest 409 → "No verdict yet"; SKILL.md tells the
  tutor to remind the user to click Ingest.
- Error-taxonomy journal counts on dashboard.

| # | Gap | Evidence |
|---|-----|----------|
| 3.1 | **No "verdict ready" signal.** User blind-clicks Ingest and may 409. Nothing polls the sessions dir or the endpoint. Most annoying seam in the loop. | `app.js` (`ingest()`), `app.py:279-284` |
| 3.2 | No orphan/stale detection: un-ingested verdicts and abandoned session files are invisible. | `sessions/` (only created on first handoff) |
| 3.3 | Due count is stale — fetched on load and after ingest only; an open tab lies overnight. | `app.js` (`loadDashboard` call sites) |
| 3.4 | `next_due` shown once in the results pane, never surfaced as "next review at…" on the dashboard. | `app.js` (`ingest()`), `dashboard.js` |
| 3.5 | Nothing signals that newly generated variants exist besides the manual Reload button. | `nav.js` |

**Suggestions**
- (S) 3.1: after handoff, poll `/api/verdict/ingest`-adjacent status (or a tiny
  `GET /api/verdict/status?session_id=`) every ~5 s and flip the Ingest button
  to "Verdict ready — ingest" when the file appears. Biggest UX win per line.
- (S) 3.3: `setInterval(loadDashboard, 60_000)` — one line.
- (S) 3.4: dashboard tile "Next review due: <min(next_due)>" from data the
  `card` table already holds.
- (M) 3.2: fold into the pending-verdicts sweep (suggestion 2-M).
- Skip: push/email/OS notifications — out of scope for a localhost personal
  tool; the plans never promised them.

---

## 4. Lightweight — footprint

**Genuinely lean:** 5 runtime deps (`pyproject.toml:5-11`); ~1,100 LOC Python
app + 875 LOC static JS/HTML; 31 test files; single-file SQLite (36 KB); vendored
CodeMirror (184 KB, offline-friendly per plan constraints). Git hygiene is good:
`.superpowers/` (896 KB), `algotrainer.egg-info`, `*.db`, `sessions/*.json`,
`content/generated/*.json` are all gitignored and **not** committed (verified
against `git ls-files`; 109 tracked files).

| # | Finding | Evidence |
|---|---------|----------|
| 4.1 | **`python-multipart` is an unused dependency** — no `Form`/`UploadFile` anywhere; all bodies are JSON. | `pyproject.toml:10` |
| 4.2 | Dead/near-dead code: `Store.record_review` (only a test calls it; production uses `ingest_verdict`); `SrsScheduler.new_card_json` (no production caller). | `store.py:130`, `scheduler.py:13` |
| 4.3 | `_reload_problems` mutates the shared `problems` dict un-locked while threadpool requests read it. Harmless single-user; technically racy. | `app.py:59-66` |
| 4.4 | Plans are 4,263 lines of markdown for ~2,000 lines of product — fine as history, but the bulk of committed weight. | `docs/superpowers/plans/` |
| 4.5 | Venv runs Python 3.14 against `requires-python >=3.11` with unpinned minimums — works today, untested claim tomorrow. | `pyproject.toml:4` |

**Suggestions**
- (S) 4.1: delete `python-multipart` from deps.
- (S) 4.2: delete `record_review` + its test (fold coverage into an
  `ingest_verdict` test) and `new_card_json`.
- (S) 4.3: swap-assign a freshly built dict (`problems = new_map`) instead of
  `clear()` + repopulate — atomic enough for CPython, zero extra machinery.
- Skip: dependency pinning, plan-doc pruning, connection pooling — all would add
  weight to solve problems this tool doesn't have.

---

## Priority order (if doing only five things)

1. Seed-bank expansion to cover all 18 patterns (1.5) — the product's promise is
   unreachable without it.
2. `localStorage` session persistence + pending-verdict sweep (2.2, 3.1/3.2) —
   removes the loop's only lossy step.
3. Stop leaking the pattern before the recall gate (1.1) — protects the
   integrity of the core mastery metric.
4. Persist or delete the dropped verdict fields (1.3).
5. Delete `python-multipart` and the dead store/scheduler methods (4.1, 4.2).
