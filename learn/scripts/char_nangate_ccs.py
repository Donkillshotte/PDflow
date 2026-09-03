#!/usr/bin/env python3
"""Re-characterize GCD-used Nangate cells: CCS I(slew, Vout) from CDL + PTM.

Official ORFS Nangate liberty stays NLDM. Writes a sidecar .lib with real
ngspice output_current tables. Not foundry CCS. Cells that do not switch
or produce no current are dropped, not faked.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "learn" / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn" / "scripts"))
from pdn_current import parse_ccs_output_current, probe_liberty_current_model  # noqa: E402

VDD = 1.1
SLEWS_S = (5e-12, 20e-12, 80e-12)
VOUTS = (0.0, 0.275, 0.55, 0.825, 1.1)
CLOAD_F = 10e-15
# Combinational GCD masters with a single enabled timing arc.
CELLS = (
    {"name": "INV_X1", "inp": "A", "out": "ZN", "sense": "negative", "tie": {}},
    {"name": "INV_X2", "inp": "A", "out": "ZN", "sense": "negative", "tie": {}},
    {"name": "INV_X4", "inp": "A", "out": "ZN", "sense": "negative", "tie": {}},
    {"name": "BUF_X1", "inp": "A", "out": "Z", "sense": "positive", "tie": {}},
    {"name": "BUF_X2", "inp": "A", "out": "Z", "sense": "positive", "tie": {}},
    {"name": "NAND2_X1", "inp": "A1", "out": "ZN", "sense": "negative", "tie": {"A2": VDD}},
    {"name": "NAND2_X2", "inp": "A1", "out": "ZN", "sense": "negative", "tie": {"A2": VDD}},
    {"name": "NOR2_X1", "inp": "A1", "out": "ZN", "sense": "negative", "tie": {"A2": 0.0}},
    {"name": "AND2_X1", "inp": "A1", "out": "ZN", "sense": "positive", "tie": {"A2": VDD}},
    {"name": "AND2_X2", "inp": "A1", "out": "ZN", "sense": "positive", "tie": {"A2": VDD}},
    {"name": "OR2_X1", "inp": "A1", "out": "ZN", "sense": "positive", "tie": {"A2": 0.0}},
    {"name": "BUF_X4", "inp": "A", "out": "Z", "sense": "positive", "tie": {}},
    {"name": "INV_X8", "inp": "A", "out": "ZN", "sense": "negative", "tie": {}},
    {"name": "CLKBUF_X1", "inp": "A", "out": "Z", "sense": "positive", "tie": {}},
    {"name": "CLKBUF_X3", "inp": "A", "out": "Z", "sense": "positive", "tie": {}},
    # AOI21 ZN=!(A|(B1&B2)); B1=B2=0 → inverter on A.
    {"name": "AOI21_X1", "inp": "A", "out": "ZN", "sense": "negative", "tie": {"B1": 0.0, "B2": 0.0}},
    {"name": "AOI21_X2", "inp": "A", "out": "ZN", "sense": "negative", "tie": {"B1": 0.0, "B2": 0.0}},
    # OAI21 ZN=!(A&(B1|B2)); B1=B2=VDD → inverter on A.
    {"name": "OAI21_X1", "inp": "A", "out": "ZN", "sense": "negative", "tie": {"B1": VDD, "B2": VDD}},
    {"name": "OAI21_X2", "inp": "A", "out": "ZN", "sense": "negative", "tie": {"B1": VDD, "B2": VDD}},
)


def _orfs_cdl(root: Path) -> Path:
    p = root / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/cdl/NangateOpenCellLibrary.cdl"
    if not p.is_file():
        raise FileNotFoundError(f"Nangate CDL missing: {p}")
    return p


def extract_subckt(cdl_text: str, cell: str) -> str:
    start = None
    lines = cdl_text.splitlines()
    pat = re.compile(rf"^\.SUBCKT\s+{re.escape(cell)}\b", re.I)
    for i, line in enumerate(lines):
        if pat.match(line.strip()):
            start = i
            break
    if start is None:
        raise RuntimeError(f"{cell} not in CDL")
    out = []
    for line in lines[start:]:
        out.append(line)
        if re.match(r"^\.ENDS\b", line.strip(), re.I):
            return "\n".join(out) + "\n"
    raise RuntimeError(f"{cell} .ENDS missing")


def write_ptm_alias(ptm_src: Path, dest: Path) -> None:
    text = ptm_src.read_text()
    text = text.replace(".model  nmos  nmos", ".model  NMOS_VTL nmos", 1)
    text = text.replace(".model  pmos  pmos", ".model  PMOS_VTL pmos", 1)
    dest.write_text(text)


def _parse_wrdata(path: Path) -> tuple[list[float], list[float], list[float]]:
    times, volts, amps = [], [], []
    for raw in path.read_text().splitlines():
        parts = raw.split()
        if len(parts) < 4:
            continue
        try:
            t, v, i = float(parts[0]), float(parts[1]), float(parts[3])
        except ValueError:
            continue
        times.append(t)
        volts.append(v)
        amps.append(i)
    if len(times) < 8:
        raise RuntimeError(f"short wrdata {path}")
    return times, volts, amps


def _sample_i_at_v(volts: list[float], amps: list[float], targets: tuple[float, ...]) -> list[float]:
    out: list[float] = []
    for vt in targets:
        found: float | None = None
        for i in range(len(volts) - 1):
            v0, v1 = volts[i], volts[i + 1]
            if (v0 - vt) * (v1 - vt) <= 0.0:
                if v1 == v0:
                    found = amps[i]
                else:
                    u = (vt - v0) / (v1 - v0)
                    found = amps[i] + u * (amps[i + 1] - amps[i])
                break
        if found is None:
            j = min(range(len(volts)), key=lambda k: abs(volts[k] - vt))
            found = amps[j]
        out.append(abs(float(found)))
    return out


def _crossing_time(times: list[float], volts: list[float], target: float) -> float | None:
    for i in range(len(volts) - 1):
        v0, v1 = volts[i], volts[i + 1]
        if (v0 - target) * (v1 - target) <= 0.0:
            if v1 == v0:
                return times[i]
            u = (target - v0) / (v1 - v0)
            return times[i] + u * (times[i + 1] - times[i])
    return None


def run_edge(
    work: Path,
    *,
    models: Path,
    netlist: Path,
    spec: dict,
    slew_s: float,
    direction: str,
) -> dict:
    t0 = 40e-12
    tstop = t0 + slew_s + 400e-12
    sense = spec["sense"]
    # Input PWL: for negative_unate, rising A → falling ZN.
    rise_in = direction == "fall" if sense == "negative" else direction == "rise"
    if rise_in:
        pwl = f"0 0 {t0} 0 {t0 + slew_s} {VDD} {tstop} {VDD}"
    else:
        pwl = f"0 {VDD} {t0} {VDD} {t0 + slew_s} 0 {tstop} 0"
    ties = "\n".join(f"Vtie_{pin} {pin} 0 DC {val}" for pin, val in spec["tie"].items())
    tag = f"{spec['name']}_{direction}_{slew_s:.3e}"
    sp = work / f"{tag}.sp"
    dat = work / f"{tag}.txt"
    outp = spec["out"]
    inp = spec["inp"]
    sp.write_text(
        f"""* {spec['name']} CCS {direction} slew={slew_s}
