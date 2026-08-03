import random
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
from algotrainer.flashcards import (
    CARD_TYPES, build_recognition_card, diff_template, grade_recognition,
)
from algotrainer.generated import GENERATED_DIR, load_generated
from algotrainer.handoff.files import read_verdict, write_session
from algotrainer.handoff.schema import SessionFile
from algotrainer.judge import run_submission
from algotrainer.pattern_docs import load_all_pattern_docs, load_pattern_doc
from algotrainer.patterns import (
    PATTERNS, confusable_group, pattern_meta, roadmap_order,
)
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


class FlashcardReviewBody(BaseModel):
    pattern: str
    card_type: str
    rating: int | None = None
    selected: str | None = None


class FlashcardDiffBody(BaseModel):
    pattern: str
    code: str


def create_app(db_path, content_dir, session_dir, generated_dir=None) -> FastAPI:
    content_dir = content_dir or DEFAULT_CONTENT_DIR
    generated_dir = generated_dir or GENERATED_DIR
    session_dir = Path(session_dir)
    app = FastAPI(title="AlgoTrainer")
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    store = Store(db_path)
    scheduler = SrsScheduler()
    problems: dict = {}

    def _reload_problems() -> int:
        nonlocal problems
        new_map = {p.id: p for p in load_problems(content_dir)}
        for p in load_generated(generated_dir):
            # seed ids win over generated on collision (setdefault keeps the seed)
            new_map.setdefault(p.id, p)
        problems = new_map
        return len(problems)

    _reload_problems()

    def _pattern_stability(pattern: str) -> float:
        from fsrs import Card
        cj = store.get_pattern_card(pattern)
        return Card.from_json(cj).stability if cj else 0.0

    def _mastery_for(pattern: str):
        rows = store.graded_attempts_by_pattern(pattern)
        return mastery_mod.compute_pattern_mastery(pattern, rows, _pattern_stability(pattern))

    def _pattern_pool(pattern: str) -> dict:
        total = sum(1 for p in problems.values() if p.pattern == pattern)
        seen = sum(
            1 for pid in store.attempted_problem_ids()
            if pid in problems and problems[pid].pattern == pattern
        )
        return {
            "total": total, "unseen": total - seen,
            "needs_more": max(0, mastery_mod.GATE_BREADTH - total),
        }

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    @app.get("/dashboard")
    def dashboard_page():
        return FileResponse(_STATIC / "dashboard.html")

    @app.get("/guide")
    def guide_page():
        return FileResponse(_STATIC / "guide.html")

    @app.get("/methodology")
    def methodology_page():
        return FileResponse(_STATIC / "methodology.html")

    @app.get("/patterns")
    def patterns_page():
        return FileResponse(_STATIC / "patterns.html")

    @app.get("/patterns/{pattern_id}")
    def patterns_detail_page(pattern_id: str):
        return FileResponse(_STATIC / "patterns_detail.html")

    @app.get("/flashcards")
    def flashcards_page():
        return FileResponse(_STATIC / "flashcards.html")

    @app.get("/flashcards/{pattern_id}")
    def flashcards_pattern_page(pattern_id: str):
        return FileResponse(_STATIC / "flashcards.html")

    @app.post("/api/reset")
    def reset():
        store.reset_progress()
        return {"ok": True}

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
        # Every id in plan.order is due. Serve due REVIEWS (already-seen) before
        # NOVEL instances, so an endless supply of new problems can't starve
        # overdue reviews — retention (the point of spaced repetition) comes first.
        # Within each class the composer's weakest-first/interleaved order is kept.
        attempted = store.attempted_problem_ids()
        reviews = [x for x in plan.order if x in attempted]
        novel = [x for x in plan.order if x not in attempted]
        pid = reviews[0] if reviews else (novel[0] if novel else plan.order[0])
        p = problems[pid]
        return {"problem": {
            "id": p.id, "title": p.title,
            "difficulty": p.difficulty, "statement": p.statement,
            "function_name": p.function_name, "starter_code": p.starter_code,
            "seen_count": store.attempt_count_for_problem(p.id),
            "pattern_pool": _pattern_pool(p.pattern),
        }}

    @app.post("/api/reload")
    def reload():
        return {"count": _reload_problems()}

    def _mastery_list():
        out = []
        for pat in store.all_graded_patterns():
            m = _mastery_for(pat)
            meta = pattern_meta(pat)
            instances = sum(1 for p in problems.values() if p.pattern == pat)
            out.append({
                "pattern": pat, "name": meta.name if meta else pat,
                "attempts": m.attempts, "transfer_breadth": m.transfer_breadth,
                "solve_rate": m.solve_rate, "pattern_id_accuracy": m.pattern_id_accuracy,
                "optimal_rate": m.optimal_rate, "stability": m.stability,
                "memorization_trap": m.memorization_trap,
                "mastery_score": m.mastery_score, "mastered": m.mastered,
                "instances": instances,
                "needs_more": max(0, mastery_mod.GATE_BREADTH - instances),
            })
        out.sort(key=lambda e: roadmap_order(e["pattern"]))
        return out

    @app.get("/api/mastery")
    def mastery():
        return {"patterns": _mastery_list()}

    @app.get("/api/patterns")
    def patterns_list():
        docs = load_all_pattern_docs()
        out = []
        for meta in PATTERNS:
            doc = docs.get(meta.id)
            out.append({
                "id": meta.id, "name": meta.name, "order": meta.order,
                "summary": doc["summary"] if doc else "",
                "has_doc": doc is not None,
                "confusable": sorted(confusable_group(meta.id) - {meta.id}),
            })
        out.sort(key=lambda e: e["order"])
        return {"patterns": out}

    @app.get("/api/patterns/{pattern_id}")
    def pattern_detail(pattern_id: str):
        meta = pattern_meta(pattern_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="unknown pattern")
        doc = load_pattern_doc(pattern_id)
        confusable_names = sorted(
            pattern_meta(pid).name
            for pid in confusable_group(pattern_id) - {pattern_id}
            if pattern_meta(pid) is not None
        )
        seed_examples = sorted(
            pid for pid, p in problems.items() if p.pattern == pattern_id
        )
        return {
            "id": meta.id, "name": meta.name, "order": meta.order,
            "summary": doc["summary"] if doc else "",
            "recognize_when": doc["recognize_when"] if doc else [],
            "complexity": doc["complexity"] if doc else {},
            "template": doc["template"] if doc else "",
            "gotchas": doc.get("gotchas", []) if doc else [],
            "examples": doc.get("examples", []) if doc else [],
            "confusable": confusable_names,
            "seed_examples": seed_examples,
        }

    @app.get("/api/flashcards/due")
    def flashcards_due():
        now = datetime.now(timezone.utc)
        docs = load_all_pattern_docs()
        due_map = store.all_flashcard_due(now)
        rng = random.Random()
        out = []
        for pattern in sorted(docs):
            doc = docs[pattern]
            meta = pattern_meta(pattern)
            for card_type in CARD_TYPES:
                due = due_map.get((pattern, card_type))
                if due is not None and due > now:
                    continue
                card = {
                    "pattern": pattern, "card_type": card_type,
                    "pattern_name": meta.name if meta else pattern,
                }
                if card_type == "recognition":
                    rc = build_recognition_card(pattern, doc, list(docs.keys()), rng)
                    card["signal"] = rc["signal"]
                    card["options"] = [
                        {"id": pid, "name": pattern_meta(pid).name if pattern_meta(pid) else pid}
                        for pid in rc["options"]
                    ]
                out.append(card)
        rng.shuffle(out)
        return {"cards": out}

    @app.post("/api/flashcards/review")
    def flashcard_review(body: FlashcardReviewBody):
        if body.card_type not in CARD_TYPES:
            raise HTTPException(status_code=404, detail="unknown card type")
        if body.card_type == "recognition":
            if body.selected is None:
                raise HTTPException(
                    status_code=400, detail="selected is required for recognition cards"
                )
            rating = grade_recognition(body.selected, body.pattern)
            correct = body.selected == body.pattern
        else:
            if body.rating is None:
                raise HTTPException(status_code=400, detail="rating is required")
            rating = body.rating
            correct = None
        now = datetime.now(timezone.utc)
        card_json = store.get_flashcard(body.pattern, body.card_type)
        new_card_json, next_due, _ = scheduler.review(card_json, rating, now)
        store.save_flashcard(body.pattern, body.card_type, new_card_json, next_due)
        return {"next_due": next_due.isoformat(), "correct": correct}

    @app.post("/api/flashcards/diff")
    def flashcard_diff(body: FlashcardDiffBody):
        doc = load_pattern_doc(body.pattern)
        if doc is None:
            raise HTTPException(status_code=404, detail="unknown pattern")
        return {"ops": diff_template(doc["template"], body.code)}

    @app.get("/api/dashboard")
    def dashboard():
        now = datetime.now(timezone.utc)
        due_map = store.all_card_due(now)
        due = scheduler.due_problem_ids(due_map, list(problems), now)
        return {
            "due_count": len(due),
            "total_problems": len(problems),
            "patterns": _mastery_list(),
            "error_counts": store.error_counts_by_pattern(),
            "next_review_due": min(due_map.values()).isoformat() if due_map else None,
        }

    @app.post("/api/judge")
    def judge(body: JudgeBody):
        p = problems.get(body.problem_id)
        if p is None:
            raise HTTPException(status_code=404, detail="unknown problem")
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
        p = problems.get(body.problem_id)
        if p is None:
            raise HTTPException(status_code=404, detail="unknown problem")
        now = datetime.now(timezone.utc)
        attempt_id = store.record_attempt(
            body.problem_id, body.code, body.recall.get("pattern"),
            body.recall.get("approach"), body.recall.get("complexity"),
            body.judge_passed, body.hints_used, now,
        )
        sid = uuid.uuid4().hex[:12]
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

    @app.get("/api/verdicts/pending")
    def verdicts_pending():
        out = []
        if session_dir.exists():
            for path in sorted(session_dir.glob("verdict-*.json")):
                sid = path.stem.removeprefix("verdict-")
                try:
                    v = read_verdict(session_dir, sid)
                except Exception:
                    continue  # malformed file: not ingestable, skip
                if not store.attempt_has_review(v.attempt_id):
                    out.append({"session_id": sid, "problem_id": v.problem_id, "grade": v.grade})
        return {"pending": out}

    @app.get("/api/verdict/status")
    def verdict_status(session_id: str):
        return {"ready": (session_dir / f"verdict-{session_id}.json").exists()}

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
            approach_used=verdict.approach_used,
            self_explanation_score=verdict.self_explanation_score,
            feedback=verdict.feedback,
        )

        return {"grade": verdict.grade, "next_due": next_due.isoformat(),
                "feedback": verdict.feedback, "already_ingested": False}

    return app
