#!/usr/bin/env python3
"""Dynamic IR on the OpenROAD write_pg_spice mesh (RedHawk-Dynamic *slice*).

Architecture (what this file actually does — not a product claim):

  OpenROAD write_pg_spice  →  PDN graph (R mesh, bump V, I_avg)
  activity layer (STA arrival t50 in clock; VCD/SAIF name-join; else synthetic)
  current layer (triangle; CCS interpolator if tables+slew)
  Solver A: direct backward-Euler + sparse LU (golden)
  Solver B: SA-AMG + CG on the same SPD companion operator
  Solver C: rational Krylov MOR — RC on δv, or descriptor RLC on x=[v; i_L]
  Solver D: restricted additive Schwarz (graph partition, local LU, GMRES)
  Vmin(t) + V(x,y) heatmap at t_worst + OpenSTA path IR delay

Solver A is the golden oracle. Solver C with L>0 reduces Eẋ+Ax=u matching
the BE companion (not an RC-only Gsoft screen). Ranking of extra I(t) stays A.

The BE time loop and MOR live in libdpn. Python orchestrates extraction and I(t).

Honest limits: Nangate45 has no CCS current tables (triangle from I_avg);
RTL VCD does not name gate pins — name-join only, no silent RTL→ITerm map.
STA t50 uses report_arrival; I_avg is not rescaled from activity Hz.

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

from pdn_activity import (  # noqa: E402
    expand_windows,
    load_insts,
    load_sta_arrivals,
    load_sta_path,
    node_xy,
    parse_saif,
    parse_vcd,
    plan_events,
    probe_activity_trace,
    shift_events_to_window,
    t50_via_counts,
    windows_from_itot,
)
from pdn_current import (  # noqa: E402
    current_source_for_event,
    events_use_ccs,
    parse_ccs_output_current,
    probe_liberty_current_model,
    triangle_above_leak,
)
from pdn_em import em_thermal_snapshot  # noqa: E402
from pdn_extract import extract_pdn, summarize_extract, parse_pg_sinks, pair_pg_rails, remap_events_to_rail  # noqa: E402
from pdn_solvers import (  # noqa: E402
    DirectLU,
    RASDD,
    RationalKrylov,
    SAAMG,
    mor_starts,
    native_adaptive,
    native_index_width,
    native_timestep,
    residual_rel,
    rl_companion,
    droop_pct,
)
from pdn_transient import build_system, solve_static  # noqa: E402
from pdn_vrm import assemble_n4_mesh, assemble_strap_rlc, load_vrm_cfg, ngspice_vrm_die_gold, timestep_descriptor  # noqa: E402


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


def assemble_be(G, idx, voltages, vdd, events, *, pkg_r, pkg_l, c_decap, dt, spef_c=None):
    """A = G + C/Δt + pad conductance. Independent of I(t) / t50.

    Pad stamp is the BE companion of lumped package R+L: g_eq = 1/(R+L/Δt).
    Inductor current i_L is *not* in A — it lives on the RHS of the time loop.
    spef_c is extra interconnect C (Farads) on named spice nodes, added to
    lumped c_decap — not a replacement, and never taken from signal SPEF.
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
    n_spef = 0
    c_spef = 0.0
    if spef_c:
        for nm, cf in spef_c.items():
            if nm in idx:
                C[idx[nm]] += float(cf)
                n_spef += 1
                c_spef += float(cf)

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
        "spef_n": n_spef,
        "spef_c_sum_f": c_spef,
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
        "worst_droop_pct": droop_pct(vdd, worst_v),
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


