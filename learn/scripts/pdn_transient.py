#!/usr/bin/env python3
"""
Static + transient IR on OpenROAD write_pg_spice netlists.

Uses apt NumPy/SciPy (PYTHONPATH=/usr/lib/python3/dist-packages if needed).

Prior art: OpenROAD PDNSim, VoltSpot, vyges-em-ir.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Prefer distro NumPy/SciPy when a newer pip NumPy breaks scipy.sparse
if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

from pdn_extract import parse_spice


def build_system(resistors, currents, voltages):
    nodes = set()
    for a, b, _ in resistors:
        if a != "0":
            nodes.add(a)
        if b != "0":
            nodes.add(b)
    nodes.update(n for n in currents if n != "0")
    nodes.update(n for n in voltages if n != "0")
    order = sorted(nodes)
    idx = {n: i for i, n in enumerate(order)}
    n = len(order)

    rows, cols, data = [], [], []
    def add(i, j, v):
        rows.append(i)
        cols.append(j)
        data.append(v)

    for a, b, r in resistors:
        g = 1.0 / r
        if a == "0" or b == "0":
            node = b if a == "0" else a
            if node in idx:
                i = idx[node]
                add(i, i, g)
            continue
        i, j = idx[a], idx[b]
        add(i, i, g)
        add(j, j, g)
        add(i, j, -g)
        add(j, i, -g)

    G = sparse.coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr()
    return order, idx, G


def solve_static(G, idx, order, currents, voltages, vdd):
    n = G.shape[0]
    fixed_set = {idx[nm] for nm in voltages if nm in idx}
    free_idx = [i for i in range(n) if i not in fixed_set]
    fixed_idx = sorted(fixed_set)
    if not free_idx:
        raise SystemExit("no free nodes")

    I = np.zeros(n)
    for nm, cur in currents.items():
        if nm in idx:
            I[idx[nm]] -= cur

    V = np.zeros(n)
    for nm, volt in voltages.items():
        if nm in idx:
            V[idx[nm]] = volt

    # Regularize floating islands (tiny shunt to a reference)
    G = G.tolil()
    for i in free_idx:
        G[i, i] += 1e-8
    G = G.tocsr()

    Gff = G[free_idx][:, free_idx].tocsc()
    Gfp = G[free_idx][:, fixed_idx]
    Vp = V[fixed_idx]
    rhs = I[free_idx] - Gfp @ Vp
    Vf = spsolve(Gff, rhs)
    V[free_idx] = Vf

    vmin = float(V.min())
    imin = int(V.argmin())
    return {
        "V": V,
        "worst_voltage": vmin,
        "worst_ir": vdd - vmin,
        "worst_ir_pct": 100.0 * (vdd - vmin) / vdd,
        "worst_node": order[imin],
        "total_current_a": float(sum(currents.values())),
        "nodes": n,
        "resistors": int(G.nnz // 2),
        "loads": len(currents),
        "sources": len(voltages),
        "solver": "spsolve",
    }


def solve_transient(G, idx, order, currents, voltages, vdd, pkg_r, pkg_l, c_decap, peak_factor, t_end, dt):
    n = G.shape[0]
    bump = [idx[nm] for nm in voltages if nm in idx]
    # Memoryless L/Δt (no i_L). Gold dynamic_ir uses the BE companion in pdn_dynamic.py.
    r_series = max(pkg_r + (pkg_l / dt if pkg_l > 0 else 0.0), 1e-9)
    g_pad = 1.0 / r_series
    Gsoft = G.tolil()
    for i in bump:
        Gsoft[i, i] += g_pad
    Gsoft = Gsoft.tocsr()

    C = np.full(n, max(c_decap * 0.02, 1e-18))
    I_avg = np.zeros(n)
    for nm, cur in currents.items():
        if nm in idx:
            C[idx[nm]] = c_decap
            I_avg[idx[nm]] = cur

    steps = max(2, int(np.ceil(t_end / dt)))
    V = np.full(n, vdd)
    t_peak = 0.2 * t_end
    wave_t, wave_vmin = [], []
    worst_v, worst_t, worst_node = vdd, 0.0, None

    ones_pad = np.zeros(n)
    for i in bump:
        ones_pad[i] = g_pad * vdd

    for s in range(steps):
        t = s * dt
        scale = peak_factor if t <= t_peak else 1.0
        I_draw = I_avg * scale
        A = (Gsoft + sparse.diags(C / dt)).tocsc()
        rhs = (C / dt) * V - I_draw + ones_pad
        V = spsolve(A, rhs)
        vmin = float(np.min(V))
        wave_t.append(float(t))
        wave_vmin.append(vmin)
        if vmin < worst_v:
            worst_v = vmin
            worst_t = float(t)
            worst_node = order[int(np.argmin(V))]

    return {
        "worst_voltage": worst_v,
        "worst_droop": vdd - worst_v,
        "worst_droop_pct": 100.0 * (vdd - worst_v) / vdd,
        "worst_time_s": worst_t,
        "worst_node": worst_node,
        "peak_factor": peak_factor,
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "c_decap": c_decap,
        "dt": dt,
        "t_end": t_end,
        "steps": steps,
        "wave_t": wave_t,
        "wave_vmin": wave_vmin,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spice", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wave", default="")
    ap.add_argument("--vdd", type=float, default=0.0)
    ap.add_argument("--pkg-r", type=float, default=0.05)
    ap.add_argument("--pkg-l", type=float, default=2e-10)
    ap.add_argument("--c-decap", type=float, default=50e-15)
    ap.add_argument("--peak-factor", type=float, default=8.0)
    ap.add_argument("--t-end", type=float, default=1e-9)
    ap.add_argument("--dt", type=float, default=5e-11)
    ap.add_argument("--mode", default="BUMPS")
    args = ap.parse_args()

    resistors, currents, voltages = parse_spice(Path(args.spice))
    order, idx, G = build_system(resistors, currents, voltages)
    vdd = args.vdd or next(iter(voltages.values()))

    static = solve_static(G, idx, order, currents, voltages, vdd)
    # drop huge V array from JSON
    V = static.pop("V")

    dyn = solve_transient(
        G,
        idx,
        order,
        currents,
        voltages,
        vdd,
        args.pkg_r,
        args.pkg_l,
        args.c_decap,
        args.peak_factor,
        args.t_end,
        args.dt,
    )

    report = {
        "engine": "studio-pdn-transient",
        "prior_art": [
            "OpenROAD PDNSim / write_pg_spice (static mesh)",
            "VoltSpot-style transient PDN",
            "vyges-em-ir backward-Euler dynamic IR",
        ],
        "mode": args.mode,
        "spice": args.spice,
        "vdd": vdd,
        "static": static,
        "transient": {k: v for k, v in dyn.items() if k not in ("wave_t", "wave_vmin")},
        "summary": (
            f"static IR {static['worst_ir']*1e3:.3f} mV ({static['worst_ir_pct']:.3f}%) · "
            f"transient droop {dyn['worst_droop']*1e3:.3f} mV ({dyn['worst_droop_pct']:.3f}%) "
            f"@ t={dyn['worst_time_s']*1e9:.2f} ns · peak×{args.peak_factor} · "
            f"pkg R={args.pkg_r}Ω L={args.pkg_l}H"
        ),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    wave = Path(args.wave) if args.wave else out.with_suffix(".wave.csv")
    with wave.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "v_min"])
        for t, v in zip(dyn["wave_t"], dyn["wave_vmin"]):
            w.writerow([f"{t:.6e}", f"{v:.9f}"])

    print("PDN_TRANSIENT_DONE")
    print(report["summary"])
    print(f"report → {out}")
    print(f"wave → {wave}")
    # sanity: static IR should be << Vdd on GCD
    if static["worst_ir"] > 0.2 * vdd:
        print(
            f"[warn] static IR {static['worst_ir']:.3f}V sospetto vs OpenROAD (~mV)",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    # ensure child processes inherit apt scipy path
    os.environ.setdefault("PYTHONPATH", "/usr/lib/python3/dist-packages")
    sys.exit(main())
