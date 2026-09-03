#!/usr/bin/env python3
"""Minimal post-finish ECO loop.

propose (default): read STA on the finished variant and write a plan.
apply: refuse locked variants (flowlab/learn/base), copy the ODB, run
OpenROAD repair_timing, write a sidecar ODB.

Never calls signoff_all. Never stamps .lvs.ok. After apply, the next
step is `FLOW_VARIANT=<copy> ./learn/scripts/run_signoff_all.sh`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn"))
from dse.flow_role import LOCKED_VARIANTS, SIGNOFF_ORCHESTRATOR, is_locked_variant  # noqa: E402

FLOW = _ROOT / "tools/OpenROAD-flow-scripts/flow"
TCL = _ROOT / "learn/scripts/eco_repair.tcl"


def _variant() -> str:
    return os.environ.get("FLOW_VARIANT", "flowlab")


def _sta(variant: str) -> dict:
    path = _ROOT / "learn/sim/reports" / f"sta_signoff_{variant}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def _plan(sta: dict) -> list[dict]:
    timing = sta.get("timing") or sta.get("metrics") or {}
    wns = timing.get("wns_ns")
    if wns is None:
        wns = (sta.get("sta") or {}).get("wns_ns")
    tns = timing.get("tns_ns")
    viol = timing.get("n_viol") or timing.get("violations")
    setup = wns is not None and float(wns) < 0
    steps = [
        {
            "step": "repair_timing",
            "args": "-setup",
            "reason": f"WNS {wns} ns" if wns is not None else "STA WNS unavailable — propose setup repair",
            "enabled": bool(setup or wns is None),
        },
        {
            "step": "repair_timing",
            "args": "-hold",
            "reason": "hold not reported on this educational STA — off unless ECO_HOLD=1",
            "enabled": os.environ.get("ECO_HOLD") == "1",
        },
        {
            "step": "detailed_placement",
            "args": "",
            "reason": "legalize cells moved by repair_timing",
            "enabled": True,
        },
    ]
    return steps


def propose(variant: str) -> dict:
    res = FLOW / "results/nangate45/gcd" / variant
    odb = res / "6_final.odb"
    sta = _sta(variant)
    steps = _plan(sta)
    return {
        "kind": "eco",
        "mode": "propose",
        "variant": variant,
        "ok": odb.is_file(),
        "signoff": False,
        "signoff_required": SIGNOFF_ORCHESTRATOR,
        "locked": is_locked_variant(variant),
        "source_odb": str(odb) if odb.is_file() else None,
        "source_sta": {
            "report": str(_ROOT / "learn/sim/reports" / f"sta_signoff_{variant}.json"),
            "ok": sta.get("ok"),
            "summary": sta.get("summary"),
        },
        "proposed": steps,
        "apply": (
            "refused on locked variants; set FLOW_VARIANT to a copy "
            "(not flowlab/learn/base) and ECO_MODE=apply"
        ),
        "summary": (
            "ECO propose · "
            + ("locked source" if is_locked_variant(variant) else "unlocked")
            + " · signoff_all still required"
        ),
    }


def apply(variant: str) -> dict:
    if is_locked_variant(variant):
        return {
            "kind": "eco",
            "mode": "apply",
            "variant": variant,
            "ok": False,
            "signoff": False,
            "error": f"refuse apply on locked FLOW_VARIANT={variant}",
            "locked": list(sorted(LOCKED_VARIANTS)),
            "summary": f"ECO apply refused on {variant}",
        }
    src = FLOW / "results/nangate45/gcd" / variant / "6_final.odb"
    if not src.is_file():
        # Fall back to flowlab ODB as the read-only source for a new variant name.
        src = FLOW / "results/nangate45/gcd/flowlab/6_final.odb"
    if not src.is_file():
        return {
            "kind": "eco",
            "mode": "apply",
            "ok": False,
            "signoff": False,
            "error": "missing 6_final.odb",
            "summary": "ECO apply missing ODB",
        }
    obj = FLOW / "objects/nangate45/gcd" / variant
    obj.mkdir(parents=True, exist_ok=True)
    work = obj / "eco_in.odb"
    out = obj / "eco_out.odb"
    shutil.copy2(src, work)
    exe = shutil.which("openroad") or "openroad"
    env = os.environ.copy()
    env["ECO_ODB"] = str(work)
    env["ECO_ODB_OUT"] = str(out)
    env["ECO_SETUP"] = "1"
    env["ECO_HOLD"] = os.environ.get("ECO_HOLD", "0")
    proc = subprocess.run(
        [exe, "-exit", str(TCL)],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    log = obj / "eco_apply.log"
    log.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
    wrote = out.is_file() and proc.returncode == 0
    return {
        "kind": "eco",
        "mode": "apply",
        "variant": variant,
        "ok": wrote,
        "signoff": False,
        "signoff_required": SIGNOFF_ORCHESTRATOR,
        "source_odb": str(src),
        "output_odb": str(out) if wrote else None,
        "log": str(log),
        "rc": proc.returncode,
        "summary": "ECO apply wrote sidecar ODB · run signoff_all next" if wrote else "ECO apply failed",
    }


def main() -> int:
    variant = _variant()
    mode = os.environ.get("ECO_MODE", "propose")
    report = apply(variant) if mode == "apply" else propose(variant)
    name = f"eco_apply_{variant}.json" if mode == "apply" else f"eco_{variant}.json"
    out = _ROOT / "learn/sim/reports" / name
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(report["summary"])
    print("WROTE", out)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
