"""The pattern taxonomy: roadmap order + confusable groupings.
Pure metadata; drives the session composer and mastery display."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternMeta:
    id: str
    name: str
    order: int
    confusable_with: tuple[str, ...]


# Dependency-ordered roadmap (subset with seed coverage first, then the broader
# taxonomy as metadata). confusable_with need only be declared one direction;
# confusable_group() makes it symmetric.
PATTERNS: tuple[PatternMeta, ...] = (
    PatternMeta("arrays-hashing", "Arrays & Hashing", 1, ()),
    PatternMeta("two-pointers", "Two Pointers", 2, ("sliding-window",)),
    PatternMeta("sliding-window", "Sliding Window", 3, ("two-pointers",)),
    PatternMeta("stack", "Stack", 4, ()),
    PatternMeta("binary-search", "Binary Search", 5, ()),
    PatternMeta("linked-list", "Linked List", 6, ()),
    PatternMeta("trees", "Trees (BFS/DFS)", 7, ("graphs",)),
    PatternMeta("tries", "Tries", 8, ()),
    PatternMeta("heaps", "Heaps / Top-K", 9, ()),
    PatternMeta("backtracking", "Backtracking", 10, ("dp-1d",)),
    PatternMeta("graphs", "Graphs", 11, ("trees",)),
    PatternMeta("dp-1d", "1-D DP", 12, ("backtracking",)),
    PatternMeta("dp-2d", "2-D DP", 13, ("dp-1d",)),
)

_BY_ID = {p.id: p for p in PATTERNS}


def pattern_meta(pid: str) -> PatternMeta | None:
    return _BY_ID.get(pid)


def confusable_group(pid: str) -> set[str]:
    group = {pid}
    meta = _BY_ID.get(pid)
    if meta:
        group.update(meta.confusable_with)
    # symmetric closure: any pattern that lists pid as confusable
    for p in PATTERNS:
        if pid in p.confusable_with:
            group.add(p.id)
    return group


def roadmap_order(pid: str) -> int:
    meta = _BY_ID.get(pid)
    return meta.order if meta else 10_000
