"""Budgeted Dynamic IR restamp. Solver A on the cached GCD extract.

Same write_pg_spice mesh as the gold run. We may change PDN knobs
(c_decap, pkg L) or scale triangle I(t) by an F3 power ratio.

This is a *candidate* F4 observation:
  — not a new PDN extract / finish
  — not an invented RTL VCD → ITerm map
  — never written over dynamic_ir_*.json gold (45.298 mV unrestamped)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
SCRIPTS = REPO / "learn" / "scripts"
ORFS = REPO / "tools/OpenROAD-flow-scripts/flow"
GOLD_MV = 45.298

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

_MESH: dict | None = None


def spice_paths(variant: str = "flowlab") -> dict[str, Path]:
    res = ORFS / "results" / "nangate45" / "gcd" / variant
    plat = ORFS / "platforms" / "nangate45"
    return {
        "spice": res / "pdn" / "pg_vdd_bumps.sp",
        "insts": res / "pdn" / "inst_power_map.json",
        "sta": REPO / "learn" / "sim" / "reports" / f"sta_arrivals_{variant}.json",
        "lef": plat / "lef" / "NangateOpenCellLibrary.tech.lef",
        "spef": res / "6_final.spef",
    }


def available(variant: str = "flowlab") -> bool:
    p = spice_paths(variant)
    return p["spice"].is_file() and p["insts"].is_file() and p["sta"].is_file()


def _load_mesh(variant: str = "flowlab") -> dict:
    global _MESH
    if _MESH and _MESH.get("variant") == variant:
        return _MESH
    from pdn_activity import load_insts, load_sta_arrivals, plan_events
    from pdn_extract import extract_pdn
    from pdn_transient import build_system

    p = spice_paths(variant)
    if not p["spice"].is_file():
        raise FileNotFoundError(p["spice"])
    ext = extract_pdn(
        p["spice"],
        lef=p["lef"] if p["lef"].is_file() else None,
        spef=p["spef"] if p["spef"].is_file() else None,
    )
    order, idx, G = build_system(ext["resistors"], ext["currents"], ext["voltages"])
    insts = load_insts(p["insts"]) if p["insts"].is_file() else []
    sta = load_sta_arrivals(p["sta"]) if p["sta"].is_file() else {}
    events = plan_events(
        ext["currents"],
        idx,
        insts,
        mode="clock",
        peak_factor=8.0,
        leak_frac=0.2,
        period_s=0.46e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        sta_arrivals=sta or None,
        vcd=None,
        saif=None,
    )
    vdd = next(iter(ext["voltages"].values()))
    _MESH = {
        "variant": variant,
        "G": G,
        "idx": idx,
        "order": order,
        "voltages": ext["voltages"],
        "events": events,
        "vdd": float(vdd),
        "spef_c": (ext.get("spef") or {}).get("node_c"),
        "n_r": ext.get("n_r"),
        "n_events": len(events),
        "spice": str(p["spice"]),
    }
    return _MESH


def _scale_events(events: list[dict], scale: float) -> list[dict]:
    if abs(float(scale) - 1.0) < 1e-15:
        return events
    out = []
    for e in events:
        ev = dict(e)
        for k in ("i_pulse", "i_leak", "i_peak", "i_avg"):
            if k in ev and ev[k] is not None:
                ev[k] = float(ev[k]) * float(scale)
        out.append(ev)
    return out


def solve_f4(
    *,
    variant: str = "flowlab",
    pkg_r: float = 0.05,
    pkg_l: float = 2e-10,
    c_decap: float = 50e-15,
    i_scale: float = 1.0,
    dt_ps: float = 10.0,
) -> dict:
    """Solver A only. Same extract; knobs/current scale may change. Not gold."""
    if not available(variant):
        return {
            "status": "GAP",
            "reason": "cached write_pg_spice / STA arrivals missing — not a new extract",
            "gold": False,
            "via": "f4_oracle",
        }
    from pdn_activity import node_xy
    from pdn_dynamic import assemble_be, contributors_at, timestep_be
    from pdn_solvers import DirectLU

    t0 = time.time()
    mesh = _load_mesh(variant)
    events = _scale_events(mesh["events"], i_scale)
    dt = float(dt_ps) * 1e-12
    period_s = 0.46e-9
    t50_s = 0.12e-9
    dur_s = 0.08e-9
    t_end = max(period_s * 1.6, t50_s + dur_s * 3)
    vdd = mesh["vdd"]
    sys = assemble_be(
        mesh["G"],
        mesh["idx"],
        mesh["voltages"],
        vdd,
        events,
        pkg_r=float(pkg_r),
        pkg_l=float(pkg_l),
        c_decap=float(c_decap),
        dt=dt,
        spef_c=mesh.get("spef_c"),
    )
    solver = DirectLU(sys["A"])
    dyn = timestep_be(sys, events, solver, vdd, mesh["order"], t_end)
    droop = float(dyn["worst_droop"])
    node = dyn.get("worst_node")
    xy = node_xy(node) if node else None
    contrib = contributors_at(events, float(dyn.get("worst_time_s") or 0.0))
    # Drop waveforms — DSE only needs the scalar + attribution hook.
    return {
        "status": "ok",
        "worst_droop_mv": droop * 1e3,
        "worst_droop_pct": float(dyn.get("worst_droop_pct") or 0.0),
        "worst_time_ns": float(dyn.get("worst_time_s") or 0.0) * 1e9,
        "worst_node": node,
        "x_dbu": xy[0] if xy else None,
        "y_dbu": xy[1] if xy else None,
        "seq_frac": contrib.get("seq_frac"),
        "combo_frac": contrib.get("combo_frac"),
        "pkg_r": float(pkg_r),
        "pkg_l": float(pkg_l),
        "c_decap": float(c_decap),
        "i_scale": float(i_scale),
        "n_r": mesh.get("n_r"),
        "n_events": mesh.get("n_events"),
        "solver": dyn.get("solver"),
        "backend": dyn.get("backend"),
        "timestep_loop": dyn.get("timestep_loop"),
        "gold": False,
        "gold_ref_mv": GOLD_MV,
        "delta_vs_gold_mv": droop * 1e3 - GOLD_MV,
        "via": "Solver A on cached write_pg_spice extract — not finish, not gold",
        "spice": mesh.get("spice"),
        "cost_s": time.time() - t0,
        "note": (
            "same PDN extract as the GCD gold run; "
            "I(t) scale is F3 power ratio (spatial pattern unchanged); "
            f"do not replace gold {GOLD_MV:.3f} mV"
        ),
    }