def windowed_timestep_be(
    sys: dict,
    events,
    solver,
    vdd: float,
    order,
    t_end: float,
    wave_t,
    wave_itot,
    dyn_full: dict,
    ccs_tables: list | None = None,
    frac: float = 0.5,
) -> dict:
    """Solver A on high-I windows. Isolated restart only when L=0 (or idle ≫ L/R).

    With package L, i_L is history: restarting UIC Vdd mid-horizon is wrong.
    Then L3 is a prefix BE [0, t_cut] that drops trailing idle, or identity if
    the I_tot window already covers the horizon.
    """
    dt = float(sys["dt"])
    pkg_r = float(sys.get("pkg_r") or 0.0)
    pkg_l = float(sys.get("pkg_l") or 0.0)
    lr = (pkg_l / pkg_r) if pkg_r > 0 else 0.0
    durs = [float(e.get("dur_s") or 0.0) for e in events] or [dt]
    pad_s = max(3 * dt, 0.5 * max(durs))
    raw = windows_from_itot(wave_t, wave_itot, frac)
    wins = expand_windows(raw, pad_s, t_end)
    full_steps = int(dyn_full.get("steps") or 0)
    gold_droop = float(dyn_full.get("worst_droop") or 0.0)
    base = {
        "n_windows_raw": len(raw),
        "n_windows": len(wins),
        "pad_s": pad_s,
        "full_steps": full_steps,
        "L_over_R_ns": lr * 1e9,
        "threshold_frac": frac,
        "windows": [
            {
                "t_start_ns": w["t_start_s"] * 1e9,
                "t_end_ns": w["t_end_s"] * 1e9,
                "t_peak_ns": w["t_peak_s"] * 1e9,
                "i_peak_a": w["i_peak_a"],
            }
            for w in wins
        ],
    }
    if not wins:
        return {
            **base,
            "status": "GAP",
            "collapsed_to_full": False,
            "steps": 0,
            "abs_err_vs_A_mv": None,
            "via": "no I_tot window",
            "note": "I_tot never crossed the window threshold",
        }

    covers = (
        len(wins) == 1
        and wins[0]["t_start_s"] <= 2 * dt
        and wins[0]["t_end_s"] >= t_end - 2 * dt
    )
    if covers:
        return {
            **base,
            "status": "READY",
            "collapsed_to_full": True,
            "steps": full_steps,
            "worst_droop_mv": gold_droop * 1e3,
            "worst_time_ns": float(dyn_full.get("worst_time_s") or 0.0) * 1e9,
            "abs_err_vs_A_mv": 0.0,
            "via": "one I_tot window covers the horizon — windowed BE is the full TRAN",
            "note": "not 100k-cycle screening; this run's I_tot already occupies [0, t_end]",
        }

    isolated_ok = pkg_l <= 0.0
    if not isolated_ok and len(wins) >= 2 and lr > 0:
        gaps = [wins[i]["t_start_s"] - wins[i - 1]["t_end_s"] for i in range(1, len(wins))]
        isolated_ok = min(gaps) >= 3 * lr and wins[0]["t_start_s"] >= 3 * lr

    if isolated_ok:
        worst_droop = 0.0
        worst_t = 0.0
        steps = 0
        per = []
        for w in wins:
            t0, t1 = w["t_start_s"], w["t_end_s"]
            evw = shift_events_to_window(events, t0, t1)
            if not evw:
                continue
            span = max(t1 - t0, 2 * dt)
            r = timestep_be(sys, evw, solver, vdd, order, span, ccs_tables=ccs_tables)
            t_abs = r["worst_time_s"] + t0
            steps += int(r["steps"])
            per.append(
                {
                    "t_start_ns": t0 * 1e9,
                    "t_end_ns": t1 * 1e9,
                    "steps": r["steps"],
                    "droop_mv": r["worst_droop"] * 1e3,
                    "t_ns": t_abs * 1e9,
                    "n_events": len(evw),
                }
            )
            if r["worst_droop"] > worst_droop:
                worst_droop = r["worst_droop"]
                worst_t = t_abs
        err_mv = abs(worst_droop - gold_droop) * 1e3
        return {
            **base,
            "status": "READY" if per and err_mv < 1.0 else ("PARTIAL" if per else "GAP"),
            "collapsed_to_full": False,
            "steps": steps,
            "isolated": True,
            "per_window": per,
            "worst_droop_mv": worst_droop * 1e3,
            "worst_time_ns": worst_t * 1e9,
            "abs_err_vs_A_mv": err_mv,
            "via": "isolated BE on I_tot windows; t50 shifted so each window starts at 0; UIC Vdd",
            "note": (
                "valid when pkg L=0 or idle gaps ≫ L/R; not 100k-cycle screening"
            ),
        }

    t_cut = wins[-1]["t_end_s"]
    if t_cut >= t_end - 2 * dt:
        return {
            **base,
            "status": "READY",
            "collapsed_to_full": True,
            "steps": full_steps,
            "worst_droop_mv": gold_droop * 1e3,
            "worst_time_ns": float(dyn_full.get("worst_time_s") or 0.0) * 1e9,
            "abs_err_vs_A_mv": 0.0,
            "via": "I_tot window reaches t_end — prefix cut would be the full TRAN",
            "note": (
                f"pkg L/R={lr*1e9:.2f} ns; isolated restart would drop i_L history"
            ),
        }
    r = timestep_be(sys, events, solver, vdd, order, t_cut, ccs_tables=ccs_tables)
    err_mv = abs(r["worst_droop"] - gold_droop) * 1e3
    return {
        **base,
        "status": "READY" if err_mv < 1.0 else "PARTIAL",
        "collapsed_to_full": False,
        "steps": int(r["steps"]),
        "isolated": False,
        "t_cut_ns": t_cut * 1e9,
        "worst_droop_mv": r["worst_droop"] * 1e3,
        "worst_time_ns": r["worst_time_s"] * 1e9,
        "abs_err_vs_A_mv": err_mv,
        "via": "prefix BE [0, t_cut] preserving i_L; not isolated restart",
        "note": (
            f"pkg L/R={lr*1e9:.2f} ns vs horizon {t_end*1e9:.2f} ns — "
            "UIC restart mid-window would drop inductor current"
        ),
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
        G, idx, voltages, vdd, events, pkg_r=pkg_r, pkg_l=pkg_l, c_decap=c_decap, dt=dt, spef_c=None
    )
    solver = DirectLU(sys["A"]) if backend in ("a", "direct", "lu") else SAAMG(sys["A"])
    return timestep_be(sys, events, solver, vdd, order, t_end)


def timing_impact(vdd: float, vmin: float, period_ns: float, alpha: float = 1.3) -> dict:
    """Delay scaling at the worst tap — used only when no OpenSTA path joins."""
    v_eff = max(float(vmin), 0.25 * vdd)
    scale = (vdd / v_eff) ** alpha
    delay_nom_ps = 30.0  # ~FO4-class inverter at 45 nm, didactic fallback
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