.include {models}
.include {netlist}
VDD VDD 0 DC {VDD}
VSS VSS 0 DC 0
VA {inp} 0 PWL({pwl})
{ties}
Vsense {outp} mid DC 0
CL mid 0 {CLOAD_F}
X1 {inp} {' '.join(spec['tie'])} {outp} VDD VSS {spec['name']}
.tran 0.05p {tstop}
.control
run
let iout = vsense#branch
wrdata {dat} v(mid) iout
quit
.endc
.end
"""
    )
    # X1 pin order must match .SUBCKT. Rebuild from the netlist header.
    header = next(ln for ln in netlist.read_text().splitlines() if ln.upper().startswith(".SUBCKT"))
    pins = header.split()[2:]
    inst_map = {inp: inp, outp: outp, "VDD": "VDD", "VSS": "VSS", **{p: p for p in spec["tie"]}}
    inst_pins = " ".join(inst_map.get(p, p) for p in pins)
    sp.write_text(
        f"""* {spec['name']} CCS {direction} slew={slew_s}
.include {models}
.include {netlist}
VDD VDD 0 DC {VDD}
VSS VSS 0 DC 0
VA {inp} 0 PWL({pwl})
{ties}
Vsense {outp} mid DC 0
CL mid 0 {CLOAD_F}
X1 {inst_pins} {spec['name']}
.tran 0.05p {tstop}
.control
run
let iout = vsense#branch
wrdata {dat} v(mid) iout
quit
.endc
.end
"""
    )
    proc = subprocess.run(
        ["ngspice", "-b", str(sp)],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=60,
    )
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if not dat.is_file():
        raise RuntimeError(f"ngspice produced no wrdata for {spec['name']}\n{log[-1200:]}")
    times, volts, amps = _parse_wrdata(dat)
    i_abs = _sample_i_at_v(volts, amps, VOUTS)
    mid = _crossing_time(times, volts, 0.5 * VDD)
    t_in = t0 + 0.5 * slew_s
    delay_s = None if mid is None else abs(mid - t_in)
    return {
        "cell": spec["name"],
        "direction": direction,
        "slew_s": slew_s,
        "i_abs_a": i_abs,
        "i_peak_a": max(abs(x) for x in amps),
        "delay_s": delay_s,
        "n_samples": len(times),
        "v_min": min(volts),
        "v_max": max(volts),
        "switched": (max(volts) - min(volts)) > 0.8,
        "rc": proc.returncode,
    }


def _fmt_row(vals: list[float]) -> str:
    return ", ".join(f"{v:.6e}" for v in vals)


def write_cell_block(spec: dict, tables: dict[str, list[list[float]]]) -> str:
    s1 = ", ".join(f"{s:.6e}" for s in SLEWS_S)
    s2 = ", ".join(f"{v:.3f}" for v in VOUTS)
    blocks = []
    for direction in ("fall", "rise"):
        rows = tables[direction]
        joined = ", \\\n\t        ".join(f'"{_fmt_row(row)}"' for row in rows)
        blocks.append(
            f"""
      output_current_{direction} (ptm45_{spec['name'].lower()}) {{
        index_1 ("{s1}");
        index_2 ("{s2}");
        values ({joined});
      }}"""
        )
    fn = "!A" if spec["sense"] == "negative" else "A"
    if spec["inp"] != "A":
        fn = f"!{spec['inp']}" if spec["sense"] == "negative" else spec["inp"]
    return f"""
  cell ({spec['name']}) {{
    pin ({spec['out']}) {{
      direction : output;
      function : "{fn}";
      timing () {{
        related_pin : "{spec['inp']}";
        timing_sense : {"negative_unate" if spec["sense"] == "negative" else "positive_unate"};{"".join(blocks)}
      }}
    }}
  }}"""


def write_sidecar_lib(path: Path, cells: list[tuple[dict, dict]]) -> None:
    body = "".join(write_cell_block(spec, tables) for spec, tables in cells)
    path.write_text(
        f"""/* Educational sidecar. PTM 45 nm re-char. Not Nangate CCS. */
