#!/usr/bin/env python3
"""Dynamic IR on the OpenROAD write_pg_spice mesh (RedHawk-Dynamic *slice*).

Architecture (what this file actually does — not a product claim):

  write_pg_spice (R + I_avg + bump V)     ← OpenROAD PDNSim, static mesh
  inst_power_map.json (optional)          ← ODB placement, seq vs combo
       │
       ▼
  Current engine: per ITerm PWL triangle
       simultaneous | spatial stagger | clock-aware
       │
       ▼
  Backward-Euler  (G + C/dt) V_{n+1} = I_{n+1} + (C/dt) V_n
       sparse LU once, then timestep
       │
       ▼
  Vmin(t) waveform + V(x,y) at worst time + SVG heatmap

Honest limits: triangle ≠ Liberty CCS; RTL VCD does not name gate pins;
Nangate45 has no CCS current tables. This is the I(t)+BE+map layer that
vyges-em-ir (simultaneous t50, no waveform) does not expose.

Prior art: OpenROAD PSM/PDNSim (static), vyges-em-ir (BE, simultaneous),
EMSim (academic PWL architecture; VCS/PT-PX/HSpice), VoltSpot (arch-level).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu, spsolve

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pdn_transient import build_system, parse_spice, solve_static  # noqa: E402

COORD_RE = re.compile(r"(ITermNode|Node)_metal(\d+)_(-?\d+)_(-?\d+)")


def node_xy(name: str) -> tuple[float, float] | None:
    m = COORD_RE.search(name)
    if not m:
        return None
    return float(m.group(3)), float(m.group(4))


def load_insts(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    blob = json.loads(path.read_text())
    return blob.get("insts") or []


def nearest_inst(x: float, y: float, insts: list[dict], max_dbu: float = 800.0):
    best = None
    best_d = max_dbu
    for inst in insts:
        if inst.get("filler"):
            continue
        d = math.hypot(float(inst["x"]) - x, float(inst["y"]) - y)
        if d < best_d:
            best_d = d
            best = inst
    return best


def viridis(t: float) -> str:
    t = min(1.0, max(0.0, t))
    stops = [
        (0.00, (68, 1, 84)),
        (0.25, (59, 82, 139)),
        (0.50, (33, 145, 140)),
        (0.75, (94, 201, 98)),
        (1.00, (253, 231, 37)),
    ]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            u = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            r = int(c0[0] + u * (c1[0] - c0[0]))
            g = int(c0[1] + u * (c1[1] - c0[1]))
            b = int(c0[2] + u * (c1[2] - c0[2]))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#fde725"


def triangle_above_leak(t: float, t50: float, dur: float, i_pulse: float) -> float:
    if dur <= 0 or i_pulse <= 0:
        return 0.0
    half = 0.5 * dur
    tau = t - t50
    if abs(tau) >= half:
        return 0.0
    return i_pulse * (1.0 - abs(tau) / half)


def plan_events(
    currents: dict[str, float],
    idx: dict[str, int],
    insts: list[dict],
    *,
    mode: str,
    peak_factor: float,
    leak_frac: float,
    period_s: float,
    dur_s: float,
    t50_s: float,
) -> list[dict]:
    loads = [(n, i) for n, i in currents.items() if n != "0" and n in idx and i > 0]
    xs = []
    for n, _ in loads:
        xy = node_xy(n)
        xs.append(xy[0] if xy else 0.0)
    xmin, xmax = (min(xs), max(xs)) if xs else (0.0, 1.0)
    span = max(xmax - xmin, 1.0)

    events = []
    for n, i_avg in loads:
        xy = node_xy(n)
        inst = nearest_inst(xy[0], xy[1], insts) if xy else None
        seq = bool(inst and inst.get("seq"))
        leak = leak_frac * i_avg
        # Charge conservation over one clock: leak*T + I_pulse*dur/2 ≈ I_avg*T
        q_switch = max(0.0, (i_avg - leak) * period_s)
        i_from_q = (2.0 * q_switch / dur_s) if dur_s > 0 else 0.0
        i_pulse = min(peak_factor * i_avg, i_from_q if i_from_q > 0 else peak_factor * i_avg)
        i_pulse = max(i_pulse, 0.0)
        if mode == "simultaneous":
            t50 = t50_s
        elif mode == "spatial":
            nx = ((xy[0] - xmin) / span) if xy else 0.0
            t50 = t50_s + nx * 0.35 * period_s
        else:  # clock: flops at edge, combo later + spatial
            nx = ((xy[0] - xmin) / span) if xy else 0.0
            if seq:
                t50 = t50_s
            else:
                t50 = t50_s + 0.22 * period_s + nx * 0.25 * period_s
        events.append(
            {
                "node": n,
                "idx": idx[n],
                "i_avg": i_avg,
                "i_leak": leak,
                "i_peak": leak + i_pulse,
                "i_pulse": i_pulse,
                "t50_s": t50,
                "dur_s": dur_s,
                "seq": seq,
                "cell": (inst or {}).get("cell"),
                "inst": (inst or {}).get("name"),
                "x": xy[0] if xy else None,
                "y": xy[1] if xy else None,
            }
        )
    return events


def solve_be(
    G,
    idx,
    order,
    voltages,
    vdd,
    events,
    *,
    pkg_r,
    pkg_l,
    c_decap,
    t_end,
    dt,
):
    n = G.shape[0]
    bump = [idx[nm] for nm in voltages if nm in idx]
    r_series = max(pkg_r + (pkg_l / dt if pkg_l > 0 else 0.0), 1e-9)
    g_pad = 1.0 / r_series
    Gsoft = G.tolil()
    for i in bump:
        Gsoft[i, i] += g_pad
    Gsoft = Gsoft.tocsr()

    C = np.full(n, max(c_decap * 0.02, 1e-18))
    leak = np.zeros(n)
    for ev in events:
        C[ev["idx"]] = c_decap
        leak[ev["idx"]] += ev["i_leak"]

    A = (Gsoft + sparse.diags(C / dt)).tocsc()
    lu = splu(A)
    pad = np.zeros(n)
    for i in bump:
        pad[i] = g_pad * vdd

    steps = max(2, int(math.ceil(t_end / dt)))
    V = np.full(n, vdd)
    wave_t, wave_vmin, wave_itot = [], [], []
    worst_v, worst_t, worst_node, worst_V = vdd, 0.0, None, V.copy()

    for s in range(steps):
        t = s * dt
        I_draw = leak.copy()
        for ev in events:
            I_draw[ev["idx"]] += triangle_above_leak(t, ev["t50_s"], ev["dur_s"], ev["i_pulse"])
        rhs = (C / dt) * V - I_draw + pad
        V = lu.solve(rhs)
        vmin = float(np.min(V))
        wave_t.append(float(t))
        wave_vmin.append(vmin)
        wave_itot.append(float(np.sum(I_draw)))
        if vmin < worst_v:
            worst_v = vmin
            worst_t = float(t)
            worst_node = order[int(np.argmin(V))]
            worst_V = V.copy()

    return {
        "worst_voltage": worst_v,
        "worst_droop": vdd - worst_v,
        "worst_droop_pct": 100.0 * (vdd - worst_v) / vdd,
        "worst_time_s": worst_t,
        "worst_node": worst_node,
        "dt": dt,
        "t_end": t_end,
        "steps": steps,
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "c_decap": c_decap,
        "solver": "backward-euler + sparse LU",
        "wave_t": wave_t,
        "wave_vmin": wave_vmin,
        "wave_itot": wave_itot,
        "V_worst": worst_V,
    }


def heatmap_points(order, V, vdd, events) -> list[dict]:
    by_idx = {ev["idx"]: ev for ev in events}
    pts = []
    for i, name in enumerate(order):
        ev = by_idx.get(i)
        xy = (ev["x"], ev["y"]) if ev and ev["x"] is not None else node_xy(name)
        if not xy or xy[0] is None:
            continue
        if not name.startswith("ITermNode"):
            continue
        ir = max(0.0, vdd - float(V[i]))
        pts.append(
            {
                "node": name,
                "x": xy[0],
                "y": xy[1],
                "v": float(V[i]),
                "ir_mv": ir * 1e3,
                "seq": bool(ev and ev.get("seq")),
            }
        )
    return pts


def current_windows(wave_t: list[float], wave_itot: list[float], frac: float = 0.5) -> list[dict]:
    """L3-lite: intervals where I_tot >= frac * I_peak (this run, not 100k-cycle scan)."""
    if not wave_itot:
        return []
    peak = max(wave_itot)
    thresh = frac * peak
    out: list[dict] = []
    in_win = False
    t0 = peak_t = 0.0
    peak_i = 0.0
    for t, i in zip(wave_t, wave_itot):
        if i >= thresh:
            if not in_win:
                in_win = True
                t0 = t
                peak_t, peak_i = t, i
            elif i > peak_i:
                peak_t, peak_i = t, i
        elif in_win:
            out.append(
                {
                    "t_start_ns": t0 * 1e9,
                    "t_end_ns": t * 1e9,
                    "t_peak_ns": peak_t * 1e9,
                    "i_peak_a": peak_i,
                    "threshold_frac": frac,
                }
            )
            in_win = False
    if in_win and wave_t:
        out.append(
            {
                "t_start_ns": t0 * 1e9,
                "t_end_ns": wave_t[-1] * 1e9,
                "t_peak_ns": peak_t * 1e9,
                "i_peak_a": peak_i,
                "threshold_frac": frac,
            }
        )
    return out


def contributors_at(events: list[dict], t: float) -> dict:
    seq_a = combo_a = 0.0
    for ev in events:
        i = ev["i_leak"] + triangle_above_leak(t, ev["t50_s"], ev["dur_s"], ev["i_pulse"])
        if ev.get("seq"):
            seq_a += i
        else:
            combo_a += i
    tot = seq_a + combo_a
    return {
        "seq_a": seq_a,
        "combo_a": combo_a,
        "seq_frac": (seq_a / tot) if tot else 0.0,
        "combo_frac": (combo_a / tot) if tot else 0.0,
    }


def write_heatmap_svg(pts: list[dict], path: Path, vdd: float, title: str) -> None:
    if not pts:
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        return
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    irs = [p["ir_mv"] for p in pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    irmax = max(irs) or 1.0
    pad = 36
    W, H = 640, 520
    dw, dh = max(xmax - xmin, 1.0), max(ymax - ymin, 1.0)

    def sx(x):
        return pad + (x - xmin) / dw * (W - 2 * pad)

    def sy(y):
        return pad + (1.0 - (y - ymin) / dh) * (H - 2 * pad - 28)

    dots = []
    for p in pts:
        t = p["ir_mv"] / irmax
        r = 4.2 if p["seq"] else 3.2
        dots.append(
            f'<circle cx="{sx(p["x"]):.1f}" cy="{sy(p["y"]):.1f}" r="{r}" '
            f'fill="{viridis(t)}" opacity="0.92"/>'
        )
    legend = []
    for i in range(24):
        t = i / 23
        legend.append(
            f'<rect x="{pad + i * 18:.1f}" y="{H - 22}" width="18" height="10" fill="{viridis(t)}"/>'
        )
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <rect width="100%" height="100%" fill="#0b1220"/>
  <text x="{pad}" y="22" fill="#e8eef9" font-size="13" font-family="ui-sans-serif,system-ui">
    {title}
  </text>
  <text x="{pad}" y="38" fill="#9aa7bd" font-size="11" font-family="ui-sans-serif,system-ui">
    ITerm VDD taps · IR at t_worst · max {irmax:.2f} mV · Vdd {vdd:.2f} V
  </text>
  {"".join(dots)}
  {"".join(legend)}
  <text x="{pad}" y="{H - 6}" fill="#9aa7bd" font-size="10">0 mV</text>
  <text x="{W - pad - 70}" y="{H - 6}" fill="#9aa7bd" font-size="10">{irmax:.2f} mV</text>
</svg>
"""
    path.write_text(svg)


