import pytest

from algotrainer.generated import load_generated, save_generated_problem

CAND = {
    "id": "two-sum-var1", "pattern": "arrays-hashing", "title": "Two Sum Variant",
    "difficulty": "easy", "statement": "s", "function_name": "f",
    "starter_code": "def f(x):\n    pass\n",
    "reference_solution": "def f(x):\n    return x * 2\n",
    "tests": [{"args": [2], "expected": 4}],
    "hints": ["hint"],
}


def test_save_then_load(tmp_path):
    save_generated_problem(CAND, existing_ids=set(), generated_dir=tmp_path)
    probs = load_generated(tmp_path)
    assert [p.id for p in probs] == ["two-sum-var1"]


def test_reject_invalid_without_writing(tmp_path):
    bad = {**CAND, "tests": [{"args": [2], "expected": 999}]}
    with pytest.raises(ValueError):
        save_generated_problem(bad, existing_ids=set(), generated_dir=tmp_path)
    assert list(tmp_path.glob("*.json")) == []


def test_reject_id_collision(tmp_path):
    with pytest.raises(ValueError):
        save_generated_problem(CAND, existing_ids={"two-sum-var1"}, generated_dir=tmp_path)


def test_load_skips_invalid_file(tmp_path):
    (tmp_path / "broken.json").write_text('{"id": "broken"}')  # bad shape
    save_generated_problem(CAND, existing_ids=set(), generated_dir=tmp_path)
    ids = {p.id for p in load_generated(tmp_path)}
    assert ids == {"two-sum-var1"}  # broken skipped, valid loaded
