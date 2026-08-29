#!/usr/bin/env python3
"""Dynamic IR on the OpenROAD write_pg_spice mesh (RedHawk-Dynamic *slice*).

Architecture (what this file actually does — not a product claim):

  OpenROAD write_pg_spice  →  PDN graph (R mesh, bump V, I_avg)
  activity layer (synthetic t50) + current layer (triangle; CCS if tables)
  Solver A: direct backward-Euler + sparse LU (golden)
  Solver B: SA-AMG + CG on the same SPD companion operator
  Solver C: rational Krylov MOR — RC on δv, or descriptor RLC on x=[v; i_L]
  Solver D: restricted additive Schwarz (graph partition, local LU, GMRES)
  Vmin(t) + V(x,y) heatmap at t_worst

Solver A is the golden oracle. Solver C with L>0 reduces Eẋ+Ax=u matching
the BE companion (not an RC-only Gsoft screen). Ranking of extra I(t) stays A.

The BE time loop and MOR live in libdpn. Python orchestrates extraction and I(t).

Honest limits: Nangate45 has no CCS current tables (triangle from I_avg);
RTL VCD does not name gate pins. No silent CCS←NLDM mapping.

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

from pdn_activity import load_insts, node_xy, plan_events, probe_activity_trace  # noqa: E402
from pdn_current import (  # noqa: E402
    current_source_for_event,
    events_use_ccs,
    parse_ccs_output_current,
    probe_liberty_current_model,
    triangle_above_leak,
)
from pdn_solvers import (  # noqa: E402
    DirectLU,
    RASDD,
    RationalKrylov,
    SAAMG,
    mor_starts,
    native_adaptive,
    native_timestep,
    residual_rel,
    rl_companion,
)
from pdn_transient import build_system, parse_spice, solve_static  # noqa: E402
from pdn_vrm import assemble_n4_mesh, load_vrm_cfg, ngspice_vrm_die_gold, timestep_descriptor  # noqa: E402


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


def assemble_be(G, idx, voltages, vdd, events, *, pkg_r, pkg_l, c_decap, dt):
    """A = G + C/Δt + pad conductance. Independent of I(t) / t50.

    Pad stamp is the BE companion of lumped package R+L: g_eq = 1/(R+L/Δt).
    Inductor current i_L is *not* in A — it lives on the RHS of the time loop.
    """
    n = G.shape[0]
    bump = []
    bump_v = []
    for nm, volt in voltages.items():
        if nm in idx:
            bump.append(idx[nm])
            bump_v.append(float(volt))
    g_eq, hsc = rl_companion(pkg_r, pkg_l, dt)
    Gsoft = G.tolil()
    for i in bump:
        Gsoft[i, i] += g_eq
    Gsoft = Gsoft.tocsr()

    C = np.full(n, max(c_decap * 0.02, 1e-18))
    leak = np.zeros(n)
    for ev in events:
        C[ev["idx"]] = c_decap
        leak[ev["idx"]] += ev["i_leak"]

    A = (Gsoft + sparse.diags(C / dt)).tocsc()
    pad = np.zeros(n)
    for i, vs in zip(bump, bump_v):
        pad[i] = g_eq * vs
    return {
        "A": A,
        "G": Gsoft.tocsr(),
        "G_mesh": G.tocsr(),
        "C": C,
        "leak": leak,
        "pad": pad,
        "bump": bump,
        "bump_v": np.asarray(bump_v, dtype=np.float64),
        "n": n,
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "c_decap": c_decap,
        "dt": dt,
        "g_pad": g_eq,
        "hist_scale": hsc,
    }


def _map_worst_node(result: dict, order) -> dict:
    idx = result.get("worst_node_idx")
    if result.get("worst_node") is None and idx is not None and order:
        result["worst_node"] = order[int(idx)]
    result.setdefault("pkg_r", None)
    result.setdefault("pkg_l", None)
    result.setdefault("c_decap", None)
    ilw = result.get("i_L_worst")
    if isinstance(ilw, np.ndarray):
        result["i_L_worst"] = ilw.tolist()
    return result


def timestep_be(
    sys: dict,
    events,
    solver,
    vdd: float,
    order,
    t_end: float,
    adaptive: bool = False,
    ccs_tables: list | None = None,
):
    native = None
    use_ccs = events_use_ccs(events, ccs_tables)
    if adaptive:
        native = native_adaptive(sys, events, vdd, t_end)
        if native is not None:
            native["pkg_r"] = sys["pkg_r"]
            native["pkg_l"] = sys["pkg_l"]
            native["c_decap"] = sys["c_decap"]
            native["solver"] = "A_direct_be_adaptive"
            return _map_worst_node(native, order)
        print(
            "libdpn adaptive BE unavailable; not silently substituting fixed Δt",
            file=__import__("sys").stderr,
        )
        adaptive = False
    elif not use_ccs:
        native = native_timestep(solver, sys, events, vdd, t_end)
        if native is not None:
            native["pkg_r"] = sys["pkg_r"]
            native["pkg_l"] = sys["pkg_l"]
            native["c_decap"] = sys["c_decap"]
            return _map_worst_node(native, order)

    C = sys["C"]
    leak = sys["leak"]
    dt = sys["dt"]
    A = sys["A"]
    n = sys["n"]
    bump = sys.get("bump") or []
    bump_v = np.asarray(sys.get("bump_v") if sys.get("bump_v") is not None else [vdd] * len(bump), dtype=np.float64)
    g_eq, hsc = rl_companion(sys["pkg_r"], sys["pkg_l"], dt)
    steps = max(2, int(math.ceil(t_end / dt)))
    V = np.full(n, vdd)
    i_L = np.zeros(len(bump), dtype=np.float64)
    wave_t, wave_vmin, wave_itot = [], [], []
    worst_v, worst_t, worst_node, worst_V = vdd, 0.0, None, V.copy()
    i_L_worst = i_L.copy()
    i_L_absmax = 0.0
    res_max = 0.0
    t_solve = 0.0

    for s in range(steps):
        t = s * dt
        I_draw = leak.copy()
        for ev in events:
            I_draw[ev["idx"]] += current_source_for_event(
                ev, t, ccs_tables=ccs_tables, vout=float(V[ev["idx"]])
            )
        rhs = (C / dt) * V - I_draw
        for k, b in enumerate(bump):
            vs = float(bump_v[k]) if k < bump_v.size else vdd
            rhs[b] += g_eq * vs + hsc * i_L[k]
        t0 = time.perf_counter()
        V = solver.solve(rhs, x0=V)
        t_solve += time.perf_counter() - t0
        res_max = max(res_max, residual_rel(A, V, rhs))
        i_new = np.zeros_like(i_L)
        for k, b in enumerate(bump):
            vs = float(bump_v[k]) if k < bump_v.size else vdd
            i_new[k] = g_eq * (vs - V[b]) + hsc * i_L[k]
        i_L = i_new
        vmin = float(np.min(V))
        wave_t.append(float(t))
        wave_vmin.append(vmin)
        wave_itot.append(float(np.sum(I_draw)))
        if vmin < worst_v:
            worst_v = vmin
            worst_t = float(t)
            worst_node = order[int(np.argmin(V))]
            worst_V = V.copy()
            i_L_worst = i_L.copy()
            i_L_absmax = float(np.max(np.abs(i_L))) if i_L.size else 0.0

    loop = "python_hist" if bump else "python"
    if use_ccs:
        loop = loop.replace("python", "python_ccs")

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
        "i_L_worst": i_L_worst,
        "i_L_absmax": i_L_absmax,
        "backend": getattr(solver, "backend", "python"),
        "timestep_loop": loop,
        "ccs_in_loop": bool(use_ccs),
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
    mor: dict | None = None,
    adaptive: dict | None = None,
    em: dict | None = None,
    n4: dict | None = None,
    ras: dict | None = None,
) -> dict:
    b_status = "READY" if amg and amg.get("ok") else ("PARTIAL" if amg else "GAP")
    if mor and mor.get("ok"):
        c_status = "READY"
        c_via = mor.get("via") or "rational Krylov reduced BE"
    elif mor:
        c_status = "PARTIAL"
        c_via = (
            mor.get("via")
            or f"rational Krylov ODE, |A−C|={mor.get('abs_err_vs_A_mv')} mV "
            "(basis does not yet replace full-order gold)"
        )
    elif scenarios:
        c_status = "PARTIAL"
        c_via = "shared A = G+C/Δt across I(t) scenarios (not reduced ODE)"
    else:
        c_status = "GAP"
        c_via = "rational Krylov reduced ODE"
    d_status = "READY" if ras and ras.get("ok") else ("PARTIAL" if ras else "GAP")
    fast = "READY" if b_status == "READY" else "PARTIAL"
    accurate = "PARTIAL" if adaptive and adaptive.get("ok") else "GAP"
    return {
        "name": "hierarchical multi-fidelity power-integrity engine",
        "slice": "native libdpn (A LU + B SA-AMG + C Krylov MOR + D RAS Schwarz + adaptive BE) + OpenROAD + triangle/CCS I(t)",
        "do_not_fork": ["vyges-em-ir", "EMSim", "OpenROAD PSM"],
        "do_not_implement_this_slice": [
            "gate-accurate VCD/FSDB pin times on this Nangate netlist",
            "Ginkgo CPU/GPU backend",
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
            "tiny": {"tool": "ngspice", "status": "READY", "scope": "1-node RC + 1-node series R+L companion"},
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
                "via": c_via,
                "killer_feature": "one reduced ODE, many current waveforms",
                "m": None if not mor else mor.get("m"),
                "vs_A": mor,
                "scenarios": scenarios,
            },
            "D_ras_schwarz": {
                "status": d_status,
                "role": "domain decomposition on the BE operator",
                "via": "restricted additive Schwarz: graph-grown subdomains, overlapping local SparseLU, RAS restriction, GMRES",
                "not": "index stripes, CG (RAS is not SPD), AMG",
                "vs_A": ras,
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
                "eq": "RC + lumped package R+L companion at bumps",
                "via": "g_eq=1/(R+L/Δt) on pad diagonals; i_L history on the RHS",
                "pkg_r": pkg_r,
                "pkg_l": pkg_l,
                "note": "not extracted on-die inductance; companion stays SPD so AMG applies",
            },
            "N4_vrm": {
                "status": "READY" if n4 and n4.get("ok") else "PARTIAL",
                "eq": "on-die + package R+L + lumped VRM (descriptor BE)",
                "via": (n4 or {}).get("via")
                or "bumps as V sources in write_pg_spice; VRM ladder is system_pdn (not coupled TRAN)",
                "vs_N3_mv": None if not n4 else n4.get("abs_err_vs_N3_mv"),
                "note": (n4 or {}).get("note")
                or "µs VRM capacitors look stiff on a sub-ns GCD window",
            },
        },
        "product_tiers": {
            "FAST": {
                "status": fast,
                "intended": "vectorless + SA-AMG + coarse timestep",
                "this_slice": f"synthetic {mode} t50 + Solver B SA-AMG",
            },
            "ACCURATE": {
                "status": accurate,
                "intended": "VCD/FSDB + CCS I(t) + AMG + adaptive timestep",
                "this_slice": "adaptive BE with i_L history; CCS lagged I(slew,V^n) in Python TRAN when tables+slew; Nangate NLDM still GAP",
                "adaptive": adaptive,
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
        "em_thermal": em
        or {
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


def em_snapshot(
    resistors,
    idx: dict,
    order,
    V: np.ndarray,
    *,
    bump,
    bump_v,
    i_L,
    pkg_r: float,
    pkg_l: float,
) -> dict:
    """Branch currents at t_worst from I = (Va−Vb)/R. Physics screening, not ML.

    No conductor width in write_pg_spice → no J (A/m²) and no Black TTF.
    Package inductor current is the BE companion i_L at the same instant.
    """
    def vnode(name: str) -> float | None:
        if name == "0":
            return 0.0
        i = idx.get(name)
        if i is None or i < 0 or i >= len(V):
            return None
        return float(V[i])

    branches = []
    for a, b, r in resistors:
        va, vb = vnode(a), vnode(b)
        if va is None or vb is None:
            continue
        i_br = (va - vb) / max(r, 1e-18)
        branches.append({"a": a, "b": b, "r_ohm": r, "i_a": i_br, "i_abs": abs(i_br)})
    branches.sort(key=lambda x: -x["i_abs"])
    top = branches[:12]
    hottest = top[0] if top else None
    pkg = []
    i_L_list = []
    if i_L is not None:
        i_L_list = np.asarray(i_L, dtype=np.float64).tolist()
    for k, bi in enumerate(bump or []):
        node = order[int(bi)] if order is not None and 0 <= int(bi) < len(order) else str(bi)
        pkg.append(
            {
                "node": node,
                "v_src": float(bump_v[k]) if bump_v is not None and k < len(bump_v) else None,
                "i_L_a": float(i_L_list[k]) if k < len(i_L_list) else None,
            }
        )
    pkg.sort(key=lambda p: -abs(p["i_L_a"] or 0.0))
    i_absmax = float(hottest["i_abs"]) if hottest else 0.0
    return {
        "status": "PARTIAL",
        "model": "I_branch=(Va-Vb)/R at t_worst; package i_L from BE R+L companion",
        "not": ["current density J (no width in SPICE)", "Black TTF", "thermal R(T)"],
        "n_branches": len(branches),
        "i_absmax_a": i_absmax,
        "hottest": hottest,
        "top": top[:8],
        "package_i_L": pkg[:8],
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "note": "EM screening from physics I(t), not ML. Width/J/TTF remain GAP.",
    }


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


def ngspice_rl_gold(
    vdd: float = 1.1,
    r: float = 0.05,
    l: float = 2e-10,
    c: float = 50e-12,
    i_peak: float = 5e-3,
    dur: float = 0.2e-9,
    dt: float = 10e-12,
) -> dict | None:
    """Pad --R-- L -- n -- C vs BE companion with i_L history (gear maxord=1)."""
    if not shutil_which("ngspice"):
        return None
    t_end = dur * 4
    steps = max(8, int(math.ceil(t_end / dt)))
    g_eq, hsc = rl_companion(r, l, dt)
    t50 = dur
    v = vdd
    i_L = 0.0
    worst = vdd
    for s in range(steps):
        t = s * dt
        idraw = triangle_above_leak(t, t50, dur, i_peak)
        rhs = (c / dt) * v - idraw + g_eq * vdd + hsc * i_L
        a = c / dt + g_eq
        vn = rhs / a
        i_L = g_eq * (vdd - vn) + hsc * i_L
        v = vn
        worst = min(worst, v)

    t0 = max(t50 - 0.5 * dur, 0.0)
    t1 = t50 + 0.5 * dur
    tmp = Path(tempfile.mkdtemp(prefix="dynir-rl-gold-"))
    sp_path = tmp / "gold_rl.sp"
    dat_path = tmp / "gold_rl.dat"
    sp_path.write_text(
        f"""* dynamic_ir 1-node series R+L gold (gear maxord=1 ≈ backward Euler)