def _parse_wrdata_vmin(path: Path) -> float | None:
    """Min voltage from ngspice ASCII wrdata (time v)."""
    if not path.is_file():
        return None
    worst = None
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            v = float(parts[1])
        except ValueError:
            continue
        worst = v if worst is None else min(worst, v)
    return worst


def ngspice_gold(
    vdd: float = 1.1,
    r: float = 2.0,
    c: float = 50e-12,
    i_peak: float = 5e-3,
    dur: float = 0.2e-9,
    dt: float = 10e-12,
) -> dict | None:
    """Single-node BE vs ngspice (gear/BE): pad --R-- n -- C to gnd, triangle I at n.

    Tiny RC + PWL — not the 4k-node chip. ngspice `.meas MIN v(n)` prints
    `vmin = <volts> at= <time>`; taking the *last* `=` matched the time, not V.
    We dump `wrdata` and take min v(n).
    """
    if not shutil_which("ngspice"):
        return None
    t_end = dur * 4
    steps = max(8, int(math.ceil(t_end / dt)))
    g = 1.0 / r
    a = g + c / dt
    v = vdd
    t50 = dur
    worst = vdd
    for s in range(steps):
        t = s * dt
        i = triangle_above_leak(t, t50, dur, i_peak)
        rhs = g * vdd - i + (c / dt) * v
        v = rhs / a
        worst = min(worst, v)

    t0 = max(t50 - 0.5 * dur, 0.0)
    t1 = t50 + 0.5 * dur
    tmp = Path(tempfile.mkdtemp(prefix="dynir-gold-"))
    sp_path = tmp / "gold.sp"
    dat_path = tmp / "gold.dat"
    # OP first (no UIC): C starts at Vdd. wrdata is ASCII time, v(n).
    sp_path.write_text(
        f"""* dynamic_ir 1-node gold (gear maxord=1 ≈ backward Euler)
Vpad pad 0 DC {vdd}
R1 pad n {r}
C1 n 0 {c}
Iload n 0 PWL(0 0 {t0:.6e} 0 {t50:.6e} {i_peak:.6e} {t1:.6e} 0 {t_end:.6e} 0)
.control
option method=gear maxord=1
set filetype=ascii
tran {dt:.6e} {t_end:.6e}
wrdata {dat_path} v(n)
quit
.endc
.end
"""
    )
    log = subprocess.run(
        ["ngspice", "-b", str(sp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    blob = (log.stdout or "") + "\n" + (log.stderr or "")
    vmin_ng = _parse_wrdata_vmin(dat_path)
    if vmin_ng is None:
        for extra in sorted(tmp.glob("gold.dat*")):
            vmin_ng = _parse_wrdata_vmin(extra)
            if vmin_ng is not None:
                break
    if vmin_ng is None:
        # Fallback: first number after the first '=' on a vmin line (not `at=`).
        for line in blob.splitlines():
            m = re.search(r"\bvmin\b[^=]*=\s*([+-]?[0-9.eE+-]+)", line, re.I)
            if m:
                vmin_ng = float(m.group(1))
                break
    if vmin_ng is None or vmin_ng < 0.05:
        return {
            "ok": False,
            "be_vmin": worst,
            "ngspice_present": True,
            "ngspice_vmin": vmin_ng,
            "raw": blob[-800:],
            "r": r,
            "c": c,
            "i_peak": i_peak,
        }
    err_mv = abs(worst - vmin_ng) * 1e3
    return {
        "ok": err_mv < 5.0,
        "be_vmin": worst,
        "ngspice_vmin": vmin_ng,
        "abs_err_mv": err_mv,
        "r": r,
        "c": c,
        "i_peak": i_peak,
        "method": "ngspice gear maxord=1 vs studio BE",
    }


def shutil_which(name: str):
    from shutil import which

    return which(name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spice", required=True, type=Path)
    ap.add_argument("--insts", type=Path, default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--mode", choices=("simultaneous", "spatial", "clock"), default="clock")
    ap.add_argument("--peak-factor", type=float, default=8.0)
    ap.add_argument("--leak-frac", type=float, default=0.2)
    ap.add_argument("--period-ns", type=float, default=0.46)
    ap.add_argument("--dur-ns", type=float, default=0.08)
    ap.add_argument("--t50-ns", type=float, default=0.12)
    ap.add_argument("--pkg-r", type=float, default=0.05)
    ap.add_argument("--pkg-l", type=float, default=2e-10)
    ap.add_argument("--c-decap", type=float, default=50e-15)
    ap.add_argument("--dt-ps", type=float, default=10.0)
    ap.add_argument("--t-end-ns", type=float, default=0.0)
    ap.add_argument("--vdd", type=float, default=0.0)
    ap.add_argument("--skip-ngspice", action="store_true")
    args = ap.parse_args()

    resistors, currents, voltages = parse_spice(args.spice)
    order, idx, G = build_system(resistors, currents, voltages)
    vdd = args.vdd or next(iter(voltages.values()))
    period_s = args.period_ns * 1e-9
    dur_s = args.dur_ns * 1e-9
    t50_s = args.t50_ns * 1e-9
    dt = args.dt_ps * 1e-12
    t_end = (args.t_end_ns * 1e-9) if args.t_end_ns > 0 else max(period_s * 1.6, t50_s + dur_s * 3)

    insts = load_insts(args.insts) if args.insts else []
    events = plan_events(
        currents,
        idx,
        insts,
        mode=args.mode,
        peak_factor=args.peak_factor,
        leak_frac=args.leak_frac,
        period_s=period_s,
        dur_s=dur_s,
        t50_s=t50_s,
    )

    static = solve_static(G, idx, order, currents, voltages, vdd)
    Vstat = static.pop("V")

    dyn = solve_be(
        G,
        idx,
        order,
        voltages,
        vdd,
        events,
        pkg_r=args.pkg_r,
        pkg_l=args.pkg_l,
        c_decap=args.c_decap,
        t_end=t_end,
        dt=dt,
    )
    Vw = dyn.pop("V_worst")
    pts = heatmap_points(order, Vw, vdd, events)
    hottest = sorted(pts, key=lambda p: p["ir_mv"], reverse=True)[:8]

    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = out.with_suffix("")
    wave_path = Path(str(stem) + ".wave.csv")
    map_path = Path(str(stem) + ".map.csv")
    svg_path = Path(str(stem) + ".svg")

    with wave_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "v_min", "i_tot_a"])
        for t, v, i in zip(dyn["wave_t"], dyn["wave_vmin"], dyn["wave_itot"]):
            w.writerow([f"{t:.6e}", f"{v:.9f}", f"{i:.6e}"])
    with map_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node", "x_dbu", "y_dbu", "v", "ir_mv", "seq"])
        for p in pts:
            w.writerow([p["node"], p["x"], p["y"], f"{p['v']:.6f}", f"{p['ir_mv']:.4f}", int(p["seq"])])

    title = (
        f"Dynamic IR · {args.mode} · droop {dyn['worst_droop']*1e3:.2f} mV "
        f"@ {dyn['worst_time_s']*1e9:.2f} ns"
    )
    write_heatmap_svg(pts, svg_path, vdd, title)

    gold = None
    if not args.skip_ngspice:
        gold = ngspice_gold(vdd=vdd)

    i_tot_peak = max(dyn["wave_itot"]) if dyn["wave_itot"] else 0.0
    n_seq = sum(1 for e in events if e["seq"])
    t50s = [e["t50_s"] for e in events]
    windows = current_windows(dyn["wave_t"], dyn["wave_itot"])
    contrib = contributors_at(events, dyn["worst_time_s"])
    hot = hottest[0] if hottest else {}
    hotspot = {
        "node": dyn["worst_node"],
        "x_dbu": hot.get("x"),
        "y_dbu": hot.get("y"),
        "t_ns": dyn["worst_time_s"] * 1e9,
        "vmin": dyn["worst_voltage"],
        "droop_mv": dyn["worst_droop"] * 1e3,
        "seq": bool(hot.get("seq")),
        "contributors": contrib,
    }
    sim_levels = {
        "L0_static": {
            "status": "READY",
            "worst_ir_mv": static["worst_ir"] * 1e3,
        },
        "L1_vectorless_dynamic": {
            "status": "READY",
            "mode": args.mode,
            "note": "synthetic t50 (clock/spatial/simultaneous), not STA arrival windows",
        },
        "L2_vcd_dynamic": {
            "status": "GAP",
            "reason": "RTL VCD (tb_gcd, 10 ns) does not name gate ITerms; SDC is 0.46 ns",
        },
        "L3_windowed": {
            "status": "PARTIAL",
            "windows": windows,
            "note": "high-I windows on this run's I_tot(t), not 100k-cycle screening",
        },
    }
    pipeline = [
        {"id": 1, "name": "PDN extraction", "status": "READY", "via": "OpenROAD write_pg_spice"},
        {"id": 2, "name": "Power model", "status": "PARTIAL", "via": "I_avg from mesh (NLDM, not CCS I(t))"},
        {"id": 3, "name": "Activity engine", "status": "PARTIAL", "via": f"synthetic {args.mode}; VCD pin-accurate = GAP"},
        {"id": 4, "name": "Current waveform", "status": "PARTIAL", "via": "per-ITerm triangle PWL"},
        {"id": 5, "name": "Transient solver", "status": "READY", "via": "backward-Euler sparse LU (not AMG/PCG product core)"},
        {"id": 6, "name": "Analysis", "status": "PARTIAL", "via": "heatmap + Vmin(t) + windows; no EM/timing coupling"},
    ]
    report = {
        "ok": True,
        "kind": "dynamic_ir",
        "engine": "studio-dynamic-ir",
        "architecture": [
            "OpenROAD write_pg_spice PDN (static R mesh)",
            "per-ITerm PWL triangle I(t) (leak + switch)",
            "backward-Euler sparse LU",
            "V(x,y) heatmap at t_worst",
        ],
        "not": [
            "Liberty CCS current waveforms",
            "gate-level VCD pin times",
            "AMG / rational Krylov / MOR",
            "RedHawk / Voltus / Totem sign-off",
            "vyges-em-ir fork",
        ],
        "roles": {
            "openroad": "PDN extract (layer 1)",
            "vyges_em_ir": "simultaneous-switch prototype / CG+BE reference — not the product core",
            "this_engine": "I(t) per pin + explicit dt + waveform + map (layers 4–6 slice)",
            "ngspice": "1-node golden, not full-chip solver",
        },
        "pipeline": pipeline,
        "sim_levels": sim_levels,
        "hotspot": hotspot,
        "spice": str(args.spice),
        "vdd": vdd,
        "mode": args.mode,
        "period_ns": args.period_ns,
        "dur_ns": args.dur_ns,
        "peak_factor": args.peak_factor,
        "events": len(events),
        "seq_events": n_seq,
        "t50_span_ns": ((max(t50s) - min(t50s)) * 1e9) if t50s else 0.0,
        "i_tot_peak_a": i_tot_peak,
        "static": static,
        "dynamic": {k: v for k, v in dyn.items() if not k.startswith("wave_")},
        "heatmap": {
            "taps": len(pts),
            "svg": str(svg_path),
            "csv": str(map_path),
            "hottest": hottest[:5],
            "ir_max_mv": hottest[0]["ir_mv"] if hottest else 0.0,
        },
        "waveform": str(wave_path),
        "ngspice_gold": gold,
        "summary": (
            f"{args.mode} · static {static['worst_ir']*1e3:.3f} mV · "
            f"dynamic droop {dyn['worst_droop']*1e3:.3f} mV "
            f"({dyn['worst_droop_pct']:.3f}%) @ {dyn['worst_time_s']*1e9:.2f} ns · "
            f"I_peak {i_tot_peak*1e3:.2f} mA · {len(events)} PWL · "
            f"t50 span {((max(t50s)-min(t50s))*1e9) if t50s else 0:.2f} ns"
        ),
    }
    out.write_text(json.dumps(report, indent=2) + "\n")
    print("DYNAMIC_IR_DONE")
    print(report["summary"])
    print(f"report → {out}")
    print(f"wave → {wave_path}")
    print(f"map → {svg_path}")
    if gold:
        print("ngspice_gold", gold)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "/usr/lib/python3/dist-packages")
    sys.exit(main())
