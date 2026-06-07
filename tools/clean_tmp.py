from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.paths import (
    DEFAULT_CAMERA_TEST_IMAGE,
    RUNTIME_DIRS,
    TMP_CAMERA_PREPROCESS_DIR,
    TMP_DEBUG_DIR,
    TMP_DIR,
    ensure_project_dirs,
)


CLEAN_PATHS = (
    TMP_CAMERA_PREPROCESS_DIR,
    TMP_DIR / "camera" / "latest",
    TMP_DIR / "camera" / "test",
    TMP_DIR / "audio" / "debug_reply_wav",
    TMP_DIR / "audio" / "received_wav",
    TMP_DIR / "audio" / "reply_wav",
    TMP_DIR / "runs",
    TMP_DEBUG_DIR / "test_ai_cancel",
    TMP_DIR / "test_ai_cancel",
)


def _safe_remove(path: Path) -> bool:
    if not path.exists():
        return False
    tmp_root = TMP_DIR.resolve()
    resolved = path.resolve()
    if resolved == tmp_root or tmp_root not in resolved.parents:
        raise RuntimeError(f"refuse to remove path outside tmp: {resolved}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def main() -> int:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    ensure_project_dirs()
    removed = []
    for path in CLEAN_PATHS:
        if _safe_remove(path):
            removed.append(str(path))
    ensure_project_dirs()
    print("[OK] tmp/project directories ensured")
    print(f"[OK] runtime_dirs={len(RUNTIME_DIRS)}")
    print(f"[OK] default_test_image={DEFAULT_CAMERA_TEST_IMAGE}")
    print(f"[OK] removed={removed if removed else 'none'}")
    print("[INFO] fixed camera test images live under tests/data/camera")
    return 0


if __name__ == "__main__":
    sys.exit(main())
