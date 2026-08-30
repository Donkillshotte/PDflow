#!/usr/bin/env python3
"""DSE F4 worker: Solver A on a write_pg_spice extract. Run with system SciPy.

PYTHONPATH=/usr/lib/python3/dist-packages:...  (see dse.f4_oracle)
Never writes dynamic_ir_*.json.

Default paths are the FlowLab finish extract (gold teacher). Pass --spice /
--insts for a *candidate* mesh. --no-sta skips finish arrivals (instance
names on a flattened F1 netlist do not join).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pdn_activity import load_insts, load_sta_arrivals, node_xy, plan_events, t50_via_counts  # noqa: E402
from pdn_dynamic import _map_worst_node, assemble_be, contributors_at, timestep_be  # noqa: E402
from pdn_em import em_thermal_snapshot  # noqa: E402
from pdn_extract import extract_pdn  # noqa: E402
from pdn_solvers import RationalKrylov, make_solver, mor_starts  # noqa: E402
from pdn_transient import build_system, solve_static  # noqa: E402

ORFS = _REPO / "tools/OpenROAD-flow-scripts/flow"
GOLD_MV = 45.298


def _paths(variant: str) -> dict[str, Path]:
    res = ORFS / "results" / "nangate45" / "gcd" / variant
    plat = ORFS / "platforms" / "nangate45"
    return {
        "spice": res / "pdn" / "pg_vdd_bumps.sp",
        "insts": res / "pdn" / "inst_power_map.json",
        "sta": _REPO / "learn" / "sim" / "reports" / f"sta_arrivals_{variant}.json",
        "lef": plat / "lef" / "NangateOpenCellLibrary.tech.lef",
        "spef": res / "6_final.spef",
    }


def _em_compact(em: dict) -> dict:
    return {
        "status": em.get("status"),
        "j_absmax_a_m2": em.get("j_absmax_a_m2"),
        "ttf_rel_min": em.get("ttf_rel_min"),
        "n_with_j": em.get("n_with_j"),
        "dT_mesh_absmax_k": em.get("dT_mesh_absmax_k"),
        "i_absmax_a": em.get("i_absmax_a"),
        "via": "pdn_em.em_thermal_snapshot on V_worst — not foundry TTF, not gold",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument("--pkg-r", type=float, default=0.05)
    ap.add_argument("--pkg-l", type=float, default=2e-10)
    ap.add_argument("--c-decap", type=float, default=50e-15)
    ap.add_argument("--i-scale", type=float, default=1.0)
    ap.add_argument("--dt-ps", type=float, default=10.0)
    ap.add_argument(
        "--period-ns",
        type=float,
        default=0.46,
        help="Clock period for I(t) triangles. aes is 0.82; never silently reuse GCD 0.46.",
    )
    ap.add_argument("--spice", type=Path, default=None)
    ap.add_argument("--insts", type=Path, default=None)
    ap.add_argument("--sta", type=Path, default=None)
    ap.add_argument("--spef", type=Path, default=None)
    ap.add_argument("--no-sta", action="store_true")
    ap.add_argument("--no-spef", action="store_true")
    ap.add_argument(
        "--extract-kind",
        default="finish",
        choices=("finish", "candidate"),
        help="finish = gold teacher mesh; candidate = DSE write_pg_spice",
    )
    ap.add_argument(
        "--solver",
        default="direct",
        choices=("direct", "amg", "bicg", "ras", "krylov", "mor"),
        help="PDN timestep: DirectLU (gold teacher), AMG, RAS, or rational Krylov/MOR. Not ABC.",
    )
    args = ap.parse_args()
    t0 = time.time()
    defaults = _paths(args.variant)
    spice = Path(args.spice) if args.spice else defaults["spice"]
    insts_p = Path(args.insts) if args.insts else defaults["insts"]
    kind = str(args.extract_kind)
    if args.spice is not None or args.insts is not None:
        kind = "candidate"
    sta_p = None if args.no_sta else (Path(args.sta) if args.sta else (None if kind == "candidate" else defaults["sta"]))
    spef_p = None if args.no_spef or kind == "candidate" else (Path(args.spef) if args.spef else defaults["spef"])
    if not spice.is_file() or not insts_p.is_file():
        print(json.dumps({"status": "GAP", "reason": "extract missing", "gold": False, "extract": kind}))
        return 0
    if kind == "finish" and sta_p is not None and not sta_p.is_file():
        print(json.dumps({"status": "GAP", "reason": "cached extract missing", "gold": False, "extract": kind}))
        return 0
    ext = extract_pdn(
        spice,
        lef=defaults["lef"] if defaults["lef"].is_file() else None,
        spef=spef_p if spef_p is not None and spef_p.is_file() else None,
    )
    order, idx, G = build_system(ext["resistors"], ext["currents"], ext["voltages"])
    insts = load_insts(insts_p)
    sta = load_sta_arrivals(sta_p) if sta_p is not None and sta_p.is_file() else {}
    events = plan_events(
        ext["currents"],
        idx,
        insts,
        mode="clock",
        peak_factor=8.0,
        leak_frac=0.2,
        period_s=float(args.period_ns) * 1e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        sta_arrivals=sta or None,
        vcd=None,
        saif=None,
    )
    scale = float(args.i_scale)
    if abs(scale - 1.0) > 1e-15:
        scaled = []
        for e in events:
            ev = dict(e)
            for k in ("i_pulse", "i_leak", "i_peak", "i_avg"):
                if k in ev and ev[k] is not None:
                    ev[k] = float(ev[k]) * scale
            scaled.append(ev)
        events = scaled
    vdd = float(next(iter(ext["voltages"].values())))
    dt = float(args.dt_ps) * 1e-12
    period_s = float(args.period_ns) * 1e-9
    t_end = max(period_s * 1.6, 0.12e-9 + 0.08e-9 * 3)
    sys_be = assemble_be(
        G,
        idx,
        ext["voltages"],
        vdd,
        events,
        pkg_r=float(args.pkg_r),
        pkg_l=float(args.pkg_l),
        c_decap=float(args.c_decap),
        dt=dt,
        spef_c=(ext.get("spef") or {}).get("node_c"),
    )
    solver_kind = "krylov" if args.solver in ("krylov", "mor") else args.solver
    mor_m = None
    if solver_kind == "krylov":
        import numpy as np

        starts = mor_starts(int(sys_be["n"]), events)
        shifts = np.array([0.0, 1e9, 1.0 / dt], dtype=np.float64)
        mor = RationalKrylov(sys_be["G"], sys_be["C"], starts, shifts, n_moments=4, sys=sys_be)
        dyn = mor.timestep(sys_be, events, vdd, t_end)
        dyn = _map_worst_node(dyn, order)
        dyn.setdefault("solver", getattr(mor, "name", "C_rational_krylov_mor"))
        dyn.setdefault("backend", getattr(mor, "backend", None))
        dyn.setdefault("timestep_loop", "mor")
        mor_m = getattr(mor, "m", dyn.get("m"))
    else:
        solver = make_solver(sys_be["A"], solver_kind)
        dyn = timestep_be(sys_be, events, solver, vdd, order, t_end)
    droop = float(dyn["worst_droop"])
    static_ir_mv = None
    static_ir_pct = None
    static_ir_pkg_mv = None
    static_node = None
    try:
        currents = ext["currents"]
        if abs(scale - 1.0) > 1e-15:
            currents = {k: float(v) * scale for k, v in currents.items()}
        st = solve_static(G, idx, order, currents, ext["voltages"], vdd)
        static_ir_mv = float(st["worst_ir"]) * 1e3
        static_ir_pct = float(st.get("worst_ir_pct") or 0.0)
        static_node = st.get("worst_node")
        try:
            st_pkg = solve_static(
                G, idx, order, currents, ext["voltages"], vdd, pkg_r=float(args.pkg_r)
            )
            static_ir_pkg_mv = float(st_pkg["worst_ir"]) * 1e3
        except (Exception, SystemExit):  # noqa: BLE001
            static_ir_pkg_mv = None
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — dynamic oracle must still report
        static_node = str(exc)[:160]
    node = dyn.get("worst_node")
    xy = node_xy(node) if node else None
    contrib = contributors_at(events, float(dyn.get("worst_time_s") or 0.0))
    em = {}
    vw = dyn.get("V_worst")
    if vw is not None:
        try:
            raw = em_thermal_snapshot(
                ext["resistors"],
                idx,
                order,
                vw,
                bump=sys_be.get("bump"),
                bump_v=sys_be.get("bump_v"),
                i_L=dyn.get("i_L_worst"),
                pkg_r=float(args.pkg_r),
                pkg_l=float(args.pkg_l),
                tech=ext.get("tech"),
                currents=ext.get("currents"),
                vdd=vdd,
                f_hz=1.0 / period_s,
            )
            raw.pop("_scaled_resistors", None)
            raw.pop("branches", None)
            raw.pop("hottest_j", None)
            raw.pop("hottest_i", None)
            em = _em_compact(raw)
        except Exception as exc:  # noqa: BLE001 — IR must still report
            em = {"status": "GAP", "reason": str(exc)[:200], "via": "em_thermal_snapshot"}
    if solver_kind == "krylov":
        via = (
            "rational Krylov/MOR on candidate write_pg_spice — reduced-order residual, not gold"
            if kind == "candidate"
            else "rational Krylov/MOR on cached write_pg_spice extract — reduced-order residual, not gold"
        )
    else:
        via = (
            "Solver A on candidate write_pg_spice (place_pins+GPL+DP+pdngen) — not finish, not gold"
            if kind == "candidate"
            else "Solver A worker on cached write_pg_spice extract — not finish, not gold"
        )
    note = (
        "candidate PDN R-graph after legalized place; do not replace gold "
        f"{GOLD_MV:.3f} mV"
        if kind == "candidate"
        else (
            "same PDN extract as the GCD gold run; "
            "I(t) scale is F3 power ratio (spatial pattern unchanged); "
            f"do not replace gold {GOLD_MV:.3f} mV"
        )
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "worst_droop_mv": droop * 1e3,
                "worst_droop_pct": float(dyn.get("worst_droop_pct") or 0.0),
                "static_ir_mv": static_ir_mv,
                "static_ir_pct": static_ir_pct,
                "static_ir_pkg_mv": static_ir_pkg_mv,
                "static_node": static_node,
                "worst_time_ns": float(dyn.get("worst_time_s") or 0.0) * 1e9,
                "worst_node": node,
                "x_dbu": xy[0] if xy else None,
                "y_dbu": xy[1] if xy else None,
                "seq_frac": contrib.get("seq_frac"),
                "combo_frac": contrib.get("combo_frac"),
                "pkg_r": float(args.pkg_r),
                "pkg_l": float(args.pkg_l),
                "c_decap": float(args.c_decap),
                "i_scale": scale,
                "n_r": ext.get("n_r"),
                "n_i": ext.get("n_i"),
                "n_events": len(events),
                "n_sta_applied": t50_via_counts(events).get("sta_arrival", 0),
                "t50_via": t50_via_counts(events),
                "solver": dyn.get("solver") or solver_kind,
                "solver_kind": solver_kind,
                "m": mor_m,
                "backend": dyn.get("backend"),
                "timestep_loop": dyn.get("timestep_loop"),
                "gold": False,
                "gold_ref_mv": GOLD_MV,
                "delta_vs_gold_mv": droop * 1e3 - GOLD_MV,
                "extract": kind,
                "em": em,
                "via": via,
                "spice": str(spice),
                "insts": str(insts_p),
                "cost_s": time.time() - t0,
                "note": note,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
