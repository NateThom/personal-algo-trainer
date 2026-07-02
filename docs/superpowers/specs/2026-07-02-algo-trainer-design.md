# AlgoTrainer — Design Document

**Date:** 2026-07-02
**Status:** Approved design, pre-implementation
**Author:** nthom (with Claude)

---

## 1. Purpose

A personal training tool that makes its owner an expert at the **algorithm/data-structures screening phase** of technical interviews — the intelligent, evidence-based way, not by brute-force grinding.

The learner is a **Data Scientist / ML Engineer** who is fluent in Python for day-to-day work but a **near-beginner at DSA puzzles**, with **no active job search** — so the tool optimizes for **durable, long-term mastery**, not cramming.

### The core problem this solves

Every polished prep tool (LeetCode, NeetCode, AlgoMonster, HackerRank, CodeSignal) is a *content-delivery / rep-volume* machine. None closes the actual learning loop the science prescribes. The unmet need — validated by research into the tools landscape, coding-interview best practices, DS/ML interview structure, and the learning science of procedural skill acquisition — is a **closed learning loop for a single motivated learner**:

> diagnose weak patterns → schedule spaced, interleaved re-solves of **novel** instances → grade objectively (correctness + optimality + time + hints) → tutor Socratically in the moment → update a per-pattern mastery model → repeat

The individual pieces (FSRS spaced repetition, pattern taxonomies, LLM tutoring/grading, code judges) are all mature; nobody has assembled them into one loop. That assembly is this project.

---

## 2. Scope

### In scope (v1)
- **DSA pattern-mastery track only.** The full closed loop, built well, for one track.
- Pattern taxonomy (~22–24 patterns) in a dependency-ordered roadmap.
- Curated seed problem bank + AI-generated novel variants.
- FSRS-based scheduler operating at pattern + problem-instance levels.
- Active-recall solve loop with recall gates and a graduated hint ladder.
- Local Python code judge (run attempt against tests).
- Claude Code tutor **skill** (in-repo) for Socratic hints, grading, approach classification, error coding, and variant generation — driven by shared state files. No API cost.
- Per-pattern mastery model with criterion-based advancement.
- Error-taxonomy journal that feeds back into scheduling.
- Dashboards: mastery per pattern, due queue, error trends, session summaries.

### Explicitly deferred (post-v1)
- SQL / pandas-NumPy / statistics-A/B / ML-coding-from-scratch / ML-system-design tracks (the engine is built to generalize to these).
- Verbal / mock-interview mode.
- Automatic FSRS parameter-fitting to the learner's personal review log (v1 uses good default weights; fitting is added once enough log data exists).
- Rich/advanced visualizations.

### Rationale for narrow scope
DSA is the learner's weakest area and the **universal gating filter** across both DS and MLE loops (even though it is only ~10–15% of a DS loop and ~30–40% of an MLE loop). Proving the closed-loop engine on one track first, then generalizing, beats spreading a shallow engine across many tracks.

---

## 3. Key decisions (settled during brainstorming)

| Decision | Choice | Why |
|---|---|---|
| v1 scope | DSA core, full closed loop | Weakest area + universal gate; proves the engine |
| Learner profile | Near-beginner DSA, fluent Python, no time pressure | Optimize durable mastery over speed-to-cram |
| Form factor | Local web app (localhost) | Best UX for solve-loop + dashboards; no deploy/auth |
| Frontend | FastAPI + lean vanilla JS + CodeMirror (CDN) | Real editor + full flow control, no heavy npm build |
| Problem source | Curated seed bank + AI-generated variants | Serves "always re-solve a **novel** instance" |
| Seed scope | Full roadmap, thin per pattern (~3 problems each) | Broad coverage sooner; AI variants add depth |
| AI tutor/grader | Claude Code skill via file-based handoff | Uses subscription (no API cost), no copy-paste friction |
| Skill packaging | Committed in the project repo | Reproducible, portable, version-controlled artifact |

---

## 4. Architecture

Three cooperating pieces that share a filesystem:

```
┌─────────────────────┐    sessions/session-<id>.json   ┌──────────────────────┐
│   Web app           │ ──────────────────────────────▶ │  Claude Code tutor   │
│  (FastAPI + browser)│                                  │  skill (IN-REPO)     │
│                     │ ◀────────────────────────────── │                      │
│  • solve view       │    sessions/verdict-<id>.json    │  • Socratic hints    │
│  • dashboards       │                                  │  • grade (composite) │
│  • code judge       │                                  │  • approach classify │
│  • FSRS scheduler   │                                  │  • error-code assign │
│  • mastery model    │                                  │  • self-expl check   │
│  • SQLite store     │                                  │  • variant generation│
└─────────────────────┘                                  └──────────────────────┘
```

