from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "algotrainer-tutor" / "SKILL.md"


def test_skill_file_exists():
    assert SKILL.exists()


def test_skill_frontmatter_name():
    text = SKILL.read_text()
    assert text.startswith("---")
    assert "name: algotrainer-tutor" in text


def test_skill_references_write_verdict_and_grades():
    text = SKILL.read_text().lower()
    assert "write_verdict.py" in text
    # the four FSRS grade names must be documented
    for g in ("again", "hard", "good", "easy"):
        assert g in text
