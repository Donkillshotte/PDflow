"""Budgeted OpenROAD GPL / GRT / F5-lite DRT+OpenRCX / F5-CTS / candidate PDN extract.

GPL: `global_placement -skip_io` → HPWL (µm) + overflow.
GRT: `place_pins` + GPL + `global_route` + `estimate_parasitics` → WNS/power.
F5-lite: legalize + GRT + `detailed_route` + OpenRCX `extract_parasitics`
  + `write_spef` — not `make finish`, clock stays ideal (no CTS).
F5-CTS: same place, then `clock_tree_synthesis` + legalize + GRT + DRT +
  OpenRCX. Clock is propagated. Not `make finish`, not a replacement for F5-lite.
PDN extract: `place_pins` + tapcell + pdngen + GPL + `detailed_placement`
  + `write_pg_spice` — a *new* R-graph, not the finish mesh, not gold.
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
PDN_TCL = PLATFORM / "grid_strategy-M1-M4-M7.tcl"
RCX_RULES = PLATFORM / "rcx_patterns.rules"
SDC = REPO / "tools/OpenROAD-flow-scripts/flow/designs/nangate45/gcd/constraint.sdc"
EXPORT_INSTS = REPO / "learn" / "scripts" / "export_odb_inst_power.py"
SITE = "FreePDK45_38x28_10R_NP_162NW_34O"
IO_H = "metal5"
IO_V = "metal6"
TAP_MASTER = "TAPCELL_X1"

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
_REGION_BIN = re.compile(
    r"DSE_REGION_BIN\s+(r\d+)\s+([0-9.eE+\-]+)\s+([0-9.eE+\-]+)\s+([0-9.eE+\-]+)\s+([0-9.eE+\-]+)"
)


def region_blockage_tcl(
    *,
    x_dbu: float | None = None,
    y_dbu: float | None = None,
    region: str | None = None,
    bins: int = 4,
    max_density: float = 0.30,
) -> str:
    """After floorplan: density cap on the IR bin. Not a chip restart.

    Uses the live core bbox. Prefer hotspot dbu; fall back to ``r{nx}{ny}``.
    """
    if (x_dbu is None or y_dbu is None) and not region:
        return ""
    nx = ny = 0
    if region and re.fullmatch(r"r\d{2}", str(region)):
        nx, ny = int(region[1]), int(region[2])
    use_xy = x_dbu is not None and y_dbu is not None
    hx = int(round(float(x_dbu))) if use_xy else 0
    hy = int(round(float(y_dbu))) if use_xy else 0
    flag = 1 if use_xy else 0
    return f"""
lassign [ord::get_core_area] _cx1 _cy1 _cx2 _cy2
set _bins {int(bins)}
set _wx [expr {{($_cx2-$_cx1)/double($_bins)}}]
set _wy [expr {{($_cy2-$_cy1)/double($_bins)}}]
set _nx {int(nx)}
set _ny {int(ny)}
if {{{int(flag)}}} {{
  set _hx [ord::dbu_to_microns {hx}]
  set _hy [ord::dbu_to_microns {hy}]
  set _nx [expr {{int(($_hx-$_cx1)/$_wx)}}]
  set _ny [expr {{int(($_hy-$_cy1)/$_wy)}}]
}}
if {{$_nx < 0}} {{ set _nx 0 }}
if {{$_ny < 0}} {{ set _ny 0 }}
if {{$_nx > [expr {{$_bins - 1}}]}} {{ set _nx [expr {{$_bins - 1}}] }}
if {{$_ny > [expr {{$_bins - 1}}]}} {{ set _ny [expr {{$_bins - 1}}] }}
set _rx1 [expr {{$_cx1 + $_nx*$_wx}}]
set _ry1 [expr {{$_cy1 + $_ny*$_wy}}]
set _rx2 [expr {{$_rx1 + $_wx}}]
set _ry2 [expr {{$_ry1 + $_wy}}]
create_blockage -region [list $_rx1 $_ry1 $_rx2 $_ry2] -max_density {float(max_density)}
puts "DSE_REGION_BIN r$_nx$_ny $_rx1 $_ry1 $_rx2 $_ry2"
"""


def _parse_region_bin(log: str) -> dict:
    m = _REGION_BIN.search(log or "")
    if not m:
        return {}
    return {
        "region_bin": m.group(1),
        "region_box_um": [float(m.group(i)) for i in range(2, 6)],
    }


def available() -> bool:
    return bool(
        shutil.which("openroad")
        and TECH_LEF.is_file()
        and SC_LEF.is_file()
        and LIB.is_file()
        and TRACKS.is_file()
    )


def extract_available() -> bool:
    return available() and PDN_TCL.is_file() and SDC.is_file() and EXPORT_INSTS.is_file()


def f5_available() -> bool:
    return available() and RCX_RULES.is_file() and SDC.is_file()


def _spice_counts(path: Path) -> tuple[int, int]:
    n_r = n_i = 0
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line:
            continue
        c = line[0]
        if c in "Rr":
            n_r += 1
        elif c in "Ii":
            n_i += 1
    return n_r, n_i


def evaluate_gpl(
    verilog: Path,
    *,
    top: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
    x_dbu: float | None = None,
    y_dbu: float | None = None,
    region: str | None = None,
    region_density: float | None = None,
) -> dict:
    """Place the candidate. Returns HPWL in microns + overflow. Not Dynamic IR.

    Optional IR-bin ``create_blockage -max_density`` is a region-local
    physical transform — not more ABC, not a chip restart.
    """
    if not available():
        return {"status": "GAP", "reason": "openroad or Nangate45 LEF/lib missing", "via": "openroad_gpl"}
    verilog = Path(verilog)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "openroad_gpl"}
    cap = float(region_density) if region_density is not None else 0.30
    blk = region_blockage_tcl(
        x_dbu=x_dbu, y_dbu=y_dbu, region=region, max_density=cap
    )
    tcl = f"""
