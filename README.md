# AlgoTrainer

A personal algorithm-practice trainer: a local web app serving pattern-based
coding problems with an FSRS spaced-repetition schedule, a recall gate, graduated
hints, and a Claude Code skill that grades sessions and generates novel variants.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The **editable install (`-e`) is required**, not just convenient: the app derives
its database (`algotrainer.db`), `sessions/`, and `content/generated/` paths from
the package's location in the repo. A plain `pip install .` would silently put
them inside site-packages and break the Claude Code handoff.

## Run

```bash
algotrainer            # or: python -m algotrainer
```

Serves at `http://127.0.0.1:8000` (open it in a browser; nothing auto-opens).
The database and `sessions/` directory are created automatically on first use.
The port is currently fixed — edit `algotrainer/__main__.py` if 8000 is taken.

## Tests

```bash
pytest
```

## Docs

- [Using the tutor](docs/USING_THE_TUTOR.md) — grading sessions and generating
  variants with the `algotrainer-tutor` Claude Code skill.
- In-app **Guide** and **Methodology** pages (nav bar) — workflow and the
  learning-science design.
- `content/problems/` — the seed problem bank; `content/patterns/` — the 18
  pattern teaching docs.
