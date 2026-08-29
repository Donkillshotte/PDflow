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
        "via": "dse.sta_f3.export_arrivals + ingest",
        "note": "OpenSTA report_arrival on the candidate (t50 teacher); no invented RTL→ITerm map",
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
    "synthesis": {
        "via": "dse.synthesis + dse.fidelity.evaluate_f1_synth",
        "note": "ORFS abc_speed.script (ABC_AREA=0) at F1; abc_area stays F0-only; not abc_ops",
    },
    "solver": {
        "via": "dse.f4_oracle + dse_f4_worker.make_solver (direct|amg|bicg|ras)",
        "note": "DirectLU restamp on named extract; AMG and RAS are MF residuals; GCD gold 45.298 mV unrestamped",
    },
    "physical_fast": {
        "via": "dse.netgraph",
        "note": "anchored barycenter + HPWL + RUDY on the candidate netlist",
    },
    "physical_gpl": {
        "via": "dse.openroad_f2.evaluate_gpl",
        "note": "OpenROAD GPL -skip_io; AutoDMP catalog and IR-bin create_blockage -max_density are measured here, not as F0 truth",
    },
    "routing": {
        "via": "dse.openroad_f2.evaluate_grt + evaluate_f5_drt",
        "note": "GRT + F5-lite DRT/OpenRCX SPEF; not make finish, clock ideal",
    },
    "timing": {
        "via": "dse.sta_f3",
        "note": "OpenSTA ideal / GRT SDF / OpenRCX SPEF WNS/power; not finish launch",
    },
}


def adapter_status() -> dict:
    from .f4_oracle import available as f4_ok
    from .openroad_f2 import available as gpl_ok, extract_available, f5_available
    from .sta_f3 import available as sta_ok
    from .synthesis import available as synth_ok

    out = {k: dict(v) for k, v in ADAPTERS.items()}
    out["physical_gpl"]["ready"] = bool(gpl_ok())
    out["routing"]["ready"] = bool(gpl_ok() or f5_available())
    out["timing"]["ready"] = bool(sta_ok())
    out["activity"]["ready"] = bool(sta_ok())
    out["solver"]["ready"] = bool(f4_ok())
    out["current"]["ready"] = bool(f4_ok())
    out["extraction"]["ready"] = bool(extract_available() or f4_ok())
    out["synthesis"]["ready"] = bool(synth_ok())
    return out
