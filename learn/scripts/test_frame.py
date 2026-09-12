"""Lineage frame starts empty for every invocation."""
from __future__ import annotations

import tempfile
from pathlib import Path

from dse.frame import refine_chain, next_stage
from dse.memory import DesignMemory


def main() -> int:
    mem = DesignMemory(Path(tempfile.mkdtemp(prefix="frame-current-")) / "memory.jsonl")
    assert refine_chain(mem) == []
    assert next_stage(mem) is None
    print("ok  current frame does not invent persisted lineage")
    print("ALL test_frame PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
