import json

from algotrainer.pattern_docs import load_all_pattern_docs, load_pattern_doc
from algotrainer.patterns import PATTERNS

VALID = {
    "id": "x", "summary": "s", "lesson": "l", "recognize_when": ["a"],
    "complexity": {"time": "O(n)", "space": "O(1)", "notes": "n"},
    "template": "def f():\n    pass\n", "gotchas": ["g"], "examples": ["e"],
}


def test_valid_doc_loads(tmp_path):
    (tmp_path / "x.json").write_text(json.dumps(VALID))
    doc = load_pattern_doc("x", tmp_path)
    assert doc is not None and doc["summary"] == "s"


def test_missing_doc_is_none(tmp_path):
    assert load_pattern_doc("nope", tmp_path) is None


def test_invalid_doc_rejected(tmp_path):
    bad = {**VALID, "template": ""}  # empty template fails validation
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    assert load_pattern_doc("bad", tmp_path) is None


def test_load_all_skips_invalid(tmp_path):
    (tmp_path / "good.json").write_text(json.dumps({**VALID, "id": "good"}))
    (tmp_path / "broken.json").write_text('{"id": "broken"}')  # missing required fields
    ids = set(load_all_pattern_docs(tmp_path))
    assert ids == {"good"}


def test_every_registry_pattern_has_a_valid_doc():
    """Coverage gate: the library must document all 18 canonical patterns."""
    docs = load_all_pattern_docs()
    registry_ids = {p.id for p in PATTERNS}
    missing = registry_ids - set(docs)
    assert not missing, f"patterns without a valid reference doc: {sorted(missing)}"


def test_doc_without_lesson_is_invalid(tmp_path):
    missing_lesson = {k: v for k, v in VALID.items() if k != "lesson"}
    (tmp_path / "no-lesson.json").write_text(json.dumps(missing_lesson))
    assert load_pattern_doc("no-lesson", tmp_path) is None