def path_ir_timing(
    path: dict | None,
    events: list,
    Vw,
    vdd: float,
    period_ns: float,
    alpha: float = 1.3,
) -> dict:
    """Scale OpenSTA NLDM typical-V *gate* delays by local Vmin. Nets stay unscaled.

    READY when ≥1 path gate joins an ITerm event. Unjoined gates stay at Vdd.
    This is not a second liberty at Vmin and not CCS voltage-dependent delay.
    """
    from pdn_activity import norm_inst

    vmin = float(np.min(Vw)) if Vw is not None and len(Vw) else vdd
    tap = timing_impact(vdd, vmin, period_ns, alpha)
    if not path or not path.get("stages"):
        tap["path"] = {
            "status": "GAP",
            "note": "no OpenSTA worst_path in arrivals JSON",
        }
        return tap
    by_inst: dict[str, float] = {}
    for ev in events:
        name = norm_inst(ev.get("inst"))
        if not name or ev.get("idx") is None or Vw is None:
            continue
        try:
            v = float(Vw[int(ev["idx"])])
        except (IndexError, TypeError, ValueError):
            continue
        prev = by_inst.get(name)
        if prev is None or v < prev:
            by_inst[name] = v
    stages_out = []
    n_joined = 0
    gate_nom = 0.0
    gate_ir = 0.0
    for st in path["stages"]:
        kind = st.get("kind") or "net"
        d_ns = float(st.get("delay_ns") or 0.0)
        v_inst = vdd
        joined = False
        if kind == "gate":
            key = norm_inst(st.get("inst_key") or st.get("inst"))
            if key in by_inst:
                v_inst = by_inst[key]
                joined = True
                n_joined += 1
            v_eff = max(v_inst, 0.25 * vdd)
            scale = (vdd / v_eff) ** alpha
            d_ir = d_ns * scale
            gate_nom += d_ns
            gate_ir += d_ir
        else:
            scale = 1.0
            d_ir = d_ns
        stages_out.append({**st, "v_inst": v_inst, "joined": joined, "delay_ir_ns": d_ir, "scale": scale})
    slack_ns = path.get("slack_ns")
    deg_ns = gate_ir - gate_nom
    slack_ir = None if slack_ns is None else (float(slack_ns) - deg_ns)
    path_meta = {
        "status": "READY" if n_joined else "GAP",
        "startpoint": path.get("startpoint"),
        "endpoint": path.get("endpoint"),
        "slack_ns": slack_ns,
        "slack_ir_ns": slack_ir,
        "slack_met": path.get("slack_met"),
        "n_gates": path.get("n_gates"),
        "n_joined": n_joined,
        "gate_delay_ns": gate_nom,
        "gate_delay_ir_ns": gate_ir,
        "via": path.get("via"),
        "note": (
            "NLDM typical-V OpenSTA delays scaled by (Vdd/V_inst)^alpha on joined gates; "
            "not a second liberty at Vmin / CCS voltage-dependent delay"
        ),
    }
    if n_joined:
        deg_ps = deg_ns * 1e3
        scale = (gate_ir / gate_nom) if gate_nom > 0 else 1.0
        return {
            "status": "READY",
            "model": "OpenSTA NLDM typical-V gate delay * (Vdd/V_inst)^alpha; nets unscaled",
            "alpha": alpha,
            "vmin": vmin,
            "scale": scale,
            "delay_nom_ps": gate_nom * 1e3,
            "degradation_ps": deg_ps,
            "period_ns": period_ns,
            "frac_of_period": (deg_ps * 1e-3) / period_ns if period_ns else None,
            "note": path_meta["note"],
            "path": path_meta,
            "tap_fallback": {
                "degradation_ps": tap["degradation_ps"],
                "scale": tap["scale"],
                "delay_nom_ps": tap["delay_nom_ps"],
            },
        }
    tap["path"] = path_meta
    tap["note"] = "path present but unjoined — delay scaling at worst tap only"
    return tap


