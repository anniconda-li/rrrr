from __future__ import annotations

import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TMP_DIR = PROJECT_ROOT / "tmp"
LATEST_DIR = TMP_DIR / "latest"
RUNS_DIR = TMP_DIR / "runs"


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main() -> None:
    for path in (LATEST_DIR, RUNS_DIR):
        remove_path(path)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    print("[OK] tmp cleaned")


if __name__ == "__main__":
    sys.exit(main())