library (nangate45_ptm_ccs_sidecar) {{
  delay_model : table_lookup;
  time_unit : "1s";
  voltage_unit : "1V";
  current_unit : "1A";
  nom_voltage : {VDD};
{body}
}}
"""
    )


def _cell_ok(runs: list[dict]) -> bool:
    if len(runs) != 2 * len(SLEWS_S):
        return False
    return all(r["switched"] and r["i_peak_a"] > 1e-5 and max(r["i_abs_a"]) > 1e-5 for r in runs)


def main() -> int:
    variant = os.environ.get("FLOW_VARIANT", "flowlab")
    root = _ROOT
    if not shutil.which("ngspice"):
        print("ngspice missing", file=sys.stderr)
        return 2
    ptm = root / "learn/platforms/nangate45/spice/ptm45hp.pm"
    if not ptm.is_file():
        print("PTM card missing", ptm, file=sys.stderr)
        return 2
    cdl_text = _orfs_cdl(root).read_text(errors="replace")
    official = root / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
    official_probe = probe_liberty_current_model(official if official.is_file() else None)

    work = Path(tempfile.mkdtemp(prefix="ccs_char_"))
    models = work / "ptm_vtl.pm"
    write_ptm_alias(ptm, models)

    kept: list[tuple[dict, dict]] = []
    skipped: list[dict] = []
    all_runs: list[dict] = []
    inv_mid = None
    for spec in CELLS:
        try:
            netlist = work / f"{spec['name']}.sp"
            netlist.write_text(extract_subckt(cdl_text, spec["name"]))
            tables = {"fall": [], "rise": []}
            runs: list[dict] = []
            for direction in ("fall", "rise"):
                for slew in SLEWS_S:
                    rec = run_edge(
                        work, models=models, netlist=netlist, spec=spec, slew_s=slew, direction=direction
                    )
                    runs.append(rec)
                    tables[direction].append(rec["i_abs_a"])
                    print(
                        f"{spec['name']} {direction} slew={slew * 1e12:.1f}ps  "
                        f"Ipeak={rec['i_peak_a'] * 1e3:.3f}mA  "
                        f"delay={((rec['delay_s'] or 0) * 1e12):.2f}ps  "
                        f"{'OK' if rec['switched'] else 'NO_SWITCH'}"
                    )
            if _cell_ok(runs):
                kept.append((spec, tables))
                all_runs.extend(runs)
                if spec["name"] == "INV_X1":
                    inv_mid = next(
                        r for r in runs if r["direction"] == "fall" and abs(r["slew_s"] - 20e-12) < 1e-15
                    )
            else:
                skipped.append({"cell": spec["name"], "reason": "no switch or Ipeak too small"})
        except Exception as exc:
            print(f"{spec['name']} SKIP: {exc}", file=sys.stderr)
            skipped.append({"cell": spec["name"], "reason": str(exc)})

    if not kept:
        print("no cells produced real CCS tables", file=sys.stderr)
        return 1

    lib_path = root / "learn/sim/lib/nangate45_ptm_ccs_sidecar.lib"
    inv_path = root / "learn/sim/lib/INV_X1_ptm45_ccs.lib"
    lib_path.parent.mkdir(parents=True, exist_ok=True)
    write_sidecar_lib(lib_path, kept)
    inv_only = [(s, t) for s, t in kept if s["name"] == "INV_X1"]
    if inv_only:
        write_sidecar_lib(inv_path, inv_only)
    sidecar_probe = probe_liberty_current_model(lib_path)
    parsed = parse_ccs_output_current(lib_path.read_text())

    nldm_ref_s = 19.2e-12
    delay_ratio = ((inv_mid["delay_s"] or 0.0) / nldm_ref_s) if inv_mid else 0.0
    ok = (
        sidecar_probe.get("status") == "READY"
        and sidecar_probe.get("n_ccs_tables", 0) >= 2 * len(kept)
        and official_probe.get("status") == "GAP"
        and official_probe.get("n_ccs_tables", 0) == 0
        and any(s["name"] == "INV_X1" for s, _ in kept)
        and 0.25 <= delay_ratio <= 4.0
    )
    names = [s["name"] for s, _ in kept]
    report = {
        "ok": ok,
        "kind": "ccs_char",
        "status": "READY" if ok else "FAIL",
        "cells": names,
        "n_cells": len(names),
        "skipped": skipped,
        "engine": "ngspice+ptm45hp",
        "sidecar_lib": str(lib_path),
        "inv_sidecar_lib": str(inv_path) if inv_only else None,
        "official_lib": str(official) if official.is_file() else None,
        "official_probe": official_probe,
        "sidecar_probe": sidecar_probe,
        "n_ccs_tables": len(parsed),
        "slews_s": list(SLEWS_S),
        "vouts_v": list(VOUTS),
        "cload_fF": CLOAD_F * 1e15,
        "runs": all_runs,
        "mid_fall_delay_ps": (inv_mid["delay_s"] or 0.0) * 1e12 if inv_mid else None,
        "nldm_ref_delay_ps": nldm_ref_s * 1e12,
        "delay_ratio_vs_nldm": delay_ratio,
        "educational_note": (
            "PTM 45 nm re-characterization of GCD combinational cells. "
            "Not original Nangate CCS. Official typical.lib stays NLDM GAP. "
            "Do not restamp gold Dynamic IR with this sidecar."
        ),
        "summary": (
            f"PTM CCS {len(names)} cells / {sidecar_probe.get('n_ccs_tables')} tables · "
            f"INV_X1 fall@20ps {((inv_mid['delay_s'] or 0) * 1e12) if inv_mid else 0:.1f}ps "
            f"(NLDM ref {nldm_ref_s * 1e12:.1f}ps, ratio {delay_ratio:.2f}) · "
            f"official {official_probe.get('kind')}/{official_probe.get('status')}"
        ),
    }
    out = root / "learn/sim/reports" / f"ccs_char_{variant}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(report["summary"])
    print("WROTE", lib_path)
    print("WROTE", out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
