#!/usr/bin/env python3
"""Run OpenSTA report_arrival on every output pin and write JSON.

Join key is the instance name with Verilog backslashes stripped.
Does not invent arrivals. Requires sta in PATH.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parents[1]
_TCL = _SCRIPTS / "export_sta_arrivals.tcl"
NUM = r"(?:[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|---)"
ARR_RE = re.compile(rf"\br\s+({NUM}):({NUM})\s+f\s+({NUM}):({NUM})")


def _num(tok: str) -> float | None:
    if not tok or tok == "---":
        return None
    try:
        return float(tok)
    except ValueError:
        return None
PIN_RE = re.compile(r"^PIN\s+(\S+)\s+activity=(\S+)\s+duty=(\S+)\s+origin=(\S*)\s*$")


def parse_arrival_log(text: str) -> list[dict]:
    rows: list[dict] = []
    cur = None
    for line in text.splitlines():
        m = PIN_RE.match(line.strip())
        if m:
            nm = m.group(1)
            slash = nm.rfind("/")
            inst = nm[:slash] if slash >= 0 else nm
            pin = nm[slash + 1 :] if slash >= 0 else ""
            cur = {
                "inst": inst,
                "inst_key": inst.replace("\\", ""),
                "pin": pin,
                "full": nm,
                "activity_hz": float(m.group(2)),
                "duty": float(m.group(3)) if m.group(3) not in ("", "nan") else None,
                "origin": m.group(4) or "",
                "rise_ns": None,
                "fall_ns": None,
            }
            rows.append(cur)
            continue
        if cur is None:
            continue
        am = ARR_RE.search(line)
        if am:
            rise = _num(am.group(2)) if _num(am.group(2)) is not None else _num(am.group(1))
            fall = _num(am.group(4)) if _num(am.group(4)) is not None else _num(am.group(3))
            if cur.get("rise_ns") is None and rise is not None:
                cur["rise_ns"] = rise
            if cur.get("fall_ns") is None and fall is not None:
                cur["fall_ns"] = fall
    return rows


def main() -> int:
    flow = _ROOT / "tools" / "OpenROAD-flow-scripts" / "flow"
    variant = os.environ.get("FLOW_VARIANT", "flowlab")
    res = flow / "results" / "nangate45" / "gcd" / variant
    lib = Path(os.environ.get("STA_LIB") or flow / "platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib")
    v = Path(os.environ.get("STA_V") or res / "6_final.v")
    sdc = Path(
        os.environ.get("STA_SDC")
        or flow / "designs/nangate45/gcd-tutorial/constraint.sdc"
    )
    out = Path(os.environ.get("STA_OUT") or _ROOT / "learn/sim/reports" / f"sta_arrivals_{variant}.json")
    if not v.is_file():
        print(f"FAIL missing {v}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["STA_LIB"] = str(lib)
    env["STA_V"] = str(v)
    env["STA_SDC"] = str(sdc)
    proc = subprocess.run(
        ["sta", "-no_init", "-exit", str(_TCL)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "STA_ARRIVALS_DONE" not in log:
        print(log[-2000:], file=sys.stderr)
        print("FAIL OpenSTA arrivals dump", file=sys.stderr)
        return 1
    rows = parse_arrival_log(log)
    with_arr = [r for r in rows if r.get("rise_ns") is not None or r.get("fall_ns") is not None]
    by_inst: dict[str, dict] = {}
    for r in with_arr:
        key = r["inst_key"]
        prev = by_inst.get(key)
        # Prefer Q/QN/ZN; keep the earlier (usually clock-to-q or data) max rise.
        if prev is None:
            by_inst[key] = r
            continue
        t_new = r.get("rise_ns") if r.get("rise_ns") is not None else r.get("fall_ns")
        t_old = prev.get("rise_ns") if prev.get("rise_ns") is not None else prev.get("fall_ns")
        if t_new is not None and (t_old is None or t_new < t_old):
            by_inst[key] = r
    payload = {
        "ok": True,
        "n_pins": len(rows),
        "n_with_arrival": len(with_arr),
        "n_inst": len(by_inst),
        "verilog": str(v),
        "sdc": str(sdc),
        "via": "OpenSTA report_arrival on output pins — t50 from rise arrival, not VCD",
        "pins": with_arr,
        "by_inst": by_inst,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print("STA_ARRIVALS_JSON", out, "n_inst", len(by_inst), "n_pins", len(with_arr))
    return 0 if with_arr else 1


if __name__ == "__main__":
    raise SystemExit(main())
