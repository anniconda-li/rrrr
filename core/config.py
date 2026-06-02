from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency should be installed from requirements
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def load_project_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH)


load_project_env()
