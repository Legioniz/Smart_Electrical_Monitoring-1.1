"""Central, safe path resolution for project assets and mutable local state.

Source assets always resolve inside the installed project directory. Only runtime
state (logs, model artifacts, caches) may be redirected with SME_DATA_DIR.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
ROOT = PROJECT_ROOT
DATA_DIR = Path(os.environ.get("SME_DATA_DIR", PROJECT_ROOT / "var")).expanduser().resolve()
LEARNING_DIR = DATA_DIR / "learning"
MODEL_DIR = LEARNING_DIR / "models"
LOG_DIR = DATA_DIR / "logs"
EXPORT_DIR = DATA_DIR / "exports"


def project_file(relative: str) -> Path:
    candidate = (PROJECT_ROOT / relative).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Project asset path escapes the installation directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"Required project file is missing: {candidate}")
    return candidate


def ensure_runtime_dirs() -> None:
    for directory in (DATA_DIR, LEARNING_DIR, MODEL_DIR, LOG_DIR, EXPORT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