- **Web app** — the mechanics: serves problems, hosts the editor, runs the judge, holds all state, runs the scheduler and mastery model, renders dashboards. Python 3.11+, FastAPI, SQLite.
- **Tutor skill** — the intelligence: a version-controlled Claude Code skill (with slash commands) in the repo. Reads a session file, performs tutoring/grading/classification/generation in the Claude Code chat, writes a structured verdict file back.
- **The contract** — the JSON schemas of `session-<id>.json` (tool → tutor) and `verdict-<id>.json` (tutor → tool). This is the most important interface in the system; both sides evolve independently behind it.

### Component boundaries (each independently understandable/testable)
1. **Store** (`store/`) — SQLite schema + data-access layer. One purpose: persist and query all state.
2. **Scheduler** (`scheduler/`) — FSRS engine + session composer. Input: current item states + config. Output: an ordered session plan. Pure logic, no I/O beyond the store.
3. **Problem service** (`problems/`) — loads seed content, requests/validates AI variants, selects the concrete instance to serve. Owns the "novel instance" guarantee.
4. **Judge** (`judge/`) — executes a user's Python against a problem's tests in a sandboxed subprocess (timeout + resource limits). Output: correctness + timing.
5. **Handoff** (`handoff/`) — writes session files, watches for / reads verdict files, validates them against the schema. The bridge to the tutor skill.
6. **Mastery model** (`mastery/`) — computes per-pattern mastery signals and the advancement gate from the review log.
7. **Web layer** (`web/`) — FastAPI routes + static front end (HTML/JS/CodeMirror).
8. **Tutor skill** (`skill/`) — the in-repo Claude Code skill + slash commands, plus the shared JSON schema definitions.

---

## 5. The core solve loop

1. **Compose session** — scheduler picks FSRS-due patterns/problems, sets the blocked-vs-interleaved ratio from each pattern's maturity, and targets problems at ~80–90% predicted success (the learner's edge / ZPD).
2. **Show problem cold** — statement only; **no pattern label, no solution**.
3. **Recall gate (active retrieval)** — learner names the pattern, states the approach in 2–4 sentences, and predicts time/space complexity **before coding**. Captured as a retrieval attempt independent of code outcome.
4. **Code** — learner writes the solution in the CodeMirror editor.
5. **Hint ladder (optional; each hint degrades the grade)** — category → invariant → pseudocode → worked step. Served from pre-authored tiered hints (offline) and/or the tutor skill (adaptive).
6. **Submit → judge** — runs the attempt against tests; reports correctness + runtime.
7. **Tutor handoff** — app writes `session-<id>.json`; learner runs the tutor slash command in Claude Code; skill grades (Again/Hard/Good/Easy from correctness + complexity-optimality + time + hints used), classifies the approach actually used, assigns an error-taxonomy code, checks the self-explanation, and writes `verdict-<id>.json`.
8. **Ingest verdict** — app updates FSRS state (pattern + problem), mastery signals, and the error journal.
9. **Self-explanation prompt** — learner explains *why* the approach/invariant is correct (retrieval + self-explanation effect); stored, optionally tutor-scored.
10. **Session summary** — what advanced, what's due next, flagged weak patterns.

### Fallback (away from Claude Code)
The app can emit the tutoring/grading prompt as copy-paste text and accept a pasted verdict, so the loop still closes without the file handoff.

---

## 6. Learning-science mechanics

These are the design's reason for existing; each maps to research.

