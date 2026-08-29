"""Independently replaceable DSE / PI adapters.

The controller imports these stages by name. Swapping an adapter must not
require flattening knobs or treating a surrogate as physical truth.
"""

from __future__ import annotations

ADAPTERS: dict[str, dict] = {
    "extraction": {
        "via": "ingest",
        "note": "PDN extract lives in learn/scripts/pdn_extract.py — DSE does not re-extract",
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
        "via": "ingest",
        "note": "CCS/ECSM GAP on Nangate45; triangle I(t) stays Solver A",
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
        "via": "ingest F4",
        "note": "libdpn A/B/C/D; GCD gold 45.298 mV unrestamped",
    },
    "physical_fast": {
        "via": "dse.netgraph",
        "note": "anchored barycenter + HPWL + RUDY on the candidate netlist",
    },
    "physical_gpl": {
        "via": "dse.openroad_f2",
        "note": "OpenROAD global_placement -skip_io; not route/finish/F5",
    },
}


def adapter_status() -> dict:
    from .openroad_f2 import available as gpl_ok

    out = {k: dict(v) for k, v in ADAPTERS.items()}
    out["physical_gpl"]["ready"] = bool(gpl_ok())
    return out
