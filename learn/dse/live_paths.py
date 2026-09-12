"""Run-scoped paths for live DSE helpers.

Callers may share one directory by setting ``PD_FLOW_RUN_DIR`` for an
explicit workflow. Otherwise each process receives a fresh directory.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIVE_ROOT = REPO / "learn" / "sim" / "dse" / "live"


def current_run_dir(design: str) -> Path:
    supplied = os.environ.get("PD_FLOW_RUN_DIR")
    if supplied:
        path = Path(supplied).expanduser().resolve()
    else:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", design).strip("._") or "run"
        path = LIVE_ROOT / safe / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def current_memory_path(design: str) -> Path:
    return current_run_dir(design) / "memory.jsonl"


def current_report_path(design: str) -> Path:
    return current_run_dir(design) / "report.json"