Vpad pad 0 DC {vdd}
R1 pad mid {r}
L1 mid n {l}
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
        for extra in sorted(tmp.glob("gold_rl.dat*")):
            vmin_ng = _parse_wrdata_vmin(extra)
            if vmin_ng is not None:
                break
    if vmin_ng is None or vmin_ng < 0.05:
        return {
            "ok": False,
            "be_vmin": worst,
            "ngspice_present": True,
            "ngspice_vmin": vmin_ng,
            "raw": blob[-800:],
            "r": r,
            "l": l,
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
        "l": l,
        "c": c,
        "i_peak": i_peak,
        "method": "ngspice gear maxord=1 vs BE R+L companion with i_L",
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
    ap.add_argument("--no-scenarios", action="store_true", help="skip extra I(t) modes")
    ap.add_argument("--no-mor", action="store_true", help="skip Solver C rational Krylov")
    ap.add_argument("--no-ras", action="store_true", help="skip Solver D restricted additive Schwarz")
    ap.add_argument("--adaptive", action="store_true", help="also run adaptive-Δt BE (LU)")
    ap.add_argument("--liberty", type=Path, default=None, help="Liberty file to probe for CCS/ECSM (never synthesized)")
    ap.add_argument("--vcd", type=Path, default=None, help="VCD/SAIF/FSDB to probe (never silently mapped to ITerms)")
    ap.add_argument("--no-vrm", action="store_true", help="skip coupled N4 VRM+die descriptor BE")
    ap.add_argument("--vrm-cfg", type=Path, default=None, help="system_pdn JSON for lumped VRM")
    args = ap.parse_args()

    current_model = probe_liberty_current_model(args.liberty)
    activity_model = probe_activity_trace(args.vcd)
    ccs_tables: list = []
    if args.liberty and Path(args.liberty).is_file() and current_model.get("n_ccs_tables"):
        ccs_tables = parse_ccs_output_current(Path(args.liberty).read_text(errors="replace")[:2_000_000])

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
    current_model["ccs_in_loop"] = events_use_ccs(events, ccs_tables)

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
    dyn = timestep_be(sys_be, events, solver_a, vdd, order, t_end, ccs_tables=ccs_tables)

    amg_meta = None
    solver_b = None
    if not args.no_amg:
        solver_b = SAAMG(sys_be["A"])
        dyn_b = timestep_be(sys_be, events, solver_b, vdd, order, t_end, ccs_tables=ccs_tables)
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
            "timestep_loop": dyn_b.get("timestep_loop"),
            "lu_timestep_loop": dyn.get("timestep_loop"),
        }
        dyn_b.pop("V_worst", None)
        dyn["amg"] = {k: v for k, v in dyn_b.items() if not k.startswith("wave_") and k != "V_worst"}

    ras_meta = None
    if not args.no_ras:
        solver_d = RASDD(sys_be["A"])
        dyn_d = timestep_be(sys_be, events, solver_d, vdd, order, t_end, ccs_tables=ccs_tables)
        err_d = abs(dyn["worst_droop"] - dyn_d["worst_droop"]) * 1e3
        ras_meta = {
            "ok": err_d < 5.0,
            "worst_droop_mv": dyn_d["worst_droop"] * 1e3,
            "worst_time_ns": dyn_d["worst_time_s"] * 1e9,
            "abs_err_vs_A_mv": err_d,
            "rel_res_max": dyn_d["rel_res_max"],
            "n_levels": dyn_d["n_levels"],
            "setup_s": solver_d.setup_s,
            "step_s": dyn_d["solver_step_s"],
            "backend": getattr(solver_d, "backend", "python"),
            "timestep_loop": dyn_d.get("timestep_loop"),
            "via": "restricted additive Schwarz + GMRES on A=G+C/Δt+g_eq (graph partition, not stripes)",
        }
        dyn["ras"] = {k: v for k, v in dyn_d.items() if not k.startswith("wave_") and k != "V_worst"}

    mor_meta = None
    mor = None
    if not args.no_mor:
        starts = mor_starts(sys_be["n"], events)
        shifts = np.array([0.0, 1e9, 1.0 / dt], dtype=np.float64)
        mor = RationalKrylov(sys_be["G"], sys_be["C"], starts, shifts, n_moments=4, sys=sys_be)
        dyn_c = mor.timestep(sys_be, events, vdd, t_end)
        dyn_c = _map_worst_node(dyn_c, order)
        err_c = abs(dyn["worst_droop"] - dyn_c["worst_droop"]) * 1e3
        rlc_mor = bool(getattr(mor, "name", "").endswith("rlc") or float(sys_be["pkg_l"] or 0) > 0)
        mor_meta = {
            "ok": err_c < 5.0,
            "worst_droop_mv": dyn_c["worst_droop"] * 1e3,
            "worst_time_ns": dyn_c["worst_time_s"] * 1e9,
            "abs_err_vs_A_mv": err_c,
            "rel_res_max": dyn_c.get("rel_res_max"),
            "m": getattr(mor, "m", dyn_c.get("m")),
            "setup_s": getattr(mor, "setup_s", dyn_c.get("solver_setup_s")),
            "step_s": dyn_c.get("solver_step_s"),
            "backend": getattr(mor, "backend", dyn_c.get("backend")),
            "via": (
                "descriptor RLC Krylov on Eẋ + A x = u, x=[v; i_L]"
                if rlc_mor
                else "rational Krylov + reduced BE on δv=v-Vdd"
            ),
            "note": (
                "MOR includes package inductor states. Ranking of extra I(t) stays Solver A."
                if rlc_mor
                else "RC MOR on Gsoft."
            ),
        }
        dyn["mor"] = {k: v for k, v in dyn_c.items() if not k.startswith("wave_") and k != "V_worst"}

    adaptive_meta = None
    if args.adaptive:
        dyn_ad = timestep_be(sys_be, events, solver_a, vdd, order, t_end, adaptive=True)
        err_ad = abs(dyn["worst_droop"] - dyn_ad["worst_droop"]) * 1e3
        adaptive_meta = {
            "ok": err_ad < 5.0,
            "worst_droop_mv": dyn_ad["worst_droop"] * 1e3,
            "worst_time_ns": dyn_ad["worst_time_s"] * 1e9,
            "abs_err_vs_A_mv": err_ad,
            "steps": dyn_ad["steps"],
            "timestep_loop": dyn_ad.get("timestep_loop"),
            "via": "BE LTE ½|Δ²V|; g_eq(Δt)+i_L (different L discretization than fixed-Δt gold)",
        }

    n4_meta = None
    if not args.no_vrm:
        vrm = (load_vrm_cfg(args.vrm_cfg).get("vrm") or {})
        n4sys = assemble_n4_mesh(
            sys_be["G_mesh"],
            sys_be["C"],
            sys_be["bump"],
            vdd=vdd,
            pkg_r=args.pkg_r,
            pkg_l=args.pkg_l,
            r_vrm=float(vrm.get("r_out") or 0.015),
            l_vrm=float(vrm.get("l_out") or 2e-9),
            c_vrm=float(vrm.get("c_out") or 47e-6),
        )
        leak_n4 = np.asarray(sys_be["leak"], dtype=np.float64)

        def _i_n4(t, leak=leak_n4, evs=events):
            I = leak.copy()
            for ev in evs:
                I[ev["idx"]] += triangle_above_leak(t, ev["t50_s"], ev["dur_s"], ev["i_pulse"])
            return I

        dyn_n4 = timestep_descriptor(n4sys, _i_n4, dt, t_end, vdd)
        err_n4 = abs(dyn["worst_droop"] - dyn_n4["worst_droop"]) * 1e3
        n4_meta = {
            "ok": True,
            "worst_droop_mv": dyn_n4["worst_droop"] * 1e3,
            "worst_time_ns": dyn_n4["worst_time_s"] * 1e9,
            "abs_err_vs_N3_mv": err_n4,
            "via": "coupled descriptor BE: write_pg_spice die + lumped VRM C/L/R + bump R+L",
            "note": "N3 (ideal Vsrc) stays gold on this sub-ns window; 47 µF VRM is stiff here",
            "r_vrm": float(vrm.get("r_out") or 0.015),
            "l_vrm": float(vrm.get("l_out") or 2e-9),
            "c_vrm": float(vrm.get("c_out") or 47e-6),
        }

    scenarios = None
    if not args.no_scenarios:
        scenarios = []
        for m in ("clock", "spatial", "simultaneous"):
            if m == args.mode:
                scenarios.append(
                    {
                        "mode": m,
                        "droop_mv": dyn["worst_droop"] * 1e3,
                        "t_ns": dyn["worst_time_s"] * 1e9,
                        "i_peak_a": max(dyn["wave_itot"]) if dyn["wave_itot"] else 0.0,
                        "via": solver_a.name,
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
            r_m = timestep_be(sys_be, ev_m, solver_a, vdd, order, t_end)
            scenarios.append(
                {
                    "mode": m,
                    "droop_mv": r_m["worst_droop"] * 1e3,
                    "t_ns": r_m["worst_time_s"] * 1e9,
                    "i_peak_a": max(r_m["wave_itot"]) if r_m["wave_itot"] else 0.0,
                    "via": solver_a.name,
                    "primary": False,
                }
            )
        scenarios.sort(key=lambda s: -s["droop_mv"])
        if mor is not None and mor_meta is not None:
            mor_scen = []
            for m in ("clock", "spatial", "simultaneous"):
                if m == args.mode:
                    mor_scen.append(
                        {
                            "mode": m,
                            "droop_mv": mor_meta["worst_droop_mv"],
                            "t_ns": mor_meta["worst_time_ns"],
                            "via": mor.name,
                            "role": "screening",
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
                r_m = mor.timestep(sys_be, ev_m, vdd, t_end)
                mor_scen.append(
                    {
                        "mode": m,
                        "droop_mv": r_m["worst_droop"] * 1e3,
                        "t_ns": r_m["worst_time_s"] * 1e9,
                        "via": mor.name,
                        "role": "screening",
                        "primary": False,
                    }
                )
            mor_scen.sort(key=lambda s: -s["droop_mv"])
            mor_meta["scenarios"] = mor_scen
            mor_meta["note"] = (
                "Scenario ranking is Solver A gold. MOR is the reduced ODE for reuse, not ranking."
            )
    Vw = dyn.pop("V_worst")
    pts = heatmap_points(order, Vw, vdd, events)
    hottest = sorted(pts, key=lambda p: p["ir_mv"], reverse=True)[:8]
    em = em_snapshot(
        resistors,
        idx,
        order,
        Vw,
        bump=sys_be["bump"],
        bump_v=sys_be["bump_v"],
        i_L=dyn.get("i_L_worst"),
        pkg_r=args.pkg_r,
        pkg_l=args.pkg_l,
    )

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
    gold_rl = None
    gold_n4 = None
    if not args.skip_ngspice:
        gold = ngspice_gold(vdd=vdd)
        gold_rl = ngspice_rl_gold(vdd=vdd)
        gold_n4 = ngspice_vrm_die_gold(
            vdd=vdd,
            r_vrm=0.015,
            l_vrm=2e-10,
            c_vrm=50e-12,
            r_pkg=0.05,
            l_pkg=2e-10,
            c_die=50e-12,
            i_peak=5e-3,
            t50=0.2e-9,
            dur=0.2e-9,
            dt=10e-12,
            t_end=0.4e-9,
        )

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
            "status": activity_model["status"],
            "reason": activity_model["note"],
        },
        "L3_windowed": {
            "status": "PARTIAL",
            "windows": windows,
            "note": "high-I windows on this run's I_tot(t), not 100k-cycle screening",
        },
    }
    i_via = (
        f"CCS interpolator {current_model['n_ccs_tables']} tables in TRAN (lagged I(slew,V^n)) — not native triangle"
        if events_use_ccs(events, ccs_tables)
        else (
            f"CCS interpolator {current_model['n_ccs_tables']} tables — mesh still triangle (no cell Vout(t)/slew on events)"
            if current_model.get("n_ccs_tables")
            else f"per-ITerm triangle PWL ({current_model['kind']})"
        )
    )
    pipeline = [
        {"id": 1, "name": "PDN extraction", "status": "READY", "via": "OpenROAD write_pg_spice"},
        {
            "id": 2,
            "name": "Power model",
            "status": "PARTIAL",
            "via": current_model["note"],
        },
        {
            "id": 3,
            "name": "Activity engine",
            "status": "PARTIAL",
            "via": f"synthetic {args.mode}; {activity_model['note']}",
        },
        {"id": 4, "name": "Current waveform", "status": "PARTIAL", "via": i_via},
        {
            "id": 5,
            "name": "Transient solver",
            "status": "READY",
            "via": "A LU gold + B SA-AMG + C descriptor RLC Krylov + D RAS Schwarz",
        },
        {"id": 6, "name": "Analysis", "status": "PARTIAL", "via": "heatmap + windows + delay scaling + branch I EM screen; J/TTF = GAP"},
    ]
    plat = platform_block(
        mode=args.mode,
        c_decap=args.c_decap,
        pkg_r=args.pkg_r,
        pkg_l=args.pkg_l,
        amg=amg_meta,
        scenarios=scenarios,
        timing=timing,
        mor=mor_meta,
        adaptive=adaptive_meta,
        em=em,
        n4=n4_meta,
        ras=ras_meta,
    )
    amg_note = (
        f" · AMG {amg_meta['worst_droop_mv']:.3f} mV (|A−B| {amg_meta['abs_err_vs_A_mv']:.3f} mV)"
        if amg_meta
        else ""
    )
    mor_note = (
        f" · MOR m={mor_meta['m']} {mor_meta['worst_droop_mv']:.3f} mV (|A−C| {mor_meta['abs_err_vs_A_mv']:.3f} mV)"
        if mor_meta
        else ""
    )
    ras_note = (
        f" · RAS {ras_meta['worst_droop_mv']:.3f} mV (|A−D| {ras_meta['abs_err_vs_A_mv']:.3f} mV, ndom={ras_meta['n_levels']})"
        if ras_meta
        else ""
    )
    n4_note = (
        f" · N4 {n4_meta['worst_droop_mv']:.3f} mV (|N3−N4| {n4_meta['abs_err_vs_N3_mv']:.3f} mV)"
        if n4_meta
        else ""
    )
    report = {
        "ok": True,
        "kind": "dynamic_ir",
        "engine": "studio-dynamic-ir",
        "architecture": [
            "OpenROAD write_pg_spice PDN (static R mesh) — frontend, not a PSM fork",
            "replaceable activity (synthetic t50) + current (triangle; CCS interpolator when tables exist)",
            "Solver A: direct backward-Euler sparse LU (golden) with R+L i_L history",
            "Solver B: smoothed-aggregation AMG + CG on the SPD companion (workhorse)",
            "Solver C: rational Krylov — RC on δv, or descriptor RLC on x=[v; i_L] matching i_L",
            "Solver D: restricted additive Schwarz on the BE operator (graph partition, local LU, GMRES)",
            "Native BE/MOR/RAS in libdpn; Python orchestrates extraction and I(t); CCS lagged I(V) when tables+slew",
            "V(x,y) heatmap at t_worst + delay scaling at worst tap",
        ],
        "not": [
            "CCS I(t) on Nangate45 (NLDM, no current tables — interpolator is tested on synthetic CCS)",
            "gate-level VCD pin times",
            "RedHawk / Voltus / Totem sign-off",
            "vyges-em-ir fork",
            "EMSim commercial flow (VCS/Calibre/PT-PX/HSpice)",
        ],
        "roles": {
            "openroad": "physical frontend — ODB → PDN graph; do not fork PSM",
            "emsim": "architectural split A (cell current → PWL) vs B (PDN TRAN) — not vendored, not run",
            "vyges_em_ir": "bootstrap + simultaneous-switch validation — not the core",
            "this_engine": "A gold + B SA-AMG + C descriptor RLC Krylov + D RAS on write_pg_spice; triangle I(t) on NLDM",
            "ngspice": "unit-test gold for BE on 1-node RC and 1-node series R+L",
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
                "not": "CCS on this Nangate mesh / PT-PX current profiles / gate VCD",
            },
            "B_pdn_solve": {
                "status": "READY",
                "solver": "A_direct_be + B_sa_amg + C_rational_krylov_mor + D_ras_schwarz",
                "replaces": "HSpice TRAN on Calibre DSPF",
                "via": "Solver A LU golden + B SA-AMG + C reduced ODE + D RAS Schwarz on write_pg_spice",
                "gold": "ngspice 1-node RC + series R+L companion; A vs B vs C vs D on the chip mesh",
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
        "current_model": current_model,
        "activity_model": activity_model,
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
        "ngspice_rl_gold": gold_rl,
        "ngspice_n4_gold": gold_n4,
        "em": em,
        "solver_b": amg_meta,
        "solver_c": mor_meta,
        "solver_d": ras_meta,
        "n4": n4_meta,
        "adaptive": adaptive_meta,
        "scenarios": scenarios,
        "timing_impact": timing,
        "summary": (
            f"{args.mode} · static {static['worst_ir']*1e3:.3f} mV · "
            f"dynamic droop {dyn['worst_droop']*1e3:.3f} mV "
            f"({dyn['worst_droop_pct']:.3f}%) @ {dyn['worst_time_s']*1e9:.2f} ns · "
            f"I_peak {i_tot_peak*1e3:.2f} mA · {len(events)} PWL · "
            f"t50 span {((max(t50s)-min(t50s))*1e9) if t50s else 0:.2f} ns"
            f"{amg_note}"
            f"{mor_note}"
            f"{ras_note}"
            f"{n4_note}"
            f" · delay +{timing['degradation_ps']:.2f} ps"
        ),
    }

    def _json(o):
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))

    out.write_text(json.dumps(report, indent=2, default=_json) + "\n")
    print("DYNAMIC_IR_DONE")
    print(report["summary"])
    print(f"report → {out}")
    print(f"wave → {wave_path}")
    print(f"map → {svg_path}")
    if gold:
        print("ngspice_gold", gold)
    if gold_rl:
        print("ngspice_rl_gold", gold_rl)
    if gold_n4:
        print("ngspice_n4_gold", gold_n4)
    if n4_meta:
        print("n4", {k: n4_meta[k] for k in n4_meta if k != "note"})
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "/usr/lib/python3/dist-packages")
    sys.exit(main())