- **Spaced repetition (FSRS) at the pattern level** (primary item) + light problem-instance level. Re-reviews of a pattern draw a **fresh instance**, never the same problem — re-solving an identical problem measures episodic memory of the solution, not pattern mastery. (This is why AI variant generation is load-bearing.)
- **Active recall / retrieval practice** — the recall gate (step 3) forces retrieval of the *approach* before any code; hints are graduated retrieval, not answer reveals; feedback comes *after* a genuine attempt.
- **Deliberate practice** — problems served at the learner's edge; immediate correctness+complexity feedback; repetition that targets the *specific* logged weakness, not random new problems.
- **Interleaving vs. blocking** — new pattern gets a short **blocked** mini-set to build the schema; as it matures, it folds into **interleaved** sessions that mix **confusable** patterns (e.g., sliding-window vs. two-pointers, BFS vs. DFS, backtracking vs. DP) to train cold discrimination. A `blocked_ratio` decreases with pattern maturity.
- **Desirable difficulties + adaptive calibration** — spacing, interleaving, and scaffolding-fade are applied on purpose; difficulty targets ~80–90% success (ZPD / ~85% rule). If success ≈100%, step up; if <~70%, step down or drop to worked examples.
- **Phase progression per pattern:** *Acquisition* (worked examples → faded worked examples, blocked mini-set) → *Retrieval* (unaided novel instances, recall gates, hint ladder) → *Consolidation* (interleaved, faded scaffolding, higher surface novelty, composition/far-transfer).
- **Metacognition** — mandatory self-explanation prompts; a structured, taxonomy-coded **error journal**; tracking predicted-vs-actual outcome to surface overconfidence.

### Error taxonomy (drives scheduling & generation)
`pattern_misidentification` · `approach_correct_execution_bug` (off-by-one, base case, boundary) · `complexity_suboptimal` · `incomplete_knowledge` (missing DS/API) · `got_stuck_no_idea` · `careless / time_pressure`.
Repeated `pattern_misidentification` → more interleaved discrimination drills; repeated base-case `execution_bug` → generate edge-case-heavy variants; etc.

---

## 7. Mastery model

Per-pattern mastery is measured on **held-out, never-seen instances** — never on re-solves of practiced problems. Signals combined into a mastery score + advancement gate:

1. **Transfer breadth** — count of distinct, surface-different novel instances solved unaided & correctly.
2. **First-attempt success on novel instances** — cleanest signal.
3. **Pattern-identification accuracy** — from the recall gate, especially in *interleaved* context. High solve-rate + low ID-rate ⇒ memorization, not mastery (flagged).
4. **Fluency** — time-to-plan and time-to-solve trending down and below threshold; low hint usage.
5. **Optimal complexity on first try** — reaches optimal approach without first coding brute force.
6. **Far-transfer / composition** — solves problems combining the pattern with another; weighted highest.
7. **Retention across a spacing gap** — high FSRS stability (survives a real interval).
8. **Self-explanation quality** — explanations reference the underlying principle/invariant, not surface cues (tutor-scored).

**Mastery gate (initial criterion, tunable):** ≥4 distinct-surface novel instances solved first-try, unaided, at optimal complexity; pattern-ID accuracy ≥90% in interleaved sessions; ≥1 far-transfer/composition problem solved; FSRS stability above threshold. Below the gate → stay in rotation with targeted remediation. Guard explicitly against the memorization trap.

---

## 8. Pattern taxonomy & seed content

~22–24 patterns, dependency-ordered (roadmap):

Arrays & Hashing → Two Pointers → Sliding Window → Stack (+ Monotonic Stack) → Prefix Sum → Binary Search (+ binary-search-on-answer) → Linked List (fast/slow, in-place reversal) → Trees (BFS, DFS) → Tries → Heaps / Top-K → Two Heaps → Intervals (merge) → Backtracking / Subsets → Graphs (matrix BFS/DFS, islands) → Union-Find → Topological Sort → K-way Merge → Cyclic Sort → 1-D DP (Fibonacci-style) → 0/1 Knapsack → Unbounded Knapsack → 2-sequence DP (LCS / edit distance) → Interval/Palindrome DP → Bit Manipulation (XOR tricks).

**Seed per pattern (v1, "full roadmap, thin"):** a concept explainer + 1 worked example + ~3 vetted seed problems. Each seed problem carries: statement, reference solution, test cases, and tiered hints.

**AI variant generation:** beyond the seed, the tutor skill generates a **novel instance** of a given pattern at a target difficulty. Every generated problem is **validated by executing its reference solution against its generated tests** before it is ever served. Invalid generations are rejected/regenerated.

---

## 9. State-file contract (tool ↔ tutor)

The precise field lists are finalized in the implementation plan; the shape:

