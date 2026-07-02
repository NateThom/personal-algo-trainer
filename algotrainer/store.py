import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS card (
    problem_id TEXT PRIMARY KEY,
    card_json  TEXT NOT NULL,
    next_due   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id TEXT NOT NULL,
    code TEXT NOT NULL,
    recall_pattern TEXT,
    recall_approach TEXT,
    recall_complexity TEXT,
    judge_passed INTEGER NOT NULL,
    hints_used INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    rating INTEGER NOT NULL,
    review_log_json TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pattern_card (
    pattern   TEXT PRIMARY KEY,
    card_json TEXT NOT NULL,
    next_due  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graded_attempt (
    attempt_id INTEGER PRIMARY KEY,
    problem_id TEXT NOT NULL,
    pattern TEXT NOT NULL,
    recall_pattern TEXT,
    hints_used INTEGER NOT NULL,
    judge_passed INTEGER NOT NULL,
    grade TEXT NOT NULL,
    complexity_ok INTEGER,
    error_code TEXT,
    reviewed_at TEXT NOT NULL
);
"""


def _iso(dt: datetime) -> str:
    assert dt.tzinfo is not None, "datetime must be timezone-aware UTC"
    return dt.astimezone(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: str | Path):
        # check_same_thread=False: FastAPI runs sync route handlers in a worker
        # threadpool, so requests may reach this connection from a thread other
        # than the one that constructed it. A single lock below serializes all
        # access, so this stays safe without a per-request connection pool.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def get_card(self, problem_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT card_json FROM card WHERE problem_id = ?", (problem_id,)
            ).fetchone()
        return row[0] if row else None

    def save_card(self, problem_id: str, card_json: str, next_due: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO card(problem_id, card_json, next_due) VALUES(?,?,?) "
                "ON CONFLICT(problem_id) DO UPDATE SET card_json=excluded.card_json, "
                "next_due=excluded.next_due",
                (problem_id, card_json, _iso(next_due)),
            )
            self._conn.commit()

    def all_card_due(self, now: datetime) -> dict[str, datetime]:
        with self._lock:
            rows = self._conn.execute("SELECT problem_id, next_due FROM card").fetchall()
        return {pid: datetime.fromisoformat(due) for pid, due in rows}

    def get_attempt(self, attempt_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT problem_id, recall_pattern, hints_used, judge_passed "
                "FROM attempt WHERE id = ?", (attempt_id,)
            ).fetchone()
        if row is None:
            return None
        return {"problem_id": row[0], "recall_pattern": row[1],
                "hints_used": row[2], "judge_passed": bool(row[3])}

    def attempt_has_review(self, attempt_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM review WHERE attempt_id = ? LIMIT 1", (attempt_id,)
            ).fetchone()
        return row is not None

    def record_attempt(
        self,
        problem_id: str,
        code: str,
        recall_pattern: str | None,
        recall_approach: str | None,
        recall_complexity: str | None,
        judge_passed: bool,
        hints_used: int,
        created_at: datetime,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO attempt(problem_id, code, recall_pattern, recall_approach, "
                "recall_complexity, judge_passed, hints_used, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (problem_id, code, recall_pattern, recall_approach, recall_complexity,
                 int(judge_passed), hints_used, _iso(created_at)),
            )
            self._conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    def record_review(self, attempt_id: int, problem_id: str, rating: int, review_log_json: str, reviewed_at: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO review(attempt_id, problem_id, rating, review_log_json, reviewed_at) "
                "VALUES(?,?,?,?,?)",
                (attempt_id, problem_id, rating, review_log_json, _iso(reviewed_at)),
            )
            self._conn.commit()

    def ingest_verdict(
        self, attempt_id: int, problem_id: str, rating: int, card_json: str, next_due: datetime, review_log_json: str, reviewed_at: datetime,
    ) -> None:
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                self._conn.execute(
                    "INSERT INTO card(problem_id, card_json, next_due) VALUES(?,?,?) "
                    "ON CONFLICT(problem_id) DO UPDATE SET card_json=excluded.card_json, "
                    "next_due=excluded.next_due",
                    (problem_id, card_json, _iso(next_due)),
                )
                self._conn.execute(
                    "INSERT INTO review(attempt_id, problem_id, rating, review_log_json, reviewed_at) "
                    "VALUES(?,?,?,?,?)",
                    (attempt_id, problem_id, rating, review_log_json, _iso(reviewed_at)),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def get_pattern_card(self, pattern: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT card_json FROM pattern_card WHERE pattern = ?", (pattern,)
            ).fetchone()
            return row[0] if row else None

    def save_pattern_card(self, pattern: str, card_json: str, next_due: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO pattern_card(pattern, card_json, next_due) VALUES(?,?,?) "
                "ON CONFLICT(pattern) DO UPDATE SET card_json=excluded.card_json, "
                "next_due=excluded.next_due",
                (pattern, card_json, _iso(next_due)),
            )
            self._conn.commit()

    def record_graded_attempt(
        self, attempt_id: int, problem_id: str, pattern: str, recall_pattern: str | None,
        hints_used: int, judge_passed: bool, grade: str, complexity_ok: bool | None,
        error_code: str | None, reviewed_at: datetime,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO graded_attempt(attempt_id, problem_id, pattern, recall_pattern, "
                "hints_used, judge_passed, grade, complexity_ok, error_code, reviewed_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(attempt_id) DO NOTHING",
                (attempt_id, problem_id, pattern, recall_pattern, hints_used,
                 int(judge_passed), grade,
                 None if complexity_ok is None else int(complexity_ok),
                 error_code, _iso(reviewed_at)),
            )
            self._conn.commit()

    def graded_attempts_by_pattern(self, pattern: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT problem_id, recall_pattern, hints_used, judge_passed, grade, "
                "complexity_ok, error_code FROM graded_attempt WHERE pattern = ? "
                "ORDER BY attempt_id", (pattern,),
            ).fetchall()
        return [
            {"problem_id": r[0], "recall_pattern": r[1], "hints_used": r[2],
             "judge_passed": bool(r[3]), "grade": r[4],
             "complexity_ok": None if r[5] is None else bool(r[5]), "error_code": r[6]}
            for r in rows
        ]

    def error_counts_by_pattern(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT pattern, COUNT(*) FROM graded_attempt "
                "WHERE error_code IS NOT NULL GROUP BY pattern"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def all_graded_patterns(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT pattern FROM graded_attempt ORDER BY pattern"
            ).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        self._conn.close()
