#!/usr/bin/env python3
"""Dynamic IR on the OpenROAD write_pg_spice mesh (RedHawk-Dynamic *slice*).

Architecture (what this file actually does — not a product claim):

  OpenROAD write_pg_spice  →  PDN graph (R mesh, bump V, I_avg)
  per-ITerm triangle I(t)  →  Solver A: direct backward-Euler + sparse LU
  Vmin(t) + V(x,y) heatmap at t_worst

Solver A (direct BE + LU) is the golden oracle.
Solver B (smoothed-aggregation AMG + CG) is the workhorse on the same A = G+C/Δt.
Solver C here is shared-operator reuse across I(t) scenarios — not a rational
Krylov reduced ODE yet. vyges-em-ir is bootstrap, not the core. No forks.

Honest limits: triangle ≠ Liberty CCS; RTL VCD does not name gate pins;
Nangate45 has no CCS current tables.

Prior art (concepts, not dependencies): OpenROAD PSM (frontend),
EMSim split A/B, ESPSim SA-AMG, MATEX/Raptor MOR, Ginkgo, Xyce/ngspice gold.
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
import time
from pathlib import Path

if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

import numpy as np
from scipy import sparse

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pdn_solvers import DirectLU, SAAMG, residual_rel  # noqa: E402
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


def assemble_be(G, idx, voltages, vdd, events, *, pkg_r, pkg_l, c_decap, dt):
    """A = G + C/Δt + pad conductance. Independent of I(t) / t50."""
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
    pad = np.zeros(n)
    for i in bump:
        pad[i] = g_pad * vdd
    return {
        "A": A,
        "C": C,
        "leak": leak,
        "pad": pad,
        "n": n,
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "c_decap": c_decap,
        "dt": dt,
        "g_pad": g_pad,
    }


def timestep_be(sys: dict, events, solver, vdd: float, order, t_end: float):
    C = sys["C"]
    leak = sys["leak"]
    pad = sys["pad"]
    dt = sys["dt"]
    A = sys["A"]
    n = sys["n"]
    steps = max(2, int(math.ceil(t_end / dt)))
    V = np.full(n, vdd)
    wave_t, wave_vmin, wave_itot = [], [], []
    worst_v, worst_t, worst_node, worst_V = vdd, 0.0, None, V.copy()
    res_max = 0.0
    t_solve = 0.0

    for s in range(steps):
        t = s * dt
        I_draw = leak.copy()
        for ev in events:
            I_draw[ev["idx"]] += triangle_above_leak(t, ev["t50_s"], ev["dur_s"], ev["i_pulse"])
        rhs = (C / dt) * V - I_draw + pad
        t0 = time.perf_counter()
        V = solver.solve(rhs, x0=V)
        t_solve += time.perf_counter() - t0
        res_max = max(res_max, residual_rel(A, V, rhs))
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
        "pkg_r": sys["pkg_r"],
        "pkg_l": sys["pkg_l"],
        "c_decap": sys["c_decap"],
        "solver": solver.name,
        "solver_setup_s": getattr(solver, "setup_s", None),
        "solver_step_s": t_solve,
        "n_levels": getattr(solver, "n_levels", 1),
        "rel_res_max": res_max,
        "wave_t": wave_t,
        "wave_vmin": wave_vmin,
        "wave_itot": wave_itot,
        "V_worst": worst_V,
    }


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
    backend: str = "a",
):
    sys = assemble_be(
        G, idx, voltages, vdd, events, pkg_r=pkg_r, pkg_l=pkg_l, c_decap=c_decap, dt=dt
    )
    solver = DirectLU(sys["A"]) if backend in ("a", "direct", "lu") else SAAMG(sys["A"])
    return timestep_be(sys, events, solver, vdd, order, t_end)


def timing_impact(vdd: float, vmin: float, period_ns: float, alpha: float = 1.3) -> dict:
    """Delay scaling at the worst tap — not a real STA path."""
    v_eff = max(float(vmin), 0.25 * vdd)
    scale = (vdd / v_eff) ** alpha
    delay_nom_ps = 30.0  # ~FO4-class inverter at 45 nm, didactic
    deg_ps = (scale - 1.0) * delay_nom_ps
    return {
        "status": "PARTIAL",
        "model": "delay = delay_nom * (Vdd/V)^alpha at worst tap",
        "alpha": alpha,
        "vmin": vmin,
        "scale": scale,
        "delay_nom_ps": delay_nom_ps,
        "degradation_ps": deg_ps,
        "period_ns": period_ns,
        "frac_of_period": (deg_ps * 1e-3) / period_ns if period_ns else None,
        "note": "not a timed path — delay scaling only",
    }


def platform_block(
    *,
    mode: str,
    c_decap: float,
    pkg_r: float,
    pkg_l: float,
    amg: dict | None,
    scenarios: list | None,
    timing: dict | None,
) -> dict:
    b_status = "READY" if amg and amg.get("ok") else ("PARTIAL" if amg else "GAP")
    c_status = "PARTIAL" if scenarios else "GAP"
    fast = "READY" if b_status == "READY" else "PARTIAL"
    return {
        "name": "hierarchical multi-fidelity power-integrity engine",
        "slice": "native libdpn (A LU + B SA-AMG) + OpenROAD frontend + triangle I(t)",
        "do_not_fork": ["vyges-em-ir", "EMSim", "OpenROAD PSM"],
        "do_not_implement_this_slice": [
            "Liberty CCS/ECSM I(t) tables",
            "Ginkgo CPU/GPU backend",
            "rational Krylov reduced ODE",
            "empty power-integrity/ tree",
        ],
        "ml": {
            "status": "GAP",
            "role": "scenario / window ranking only (MAVIREC, PowerNet, IR-Hunter)",
            "not": "neural voltage map as sign-off",
        },
        "gpu": {
            "status": "GAP",
            "idea": "one LinearSolver API → CPU AMG / CPU Krylov / GPU AMG / GPU Krylov (Ginkgo)",
        },
        "gold": {
            "tiny": {"tool": "ngspice", "status": "READY", "scope": "1-node RC + triangle"},
            "medium": {
                "tool": "Xyce",
                "status": "GAP",
                "scope": "parallel TRAN validation — not PDN-structure-aware core",
            },
        },
        "solvers": {
            "A_direct_be": {
                "status": "READY",
                "role": "golden reference",
                "via": "(G + C/dt) Vnext = rhs · sparse LU",
                "not": "product workhorse",
            },
            "B_sa_amg": {
                "status": b_status,
                "role": "full-chip workhorse",
                "ref": "smoothed aggregation + Jacobi V-cycle + CG (ESPSim-class)",
                "vs_A": amg,
            },
            "C_rational_krylov_mor": {
                "status": c_status,
                "role": "multi-scenario reuse on the same PDN",
                "via": "shared A = G+C/Δt across I(t) scenarios (not rational Krylov ODE)",
                "killer_feature": "same PDN operator, many current waveforms",
                "scenarios": scenarios,
            },
        },
        "network_levels": {
            "N1_R": {
                "status": "READY",
                "eq": "G V = I",
                "via": "solve_static on write_pg_spice",
            },
            "N2_RC": {
                "status": "READY",
                "eq": "G V + C dV/dt = I(t)",
                "via": "lumped c_decap on ITerm nodes",
                "c_decap": c_decap,
            },
            "N3_RC_pkg": {
                "status": "READY",
                "eq": "RC + lumped package R/L at bumps",
                "via": "pkg_r + pkg_l/dt series on pad nodes",
                "pkg_r": pkg_r,
                "pkg_l": pkg_l,
                "note": "not extracted on-die inductance",
            },
            "N4_vrm": {
                "status": "PARTIAL",
                "eq": "on-die + package + bumps + VRM",
                "via": "bumps as V sources in write_pg_spice; VRM ladder is system_pdn (not coupled TRAN)",
            },
        },
        "product_tiers": {
            "FAST": {
                "status": fast,
                "intended": "vectorless + SA-AMG + coarse timestep",
                "this_slice": f"synthetic {mode} t50 + Solver B SA-AMG",
            },
            "ACCURATE": {
                "status": "GAP",
                "intended": "VCD/FSDB + CCS I(t) + AMG + adaptive timestep",
            },
            "SIGNOFF": {
                "status": "GAP",
                "intended": "RLC + MOR/Krylov + direct spot checks + EM + package",
            },
        },
        "timing_impact": timing
        or {
            "status": "GAP",
            "idea": "V(t) → delay(V) → STA path degradation",
        },
        "em_thermal": {
            "status": "GAP",
            "idea": "I(t)→J→EM and P→T→R(T) as later coupling",
        },
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
    ap.add_argument("--no-amg", action="store_true", help="skip Solver B SA-AMG")
    ap.add_argument("--no-scenarios", action="store_true", help="skip extra I(t) modes on shared A")
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

    sys_be = assemble_be(
        G,
        idx,
        voltages,
        vdd,
        events,
        pkg_r=args.pkg_r,
        pkg_l=args.pkg_l,
        c_decap=args.c_decap,
        dt=dt,
    )
    solver_a = DirectLU(sys_be["A"])
    dyn = timestep_be(sys_be, events, solver_a, vdd, order, t_end)

    amg_meta = None
    solver_b = None
    if not args.no_amg:
        solver_b = SAAMG(sys_be["A"])
        dyn_b = timestep_be(sys_be, events, solver_b, vdd, order, t_end)
        err_mv = abs(dyn["worst_droop"] - dyn_b["worst_droop"]) * 1e3
        amg_meta = {
            "ok": err_mv < 5.0,
            "worst_droop_mv": dyn_b["worst_droop"] * 1e3,
            "worst_time_ns": dyn_b["worst_time_s"] * 1e9,
            "abs_err_vs_A_mv": err_mv,
            "rel_res_max": dyn_b["rel_res_max"],
            "n_levels": dyn_b["n_levels"],
            "setup_s": solver_b.setup_s,
            "step_s": dyn_b["solver_step_s"],
            "lu_setup_s": solver_a.setup_s,
            "lu_step_s": dyn["solver_step_s"],
            "backend": getattr(solver_b, "backend", "python"),
            "lu_backend": getattr(solver_a, "backend", "python"),
        }
        dyn_b.pop("V_worst", None)
        dyn["amg"] = {k: v for k, v in dyn_b.items() if not k.startswith("wave_") and k != "V_worst"}

    scenarios = None
    if not args.no_scenarios and solver_b is not None:
        scenarios = []
        for m in ("clock", "spatial", "simultaneous"):
            if m == args.mode and amg_meta is not None:
                scenarios.append(
                    {
                        "mode": m,
                        "droop_mv": amg_meta["worst_droop_mv"],
                        "t_ns": amg_meta["worst_time_ns"],
                        "i_peak_a": max(dyn["wave_itot"]) if dyn["wave_itot"] else 0.0,
                        "via": solver_b.name,
                        "primary": True,
                    }
                )
                continue
            ev_m = plan_events(
                currents,
                idx,
                insts,
                mode=m,
                peak_factor=args.peak_factor,
                leak_frac=args.leak_frac,
                period_s=period_s,
                dur_s=dur_s,
                t50_s=t50_s,
            )
            r_m = timestep_be(sys_be, ev_m, solver_b, vdd, order, t_end)
            scenarios.append(
                {
                    "mode": m,
                    "droop_mv": r_m["worst_droop"] * 1e3,
                    "t_ns": r_m["worst_time_s"] * 1e9,
                    "i_peak_a": max(r_m["wave_itot"]) if r_m["wave_itot"] else 0.0,
                    "via": solver_b.name,
                    "primary": False,
                }
            )
        scenarios.sort(key=lambda s: -s["droop_mv"])
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
    timing = timing_impact(vdd, dyn["worst_voltage"], args.period_ns)
    hotspot["timing"] = {
        "degradation_ps": timing["degradation_ps"],
        "scale": timing["scale"],
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
        {"id": 5, "name": "Transient solver", "status": "READY", "via": "A golden LU + B SA-AMG on shared A=G+C/Δt"},
        {"id": 6, "name": "Analysis", "status": "PARTIAL", "via": "heatmap + windows + delay scaling; EM = GAP"},
    ]
    plat = platform_block(
        mode=args.mode,
        c_decap=args.c_decap,
        pkg_r=args.pkg_r,
        pkg_l=args.pkg_l,
        amg=amg_meta,
        scenarios=scenarios,
        timing=timing,
    )
    amg_note = (
        f" · AMG {amg_meta['worst_droop_mv']:.3f} mV (|A−B| {amg_meta['abs_err_vs_A_mv']:.3f} mV)"
        if amg_meta
        else ""
    )
    report = {
        "ok": True,
        "kind": "dynamic_ir",
        "engine": "studio-dynamic-ir",
        "architecture": [
            "OpenROAD write_pg_spice PDN (static R mesh) — frontend, not a PSM fork",
            "per-ITerm PWL triangle I(t) (leak + switch) — not CCS",
            "Solver A: direct backward-Euler sparse LU (golden)",
            "Solver B: smoothed-aggregation AMG + CG (workhorse)",
            "Shared A = G+C/Δt across I(t) scenarios",
            "V(x,y) heatmap at t_worst + delay scaling at worst tap",
        ],
        "not": [
            "Liberty CCS current waveforms",
            "gate-level VCD pin times",
            "rational Krylov reduced ODE",
            "RedHawk / Voltus / Totem sign-off",
            "vyges-em-ir fork",
            "EMSim commercial flow (VCS/Calibre/PT-PX/HSpice)",
        ],
        "roles": {
            "openroad": "physical frontend — ODB → PDN graph; do not fork PSM",
            "emsim": "architectural split A (cell current → PWL) vs B (PDN TRAN) — not vendored, not run",
            "vyges_em_ir": "bootstrap + simultaneous-switch validation — not the core",
            "this_engine": "Solver A gold + Solver B SA-AMG on write_pg_spice; triangle I(t)",
            "ngspice": "unit-test gold for BE on a 1-node RC",
            "xyce": "GAP — future medium-scale gold, not the PDN-aware core",
        },
        "platform": plat,
        "emsim_split": {
            "upstream": "https://github.com/jinyier/EMSim",
            "citation": "Ma et al., TIFS 2023 — EM emanation, not IR sign-off",
            "A_cell_current": {
                "status": "PARTIAL",
                "replaces": "PrimeTime PX time-based power + logic_cell_modeling.py",
                "pwl_sources": len(events),
                "shape": "triangle leak+switch",
                "not": "CCS / PT-PX current profiles / gate VCD",
            },
            "B_pdn_solve": {
                "status": "READY",
                "solver": "A_direct_be + B_sa_amg",
                "replaces": "HSpice TRAN on Calibre DSPF",
                "via": "Solver A LU golden + Solver B SA-AMG on write_pg_spice",
                "gold": "ngspice 1-node gear/BE; A vs B droop on the chip mesh",
            },
            "commercial_not_used": {
                "VCS": "GAP — Icarus RTL VCD does not name gate ITerms",
                "Calibre_xRC": "MAPPED — OpenROAD write_pg_spice (R mesh, not DSPF)",
                "PrimeTime_PX": "MAPPED — I_avg in the SPICE mesh, not time-based cell power",
                "HSpice": "MAPPED — ngspice gold only; B is Solver A BE",
            },
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
        "solver_b": amg_meta,
        "scenarios": scenarios,
        "timing_impact": timing,
        "summary": (
            f"{args.mode} · static {static['worst_ir']*1e3:.3f} mV · "
            f"dynamic droop {dyn['worst_droop']*1e3:.3f} mV "
            f"({dyn['worst_droop_pct']:.3f}%) @ {dyn['worst_time_s']*1e9:.2f} ns · "
            f"I_peak {i_tot_peak*1e3:.2f} mA · {len(events)} PWL · "
            f"t50 span {((max(t50s)-min(t50s))*1e9) if t50s else 0:.2f} ns"
            f"{amg_note}"
            f" · delay +{timing['degradation_ps']:.2f} ps"
        ),
    }

    def _json(o):
        if isinstance(o, np.generic):
            return o.item()
        raise TypeError(type(o))

    out.write_text(json.dumps(report, indent=2, default=_json) + "\n")
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