**`session-<id>.json` (tool → tutor)** — everything the tutor needs, self-contained:
- `problem`: statement, pattern(s), difficulty, reference solution, tests, tiered hints
- `attempt`: the learner's code, judge result (pass/fail per test, runtime)
- `recall`: learner's stated pattern guess, approach, predicted complexity
- `hints_used`: count + which tiers
- `history`: compact prior performance on this pattern (for calibrating tutoring)
- `request`: what the tutor should do this turn (e.g., `hint`, `grade`, `generate_variant`)

**`verdict-<id>.json` (tutor → tool)** — structured, machine-ingestible:
- `grade`: one of `again` | `hard` | `good` | `easy`
- `approach_used`: classified approach / pattern actually applied
- `error_code`: from the error taxonomy (nullable)
- `complexity_ok`: bool + observed vs. optimal
- `self_explanation_score`: principle-level vs. surface (nullable)
- `feedback`: free-text Socratic feedback surfaced to the learner
- `next_hint`: (when `request=hint`) the next graduated hint only

Both files are schema-validated on read; malformed verdicts are rejected with a clear error rather than silently corrupting state.

---

## 10. Technology

- **Language:** Python 3.11+
- **Backend:** FastAPI (serves API + static front end)
- **Store:** SQLite (single-user, zero-config); accessed via a thin data layer
- **Frontend:** static HTML/CSS/vanilla JS, **CodeMirror** (via CDN) for the editor — no npm build toolchain
- **Judge:** sandboxed Python subprocess (timeout + resource limits)
- **Tutor:** in-repo Claude Code skill + slash commands, sharing JSON state files
- **Scheduler:** FSRS (default published weights in v1; personal fitting deferred)

---

## 11. Data model (initial)

- **pattern** — id, name, roadmap_order, prerequisites, concept_explainer, phase-config
- **problem** — id, pattern_id(s), origin (`seed` | `generated`), difficulty vector, statement, reference_solution, tests, tiered_hints, surface_features
- **fsrs_state** — polymorphic (pattern-level and problem-level): stability, difficulty, last_review, next_due, desired_retention, state
- **attempt** — id, problem_id, session_id, code, judge_result, recall (pattern-guess/approach/predicted-complexity), hints_used, time_to_plan, time_to_solve, timestamps
- **review_log** — one row per graded review (full FSRS log): elapsed_days, grade, correctness, complexity_ok, hints, R_predicted — required for future parameter fitting
- **error_log** — attempt_id, error_code, free-text reflection
- **session** — id, plan (ordered items), blocked_ratio, summary
- **mastery** — pattern_id, computed signals, mastery_score, gate_status

---

## 12. Error handling

- **Judge**: enforce timeout + memory cap; capture stdout/stderr; distinguish compile/runtime error vs. wrong-answer vs. timeout; never let learner code hang or affect the host.
- **Handoff**: validate verdict JSON against schema on read; on malformed/missing verdict, surface a clear actionable error and keep the attempt re-gradable (no partial state corruption).
- **AI variant generation**: reject any generated problem whose reference solution fails its own tests; cap regeneration attempts, then fall back to a seed instance.
- **Store**: single-writer SQLite; wrap multi-step updates (verdict ingestion) in transactions so scheduler/mastery/journal update atomically.

---

## 13. Testing strategy

- **Scheduler / FSRS** — unit tests against known FSRS reference vectors; property tests (intervals monotonic in stability, due-ordering correctness).
- **Mastery model** — unit tests: memorization-trap detection (high solve, low ID), gate boundary conditions.
- **Judge** — tests for correct/incorrect/timeout/error submissions; sandbox escape/hang resistance.
- **Handoff** — round-trip session→verdict schema validation; malformed-verdict rejection.
- **Problem service** — generated-problem validation (reference solution must pass its tests); "novel instance" selection never returns an already-solved problem for a review.
- **Integration** — one full loop end-to-end with a stubbed tutor verdict.

---

## 14. Success criteria

1. The learner can run a spaced, interleaved session end-to-end: cold problem → recall gate → code → judge → tutor verdict → state update → summary.
2. Re-reviews of a pattern serve **novel** instances, never a repeat.
3. Mastery advances only on the criterion gate, measured on held-out instances; the memorization trap is detected and flagged.
4. The error journal demonstrably changes what gets scheduled next.
5. Zero API cost: all tutoring/grading/generation runs through the in-repo Claude Code skill.
6. The engine's track-specific pieces (taxonomy, seed content, problem service) are cleanly separable, so a second track (e.g., SQL) can be added without touching the scheduler/mastery/handoff core.
