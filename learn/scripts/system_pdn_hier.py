#!/usr/bin/env python3
"""
Hierarchical *System* PDN analysis with ngspice.

Domains (not chip PDNSim):
  VRM → board plane/decap → package RLC/bumps → die C + current load

Outputs:
  - SPICE netlists (tran + ac)
  - AC impedance Z(f) seen at the die
  - Transient voltages under a die load-step
  - JSON report for /pkg System PDN / system_pdn

Requires: ngspice
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path


def load_cfg(path: Path) -> dict:
    return json.loads(path.read_text())


def _ladder(cfg: dict) -> list[str]:
    """Shared passive ladder: VRM → board → package → die node n_die."""
    v = cfg["vdd"]
    vrm = cfg["vrm"]
    brd = cfg["board"]
    pkg = cfg["package"]
    die = cfg["die"]

    n = max(int(pkg.get("n_bumps", 1)), 1)
    r_bump = float(pkg["r_bump"]) / n
    l_bump = float(pkg["l_bump"]) / n

    return [
        f"V_VRM n_vrm_src 0 DC {v}",
        f"R_VRM n_vrm_src n_vrm {vrm['r_out']}",
        f"L_VRM n_vrm n_vrm_l {vrm['l_out']}",
        f"C_VRM n_vrm_l 0 {vrm['c_out']}",
        f"R_ESR_VRM n_vrm_l n_board_in {vrm['esr_cout']}",
        "",
        f"R_PLANE n_board_in n_board {brd['r_plane']}",
        f"L_PLANE n_board n_board_l {brd['l_plane']}",
        f"C_BULK n_board_l 0 {brd['c_bulk']}",
        f"R_ESR_BULK n_board_l n_board_mid {brd['esr_bulk']}",
        f"C_HF n_board_mid 0 {brd['c_hf']}",
        f"R_ESR_HF n_board_mid n_board_out {brd['esr_hf']}",
        f"L_VIA n_board_out n_pkg_in {brd['l_via_to_pkg']}",
        "",
        f"R_PKG n_pkg_in n_pkg {pkg['r_pkg']}",
        f"L_PKG n_pkg n_pkg_l {pkg['l_pkg']}",
        f"C_PKG n_pkg_l 0 {pkg['c_pkg']}",
        f"R_BUMP n_pkg_l n_die_pre {r_bump}",
        f"L_BUMP n_die_pre n_die {l_bump}",
        "",
        f"C_DIE n_die 0 {die['c_die']}",
    ]


def write_tran_netlist(cfg: dict, i_die_avg: float, out: Path) -> None:
    tr = cfg["tran"]
    i_idle = i_die_avg * float(tr["i_idle_factor"])
    i_peak = i_die_avg * float(tr["i_peak_factor"])
    edge = float(tr["edge_ns"]) * 1e-9
    ton = 80e-9
    period = 1.0

    lines = [
        "* System PDN TRAN — VRM / board / package / die load-step",
        f"* I_avg={i_die_avg:.6e} idle={i_idle:.6e} peak={i_peak:.6e}",
        "",
        *_ladder(cfg),
        "",
        f"I_DIE n_die 0 PULSE({i_idle} {i_peak} 20n {edge} {edge} {ton} {period})",
        "",
        ".control",
        "set filetype=ascii",
        f"tran {tr['t_step']} {tr['t_stop']}",
        "wrdata __TRAN__ v(n_vrm_l) v(n_board_out) v(n_pkg_l) v(n_die)",
        "quit",
        ".endc",
        ".end",
        "",
    ]
    out.write_text("\n".join(lines))


def write_ac_netlist(cfg: dict, out: Path) -> None:
    ac = cfg["ac"]
    lines = [
        "* System PDN AC — impedance Z(f) at die (Iac=1A → |Z|=|V(n_die)|)",
        "",
        *_ladder(cfg),
        "",
        "I_AC n_die 0 DC 0 AC 1",
        "",
        ".control",
        "set filetype=ascii",
        f"ac dec {ac['points_per_decade']} {ac['f_start']} {ac['f_stop']}",
        "let zmag = abs(v(n_die))",
        "wrdata __AC__ zmag",
        "quit",
        ".endc",
        ".end",
        "",
    ]
    out.write_text("\n".join(lines))


def parse_wrdata(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        try:
            parts = [float(x) for x in line.split()]
        except ValueError:
            continue
        if parts:
            rows.append(parts)
    return rows


def analyze(cfg: dict, tran_rows: list, ac_rows: list, i_die_avg: float) -> dict:
    vdd = float(cfg["vdd"])
    die_wave: list[tuple[float, float]] = []
    vmin_die = vdd

    if tran_rows:
        sample = tran_rows[0]
        # ngspice wrdata multi-vector: t v1 t v2 t v3 t v4
        if len(sample) >= 8:
            for r in tran_rows:
                t = r[0]
                vv = [r[1], r[3], r[5], r[7]]
                die_wave.append((t, vv[3]))
                vmin_die = min(vmin_die, vv[3])
        elif len(sample) >= 5:
            for r in tran_rows:
                t, _a, _b, _c, d = r[0], r[1], r[2], r[3], r[4]
                die_wave.append((t, d))
                vmin_die = min(vmin_die, d)

    z_curve: list[dict] = []
    z_max = 0.0
    f_at_zmax = 0.0
    if ac_rows:
        for r in ac_rows:
            if len(r) >= 3:
                f, re, im = r[0], r[1], r[2]
                mag = math.hypot(re, im)
            elif len(r) >= 2:
                f, mag = r[0], abs(r[1])
            else:
                continue
            z_curve.append({"f_hz": f, "z_ohm": mag})
            if mag > z_max:
                z_max = mag
                f_at_zmax = f

    z_target = float(cfg["ac"]["z_target_mohm"]) / 1000.0
    droop = vdd - vmin_die
    step = max(1, len(die_wave) // 200)
    z_step = max(1, len(z_curve) // 100) if z_curve else 1

    return {
        "kind": "system_pdn",
        "engine": "ngspice-hierarchical",
        "domains": ["VRM", "board", "package", "die"],
        "vdd": vdd,
        "i_die_avg_a": i_die_avg,
        "transient": {
            "v_die_min": vmin_die,
            "droop_v": droop,
            "droop_mv": droop * 1000.0,
            "droop_pct": 100.0 * droop / vdd if vdd else 0.0,
            "wave_die": [{"t_s": t, "v": v} for t, v in die_wave[::step]],
        },
        "impedance": {
            "z_max_ohm": z_max,
            "z_max_mohm": z_max * 1000.0,
            "f_at_zmax_hz": f_at_zmax,
            "z_target_mohm": cfg["ac"]["z_target_mohm"],
            "pass_target": (z_max <= z_target) if z_max > 0 else None,
            "curve": z_curve[::z_step],
        },
        "summary": (
            f"System PDN · die droop {droop * 1e3:.2f} mV ({100 * droop / vdd:.2f}%) · "
            f"Zmax {z_max * 1e3:.2f} mΩ @ {f_at_zmax:.3e} Hz · Iavg {i_die_avg * 1e3:.3f} mA"
        ),
    }


def guess_die_current(repo: Path, variant: str, fallback: float) -> float:
    # Prefer finished design power from activity / finish logs
    for name in (
        f"activity_power_{variant}.log",
        "activity_power.log",
        f"system_pdn_{variant}.log",
    ):
        p = repo / "learn/sim/reports" / name
        if not p.exists():
            continue
        text = p.read_text(errors="ignore")
        m = re.search(
            r"Total\s+[\d.eE+-]+\s+[\d.eE+-]+\s+[\d.eE+-]+\s+([\d.eE+-]+)",
            text,
        )
        if m:
            pwr = float(m.group(1))
            if pwr > 0:
                return max(pwr / 1.1, fallback)

    # Optional chip IR report (separate analysis) if present
    rep = repo / "learn/sim/reports" / f"pdn_chip_ir_{variant}.json"
    if not rep.exists():
        rep = repo / "learn/sim/reports" / f"pdn_transient_{variant}.json"
    if rep.exists():
        try:
            r = json.loads(rep.read_text())
            i = float(r.get("static", {}).get("total_current_a") or 0)
            if i > 0:
                return i
        except Exception:
            pass
    return fallback


def run_one(netlist_src: Path, work: Path, tag: str, placeholder: str) -> Path:
    text = netlist_src.read_text().replace(placeholder, str(work / tag))
    nl = work / f"{tag}.sp"
    nl.write_text(text)
    log = work / f"{tag}.ngspice.log"
    subprocess.run(
        ["ngspice", "-b", "-o", str(log), str(nl)],
        check=False,
        cwd=str(work),
        capture_output=True,
        text=True,
    )
    for p in sorted(work.glob(f"{tag}*")):
        if p.suffix == ".data" or p.name == tag:
            return p
    # ngspice sometimes writes tag.data
    candidate = work / f"{tag}.data"
    return candidate if candidate.exists() else work / tag


def main() -> int:
    ap = argparse.ArgumentParser(description="Hierarchical System PDN (ngspice)")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument("--i-die", type=float, default=0.0)
    args = ap.parse_args()

    cfg = load_cfg(Path(args.config))
    repo = Path(args.repo)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if subprocess.run(["which", "ngspice"], capture_output=True).returncode != 0:
        print("FAIL: ngspice non installato (apt install ngspice)", file=sys.stderr)
        return 2

    i_die = args.i_die if args.i_die > 0 else guess_die_current(repo, args.variant, 0.002)

    tran_src = out_dir / "system_pdn_tran.src.sp"
    ac_src = out_dir / "system_pdn_ac.src.sp"
    write_tran_netlist(cfg, i_die, tran_src)
    write_ac_netlist(cfg, ac_src)

    tpath = run_one(tran_src, out_dir, "tran", "__TRAN__")
    apath = run_one(ac_src, out_dir, "ac", "__AC__")

    tran_rows = parse_wrdata(tpath)
    ac_rows = parse_wrdata(apath)
    report = analyze(cfg, tran_rows, ac_rows, i_die)
    report["ok"] = bool(tran_rows) and bool(ac_rows)
    report["variant"] = args.variant
    report["files"] = {
        "tran_netlist": str(out_dir / "tran.sp"),
        "ac_netlist": str(out_dir / "ac.sp"),
        "tran_data": str(tpath),
        "ac_data": str(apath),
        "config": args.config,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
    print("SYSTEM_PDN_HIER_DONE")
    print(report["summary"])
    print(f"report → {args.report}")

    if not tran_rows:
        print("[warn] transient data empty — see *.ngspice.log", file=sys.stderr)
        return 3
    if not ac_rows:
        print("[warn] AC Z(f) data empty — see ac.ngspice.log", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
