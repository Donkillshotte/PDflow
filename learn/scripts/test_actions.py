"""Refine action contracts without persisted run data."""
from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(ROOT / "learn"))

from dse.actions import should_pay_refine_sizeup
from dse.memory import DesignMemory


def main() -> int:
    mem = DesignMemory(Path(tempfile.mkdtemp(prefix="actions-current-")) / "memory.jsonl")
    pay, reason = should_pay_refine_sizeup(mem, depth=0, budget_left=600.0, steer=None)
    assert pay is False and "residual" in reason
    print("ok  refine action requires a same-invocation steer")
    print("ALL test_actions PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