set_thread_count 1
read_lef {TECH_LEF}
read_lef {SC_LEF}
read_liberty {LIB}
read_verilog {verilog}
link_design {top}
initialize_floorplan -utilization {float(util)} -aspect_ratio 1.0 -core_space 2.0 -site {SITE}
source {TRACKS}
{blk}
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
    err = next(
        (ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR") or ln.startswith("Error:")),
        "",
    )
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
        "via": (
            "openroad_gpl_skip_io + IR-bin density cap — region-local F2, not finish/F5"
            if blk
            else "openroad_gpl_skip_io — F2, not GRT, not finish/F5, not IR"
        ),
        "cost_s": time.time() - t0,
        "n_iters": int(rows[-1][0]) if rows else 0,
        **_parse_region_bin(log),
        **(
            {
                "region": region,
                "x_dbu": x_dbu,
                "y_dbu": y_dbu,
                "region_density": cap,
            }
            if blk
            else {}
        ),
    }


def evaluate_grt(
    verilog: Path,
    *,
    top: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
    sdf_out: Path | None = None,
) -> dict:
    """Place pins + GPL + global_route. Routing-level F2. Not detailed route/F5."""
    if not available() or not SDC.is_file():
        return {"status": "GAP", "reason": "openroad/LEF/SDC missing", "via": "openroad_grt"}
    verilog = Path(verilog)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "openroad_grt"}
    rc = f"source {SETRC}" if SETRC.is_file() else ""
    sdf_write = ""
    sdf_tmp = None
    if sdf_out is not None:
        sdf_tmp = Path(sdf_out)
        sdf_tmp.parent.mkdir(parents=True, exist_ok=True)
        sdf_write = f"write_sdf {sdf_tmp}"
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
{sdf_write}
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
    err = next(
        (ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR") or ln.startswith("Error:")),
        "",
    )
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
        "sdf": str(sdf_tmp) if ok and sdf_tmp is not None and sdf_tmp.is_file() else None,
        "interconnect": "sdf_grt" if ok and sdf_tmp is not None and sdf_tmp.is_file() else "grt_inmem",
    }


