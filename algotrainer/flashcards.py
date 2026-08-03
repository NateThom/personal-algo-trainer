"""Pure flashcard logic: how a recognition card's MCQ options are built, how
it's graded, and how a typed template compares to the reference. No I/O — the
web layer wires this to Store and the pattern-doc loader. All 18 patterns'
cards are available from day one (no unlock gating) — see the design doc for
why that's a deliberate choice, not an oversight."""
import difflib
import random

from algotrainer.patterns import confusable_group
from algotrainer.scheduler import RATING_BY_NAME

CARD_TYPES: tuple[str, ...] = ("recognition", "complexity", "template", "gotcha")


def build_recognition_card(
    pattern_id: str, doc: dict, all_pattern_ids: list[str], rng: random.Random
) -> dict:
    """A recognition MCQ: a randomly-chosen recognize_when signal for
    pattern_id, plus 3 distractor pattern ids (preferring the declared
    confusable group, padded with random other patterns when that group is
    smaller than 3), shuffled into a 4-option list."""
    signal = rng.choice(doc["recognize_when"])
    distractors = sorted(confusable_group(pattern_id) - {pattern_id})
    rng.shuffle(distractors)
    distractors = distractors[:3]
    if len(distractors) < 3:
        pool = [pid for pid in all_pattern_ids if pid != pattern_id and pid not in distractors]
        rng.shuffle(pool)
        distractors += pool[: 3 - len(distractors)]
    options = [pattern_id] + distractors
    rng.shuffle(options)
    return {"signal": signal, "options": options, "correct": pattern_id}


def grade_recognition(selected: str, correct: str) -> int:
    """MCQ correctness maps directly to an FSRS rating: correct -> good,
    incorrect -> again. No partial credit."""
    return RATING_BY_NAME["good"] if selected == correct else RATING_BY_NAME["again"]


def diff_template(reference: str, typed: str) -> list[dict]:
    """Line-level diff between the reference template and what was typed, both
    whitespace-normalized (collapsed internal whitespace, stripped
    leading/trailing newlines) so indentation differences don't dominate."""
    def _norm_lines(text: str) -> list[str]:
        return [" ".join(line.split()) for line in text.strip("\n").splitlines()]

    ref_lines = _norm_lines(reference)
    typed_lines = _norm_lines(typed)
    matcher = difflib.SequenceMatcher(a=ref_lines, b=typed_lines, autojunk=False)
    return [
        {"op": tag, "reference": ref_lines[i1:i2], "typed": typed_lines[j1:j2]}
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
    ]
