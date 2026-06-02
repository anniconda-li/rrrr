from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.config  # noqa: F401 - loads project .env
from services.dify_service import DifyService


def main() -> None:
    service = DifyService(
        os.getenv("DIFY_BASE_URL", ""),
        os.getenv("DIFY_API_KEY", ""),
    )
    answer = service.run_workflow(
        question="这个塔有什么故事？",
        image_context='{"possible_landmark":"大雁塔","ocr_text":["大慈恩寺"],"confidence":0.82}',
        device="walkie-01",
        spot_id="dayanta",
    )
    print(answer)


if __name__ == "__main__":
    main()
