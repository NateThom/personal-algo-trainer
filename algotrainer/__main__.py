from pathlib import Path

import uvicorn

from algotrainer.web.app import create_app

_ROOT = Path(__file__).resolve().parent.parent

app = create_app(
    db_path=_ROOT / "algotrainer.db",
    content_dir=None,
    session_dir=_ROOT / "sessions",
)


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
