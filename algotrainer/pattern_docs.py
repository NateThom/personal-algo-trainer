"""Loader for the pattern reference library (content/patterns/<id>.json).
Pure: reads JSON docs, validates shape, skips invalid ones. The registry
(patterns.py) supplies name/order/confusable; these docs supply the teaching
content (summary, lesson, recognition signals, complexity, template, gotchas, examples)."""
import json
from pathlib import Path

PATTERN_DOCS_DIR = Path(__file__).resolve().parent.parent / "content" / "patterns"

_REQUIRED = ("id", "summary", "lesson", "recognize_when", "complexity", "template")


def _valid(doc: dict) -> bool:
    if not isinstance(doc, dict) or not all(doc.get(k) for k in _REQUIRED):
        return False
    if not isinstance(doc.get("recognize_when"), list) or not doc["recognize_when"]:
        return False
    c = doc.get("complexity")
    if not isinstance(c, dict) or not c.get("time") or not c.get("space"):
        return False
    return isinstance(doc.get("template"), str) and bool(doc["template"].strip())


def load_pattern_doc(pid: str, docs_dir: Path = PATTERN_DOCS_DIR) -> dict | None:
    path = docs_dir / f"{pid}.json"
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return doc if _valid(doc) else None


def load_all_pattern_docs(docs_dir: Path = PATTERN_DOCS_DIR) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not docs_dir.exists():
        return out
    for path in sorted(docs_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if _valid(doc):
            out[doc["id"]] = doc
    return out
