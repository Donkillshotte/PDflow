#!/usr/bin/env python3
"""Re-characterize INV_X1 CCS I(slew, Vout) from Nangate CDL + PTM 45 nm.

Official ORFS Nangate liberty stays NLDM. This writes a sidecar .lib with
real ngspice output_current tables. Not foundry CCS. Not a synthetic grid.
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
CELL = "INV_X1"
IN_PIN = "A"
OUT_PIN = "ZN"
SLEWS_S = (5e-12, 20e-12, 80e-12)
VOUTS = (0.0, 0.275, 0.55, 0.825, 1.1)
CLOAD_F = 10e-15
SUBCKT_RE = re.compile(rf"^\.SUBCKT\s+{re.escape(CELL)}\b", re.I)


def _orfs_cdl(root: Path) -> Path:
    p = root / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/cdl/NangateOpenCellLibrary.cdl"
    if not p.is_file():
        raise FileNotFoundError(f"Nangate CDL missing: {p}")
    return p


def extract_inv_x1(cdl_text: str) -> str:
    lines = cdl_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if SUBCKT_RE.match(line.strip()):
            start = i
            break
    if start is None:
        raise RuntimeError(f"{CELL} not in CDL")
    out = []
    for line in lines[start:]:
        out.append(line)
        if re.match(r"^\.ENDS\b", line.strip(), re.I):
            return "\n".join(out) + "\n"
    raise RuntimeError(f"{CELL} .ENDS missing")


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
            t = float(parts[0])
            v = float(parts[1])
            i = float(parts[3])
        except ValueError:
            continue
        times.append(t)
        volts.append(v)
        amps.append(i)
    if len(times) < 8:
        raise RuntimeError(f"short wrdata {path}")
    return times, volts, amps


def _sample_i_at_v(
    volts: list[float], amps: list[float], targets: tuple[float, ...]
) -> list[float]:
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
    slew_s: float,
    direction: str,
) -> dict:
    t0 = 40e-12
    tstop = t0 + slew_s + 400e-12
    if direction == "fall":
        pwl = f"0 0 {t0} 0 {t0 + slew_s} {VDD} {tstop} {VDD}"
    else:
        pwl = f"0 {VDD} {t0} {VDD} {t0 + slew_s} 0 {tstop} 0"
    sp = work / f"{direction}_{slew_s:.3e}.sp"
    dat = work / f"{direction}_{slew_s:.3e}.txt"
    sp.write_text(
        f"""* {CELL} CCS {direction} slew={slew_s}
.include {models}
.include {netlist}
VDD VDD 0 DC {VDD}
VSS VSS 0 DC 0
VA A 0 PWL({pwl})
Vsense ZN mid DC 0
CL mid 0 {CLOAD_F}
X1 A ZN VDD VSS {CELL}
.tran 0.05p {tstop}
.control
run
let iout = vsense#branch
wrdata {dat} v(zn) iout
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
        raise RuntimeError(f"ngspice produced no wrdata\n{log[-1500:]}")
    times, volts, amps = _parse_wrdata(dat)
    i_abs = _sample_i_at_v(volts, amps, VOUTS)
    mid = _crossing_time(times, volts, 0.5 * VDD)
    t_in = t0 + 0.5 * slew_s
    delay_s = None if mid is None else abs(mid - t_in)
    return {
        "direction": direction,
        "slew_s": slew_s,
        "i_abs_a": i_abs,
        "i_peak_a": max(abs(x) for x in amps),
        "delay_s": delay_s,
        "n_samples": len(times),
        "v_min": min(volts),
        "v_max": max(volts),
    }


def _fmt_row(vals: list[float]) -> str:
    return ", ".join(f"{v:.6e}" for v in vals)


