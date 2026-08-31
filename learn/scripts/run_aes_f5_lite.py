#!/usr/bin/env python3
"""Pay aes F5-lite (2 DRT iters, ideal clock, no CTS) into memory_aes.jsonl.

Uses the 0.82 ns AES SDC. Does not run CTS, does not run Krylov, does not
touch the 73k-R / 6.954 mV row.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))
sys.path.insert(0, str(REPO / "learn" / "scripts"))

from heavy_analysis import require_heavy  # noqa: E402
from dse.fidelity import evaluate_f5_drt  # noqa: E402
from dse.memory import DesignMemory  # noqa: E402


def main() -> int:
    require_heavy("AES F5-lite DRT+OpenRCX (not CTS, not Krylov)")
    if os.environ.get("AES_F5_ALLOW_CTS") == "1":
        print("REFUSED: AES F5-CTS is not part of this cloud shot")
        return 2
    mem_path = REPO / "learn" / "sim" / "dse" / "memory_aes.jsonl"
    mem = DesignMemory(mem_path)
    f1 = None
    for c in reversed(list(mem.by_level("logic"))):
        if c.status == "ok" and (c.knobs or {}).get("name") == "liberty_default":
            f1 = c
            break
    if f1 is None:
        print("no aes F1")
        return 1
    mapped = (f1.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        print("mapped netlist missing")
        return 1
    timeout_s = float(os.environ.get("AES_F5_TIMEOUT_S") or 300)
    f5 = evaluate_f5_drt(f1, mem, design_id="aes", timeout_s=timeout_s)
    if f5 is None:
        print("F5-lite skipped")
        return 1
    print(
        f"F5-lite {f5.id} status={f5.status} wns={(f5.artifacts or {}).get('wns_ns')} "
        f"sdc={(f5.knobs or {}).get('sdc')} top={(f5.knobs or {}).get('top')} "
        f"clock={(f5.knobs or {}).get('clock')} cost={f5.cost_s:.1f}s "
        f"fail={f5.failure}"
    )
    dest = REPO / "learn" / "sim" / "reports" / "dse_aes.json"
    report = json.loads(dest.read_text()) if dest.is_file() else {}
    report["f5_lite_id"] = f5.id
    report["f5_lite_status"] = f5.status
    report["f5_lite_wns_ns"] = (f5.artifacts or {}).get("wns_ns")
    report["f5_lite_sdc"] = (f5.knobs or {}).get("sdc")
    report["f5_lite_top"] = (f5.knobs or {}).get("top")
    report["f5_lite_clock"] = (f5.knobs or {}).get("clock")
    report["n_candidates"] = len(mem)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    if f5.status != "ok":
        return 1
    sdc = str((f5.knobs or {}).get("sdc") or "")
    if "aes" not in sdc or "gcd" in sdc:
        print(f"REFUSED: F5 used non-aes SDC {sdc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
