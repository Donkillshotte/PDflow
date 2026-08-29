#!/usr/bin/env python3
"""DSE F4 worker: Solver A on the cached extract. Run with system SciPy.

PYTHONPATH=/usr/lib/python3/dist-packages:...  (see dse.f4_oracle)
Never writes dynamic_ir_*.json.
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

from pdn_activity import load_insts, load_sta_arrivals, node_xy, plan_events  # noqa: E402
from pdn_dynamic import assemble_be, contributors_at, timestep_be  # noqa: E402
from pdn_extract import extract_pdn  # noqa: E402
from pdn_solvers import DirectLU  # noqa: E402
from pdn_transient import build_system  # noqa: E402

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument("--pkg-r", type=float, default=0.05)
    ap.add_argument("--pkg-l", type=float, default=2e-10)
    ap.add_argument("--c-decap", type=float, default=50e-15)
    ap.add_argument("--i-scale", type=float, default=1.0)
    ap.add_argument("--dt-ps", type=float, default=10.0)
    args = ap.parse_args()
    t0 = time.time()
    p = _paths(args.variant)
    if not p["spice"].is_file() or not p["insts"].is_file() or not p["sta"].is_file():
        print(json.dumps({"status": "GAP", "reason": "cached extract missing", "gold": False}))
        return 0
    ext = extract_pdn(
        p["spice"],
        lef=p["lef"] if p["lef"].is_file() else None,
        spef=p["spef"] if p["spef"].is_file() else None,
    )
    order, idx, G = build_system(ext["resistors"], ext["currents"], ext["voltages"])
    insts = load_insts(p["insts"])
    sta = load_sta_arrivals(p["sta"])
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
    t_end = max(0.46e-9 * 1.6, 0.12e-9 + 0.08e-9 * 3)
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
    dyn = timestep_be(sys_be, events, DirectLU(sys_be["A"]), vdd, order, t_end)
    droop = float(dyn["worst_droop"])
    node = dyn.get("worst_node")
    xy = node_xy(node) if node else None
    contrib = contributors_at(events, float(dyn.get("worst_time_s") or 0.0))
    print(
        json.dumps(
            {
                "status": "ok",
                "worst_droop_mv": droop * 1e3,
                "worst_droop_pct": float(dyn.get("worst_droop_pct") or 0.0),
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
                "n_events": len(events),
                "solver": dyn.get("solver"),
                "backend": dyn.get("backend"),
                "timestep_loop": dyn.get("timestep_loop"),
                "gold": False,
                "gold_ref_mv": GOLD_MV,
                "delta_vs_gold_mv": droop * 1e3 - GOLD_MV,
                "via": "Solver A worker on cached write_pg_spice extract — not finish, not gold",
                "spice": str(p["spice"]),
                "cost_s": time.time() - t0,
                "note": (
                    "same PDN extract as the GCD gold run; "
                    "I(t) scale is F3 power ratio (spatial pattern unchanged); "
                    f"do not replace gold {GOLD_MV:.3f} mV"
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