def evaluate_f5_drt(
    verilog: Path,
    *,
    top: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 45.0,
    spef_out: Path | None = None,
    droute_end_iter: int = 2,
) -> dict:
    """Legalize + GRT + detailed_route + OpenRCX SPEF. Not make finish.

    Clock stays ideal (no CTS). `droute_end_iter` is a budget cap, not signoff
    convergence. Timing truth is OpenSTA `read_spef`, not OpenROAD report_wns.
    """
    if not f5_available():
        return {"status": "GAP", "reason": "openroad/LEF/RCX rules missing", "via": "openroad_f5_drt"}
    verilog = Path(verilog)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "openroad_f5_drt"}
    rc = f"source {SETRC}" if SETRC.is_file() else ""
    spef_tmp = Path(spef_out) if spef_out is not None else None
    if spef_tmp is not None:
        spef_tmp.parent.mkdir(parents=True, exist_ok=True)
    else:
        spef_tmp = Path(tempfile.mkdtemp(prefix="dse-f5-")) / "cand.spef"
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
detailed_placement
global_route
detailed_route -droute_end_iter {int(droute_end_iter)} -verbose 1
extract_parasitics -ext_model_file {RCX_RULES}
write_spef {spef_tmp}
report_wns
report_tns
report_power
puts STA_PATH_BEGIN
report_checks -path_delay max -fields {{input_pin}} -digits 4 -format full -group_path_count 1
puts STA_PATH_END
puts DSE_F5_OK
exit
"""
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="dse-f5-") as tmp:
        script = Path(tmp) / "f5.tcl"
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
                "reason": f"F5 DRT/RCX timeout {timeout_s}s",
                "via": "openroad_f5_drt",
                "cost_s": time.time() - t0,
            }
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    wns = _WNS.search(log)
    tns = _TNS.search(log)
    pwr = _PWR.search(log)
    start = _START.search(log)
    end = _END.search(log)
    gwl = _GRT_WL.search(log)
    gov = _GRT_OV.search(log)
    ok = "DSE_F5_OK" in log and proc.returncode == 0 and spef_tmp.is_file()
    err = next(
        (ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR") or ln.startswith("Error:")),
        "",
    )
    segs = None
    mseg = re.search(r"Final (\d+) rc segments", log)
    if mseg:
        segs = int(mseg.group(1))
    return {
        "status": "ok" if ok else "fail",
        "reason": None if ok else (err or "f5_drt_rcx_failed"),
        "spef": str(spef_tmp) if ok else None,
        "spef_bytes": spef_tmp.stat().st_size if ok else 0,
        "n_rc_segments": segs,
        "wns_or_ns": float(wns.group(1)) if wns else None,
        "tns_or_ns": float(tns.group(1)) if tns else None,
        "power_or_w": float(pwr.group(1)) if pwr else None,
        "path_start": start.group(1) if start else None,
        "path_end": end.group(1) if end else None,
        "grt_wl": float(gwl.group(1)) if gwl else None,
        "grt_overflow": float(gov.group(6)) if gov else None,
        "util": float(util),
        "density": float(density),
        "droute_end_iter": int(droute_end_iter),
        "clock": "ideal",
        "interconnect": "spef_openrcx" if ok else "none",
        "via": (
            "openroad detailed_route+OpenRCX write_spef — F5-lite, not make finish, "
            "clock ideal (no CTS); OpenSTA read_spef is the timing oracle"
        ),
        "cost_s": time.time() - t0,
    }


_CTS_BUFS = re.compile(r"Number of Buffers Inserted:\s+(\d+)")
_CLKBUF_ROW = re.compile(r"CLKBUF_X\d+\s+(\d+)")
_CLKBUF_V = re.compile(r"\bCLKBUF_X\d+\b")


def _count_clkbuf(log: str, verilog: Path | None = None) -> int:
    n = 0
    if verilog is not None and Path(verilog).is_file():
        n = max(n, len(_CLKBUF_V.findall(Path(verilog).read_text(errors="replace"))))
    m = _CTS_BUFS.search(log)
    if m:
        n = max(n, int(m.group(1)))
    rows = _CLKBUF_ROW.findall(log)
    if rows:
        n = max(n, sum(int(x) for x in rows))
    return n


def evaluate_f5_cts(
    verilog: Path,
    *,
    top: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    timeout_s: float = 90.0,
    spef_out: Path | None = None,
    verilog_out: Path | None = None,
    droute_end_iter: int = 2,
) -> dict:
    """CTS + legalize + GRT + DRT + OpenRCX SPEF. Not make finish.

    Separate paid shot from F5-lite. Clock is propagated. Timing truth is
    OpenSTA `read_spef` + `set_propagated_clock` on the *post-CTS* netlist
    (CLKBUF instances are not in the pre-CTS mapped.v).
    """
    if not f5_available():
        return {"status": "GAP", "reason": "openroad/LEF/RCX rules missing", "via": "openroad_f5_cts"}
    verilog = Path(verilog)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "openroad_f5_cts"}
    rc = f"source {SETRC}" if SETRC.is_file() else ""
    spef_tmp = Path(spef_out) if spef_out is not None else None
    if spef_tmp is not None:
        spef_tmp.parent.mkdir(parents=True, exist_ok=True)
    else:
        spef_tmp = Path(tempfile.mkdtemp(prefix="dse-f5cts-")) / "cand_cts.spef"
    v_tmp = Path(verilog_out) if verilog_out is not None else None
    if v_tmp is not None:
        v_tmp.parent.mkdir(parents=True, exist_ok=True)
    else:
        v_tmp = Path(tempfile.mkdtemp(prefix="dse-f5cts-v-")) / "cand_cts.v"
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
detailed_placement
repair_clock_inverters
clock_tree_synthesis -sink_clustering_enable -repair_clock_nets \\
    -buf_list {{CLKBUF_X3 CLKBUF_X2 CLKBUF_X1}} -root_buf CLKBUF_X3
estimate_parasitics -placement
if {{[catch {{detailed_placement}} dp_err]}} {{
  puts "DSE_CTS_DP_WARN $dp_err"
}}
global_route
detailed_route -droute_end_iter {int(droute_end_iter)} -verbose 1
extract_parasitics -ext_model_file {RCX_RULES}
write_spef {spef_tmp}
write_verilog {v_tmp}
puts DSE_CLKBUF_BEGIN
report_cell_usage
puts DSE_CLKBUF_END
report_wns
report_tns
report_power
puts STA_PATH_BEGIN
report_checks -path_delay max -fields {{input_pin}} -digits 4 -format full -group_path_count 1
puts STA_PATH_END
puts DSE_F5_CTS_OK
exit
"""
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="dse-f5cts-") as tmp:
        script = Path(tmp) / "f5_cts.tcl"
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
                "reason": f"F5 CTS/DRT/RCX timeout {timeout_s}s",
                "via": "openroad_f5_cts",
                "cost_s": time.time() - t0,
            }
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    wns = _WNS.search(log)
    tns = _TNS.search(log)
    pwr = _PWR.search(log)
    start = _START.search(log)
    end = _END.search(log)
    gwl = _GRT_WL.search(log)
    gov = _GRT_OV.search(log)
    n_clkbuf = _count_clkbuf(log, v_tmp)
    ok = (
        "DSE_F5_CTS_OK" in log
        and proc.returncode == 0
        and spef_tmp.is_file()
        and v_tmp.is_file()
        and n_clkbuf >= 1
    )
    err = next(
        (ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR") or ln.startswith("Error:")),
        "",
    )
    if "DSE_F5_CTS_OK" in log and n_clkbuf < 1:
        err = err or "cts_inserted_no_clkbuf"
    segs = None
    mseg = re.search(r"Final (\d+) rc segments", log)
    if mseg:
        segs = int(mseg.group(1))
    return {
        "status": "ok" if ok else "fail",
        "reason": None if ok else (err or "f5_cts_rcx_failed"),
        "spef": str(spef_tmp) if ok else None,
        "spef_bytes": spef_tmp.stat().st_size if ok and spef_tmp.is_file() else 0,
        "cts_v": str(v_tmp) if ok else None,
        "n_clkbuf": n_clkbuf,
        "n_rc_segments": segs,
        "wns_or_ns": float(wns.group(1)) if wns else None,
        "tns_or_ns": float(tns.group(1)) if tns else None,
        "power_or_w": float(pwr.group(1)) if pwr else None,
        "path_start": start.group(1) if start else None,
        "path_end": end.group(1) if end else None,
        "grt_wl": float(gwl.group(1)) if gwl else None,
        "grt_overflow": float(gov.group(6)) if gov else None,
        "util": float(util),
        "density": float(density),
        "droute_end_iter": int(droute_end_iter),
        "clock": "propagated",
        "cts": 1,
        "interconnect": "spef_openrcx" if ok else "none",
        "via": (
            "openroad clock_tree_synthesis+detailed_route+OpenRCX write_spef — "
            "F5-CTS, not make finish, clock propagated; OpenSTA read_spef + "
            "set_propagated_clock on the post-CTS netlist is the timing oracle"
        ),
        "cost_s": time.time() - t0,
    }


def extract_pdn(
    verilog: Path,
    out_dir: Path,
    *,
    top: str = "gcd",
    util: float = 35.0,
    density: float = 0.55,
    pkg_r: float = 0.05,
    timeout_s: float = 60.0,
    x_dbu: float | None = None,
    y_dbu: float | None = None,
    region: str | None = None,
    region_density: float | None = None,
) -> dict:
    """Place + legalize + pdngen + write_pg_spice. Not finish, not gold.

    GPL without detailed_placement leaves cells off M1 followpins and
    analyze_power_grid fails connectivity. Do not use -skip_io here —
    write_pg_spice needs placed pins. Vectorless activity 0.2; no RTL VCD.
    """
    if not extract_available():
        return {
            "status": "GAP",
            "reason": "openroad/LEF/PDN tcl missing",
            "via": "openroad_pdn_extract",
            "gold": False,
        }
    verilog = Path(verilog)
    out_dir = Path(out_dir)
    if not verilog.is_file():
        return {"status": "fail", "reason": f"missing {verilog}", "via": "openroad_pdn_extract", "gold": False}
    out_dir.mkdir(parents=True, exist_ok=True)
    spice = out_dir / "pg_vdd_bumps.sp"
    odb = out_dir / "candidate.odb"
    insts = out_dir / "inst_power_map.json"
    logp = out_dir / "extract.log"
    cap = float(region_density) if region_density is not None else 0.30
    blk = region_blockage_tcl(
        x_dbu=x_dbu, y_dbu=y_dbu, region=region, max_density=cap
    )
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
tapcell -distance 25 -tapcell_master {TAP_MASTER} -endcap_master {TAP_MASTER}
source {PDN_TCL}
pdngen
place_pins -hor_layers {IO_H} -ver_layers {IO_V}
{blk}
global_placement -density {float(density)}
detailed_placement
global_connect
set_power_activity -global -activity 0.2 -duty 0.5
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 3 -external_resistance {float(pkg_r)}
analyze_power_grid -net VDD -source_type BUMPS
write_pg_spice -net VDD -source_type BUMPS {spice}
write_db {odb}
puts DSE_PDN_EXTRACT_OK
exit
"""
    t0 = time.time()
    script = out_dir / "extract.tcl"
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
            "reason": f"PDN extract timeout {timeout_s}s",
            "via": "openroad_pdn_extract",
            "gold": False,
            "cost_s": time.time() - t0,
        }
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    logp.write_text(log)
    err = next(
        (ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR") or ln.startswith("Error:")),
        "",
    )
    if "DSE_PDN_EXTRACT_OK" not in log or proc.returncode != 0 or not spice.is_file() or not odb.is_file():
        return {
            "status": "fail",
            "reason": err or "pdn_extract_failed",
            "via": "openroad_pdn_extract",
            "gold": False,
            "cost_s": time.time() - t0,
            "log": str(logp),
        }
    try:
        exp = subprocess.run(
            ["openroad", "-python", "-no_init", "-exit", str(EXPORT_INSTS), str(odb), str(insts)],
            capture_output=True,
            text=True,
            timeout=min(30.0, timeout_s),
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "fail",
            "reason": "inst map export timeout",
            "via": "openroad_pdn_extract",
            "gold": False,
            "spice": str(spice),
            "cost_s": time.time() - t0,
        }
    if exp.returncode != 0 or not insts.is_file():
        return {
            "status": "fail",
            "reason": (exp.stderr or exp.stdout or "inst map export failed")[-300:],
            "via": "openroad_pdn_extract",
            "gold": False,
            "spice": str(spice),
            "cost_s": time.time() - t0,
        }
    n_r, n_i = _spice_counts(spice)
    rows = _ROW.findall(log)
    hpwl = float(rows[-1][2]) if rows else None
    overflow = float(rows[-1][1]) if rows else None
    return {
        "status": "ok",
        "spice": str(spice),
        "insts": str(insts),
        "odb": str(odb),
        "n_r": n_r,
        "n_i": n_i,
        "hpwl_um": hpwl,
        "overflow": overflow,
        "util": float(util),
        "density": float(density),
        "legalize": "detailed_placement",
        "gold": False,
        "via": (
            "openroad write_pg_spice after place_pins+tapcell+pdngen+GPL+DP"
            + (" + IR-bin density cap" if blk else "")
            + " — candidate mesh, not finish, not gold"
        ),
        "cost_s": time.time() - t0,
        **_parse_region_bin(log),
        **(
            {
                "region": region,
                "x_dbu": x_dbu,
                "y_dbu": y_dbu,
                "region_density": cap,
            }
            if blk
            else {}
        ),
    }


def extract_pdn_bumps(
    odb: Path,
    out_dir: Path,
    *,
    bump_dx: float = 80.0,
    bump_dy: float = 80.0,
    bump_size: float = 40.0,
    bump_interval: int = 3,
    pkg_r: float = 0.05,
    timeout_s: float = 45.0,
    insts_src: Path | str | None = None,
) -> dict:
    """Same legalized ODB, denser bump sources. Not a new GPL, not gold, not pkg_r.

    write_pg_spice voltage sources are ideal; on-die static IR moves with bump
    pitch. Package R stays a worker-side Thevenin pad (static_ir_pkg_mv).
    """
    if not extract_available():
        return {
            "status": "GAP",
            "reason": "openroad/LEF/PDN tcl missing",
            "via": "openroad_pdn_bumps",
            "gold": False,
        }
    odb = Path(odb)
    out_dir = Path(out_dir)
    if not odb.is_file():
        return {"status": "fail", "reason": f"missing {odb}", "via": "openroad_pdn_bumps", "gold": False}
    out_dir.mkdir(parents=True, exist_ok=True)
    spice = out_dir / "pg_vdd_bumps.sp"
    out_odb = out_dir / "candidate.odb"
    insts = out_dir / "inst_power_map.json"
    logp = out_dir / "extract.log"
    tcl = f"""
set_thread_count 1
read_lef {TECH_LEF}
read_lef {SC_LEF}
read_liberty {LIB}
read_db {odb}
read_sdc {SDC}
set_power_activity -global -activity 0.2 -duty 0.5
set_pdnsim_source_settings -bump_dx {int(bump_dx)} -bump_dy {int(bump_dy)} -bump_size {int(bump_size)} -bump_interval {int(bump_interval)} -external_resistance {float(pkg_r)}
analyze_power_grid -net VDD -source_type BUMPS
write_pg_spice -net VDD -source_type BUMPS {spice}
write_db {out_odb}
puts DSE_PDN_BUMPS_OK
exit
"""
    t0 = time.time()
    script = out_dir / "extract.tcl"
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
            "reason": f"PDN bump extract timeout {timeout_s}s",
            "via": "openroad_pdn_bumps",
            "gold": False,
            "cost_s": time.time() - t0,
        }
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    logp.write_text(log)
    err = next(
        (ln.strip() for ln in log.splitlines() if ln.startswith("[ERROR") or ln.startswith("Error:")),
        "",
    )
    if "DSE_PDN_BUMPS_OK" not in log or proc.returncode != 0 or not spice.is_file():
        return {
            "status": "fail",
            "reason": err or "pdn_bump_extract_failed",
            "via": "openroad_pdn_bumps",
            "gold": False,
            "cost_s": time.time() - t0,
            "log": str(logp),
        }
    if out_odb.is_file():
        try:
            exp = subprocess.run(
                ["openroad", "-python", "-no_init", "-exit", str(EXPORT_INSTS), str(out_odb), str(insts)],
                capture_output=True,
                text=True,
                timeout=min(30.0, timeout_s),
            )
            if exp.returncode != 0 or not insts.is_file():
                insts = Path(insts_src) if insts_src and Path(insts_src).is_file() else insts
        except subprocess.TimeoutExpired:
            if insts_src and Path(insts_src).is_file():
                insts = Path(insts_src)
    elif insts_src and Path(insts_src).is_file():
        insts = Path(insts_src)
    if not Path(insts).is_file():
        return {
            "status": "fail",
            "reason": "inst map missing after bump restamp",
            "via": "openroad_pdn_bumps",
            "gold": False,
            "spice": str(spice),
            "cost_s": time.time() - t0,
        }
    n_r, n_i = _spice_counts(spice)
    n_v = sum(1 for ln in spice.read_text(errors="replace").splitlines() if ln.startswith("V"))
    return {
        "status": "ok",
        "spice": str(spice),
        "insts": str(insts),
        "odb": str(out_odb) if out_odb.is_file() else str(odb),
        "n_r": n_r,
        "n_i": n_i,
        "n_v": n_v,
        "bump_dx": float(bump_dx),
        "bump_dy": float(bump_dy),
        "bump_size": float(bump_size),
        "bump_interval": int(bump_interval),
        "legalize": "reuse_odb",
        "gold": False,
        "via": (
            f"openroad write_pg_spice bump_dx={bump_dx} on the static-IR champ ODB "
            "— same place, not a new GPL, not decap, not gold"
        ),
        "cost_s": time.time() - t0,
    }
