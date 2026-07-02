"""Per-pattern mastery model. Pure functions over graded-attempt rows.
Mastery is measured on outcomes (distinct unaided-correct solves, pattern-ID
accuracy, optimality, retention), never on re-reading; the memorization trap
(high solve rate + low pattern-ID accuracy) blocks mastery."""
from dataclasses import dataclass

GATE_BREADTH = 4
GATE_ID_ACCURACY = 0.9
GATE_STABILITY = 7.0
TRAP_SOLVE_RATE = 0.8
TRAP_ID_ACCURACY = 0.6
TRAP_MIN_ATTEMPTS = 3


@dataclass
class PatternMastery:
    pattern: str
    attempts: int
    transfer_breadth: int
    solve_rate: float
    pattern_id_accuracy: float
    optimal_rate: float
    stability: float
    memorization_trap: bool
    mastery_score: float
    mastered: bool


def _frac(num: int, den: int) -> float:
    return num / den if den else 0.0


def compute_pattern_mastery(pattern: str, rows: list[dict], stability: float) -> PatternMastery:
    attempts = len(rows)
    passed = [r for r in rows if r["judge_passed"]]
    unaided_correct = {
        r["problem_id"] for r in rows if r["judge_passed"] and r["hints_used"] == 0
    }
    transfer_breadth = len(unaided_correct)
    solve_rate = _frac(len(passed), attempts)
    pattern_id_accuracy = _frac(
        sum(1 for r in rows if r["recall_pattern"] == pattern), attempts
    )
    optimal_rate = _frac(
        sum(1 for r in passed if r["complexity_ok"] is True), len(passed)
    )
    memorization_trap = (
        attempts >= TRAP_MIN_ATTEMPTS
        and solve_rate >= TRAP_SOLVE_RATE
        and pattern_id_accuracy < TRAP_ID_ACCURACY
    )
    mastery_score = round(
        0.4 * min(transfer_breadth / GATE_BREADTH, 1.0)
        + 0.3 * pattern_id_accuracy
        + 0.2 * optimal_rate
        + 0.1 * min(stability / GATE_STABILITY, 1.0),
        3,
    )
    mastered = (
        transfer_breadth >= GATE_BREADTH
        and pattern_id_accuracy >= GATE_ID_ACCURACY
        and stability >= GATE_STABILITY
        and not memorization_trap
    )
    return PatternMastery(
        pattern=pattern, attempts=attempts, transfer_breadth=transfer_breadth,
        solve_rate=round(solve_rate, 3), pattern_id_accuracy=round(pattern_id_accuracy, 3),
        optimal_rate=round(optimal_rate, 3), stability=round(stability, 3),
        memorization_trap=memorization_trap, mastery_score=mastery_score, mastered=mastered,
    )
