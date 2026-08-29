"""Independently replaceable DSE / PI adapters.

The controller imports these stages by name. Swapping an adapter must not
require flattening knobs or treating a surrogate as physical truth.
"""

from __future__ import annotations

ADAPTERS: dict[str, dict] = {
    "extraction": {
        "via": "openroad write_pg_spice after place_pins+GPL+DP+pdngen, or ingest finish",
        "note": "candidate mesh is not gold; finish gold 45.298 mV stays unrestamped",
    },
    "power": {
        "via": "ingest",
        "note": "ORFS finish power / STA power reports",
    },
    "activity": {
        "via": "ingest",
        "note": "STA/VCD/SAIF via PI reports; no invented RTL→ITerm map",
    },
    "current": {
        "via": "ingest + F3 power scale",
        "note": "triangle I(t) on named extract; amplitude × P_F3/P_base — no invented RTL→ITerm map",
    },
    "dse": {
        "via": "dse.controller",
        "note": "budget-aware inspect→transform→fidelity→attribute loop",
    },
    "surrogate": {
        "via": "dse.surrogate + dse.gnn",
        "note": "SSK-GP / residual / GNN readout — never Dynamic IR gold",
    },
    "solver": {
        "via": "ingest F4 + budgeted Solver A restamp",
        "note": "libdpn A on named extract; GCD gold 45.298 mV unrestamped",
    },
    "physical_fast": {
        "via": "dse.netgraph",
        "note": "anchored barycenter + HPWL + RUDY on the candidate netlist",
    },
    "physical_gpl": {
        "via": "dse.openroad_f2.evaluate_gpl",
        "note": "OpenROAD global_placement -skip_io; AutoDMP catalog util/density is measured here, not as F0 truth",
    },
    "routing": {
        "via": "dse.openroad_f2.evaluate_grt",
        "note": "place_pins + GPL + global_route; not detailed route/F5",
    },
    "timing": {
        "via": "dse.sta_f3",
        "note": "OpenSTA ideal WNS/power on the candidate; SPEF optional",
    },
}


def adapter_status() -> dict:
    from .f4_oracle import available as f4_ok
    from .openroad_f2 import available as gpl_ok, extract_available
    from .sta_f3 import available as sta_ok

    out = {k: dict(v) for k, v in ADAPTERS.items()}
    out["physical_gpl"]["ready"] = bool(gpl_ok())
    out["routing"]["ready"] = bool(gpl_ok())
    out["timing"]["ready"] = bool(sta_ok())
    out["solver"]["ready"] = bool(f4_ok())
    out["current"]["ready"] = bool(f4_ok())
    out["extraction"]["ready"] = bool(extract_available() or f4_ok())
    return out
