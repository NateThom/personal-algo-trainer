import random

from algotrainer.flashcards import (
    CARD_TYPES, build_recognition_card, diff_template, grade_recognition,
)
from algotrainer.pattern_docs import load_pattern_doc
from algotrainer.patterns import PATTERNS


def test_card_types_are_the_four_facets():
    assert set(CARD_TYPES) == {"recognition", "complexity", "template", "gotcha"}


def test_recognition_card_has_four_unique_options_including_correct():
    doc = load_pattern_doc("two-pointers")
    all_ids = [p.id for p in PATTERNS]
    rng = random.Random(0)
    card = build_recognition_card("two-pointers", doc, all_ids, rng)
    assert len(card["options"]) == 4
    assert len(set(card["options"])) == 4
    assert card["correct"] == "two-pointers"
    assert "two-pointers" in card["options"]
    assert card["signal"] in doc["recognize_when"]


def test_recognition_card_prefers_confusable_distractors():
    doc = load_pattern_doc("sliding-window")
    all_ids = [p.id for p in PATTERNS]
    rng = random.Random(1)
    card = build_recognition_card("sliding-window", doc, all_ids, rng)
    # sliding-window's declared confusable group is {two-pointers, prefix-sum} —
    # both must be offered since the group has fewer than the needed 3 slots
    assert "two-pointers" in card["options"]
    assert "prefix-sum" in card["options"]


def test_recognition_card_pads_from_pool_when_no_confusables():
    # arrays-hashing has an empty confusable_with and nothing points back at
    # it either, so all 3 distractors must come from the random-pool fallback
    doc = load_pattern_doc("arrays-hashing")
    all_ids = [p.id for p in PATTERNS]
    rng = random.Random(2)
    card = build_recognition_card("arrays-hashing", doc, all_ids, rng)
    assert len(card["options"]) == 4
    assert len(set(card["options"])) == 4


def test_grade_recognition_correct_is_good():
    assert grade_recognition("two-pointers", "two-pointers") == 3


def test_grade_recognition_incorrect_is_again():
    assert grade_recognition("sliding-window", "two-pointers") == 1


def test_diff_template_identical_text_is_all_equal():
    ops = diff_template("def f():\n    pass\n", "def f():\n    pass\n")
    assert all(op["op"] == "equal" for op in ops)


def test_diff_template_ignores_whitespace_differences():
    ops = diff_template("def f():\n    pass\n", "def f():\n  pass\n")
    assert all(op["op"] == "equal" for op in ops)


def test_diff_template_flags_real_differences():
    ops = diff_template("left, right = 0, len(arr) - 1\n", "left = 0\n")
    assert any(op["op"] != "equal" for op in ops)
