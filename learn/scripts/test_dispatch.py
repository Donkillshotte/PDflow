"""Dispatch never reads a persisted run outside the selected memory."""
from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(ROOT / "learn"))

from dse.dispatch import next_stage
from dse.memory import DesignMemory


def main() -> int:
    mem = DesignMemory(Path(tempfile.mkdtemp(prefix="dispatch-current-")) / "memory.jsonl")
    assert next_stage(mem) is None
    print("ok  empty current memory has no invented next stage")
    print("ALL test_dispatch PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
