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
    PatternMeta("prefix-sum", "Prefix Sum", 5, ("sliding-window",)),
    PatternMeta("binary-search", "Binary Search", 6, ()),
    PatternMeta("linked-list", "Linked List", 7, ()),
    PatternMeta("trees", "Trees (BFS/DFS)", 8, ("graphs",)),
    PatternMeta("tries", "Tries", 9, ()),
    PatternMeta("heaps", "Heaps / Top-K", 10, ()),
    PatternMeta("intervals", "Intervals", 11, ()),
    PatternMeta("backtracking", "Backtracking", 12, ("dp-1d",)),
    PatternMeta("graphs", "Graphs", 13, ("trees", "union-find", "topological-sort")),
    PatternMeta("union-find", "Union-Find", 14, ("graphs",)),
    PatternMeta("topological-sort", "Topological Sort", 15, ("graphs",)),
    PatternMeta("dp-1d", "1-D DP", 16, ("backtracking",)),
    PatternMeta("dp-2d", "2-D DP", 17, ("dp-1d",)),
    PatternMeta("bit-manipulation", "Bit Manipulation", 18, ()),
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
