from pathlib import Path

from algotrainer.handoff.schema import SessionFile, Verdict


def write_session(session_dir: Path, session: SessionFile) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"session-{session.session_id}.json"
    path.write_text(session.model_dump_json(indent=2))
    return path


def read_verdict(session_dir: Path, session_id: str) -> Verdict:
    path = session_dir / f"verdict-{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No verdict at {path}")
    return Verdict.model_validate_json(path.read_text())
