"""Session composer. Blocked practice while a pattern is immature, interleaved
(with confusable patterns adjacent) once it matures; weakest patterns first."""
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class SessionPlan:
    order: list[str]
    blocked_ratio: float


def _patterns_weakest_first(patterns: set[str], error_weight: dict[str, int]) -> list[str]:
    return sorted(patterns, key=lambda p: (-error_weight.get(p, 0), p))


def compose_order(
    due: list[str],
    problem_pattern: dict[str, str],
    immature: set[str],
    error_weight: dict[str, int],
    confusable_of=None,
) -> SessionPlan:
    if not due:
        return SessionPlan(order=[], blocked_ratio=0.0)

    blocked_ids = [pid for pid in due if problem_pattern.get(pid) in immature]
    interleaved_ids = [pid for pid in due if problem_pattern.get(pid) not in immature]

    # --- blocked section: contiguous by pattern, weakest-first ---
    blocked_by_pat: dict[str, list[str]] = defaultdict(list)
    for pid in blocked_ids:
        blocked_by_pat[problem_pattern[pid]].append(pid)
    blocked_order: list[str] = []
    for pat in _patterns_weakest_first(set(blocked_by_pat), error_weight):
        blocked_order.extend(blocked_by_pat[pat])

    # --- interleaved section: round-robin across patterns, confusable-adjacent ---
    inter_by_pat: dict[str, list[str]] = defaultdict(list)
    for pid in interleaved_ids:
        inter_by_pat[problem_pattern[pid]].append(pid)
    available = _patterns_weakest_first(set(inter_by_pat), error_weight)
    inter_order: list[str] = []
    last_pat: str | None = None
    next_pat_idx = 0
    while available:
        # prefer a confusable counterpart of the last-emitted pattern
        pick = None
        if last_pat is not None and confusable_of is not None:
            group = confusable_of(last_pat) - {last_pat}
            for cand in available:
                if cand in group:
                    pick = cand
                    break
        if pick is None:
            # Round-robin: cycle through available patterns
            pick = available[next_pat_idx % len(available)]
            next_pat_idx += 1
        inter_order.append(inter_by_pat[pick].pop(0))
        last_pat = pick
        if not inter_by_pat[pick]:
            available.remove(pick)
            # Reset next_pat_idx to stay in bounds
            if available:
                next_pat_idx = next_pat_idx % len(available)

    order = blocked_order + inter_order
    return SessionPlan(order=order, blocked_ratio=len(blocked_ids) / len(due))
