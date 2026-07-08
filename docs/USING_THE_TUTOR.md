# Using the AlgoTrainer tutor

The tutor is a Claude Code skill committed at `.claude/skills/algotrainer-tutor/`.
When you work in this repo with Claude Code, it is auto-discoverable.

## Setup (first time)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The editable install (`-e`) is required — the app resolves its database,
`sessions/`, and `content/generated/` paths relative to the package source.

## Run it

Activate `.venv`, then run:

```bash
algotrainer
```

Or without the console script entry point:

```bash
python -m algotrainer
```

The app serves at `http://127.0.0.1:8000` (open it in your browser). The
database and `sessions/` directory are created automatically on first use.

## Grade a session
1. In the web app: solve a problem, click **Run tests**, then **Send to tutor**.
   Note the session id shown in the results pane (e.g. `a1b2c3d4e5f6`).
2. In Claude Code (in this repo), say: **"Use the algotrainer-tutor skill to grade
   session a1b2c3d4e5f6."** The skill reads `sessions/session-a1b2c3d4e5f6.json`,
   grades it, and writes `sessions/verdict-a1b2c3d4e5f6.json`.
3. Back in the web app, click **Ingest verdict** to update your schedule.

Mid-solve hints come from the app's own **Get hint** button (pre-authored,
graduated tiers) — the tutor skill only grades and generates variants.

## Generate a novel variant
Ask: **"Use the algotrainer-tutor skill to generate an arrays-hashing variant
(medium)."** The skill authors a fresh problem and saves it via
`scripts/add_variant.py` (which rejects it unless its reference solution passes its
own tests). Click **Reload problems** in the app to bring new variants into rotation.

## Offline / automated fallback
`scripts/stub_tutor.py <session_dir> <session_id>` writes a mechanical verdict
(used by the test suite and when you're away from Claude Code).
