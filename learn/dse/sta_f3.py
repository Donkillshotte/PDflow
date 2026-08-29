"""OpenSTA F3 on a mapped netlist. Replaceable timing/power layer.

Ideal interconnect (no SPEF) unless a SPEF path is passed. Compares
candidates; it is not signoff and not Dynamic IR. Liberty CCS/ECSM are
not required — NLDM delay is enough for WNS ranking.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
LIB = (
    REPO
    / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
)
SDC = REPO / "tools/OpenROAD-flow-scripts/flow/designs/nangate45/gcd/constraint.sdc"
EXPORT_ARRIVALS = REPO / "learn" / "scripts" / "export_sta_arrivals.py"

_WNS = re.compile(r"wns max\s+(-?[0-9.]+)")
_TNS = re.compile(r"tns max\s+(-?[0-9.]+)")
_PWR = re.compile(
    r"^Total\s+[0-9.eE+\-]+\s+[0-9.eE+\-]+\s+[0-9.eE+\-]+\s+([0-9.eE+\-]+)",
    re.M,
)
_START = re.compile(r"Startpoint:\s+(\S+)")
_END = re.compile(r"Endpoint:\s+(\S+)")
_PATH_PIN = re.compile(
    r"([A-Za-z0-9_./$\\]+)/([A-Za-z0-9]+)\s+\(([A-Za-z0-9_]+)\)"
)


def available() -> bool:
    return bool(shutil.which("sta") and LIB.is_file() and SDC.is_file())


def evaluate_sta(
    verilog: Path,
    *,
    top: str = "gcd",
    spef: Path | None = None,
    sdf: Path | None = None,
    propagated_clock: bool = False,
    timeout_s: float = 20.0,
) -> dict:
    """WNS / TNS / power on the candidate. Ideal nets unless SPEF/SDF is given.

    GRT `write_spef` needs OpenRCX (detailed route / F5). After
    `estimate_parasitics -global_routing`, `write_sdf` is the honest
    parasitic annotation we can persist — not SPEF signoff.

    `propagated_clock=True` is for a post-CTS netlist + SPEF (F5-CTS).
    F5-lite keeps the default (ideal clock on the pre-CTS mapped.v).
    """
    if not available():
        return {"status": "GAP", "reason": "opensta or liberty/sdc missing", "via": "opensta_f3"}
    verilog = Path(verilog)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "opensta_f3"}
    anno = ""
    interconnect = "ideal"
    if spef and Path(spef).is_file():
        anno = f"read_spef {spef}"
        interconnect = "spef"
    elif sdf and Path(sdf).is_file():
        anno = f"read_sdf {sdf}"
        interconnect = "sdf_grt"
    prop = "set_propagated_clock [all_clocks]" if propagated_clock else ""
    clock = "propagated" if propagated_clock else "ideal"
    tcl = f"""
read_liberty {LIB}
read_verilog {verilog}
link_design {top}
read_sdc {SDC}
{anno}
{prop}
report_wns
report_tns
report_power
puts STA_PATH_BEGIN
report_checks -path_delay max -fields {{input_pin}} -digits 4 -format full -group_path_count 1
puts STA_PATH_END
puts DSE_STA_OK
"""
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="dse-sta-") as tmp:
        script = Path(tmp) / "sta.tcl"
        script.write_text(tcl)
        try:
            proc = subprocess.run(
                ["sta", "-no_init", "-exit", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "reason": f"STA timeout {timeout_s}s",
                "via": "opensta_f3",
                "cost_s": time.time() - t0,
            }
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    wns = _WNS.search(log)
    tns = _TNS.search(log)
    pwr = _PWR.search(log)
    start = _START.search(log)
    end = _END.search(log)
    path_cells, path_nets, path_types = _parse_path(log)
    ok = "DSE_STA_OK" in log and wns is not None and proc.returncode == 0
    return {
        "status": "ok" if ok else "fail",
        "reason": None if ok else "sta_failed",
        "wns_ns": float(wns.group(1)) if wns else None,
        "tns_ns": float(tns.group(1)) if tns else None,
        "power_w": float(pwr.group(1)) if pwr else None,
        "path_start": start.group(1) if start else None,
        "path_end": end.group(1) if end else None,
        "path_cells": path_cells,
        "path_nets": path_nets,
        "path_types": path_types,
        "interconnect": interconnect,
        "clock": clock,
        "via": (
            "opensta_f3 — "
            + (
                "SDF from GRT estimate_parasitics (not SPEF/OpenRCX, not finish)"
                if interconnect == "sdf_grt"
                else (
                    "SPEF WNS/power with set_propagated_clock; not IR, not finish"
                    if clock == "propagated"
                    else "SPEF WNS/power; not IR, not finish"
                )
                if interconnect == "spef"
                else "ideal WNS/power; not IR, not finish"
            )
        ),
        "cost_s": time.time() - t0,
    }


def _parse_path(log: str) -> tuple[list[str], list[str], dict[str, str]]:
    """Unique instances / hops on the worst path. Clock-network-only lines skipped."""
    blob = log
    if "STA_PATH_BEGIN" in log and "STA_PATH_END" in log:
        blob = log.split("STA_PATH_BEGIN", 1)[1].split("STA_PATH_END", 1)[0]
    cells: list[str] = []
    types: dict[str, str] = {}
    for inst, _pin, typ in _PATH_PIN.findall(blob):
        if inst.startswith("clock"):
            continue
        if inst not in cells:
            cells.append(inst)
        types.setdefault(inst, typ)
    nets = [f"{a}->{b}" for a, b in zip(cells, cells[1:])]
    return cells, nets, types


def export_arrivals(
    verilog: Path,
    dest: Path,
    *,
    spef: Path | None = None,
    timeout_s: float = 60.0,
) -> dict:
    """OpenSTA report_arrival on the candidate. t50 teacher — not a VCD→ITerm map."""
    if not available() or not EXPORT_ARRIVALS.is_file():
        return {"status": "GAP", "reason": "opensta or export_sta_arrivals missing", "via": "opensta_arrivals"}
    verilog = Path(verilog)
    dest = Path(dest)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "opensta_arrivals"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["STA_LIB"] = str(LIB)
    env["STA_V"] = str(verilog)
    env["STA_SDC"] = str(SDC)
    env["STA_OUT"] = str(dest)
    if spef and Path(spef).is_file():
        env["STA_SPEF"] = str(spef)
    else:
        env.pop("STA_SPEF", None)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(EXPORT_ARRIVALS)],
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "fail",
            "reason": f"arrivals timeout {timeout_s}s",
            "via": "opensta_arrivals",
            "cost_s": time.time() - t0,
        }
    if not dest.is_file():
        err = ((proc.stderr or "") + (proc.stdout or ""))[-300:]
        return {"status": "fail", "reason": err or "arrivals_failed", "via": "opensta_arrivals"}
    try:
        blob = json.loads(dest.read_text())
    except json.JSONDecodeError:
        return {"status": "fail", "reason": "arrivals json", "via": "opensta_arrivals"}
    blob["status"] = "ok" if blob.get("n_inst") else "fail"
    blob["cost_s"] = time.time() - t0
    blob.setdefault("via", "opensta_arrivals — t50 from report_arrival, not VCD")
    return blob
