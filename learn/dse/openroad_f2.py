"""Budgeted OpenROAD GPL / GRT. Replaceable physical + routing layers.

GPL: `global_placement -skip_io` → HPWL (µm) + overflow.
GRT: `place_pins` + GPL + `global_route` + `estimate_parasitics` → WNS/power.
No CTS, no detailed route, no finish, no PDN solve, not Dynamic IR.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
PLATFORM = REPO / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45"
TECH_LEF = PLATFORM / "lef/NangateOpenCellLibrary.tech.lef"
SC_LEF = PLATFORM / "lef/NangateOpenCellLibrary.macro.mod.lef"
LIB = PLATFORM / "lib/NangateOpenCellLibrary_typical.lib"
TRACKS = PLATFORM / "make_tracks.tcl"
SETRC = PLATFORM / "setRC.tcl"
SDC = REPO / "tools/OpenROAD-flow-scripts/flow/designs/nangate45/gcd/constraint.sdc"
SITE = "FreePDK45_38x28_10R_NP_162NW_34O"
IO_H = "metal5"
IO_V = "metal6"

_WNS = re.compile(r"wns max\s+(-?[0-9.]+)")
_TNS = re.compile(r"tns max\s+(-?[0-9.]+)")
_PWR = re.compile(
    r"^Total\s+[0-9.eE+\-]+\s+[0-9.eE+\-]+\s+[0-9.eE+\-]+\s+([0-9.eE+\-]+)",
    re.M,
)
_START = re.compile(r"Startpoint:\s+(\S+)")
_END = re.compile(r"Endpoint:\s+(\S+)")
_GRT_WL = re.compile(r"Total wirelength:\s+([0-9.]+)")
_GRT_OV = re.compile(
    r"^Total\s+(\d+)\s+(\d+)\s+([0-9.]+)%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
    re.M,
)

_ROW = re.compile(
    r"^\s*(\d+)\s+\|\s+([0-9.]+)\s+\|\s+([0-9.eE+\-]+)\s+\|",
    re.M,
)
_AREA = re.compile(r"Placed Cell Area\s+([0-9.]+)")
_INST = re.compile(r"Number of instances:\s+(\d+)")


def available() -> bool:
    return bool(
        shutil.which("openroad")
        and TECH_LEF.is_file()
        and SC_LEF.is_file()
        and LIB.is_file()
        and TRACKS.is_file()
    )


def evaluate_gpl(
    verilog: Path,
    *,
    top: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
) -> dict:
    """Place the candidate. Returns HPWL in microns + overflow. Not Dynamic IR."""
    if not available():
        return {"status": "GAP", "reason": "openroad or Nangate45 LEF/lib missing", "via": "openroad_gpl"}
    verilog = Path(verilog)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "openroad_gpl"}
    tcl = f"""
set_thread_count 1
read_lef {TECH_LEF}
read_lef {SC_LEF}
read_liberty {LIB}
read_verilog {verilog}
link_design {top}
initialize_floorplan -utilization {float(util)} -aspect_ratio 1.0 -core_space 2.0 -site {SITE}
source {TRACKS}
global_placement -skip_io -density {float(density)}
puts DSE_GPL_OK
exit
"""
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="dse-gpl-") as tmp:
        script = Path(tmp) / "place.tcl"
        script.write_text(tcl)
        try:
            proc = subprocess.run(
                ["openroad", "-exit", "-no_init", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "reason": f"GPL timeout {timeout_s}s",
                "via": "openroad_gpl",
                "cost_s": time.time() - t0,
            }
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    rows = _ROW.findall(log)
    hpwl = float(rows[-1][2]) if rows else None
    overflow = float(rows[-1][1]) if rows else None
    area_m = _AREA.search(log)
    inst_m = _INST.search(log)
    ok = "DSE_GPL_OK" in log and hpwl is not None and proc.returncode == 0
    err = next((ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR")), "")
    return {
        "status": "ok" if ok else "fail",
        "reason": None if ok else (err or "gpl_failed"),
        "hpwl_um": hpwl,
        "overflow": overflow,
        "inst_area_um2": float(area_m.group(1)) if area_m else None,
        "n_inst": int(inst_m.group(1)) if inst_m else None,
        "util": float(util),
        "density": float(density),
        "skip_io": True,
        "via": "openroad_gpl_skip_io — F2, not GRT, not finish/F5, not IR",
        "cost_s": time.time() - t0,
        "n_iters": int(rows[-1][0]) if rows else 0,
    }


def evaluate_grt(
    verilog: Path,
    *,
    top: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
) -> dict:
    """Place pins + GPL + global_route. Routing-level F2. Not detailed route/F5."""
    if not available() or not SDC.is_file():
        return {"status": "GAP", "reason": "openroad/LEF/SDC missing", "via": "openroad_grt"}
    verilog = Path(verilog)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "openroad_grt"}
    rc = f"source {SETRC}" if SETRC.is_file() else ""
    tcl = f"""
set_thread_count 1
read_lef {TECH_LEF}
read_lef {SC_LEF}
read_liberty {LIB}
read_verilog {verilog}
link_design {top}
read_sdc {SDC}
initialize_floorplan -utilization {float(util)} -aspect_ratio 1.0 -core_space 2.0 -site {SITE}
source {TRACKS}
{rc}
place_pins -hor_layers {IO_H} -ver_layers {IO_V}
global_placement -density {float(density)}
global_route
estimate_parasitics -global_routing
report_wns
report_tns
report_power
puts STA_PATH_BEGIN
report_checks -path_delay max -fields {{input_pin}} -digits 4 -format full -group_path_count 1
puts STA_PATH_END
puts DSE_GRT_OK
exit
"""
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="dse-grt-") as tmp:
        script = Path(tmp) / "grt.tcl"
        script.write_text(tcl)
        try:
            proc = subprocess.run(
                ["openroad", "-exit", "-no_init", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "reason": f"GRT timeout {timeout_s}s",
                "via": "openroad_grt",
                "cost_s": time.time() - t0,
            }
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    rows = _ROW.findall(log)
    hpwl = float(rows[-1][2]) if rows else None
    overflow = float(rows[-1][1]) if rows else None
    wns = _WNS.search(log)
    tns = _TNS.search(log)
    pwr = _PWR.search(log)
    gwl = _GRT_WL.search(log)
    gov = _GRT_OV.search(log)
    start = _START.search(log)
    end = _END.search(log)
    ok = "DSE_GRT_OK" in log and proc.returncode == 0
    err = next((ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR")), "")
    grt_overflow = float(gov.group(6)) if gov else (0.0 if ok else None)
    return {
        "status": "ok" if ok else "fail",
        "reason": None if ok else (err or "grt_failed"),
        "hpwl_um": hpwl,
        "overflow": overflow,
        "grt_overflow": grt_overflow,
        "grt_wl": float(gwl.group(1)) if gwl else None,
        "wns_ns": float(wns.group(1)) if wns else None,
        "tns_ns": float(tns.group(1)) if tns else None,
        "power_w": float(pwr.group(1)) if pwr else None,
        "path_start": start.group(1) if start else None,
        "path_end": end.group(1) if end else None,
        "util": float(util),
        "density": float(density),
        "via": "openroad_grt — place_pins+GPL+global_route; not detailed route/F5, not IR",
        "cost_s": time.time() - t0,
        "n_iters": int(rows[-1][0]) if rows else 0,
    }
