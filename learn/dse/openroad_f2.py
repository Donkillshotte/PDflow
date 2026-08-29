"""Budgeted OpenROAD GPL (F2). Replaceable physical layer — not F5, not IR.

Runs `global_placement -skip_io` on a gate-level mapped netlist. Parses the
GPL iteration table for HPWL (µm) and overflow. No CTS, no route, no finish,
no PDN solve. Independent of the F2-fast barycenter oracle and of libdpn.
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
SITE = "FreePDK45_38x28_10R_NP_162NW_34O"

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
