from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "algotrainer-tutor"


def test_variant_reference_exists():
    assert (BASE / "references" / "variant.md").exists()


def test_skill_documents_variant_mode():
    text = (BASE / "SKILL.md").read_text().lower()
    assert "add_variant.py" in text
    assert "variant" in text