def write_sidecar_lib(path: Path, tables: dict[str, list[list[float]]]) -> None:
    s1 = ", ".join(f"{s:.6e}" for s in SLEWS_S)
    s2 = ", ".join(f"{v:.3f}" for v in VOUTS)
    blocks = []
    for direction in ("fall", "rise"):
        rows = tables[direction]
        joined = ", \\\n\t        ".join(f'"{_fmt_row(row)}"' for row in rows)
        blocks.append(
            f"""
      output_current_{direction} (ptm45_inv_x1) {{
        index_1 ("{s1}");
        index_2 ("{s2}");
        values ({joined});
      }}"""
        )
    path.write_text(
        f"""/* Educational sidecar. PTM 45 nm re-char of {CELL}. Not Nangate CCS. */
library (nangate45_ptm_ccs_sidecar) {{
  delay_model : table_lookup;
  time_unit : "1s";
  voltage_unit : "1V";
  current_unit : "1A";
  nom_voltage : {VDD};
  cell ({CELL}) {{
    pin ({OUT_PIN}) {{
      direction : output;
      function : "!{IN_PIN}";
      timing () {{
        related_pin : "{IN_PIN}";
        timing_sense : negative_unate;{"".join(blocks)}
      }}
    }}
  }}
}}
"""
    )


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
    cdl = extract_inv_x1(_orfs_cdl(root).read_text(errors="replace"))
    official = root / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
    official_probe = probe_liberty_current_model(official if official.is_file() else None)

    work = Path(tempfile.mkdtemp(prefix="ccs_char_"))
    models = work / "ptm_vtl.pm"
    netlist = work / "inv_x1.sp"
    write_ptm_alias(ptm, models)
    netlist.write_text(cdl)

    runs: list[dict] = []
    tables = {"fall": [], "rise": []}
    try:
        for direction in ("fall", "rise"):
            for slew in SLEWS_S:
                rec = run_edge(work, models=models, netlist=netlist, slew_s=slew, direction=direction)
                runs.append(rec)
                tables[direction].append(rec["i_abs_a"])
                print(
                    f"{direction} slew={slew * 1e12:.1f}ps  "
                    f"Ipeak={rec['i_peak_a'] * 1e3:.3f}mA  "
                    f"delay={((rec['delay_s'] or 0) * 1e12):.2f}ps"
                )
    except Exception as exc:
        print("CCS char failed:", exc, file=sys.stderr)
        return 1

    lib_path = root / "learn/sim/lib/INV_X1_ptm45_ccs.lib"
    lib_path.parent.mkdir(parents=True, exist_ok=True)
    write_sidecar_lib(lib_path, tables)
    sidecar_probe = probe_liberty_current_model(lib_path)
    parsed = parse_ccs_output_current(lib_path.read_text())

    delays = [r["delay_s"] for r in runs if r["delay_s"]]
    mid_fall = next(
        r for r in runs if r["direction"] == "fall" and abs(r["slew_s"] - 20e-12) < 1e-15
    )
    # Nangate NLDM cell_fall ~19 ps at 17 ps slew / 7.6 fF. Order-of-magnitude check.
    nldm_ref_s = 19.2e-12
    delay_ratio = (mid_fall["delay_s"] or 0.0) / nldm_ref_s
    currents_ok = all(max(r["i_abs_a"]) > 1e-5 for r in runs)
    switched = all(r["v_max"] - r["v_min"] > 0.8 for r in runs)
    ok = (
        sidecar_probe.get("status") == "READY"
        and sidecar_probe.get("n_ccs_tables", 0) >= 2
        and official_probe.get("status") == "GAP"
        and official_probe.get("n_ccs_tables", 0) == 0
        and currents_ok
        and switched
        and 0.25 <= delay_ratio <= 4.0
    )
    report = {
        "ok": ok,
        "kind": "ccs_char",
        "status": "READY" if ok else "FAIL",
        "cell": CELL,
        "engine": "ngspice+ptm45hp",
        "sidecar_lib": str(lib_path),
        "official_lib": str(official) if official.is_file() else None,
        "official_probe": official_probe,
        "sidecar_probe": sidecar_probe,
        "n_ccs_tables": len(parsed),
        "slews_s": list(SLEWS_S),
        "vouts_v": list(VOUTS),
        "cload_fF": CLOAD_F * 1e15,
        "runs": runs,
        "mid_fall_delay_ps": (mid_fall["delay_s"] or 0.0) * 1e12,
        "nldm_ref_delay_ps": nldm_ref_s * 1e12,
        "delay_ratio_vs_nldm": delay_ratio,
        "educational_note": (
            "PTM 45 nm re-characterization of INV_X1. "
            "Not original Nangate CCS. Official typical.lib stays NLDM GAP. "
            "Do not restamp gold Dynamic IR with this sidecar."
        ),
        "summary": (
            f"INV_X1 PTM CCS {sidecar_probe.get('n_ccs_tables')} tables · "
            f"fall@20ps {((mid_fall['delay_s'] or 0) * 1e12):.1f}ps "
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
