from __future__ import annotations

import shutil
from pathlib import Path

from scripts.merge_schools import build_status
from scripts.utils import DATA_DIR, DOCS_DIR, read_json, write_json


def main() -> None:
    status = read_json(DATA_DIR / "status.json", default=None)
    if status is None:
        status = build_status()
        write_json(DATA_DIR / "status.json", status)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DOCS_DIR / "status.json", status)
    history_path = DATA_DIR / "history.csv"
    if history_path.exists():
        shutil.copy2(history_path, DOCS_DIR / "history.csv")
    print("[build_dashboard] docs/status.json and docs/history.csv updated")


if __name__ == "__main__":
    main()
