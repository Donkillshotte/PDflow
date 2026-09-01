#!/usr/bin/env python3
"""Register already-finished GCD bake-off cooks into the campaign JSONL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_LEARN = Path(__file__).resolve().parents[1]
if str(_LEARN) not in sys.path:
    sys.path.insert(0, str(_LEARN))

from dse.experiments import ExperimentLog, seed_gcd_bakeoff  # noqa: E402


def main() -> int:
    log = ExperimentLog()
    added = seed_gcd_bakeoff(log)
    print(json.dumps({"added": added, "n": len(log), "path": str(log.path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
