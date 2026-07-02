import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from algotrainer import mastery as mastery_mod
from algotrainer.composer import compose_order
from algotrainer.content import DEFAULT_CONTENT_DIR, load_problems
from algotrainer.generated import load_generated
from algotrainer.handoff.files import read_verdict, write_session
from algotrainer.handoff.schema import SessionFile
from algotrainer.judge import run_submission
from algotrainer.patterns import confusable_group, pattern_meta, roadmap_order
from algotrainer.scheduler import RATING_BY_NAME, SrsScheduler
from algotrainer.store import Store

_STATIC = Path(__file__).resolve().parent / "static"


class JudgeBody(BaseModel):
    problem_id: str
    code: str


class SessionBody(BaseModel):
    problem_id: str
    code: str
    recall: dict
    judge_passed: bool
    hints_used: int = 0


class IngestBody(BaseModel):
    session_id: str


class HintBody(BaseModel):
    problem_id: str
    tier: int


def create_app(db_path, content_dir, session_dir) -> FastAPI:
    content_dir = content_dir or DEFAULT_CONTENT_DIR
    session_dir = Path(session_dir)
    app = FastAPI(title="AlgoTrainer")
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    store = Store(db_path)
    scheduler = SrsScheduler()
    problems: dict = {}

    def _reload_problems() -> int:
        problems.clear()
        for p in load_problems(content_dir):
            problems[p.id] = p
        for p in load_generated():
            problems[p.id] = p
        return len(problems)

    _reload_problems()

    def _pattern_stability(pattern: str) -> float:
        from fsrs import Card
        cj = store.get_pattern_card(pattern)
        return Card.from_json(cj).stability if cj else 0.0

    def _mastery_for(pattern: str):
        rows = store.graded_attempts_by_pattern(pattern)
        return mastery_mod.compute_pattern_mastery(pattern, rows, _pattern_stability(pattern))

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    @app.get("/api/next")
    def next_problem():
        now = datetime.now(timezone.utc)
        due_map = store.all_card_due(now)
        ids = scheduler.due_problem_ids(due_map, list(problems), now)
        if not ids:
            return {"problem": None}
        problem_pattern = {pid: problems[pid].pattern for pid in ids}
        # "Immature" for blocked-practice purposes is deliberately keyed on
        # transfer breadth (initial exposure), NOT the full mastery gate: a
        # pattern with breadth but a memorization trap / low stability should
        # still graduate to interleaving, where discrimination is trained.
        immature = {
            pat for pat in set(problem_pattern.values())
            if _mastery_for(pat).transfer_breadth < mastery_mod.GATE_BREADTH
        }
        plan = compose_order(
            ids, problem_pattern, immature, store.error_counts_by_pattern(),
            confusable_of=confusable_group,
        )
        attempted = store.attempted_problem_ids()
        pid = next((x for x in plan.order if x not in attempted), plan.order[0])
        p = problems[pid]
        return {"problem": {
            "id": p.id, "title": p.title, "pattern": p.pattern,
            "difficulty": p.difficulty, "statement": p.statement,
            "function_name": p.function_name, "starter_code": p.starter_code,
        }}

    @app.post("/api/reload")
    def reload():
        return {"count": _reload_problems()}

    @app.get("/api/mastery")
    def mastery():
        out = []
        for pat in store.all_graded_patterns():
            m = _mastery_for(pat)
            meta = pattern_meta(pat)
            out.append({
                "pattern": pat, "name": meta.name if meta else pat,
                "attempts": m.attempts, "transfer_breadth": m.transfer_breadth,
                "solve_rate": m.solve_rate, "pattern_id_accuracy": m.pattern_id_accuracy,
                "optimal_rate": m.optimal_rate, "stability": m.stability,
                "memorization_trap": m.memorization_trap,
                "mastery_score": m.mastery_score, "mastered": m.mastered,
            })
        out.sort(key=lambda e: roadmap_order(e["pattern"]))
        return {"patterns": out}

    @app.post("/api/judge")
    def judge(body: JudgeBody):
        p = problems[body.problem_id]
        r = run_submission(body.code, p.function_name, p.tests)
        return {
            "passed": r.passed, "error": r.error, "runtime_ms": r.runtime_ms,
            "cases": [
                {"args": c.args, "expected": c.expected, "got": c.got,
                 "passed": c.passed, "error": c.error} for c in r.cases
            ],
        }

    @app.post("/api/session")
    def session(body: SessionBody):
        now = datetime.now(timezone.utc)
        attempt_id = store.record_attempt(
            body.problem_id, body.code, body.recall.get("pattern"),
            body.recall.get("approach"), body.recall.get("complexity"),
            body.judge_passed, body.hints_used, now,
        )
        sid = uuid.uuid4().hex[:12]
        p = problems[body.problem_id]
        sf = SessionFile(
            session_id=sid, attempt_id=attempt_id,
            problem={"id": p.id, "title": p.title, "pattern": p.pattern,
                     "statement": p.statement, "reference_solution": p.reference_solution},
            attempt={"code": body.code, "judge_passed": body.judge_passed},
            recall=body.recall, hints_used=body.hints_used, request="grade",
        )
        write_session(session_dir, sf)
        return {"session_id": sid, "attempt_id": attempt_id}

    @app.post("/api/hint")
    def hint(body: HintBody):
        p = problems.get(body.problem_id)
        if p is None:
            raise HTTPException(status_code=404, detail="unknown problem")
        hints = p.hints
        if body.tier < 0 or body.tier >= len(hints):
            return {"hint": None, "tier": body.tier, "has_more": False}
        return {"hint": hints[body.tier], "tier": body.tier,
                "has_more": body.tier + 1 < len(hints)}

    @app.post("/api/verdict/ingest")
    def ingest(body: IngestBody):
        try:
            verdict = read_verdict(session_dir, body.session_id)
        except FileNotFoundError:
            return JSONResponse({"error": "verdict not found yet"}, status_code=409)

        if verdict.session_id != body.session_id:
            return JSONResponse({"error": "verdict/session mismatch"}, status_code=400)

        attempt = store.get_attempt(verdict.attempt_id)
        if attempt is None:
            return JSONResponse({"error": "unknown attempt"}, status_code=400)
        if attempt["problem_id"] != verdict.problem_id:
            return JSONResponse({"error": "verdict/attempt problem mismatch"}, status_code=400)

        if store.attempt_has_review(verdict.attempt_id):
            return {"grade": verdict.grade, "next_due": None,
                    "feedback": verdict.feedback, "already_ingested": True}

        now = datetime.now(timezone.utc)
        rating = RATING_BY_NAME[verdict.grade]
        card_json = store.get_card(verdict.problem_id)
        new_card_json, next_due, log_json = scheduler.review(card_json, rating, now)
        store.ingest_verdict(
            verdict.attempt_id, verdict.problem_id, rating,
            new_card_json, next_due, log_json, now,
        )

        # --- Plan 3: pattern-level FSRS + analytics row ---
        p = problems.get(verdict.problem_id)
        pattern = p.pattern if p else verdict.problem_id
        pcard = store.get_pattern_card(pattern)
        new_pcard, p_next_due, _ = scheduler.review(pcard, rating, now)
        store.save_pattern_card(pattern, new_pcard, p_next_due)
        store.record_graded_attempt(
            attempt_id=verdict.attempt_id, problem_id=verdict.problem_id, pattern=pattern,
            recall_pattern=(attempt or {}).get("recall_pattern"),
            hints_used=(attempt or {}).get("hints_used", 0),
            judge_passed=(attempt or {}).get("judge_passed", False),
            grade=verdict.grade, complexity_ok=verdict.complexity_ok,
            error_code=verdict.error_code, reviewed_at=now,
        )

        return {"grade": verdict.grade, "next_due": next_due.isoformat(),
                "feedback": verdict.feedback, "already_ingested": False}

    return app