def run_return_rail(
    spice_vdd: Path,
    spice_vss: Path,
    events: list,
    vdd_idx: dict,
    *,
    pkg_r: float,
    pkg_l: float,
    c_decap: float,
    dt: float,
    t_end: float,
    lef: Path | None,
    spef: Path | None,
) -> dict:
    """VSS return-path TRAN. Same I(t) magnitude as VDD on paired sinks. Does not change VDD gold.

    Block-diagonal dual-rail MNA (no rail-to-rail C). UIC and pads are 0 V.
    Bounce = −Vmin (I DC convention: current from node to 0, same as PDNSim).
    """
    vdd_sinks = parse_pg_sinks(spice_vdd)
    vss_sinks = parse_pg_sinks(spice_vss)
    paired = pair_pg_rails(vdd_sinks, vss_sinks)
    if paired.get("status") != "READY":
        return {
            "status": "GAP",
            "reason": "no inst-pin pairs between VDD and VSS spice sinks",
            "pair": paired,
        }
    ext_s = extract_pdn(spice_vss, lef=lef, spef=spef)
    resistors, currents, voltages = ext_s["resistors"], ext_s["currents"], ext_s["voltages"]
    order_s, idx_s, G_s = build_system(resistors, currents, voltages)
    ev_s = remap_events_to_rail(events, vdd_idx, idx_s, paired["pairs"])
    if not ev_s:
        return {
            "status": "GAP",
            "reason": "paired sinks but no VDD events remapped",
            "pair": {k: v for k, v in paired.items() if k != "pairs"},
            "n_pairs": paired["n_pairs"],
        }
    sys_s = assemble_be(
        G_s,
        idx_s,
        voltages,
        0.0,
        ev_s,
        pkg_r=pkg_r,
        pkg_l=pkg_l,
        c_decap=c_decap,
        dt=dt,
        spef_c=(ext_s.get("spef") or {}).get("node_c"),
    )
    lu = DirectLU(sys_s["A"])
    dyn_s = timestep_be(sys_s, ev_s, lu, 0.0, order_s, t_end)
    bounce = -float(dyn_s["worst_voltage"])
    return {
        "status": "READY",
        "ok": True,
        "n_pairs": paired["n_pairs"],
        "n_events": len(ev_s),
        "n_nodes": sys_s["n"],
        "n_pads": len(sys_s.get("bump") or []),
        "worst_bounce_mv": bounce * 1e3,
        "worst_voltage": dyn_s["worst_voltage"],
        "worst_time_ns": dyn_s["worst_time_s"] * 1e9,
        "worst_node": dyn_s.get("worst_node"),
        "backend": dyn_s.get("backend"),
        "timestep_loop": dyn_s.get("timestep_loop"),
        "extract": summarize_extract(ext_s),
        "pair": {k: v for k, v in paired.items() if k != "pairs"},
        "via": paired["via"],
        "note": paired["note"],
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
    extract: dict | None = None,
    activity: dict | None = None,
    on_die_l: dict | None = None,
    vss: dict | None = None,
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
    n_sta = int(((activity or {}).get("sta") or {}).get("n_applied") or 0)
    fast_slice = (
        f"STA arrival t50 ({n_sta} ITerms) + Solver B SA-AMG"
        if n_sta
        else f"synthetic {mode} t50 + Solver B SA-AMG"
    )
    idx_bits = native_index_width()
    return {
        "name": "hierarchical multi-fidelity power-integrity engine",
        "slice": "native libdpn (A LU + B SA-AMG + C Krylov MOR + D RAS Schwarz + descriptor N4) + extract/EM layers + OpenROAD + triangle/CCS I(t)",
        "native_index_bits": idx_bits,
        "native_index": {
            "status": "READY" if idx_bits == 64 else "GAP",
            "bits": idx_bits,
            "via": "libdpn Index = int64_t (Eigen StorageIndex + C API); SciPy fallback CSR may still be int32",
        },
        "do_not_fork": ["vyges-em-ir", "EMSim", "OpenROAD PSM"],
        "do_not_implement_this_slice": [
            "silent RTL VCD → gate ITerm mapping (name-join only)",
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
                "role": "domain decomposition on the BE operator and on unsymmetric descriptor K",
                "via": "restricted additive Schwarz: undirected graph-grown subdomains, overlapping local SparseLU, RAS restriction, GMRES; kind=2 on descriptor K (never AMG)",
                "not": "index stripes, CG (RAS is not SPD), AMG",
                "vs_A": ras,
            },
            "VSS_return": {
                "status": (vss or {}).get("status") or "GAP",
                "role": "return-path TRAN on write_pg_spice VSS (block-diagonal dual-rail)",
                "via": (vss or {}).get("via") or "write_pg_spice -net VSS + Sink-for inst pair",
                "not": "rail-to-rail C, replacement of VDD gold",
                "meta": None if not vss else {k: v for k, v in vss.items() if k not in ("extract",)},
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
                "via": (
                    f"lumped c_decap + SPEF PG C on {((extract or {}).get('spef') or {}).get('n_stamped')} nodes"
                    if ((extract or {}).get("spef") or {}).get("status") == "READY"
                    else "lumped c_decap on ITerm nodes"
                ),
                "c_decap": c_decap,
                "spef": None if not extract else ((extract.get("spef") or {}).get("status")),
            },
            "N3_RC_pkg": {
                "status": "READY",
                "eq": "RC + lumped package R+L companion at bumps",
                "via": "g_eq=1/(R+L/Δt) on pad diagonals; i_L history on the RHS",
                "pkg_r": pkg_r,
                "pkg_l": pkg_l,
                "on_die_l": None if not extract else ((extract.get("on_die_l") or {}).get("status")),
                "note": (
                    f"Grover partial self on {((extract or {}).get('on_die_l') or {}).get('n_stamped')} straps "
                    f"(Σ {(((extract or {}).get('on_die_l') or {}).get('L_sum_h') or 0)*1e9:.3f} nH is not loop L; "
                    f"{((extract or {}).get('on_die_l') or {}).get('n_mutual') or 0} mutual pairs, d≤2 µm); "
                    + (
                        "descriptor TRAN stamped (--on-die-l)"
                        if on_die_l and on_die_l.get("ok")
                        else "default TRAN is still RC+pkg companion so AMG applies"
                    )
                    if ((extract or {}).get("on_die_l") or {}).get("status") == "READY"
                    else "not extracted on-die inductance; companion stays SPD so AMG applies"
                ),
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
                "this_slice": fast_slice,
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
        "extract": extract
        or {
            "status": "READY",
            "backend": "write_pg_spice",
            "idea": "OpenROAD SPICE + tech LEF; SPEF PG C stamped from PG *D_NET by name-join",
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
    return [
        {
            "t_start_ns": w["t_start_s"] * 1e9,
            "t_end_ns": w["t_end_s"] * 1e9,
            "t_peak_ns": w["t_peak_s"] * 1e9,
            "i_peak_a": w["i_peak_a"],
            "threshold_frac": w["threshold_frac"],
        }
        for w in windows_from_itot(wave_t, wave_itot, frac)
    ]


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
    ap.add_argument("--vcd", type=Path, default=None, help="VCD/SAIF/FSDB: name-join only, never a silent RTL map")
    ap.add_argument("--sta", type=Path, default=None, help="OpenSTA arrivals JSON (t50 from rise arrival in clock mode)")
    ap.add_argument("--no-vrm", action="store_true", help="skip coupled N4 VRM+die descriptor BE")
    ap.add_argument("--vrm-cfg", type=Path, default=None, help="system_pdn JSON for lumped VRM")
    ap.add_argument("--lef", type=Path, default=None, help="tech LEF for metal WIDTH/THICKNESS/RPERSQ (EM J)")
    ap.add_argument("--spef", type=Path, default=None, help="SPEF PG *D_NET *CAP stamped by name-join (never mapped from signal nets)")
    ap.add_argument("--spice-vss", type=Path, default=None, help="write_pg_spice VSS mesh; dual-rail return TRAN (does not change VDD gold)")
    args = ap.parse_args()

    current_model = probe_liberty_current_model(args.liberty)
    ccs_tables: list = []
    if args.liberty and Path(args.liberty).is_file() and current_model.get("n_ccs_tables"):
        ccs_tables = parse_ccs_output_current(Path(args.liberty).read_text(errors="replace")[:2_000_000])

    ext = extract_pdn(args.spice, lef=args.lef, spef=args.spef)
    extract_report = summarize_extract(ext)
    resistors, currents, voltages = ext["resistors"], ext["currents"], ext["voltages"]
    order, idx, G = build_system(resistors, currents, voltages)
    vdd = args.vdd or next(iter(voltages.values()))
    period_s = args.period_ns * 1e-9
    dur_s = args.dur_ns * 1e-9
    t50_s = args.t50_ns * 1e-9
    dt = args.dt_ps * 1e-12
    t_end = (args.t_end_ns * 1e-9) if args.t_end_ns > 0 else max(period_s * 1.6, t50_s + dur_s * 3)

    insts = load_insts(args.insts) if args.insts else []
    activity_model = probe_activity_trace(args.vcd, insts)
    sta_arrivals = load_sta_arrivals(args.sta)
    sta_path = load_sta_path(args.sta)
    vcd_parsed = None
    saif_parsed = None
    if args.vcd and Path(args.vcd).is_file():
        kind = activity_model.get("kind")
        if kind == "vcd":
            vcd_parsed = parse_vcd(Path(args.vcd))
        elif kind == "saif":
            saif_parsed = parse_saif(Path(args.vcd))
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
        sta_arrivals=sta_arrivals if args.mode == "clock" else None,
        vcd=vcd_parsed,
        saif=saif_parsed,
    )
    via_n = t50_via_counts(events)
    n_sta = via_n.get("sta_arrival") or 0
    n_vcd_applied = via_n.get("vcd_name_join") or 0
    n_saif_idle = sum(1 for e in events if e.get("saif_idle"))
    n_saif_joined = sum(1 for e in events if e.get("saif_tc") is not None)
    if not sta_arrivals:
        sta_status = "GAP"
        sta_note = "no STA arrivals JSON"
    elif args.mode != "clock":
        sta_status = "GAP"
        sta_note = "STA arrivals are clock-mode only; ranking extra I(t) stays synthetic"
    elif n_sta:
        sta_status = "READY"
        sta_note = (
            f"clock-mode t50 from OpenSTA report_arrival on {n_sta}/{len(events)} ITerms; "
            "I_avg not rescaled from activity Hz"
        )
    else:
        sta_status = "GAP"
        sta_note = "STA JSON present but no instance-name join to ITerms"
    sta_meta = {
        "status": sta_status,
        "n_inst": len(sta_arrivals),
        "n_applied": n_sta,
        "via": "OpenSTA report_arrival rise folded into the SDC period (clock mode only)",
        "note": sta_note,
        "path": str(args.sta) if args.sta else None,
        "worst_path": (
            {
                "startpoint": sta_path.get("startpoint"),
                "endpoint": sta_path.get("endpoint"),
                "slack_ns": sta_path.get("slack_ns"),
                "n_gates": sta_path.get("n_gates"),
                "gate_delay_ns": sta_path.get("gate_delay_ns"),
            }
            if sta_path
            else None
        ),
    }
    if activity_model.get("kind") == "vcd":
        vcd_meta = {
            "status": activity_model["status"],
            "n_matched": activity_model.get("n_matched") or 0,
            "n_applied": n_vcd_applied,
            "kind": "vcd",
            "note": activity_model.get("note"),
            "path": activity_model.get("path"),
        }
    else:
        vcd_meta = {
            "status": "GAP",
            "n_matched": 0,
            "n_applied": n_vcd_applied,
            "kind": activity_model.get("kind"),
            "note": (
                "SAIF is not VCD; see activity_model.saif"
                if activity_model.get("kind") == "saif"
                else activity_model.get("note")
            ),
            "path": None,
        }
    saif_meta = {
        "status": "GAP",
        "n_matched": 0,
        "n_idle": n_saif_idle,
        "n_joined": n_saif_joined,
        "kind": activity_model.get("kind"),
        "note": "no SAIF",
        "path": None,
    }
    if activity_model.get("kind") == "saif":
        saif_meta = {
            "status": "READY" if n_saif_joined else activity_model["status"],
            "n_matched": activity_model.get("n_matched") or n_saif_joined,
            "n_idle": n_saif_idle,
            "n_joined": n_saif_joined,
            "kind": "saif",
            "note": (
                f"SAIF name-join {n_saif_joined} ITerms, idle-zero {n_saif_idle}; "
                "no t50 from SAIF; I_avg not rescaled from TC"
            ),
            "path": activity_model.get("path"),
            "duration_s": activity_model.get("duration_s"),
        }
    elif activity_model.get("kind") == "fsdb":
        saif_meta["note"] = "FSDB is proprietary binary — no decoder"
        saif_meta["kind"] = "fsdb"
    activity_model["sta"] = sta_meta
    activity_model["vcd"] = vcd_meta
    activity_model["saif"] = saif_meta
    activity_model["t50_via"] = via_n
    activity_model["n_with_inst"] = sum(1 for e in events if e.get("inst"))
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
        spef_c=(ext.get("spef") or {}).get("node_c"),
    )
    solver_a = DirectLU(sys_be["A"])
    dyn = timestep_be(sys_be, events, solver_a, vdd, order, t_end, ccs_tables=ccs_tables)
    win_run = windowed_timestep_be(
        sys_be,
        events,
        solver_a,
        vdd,
        order,
        t_end,
        dyn["wave_t"],
        dyn["wave_itot"],
        dyn,
        ccs_tables=ccs_tables,
    )

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

    vss_meta = None
    if args.spice_vss and Path(args.spice_vss).is_file():
        vss_meta = run_return_rail(
            args.spice,
            args.spice_vss,
            events,
            idx,
            pkg_r=args.pkg_r,
            pkg_l=args.pkg_l,
            c_decap=args.c_decap,
            dt=dt,
            t_end=t_end,
            lef=args.lef,
            spef=args.spef,
        )

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

        dyn_n4 = timestep_descriptor(n4sys, _i_n4, dt, t_end, vdd, leak=leak_n4, events=events)
        err_n4 = abs(dyn["worst_droop"] - dyn_n4["worst_droop"]) * 1e3
        n4_meta = {
            "ok": True,
            "worst_droop_mv": dyn_n4["worst_droop"] * 1e3,
            "worst_time_ns": dyn_n4["worst_time_s"] * 1e9,
            "abs_err_vs_N3_mv": err_n4,
            "via": dyn_n4.get("via")
            or "coupled descriptor BE: write_pg_spice die + lumped VRM C/L/R + bump R+L",
            "backend": dyn_n4.get("backend"),
            "timestep_loop": dyn_n4.get("timestep_loop"),
            "rel_res_max": dyn_n4.get("rel_res_max"),
            "note": "N3 (ideal Vsrc) stays gold on this sub-ns window; 47 µF VRM is stiff here",
            "r_vrm": float(vrm.get("r_out") or 0.015),
            "l_vrm": float(vrm.get("l_out") or 2e-9),
            "c_vrm": float(vrm.get("c_out") or 47e-6),
        }

    ondie_meta = None
    if args.on_die_l:
        branches = (ext.get("on_die_l") or {}).get("branches") or []
        if branches:
            sys_l = assemble_strap_rlc(
                sys_be["G_mesh"],
                sys_be["C"],
                idx,
                voltages,
                branches,
                pkg_r=args.pkg_r,
                pkg_l=args.pkg_l,
                dt=dt,
                vdd=vdd,
                pad="companion",
                mutual=(ext.get("on_die_l") or {}).get("mutual"),
            )
            leak_l = np.asarray(sys_be["leak"], dtype=np.float64)

            def _i_strap(t, leak=leak_l, evs=events):
                I = leak.copy()
                for ev in evs:
                    I[ev["idx"]] += triangle_above_leak(t, ev["t50_s"], ev["dur_s"], ev["i_pulse"])
                return I

            dyn_l = timestep_descriptor(sys_l, _i_strap, dt, t_end, vdd, leak=leak_l, events=events)
            ondie_meta = {
                "ok": True,
                "status": "READY",
                "n_straps": sys_l.get("n_straps"),
                "n": int(sys_l["A"].shape[0]),
                "pad": sys_l.get("pad"),
                "worst_droop_mv": dyn_l["worst_droop"] * 1e3,
                "worst_time_ns": dyn_l["worst_time_s"] * 1e9,
                "abs_err_vs_N3_mv": abs(dyn_l["worst_droop"] - dyn["worst_droop"]) * 1e3,
                "n_mutual": sys_l.get("n_mutual"),
                "backend": dyn_l.get("backend"),
                "via": sys_l.get("via"),
                "note": "Grover partial self + cutoff mutual; pads stay N3 companion; unsymmetric — not AMG",
            }
        else:
            ondie_meta = {
                "ok": False,
                "status": "GAP",
                "note": "no Grover straps to stamp",
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
    em = em_thermal_snapshot(
        resistors,
        idx,
        order,
        Vw,
        bump=sys_be["bump"],
        bump_v=sys_be["bump_v"],
        i_L=dyn.get("i_L_worst"),
        pkg_r=args.pkg_r,
        pkg_l=args.pkg_l,
        tech=ext.get("tech"),
        currents=currents,
        vdd=vdd,
        f_hz=(1.0 / period_s) if period_s > 0 else None,
    )
    scaled = em.pop("_scaled_resistors", None)
    if scaled and em.get("n_r_scaled"):
        _, _, G_t = build_system(scaled, currents, voltages)
        st_t = solve_static(G_t, idx, order, currents, voltages, vdd)
        em["rT_static_ir_mv"] = st_t["worst_ir"] * 1e3
        em["rT_delta_ir_mv"] = (st_t["worst_ir"] - static["worst_ir"]) * 1e3
        em["rT_via"] = (
            "one-shot N1 restamp R'=R(1+αΔT) from metal-graph T "
            "(cell P=I_avg·Vdd + strap/via I²R; pad Rth=50 K/W); not 3D CFD"
            if (em.get("thermal_mesh") or {}).get("status") == "READY"
            else "one-shot N1 restamp R'=R(1+αΔT) from lumped ΔT=Rth·I²R; mesh GAP"
        )
    else:
        em["rT_static_ir_mv"] = static["worst_ir"] * 1e3
        em["rT_delta_ir_mv"] = 0.0
        em["rT_via"] = "no same-layer J or ΔT≈0 — G not restamped"

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
    timing = path_ir_timing(sta_path, events, Vw, vdd, args.period_ns)
    hotspot["timing"] = {
        "degradation_ps": timing["degradation_ps"],
        "scale": timing["scale"],
        "status": timing.get("status"),
        "path_slack_ns": (timing.get("path") or {}).get("slack_ns"),
        "path_slack_ir_ns": (timing.get("path") or {}).get("slack_ir_ns"),
        "n_joined": (timing.get("path") or {}).get("n_joined"),
    }
    sim_levels = {
        "L0_static": {
            "status": "READY",
            "worst_ir_mv": static["worst_ir"] * 1e3,
        },
        "L1_vectorless_dynamic": {
            "status": "READY",
            "mode": args.mode,
            "t50_via": via_n,
            "note": (
                sta_note
                if n_sta
                else "synthetic t50 (clock/spatial/simultaneous); STA arrivals not applied"
            ),
        },
        "L2_vcd_dynamic": {
            "status": activity_model["status"],
            "kind": activity_model.get("kind"),
            "reason": activity_model["note"],
            "n_matched": activity_model.get("n_matched") or 0,
            "saif_idle": n_saif_idle,
        },
        "L3_windowed": {
            "status": win_run.get("status") or "PARTIAL",
            "windows": windows,
            "n_windows": win_run.get("n_windows"),
            "collapsed_to_full": win_run.get("collapsed_to_full"),
            "steps": win_run.get("steps"),
            "full_steps": win_run.get("full_steps"),
            "abs_err_vs_A_mv": win_run.get("abs_err_vs_A_mv"),
            "via": win_run.get("via"),
            "note": win_run.get("note")
            or "high-I windows on this run's I_tot(t), not 100k-cycle screening",
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
    path_ok = (timing.get("path") or {}).get("status") == "READY"
    em_via = (
        f"heatmap + windows + {'path STA delay' if path_ok else 'tap delay scaling'} + J={em.get('j_absmax_a_m2', 0):.3e} A/m² "
        f"+ relative Black TTF + lumped R(T) N1 restamp"
        if em.get("n_with_j")
        else (
            f"heatmap + windows + {'path STA delay' if path_ok else 'tap delay scaling'} + branch I (no same-layer coords for J)"
        )
    )
    pipeline = [
        {
            "id": 1,
            "name": "PDN extraction",
            "status": "READY",
            "via": (
                f"{extract_report.get('backend')} + tech LEF "
                f"({(extract_report.get('tech') or {}).get('status')}); "
                f"SPEF PG C {(extract_report.get('spef') or {}).get('status')}"
            ),
        },
        {
            "id": 2,
            "name": "Power model",
            "status": "PARTIAL",
            "via": current_model["note"],
        },
        {
            "id": 3,
            "name": "Activity engine",
            "status": "READY" if (n_sta or n_vcd_applied or n_saif_joined) else "PARTIAL",
            "via": (
                f"STA t50 {n_sta}/{len(events)}"
                + (f"; VCD name-join {n_vcd_applied}" if n_vcd_applied else f"; VCD {vcd_meta['status']}")
                + (
                    f"; SAIF join {n_saif_joined} idle {n_saif_idle}"
                    if n_saif_joined
                    else f"; SAIF {saif_meta['status']}"
                )
                + f"; synthetic remainder {via_n.get('synthetic') or 0}"
            ),
        },
        {"id": 4, "name": "Current waveform", "status": "PARTIAL", "via": i_via},
        {
            "id": 5,
            "name": "Transient solver",
            "status": "READY",
            "via": "A LU gold + B SA-AMG + C descriptor RLC Krylov + D RAS Schwarz + native N4 descriptor BE",
        },
        {"id": 6, "name": "Analysis", "status": "PARTIAL", "via": em_via},
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
        extract=extract_report,
        activity=activity_model,
        on_die_l=ondie_meta,
        vss=vss_meta,
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
        f" · N4 {n4_meta['worst_droop_mv']:.3f} mV "
        f"(|N3−N4| {n4_meta['abs_err_vs_N3_mv']:.3f} mV, {n4_meta.get('backend', '?')})"
        if n4_meta
        else ""
    )
    em_note = (
        f" · J {em['j_absmax_a_m2']:.3e} A/m² TTF_rel {em.get('ttf_rel_min')}"
        if em.get("n_with_j")
        else ""
    )
    vss_note = (
        f" · VSS bounce {vss_meta['worst_bounce_mv']:.3f} mV ({vss_meta['n_pairs']} pairs)"
        if vss_meta and vss_meta.get("status") == "READY"
        else (" · VSS GAP" if args.spice_vss else "")
    )
    win_err = win_run.get("abs_err_vs_A_mv")
    l3_note = (
        f" · L3 |A−W| {win_err:.3f} mV"
        if win_err is not None
        else ""
    )
    report = {
        "ok": True,
        "kind": "dynamic_ir",
        "engine": "studio-dynamic-ir",
        "architecture": [
            "OpenROAD write_pg_spice PDN (static R mesh) — frontend, not a PSM fork",
            "replaceable extract layer (pdn_extract): SPICE + tech LEF; SPEF PG C from PG *D_NET; Grover on-die L (descriptor opt-in); dual-rail VSS sink-pair",
            "replaceable activity (STA arrival t50 in clock mode, VCD/SAIF name-join, else synthetic) + current (triangle; CCS/ECSM interpolators when tables exist — never from NLDM)",
            "Solver A: direct backward-Euler sparse LU (golden) with R+L i_L history",
            "Solver B: smoothed-aggregation AMG + CG on the SPD companion (workhorse)",
            "Solver C: rational Krylov — RC on δv, or descriptor RLC on x=[v; i_L] matching i_L",
            "Solver D: restricted additive Schwarz on the BE operator (graph partition, local LU, GMRES)",
            "N4: native descriptor BE on Eẋ+Ax=u (VRM + bump R+L + die mesh); SparseLU, not AMG",
            "EM: J=I/(w t) with w from RPERSQ·L/R; relative Black TTF; metal-graph thermal ΔT (straps+vias) + N1 R(T) restamp; skin depth reported",
            "Native BE/MOR/RAS/N4 in libdpn (Index=int64); Python orchestrates extraction and I(t); CCS lagged I(V) when tables+slew",
            "V(x,y) heatmap at t_worst + OpenSTA path delay scaled by local Vmin (NLDM typical-V, not a second liberty)",
        ],
        "not": [
            "CCS/ECSM I(t) on Nangate45 (NLDM, no current tables — interpolators are tested on synthetic Liberty)",
            "gate-level VCD pin times (RTL VCD names do not match ODB ITerms — no silent map)",
            "foundry Black TTF hours / extracted strap WIDTH from LEF geometry",
            "3D thermal / Si substrate / package CFD (metal-graph straps+vias is not that)",
            "RedHawk / Voltus / Totem sign-off",
            "vyges-em-ir fork",
            "EMSim commercial flow (VCS/Calibre/PT-PX/HSpice)",
        ],
        "roles": {
            "openroad": "physical frontend — ODB → PDN graph; do not fork PSM",
            "extract": "pdn_extract.write_pg_spice + tech LEF; SPEF PG C READY only when *CAP is stamped",
            "activity": "pdn_activity: OpenSTA report_arrival t50 (clock); VCD/SAIF name-join only; windowed BE",
            "em": "pdn_em: J from RPERSQ·L/R, relative Black TTF, lumped ΔT → R(T) N1 restamp — not foundry hours",
            "emsim": "architectural split A (cell current → PWL) vs B (PDN TRAN) — not vendored, not run",
            "vyges_em_ir": "bootstrap + simultaneous-switch validation — not the core",
            "this_engine": "A gold + B SA-AMG + C descriptor RLC Krylov + D RAS + native N4 on write_pg_spice; triangle I(t) on NLDM",
            "ngspice": "unit-test gold for BE on 1-node RC, 1-node series R+L, and compact VRM+die",
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
                "solver": "A_direct_be + B_sa_amg + C_rational_krylov_mor + D_ras_schwarz + N4_descriptor",
                "replaces": "HSpice TRAN on Calibre DSPF",
                "via": "Solver A LU golden + B SA-AMG + C reduced ODE + D RAS Schwarz + native N4 on write_pg_spice",
                "gold": "ngspice 1-node RC + series R+L companion + compact VRM+die; A vs B vs C vs D on the chip mesh",
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
        "extract": extract_report,
        "em": em,
        "solver_b": amg_meta,
        "solver_c": mor_meta,
        "solver_d": ras_meta,
        "vss_rail": vss_meta,
        "n4": n4_meta,
        "on_die_l": ondie_meta or extract_report.get("on_die_l"),
        "adaptive": adaptive_meta,
        "windowed": {k: v for k, v in win_run.items() if k != "V_worst"},
        "scenarios": scenarios,
        "timing_impact": timing,
        "summary": (
            f"{args.mode} · static {static['worst_ir']*1e3:.3f} mV · "
            f"dynamic droop {dyn['worst_droop']*1e3:.3f} mV "
            f"({dyn['worst_droop_pct']:.3f}%) @ {dyn['worst_time_s']*1e9:.2f} ns · "
            f"I_peak {i_tot_peak*1e3:.2f} mA · {len(events)} PWL · "
            f"t50 span {((max(t50s)-min(t50s))*1e9) if t50s else 0:.2f} ns"
            f"{sta_note_sum}"
            f"{amg_note}"
            f"{mor_note}"
            f"{ras_note}"
            f"{n4_note}"
            f"{em_note}"
            f"{l3_note}"
            f"{vss_note}"
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
    if em.get("n_with_j"):
        print(
            "em",
            {
                "status": em.get("status"),
                "j_absmax_a_m2": em.get("j_absmax_a_m2"),
                "ttf_rel_min": em.get("ttf_rel_min"),
                "dT_absmax_k": em.get("dT_absmax_k"),
                "rT_delta_ir_mv": em.get("rT_delta_ir_mv"),
            },
        )
    if n_sta:
        print("sta", {"status": sta_meta["status"], "n_applied": n_sta, "n_inst": sta_meta["n_inst"]})
    print(
        "windowed",
        {
            "status": win_run.get("status"),
            "n_windows": win_run.get("n_windows"),
            "steps": win_run.get("steps"),
            "full_steps": win_run.get("full_steps"),
            "abs_err_vs_A_mv": win_run.get("abs_err_vs_A_mv"),
            "collapsed_to_full": win_run.get("collapsed_to_full"),
        },
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "/usr/lib/python3/dist-packages")
    sys.exit(main())
