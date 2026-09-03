#!/usr/bin/env python3
"""Record flowlab gridcheck from the OpenROAD log. Does not stamp .ok."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "learn/sim/reports/gridcheck_flowlab_pdn.log"
STAMP = (
    ROOT
    / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/.gridcheck_pdn.ok"
)
OUT = ROOT / "learn/sim/reports/gridcheck_flowlab.json"


def main() -> int:
    text = LOG.read_text(errors="replace") if LOG.is_file() else ""
    vdd = "All shapes on net VDD are connected" in text
    vss = "All shapes on net VSS are connected" in text
    done = "GRIDCHECK_DONE" in text
    ok = vdd and vss and done and STAMP.is_file()
    report = {
        "ok": ok,
        "kind": "gridcheck",
        "variant": "flowlab",
        "stage": "pdn",
        "vdd_connected": vdd,
        "vss_connected": vss,
        "stamp": str(STAMP) if STAMP.is_file() else None,
        "log": str(LOG) if LOG.is_file() else None,
        "educational_note": "OpenROAD check_power_grid on flowlab PDN. Not Voltus.",
        "summary": (
            "GRIDCHECK PASS · VDD+VSS connected"
            if ok
            else "GRIDCHECK FAIL or missing log/stamp"
        ),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(report["summary"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
