#!/usr/bin/env python3
"""DSE files must not invoke signoff_all."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn"))
from dse.flow_role import SIGNOFF_ORCHESTRATOR, dse_mentions_signoff_all  # noqa: E402


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    hits = dse_mentions_signoff_all(ROOT)
    check(hits == [], f"DSE does not call signoff_all (hits={hits})")
    check((ROOT / SIGNOFF_ORCHESTRATOR).is_file(), "signoff orchestrator exists")
    ctrl = (ROOT / "learn/dse/controller.py").read_text()
    check("signoff" in ctrl.lower(), "controller mentions signoff in the 'not' list")
    print("ALL test_dse_role PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
