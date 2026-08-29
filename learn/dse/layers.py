"""Independently replaceable DSE / PI adapters.

The controller imports these stages by name. Swapping an adapter must not
require flattening knobs or treating a surrogate as physical truth.
"""

from __future__ import annotations

ADAPTERS: dict[str, dict] = {
    "extraction": {
        "via": "openroad write_pg_spice after place_pins+GPL+DP+pdngen, or ingest finish",
        "note": (
            "candidate mesh is not gold; host extract is the attributed netlist "
            "(not synth-only); host-region density-caps the host IR bin "
            "(not gold rXY on synth); finish gold 45.298 mV stays unrestamped"
        ),
    },
    "power": {
        "via": "ingest",
        "note": "ORFS finish power / STA power reports",
    },
    "activity": {
        "via": "dse.sta_f3.export_arrivals + ingest",
        "note": (
            "OpenSTA report_arrival on the attributed host (port-steer/port-net/…) "
            "as t50 teacher; name-join onto the named extract — no invented RTL→ITerm map"
        ),
    },
    "current": {
        "via": "ingest + F3 power scale",
        "note": (
            "triangle I(t) on named extract; amplitude × P_F3/P_base of the "
            "attributed host; t50 from host report_arrival when paid — "
            "no invented RTL→ITerm map"
        ),
    },
    "dse": {
        "via": "dse.controller",
        "note": "budget-aware inspect→transform→fidelity→attribute loop; ctrl is a first-class cone, not leftover of dpath",
    },
    "surrogate": {
        "via": "dse.surrogate + dse.gnn + dse.active",
        "note": "SSK-GP / F1→F2 residual / F3→F5-lite+local residual steers the next level / F4 IR residual steers PDN / F4 host-region residual vs unconstrained host / GNN readout — never Dynamic IR gold",
    },
    "active": {
        "via": "dse.active.steer_from_residual + steer_from_port_residual + steer_from_ir_residual + iscale_host + order_local_hosts",
        "note": "F3→F5 residual picks cell|net|f5_local; F5-port residual steers SPEF hops; F4 I-scale picks the attributed host; F4 IR residual loops region-decap then unused pkg L; not a mixed knob vector",
    },
    "synthesis": {
        "via": "dse.synthesis + dse.fidelity.evaluate_f1_synth",
        "note": "ORFS abc_speed.script (ABC_AREA=0) at F1; abc_area stays F0-only; not abc_ops",
    },
    "cell": {
        "via": "dse.cell_space.upsize_path_cells + dse.fidelity.evaluate_cell_size",
        "note": "attributed STA path drive-up (module-scoped); not ABC ops, not a chip restart",
    },
    "net": {
        "via": "dse.net_space.buffer_path_nets + buffer_port_nets + dse.fidelity.evaluate_net_buffer",
        "note": (
            "attributed STA path BUF insert (module-scoped) and parent-scoped "
            "port-net BUF on ctrl↔dpath hops (including bus bits like a_mux_sel[0]); "
            "F5-port residual may BUF SPEF intra hops; not ABC, not a cell drive-up"
        ),
    },
    "solver": {
        "via": "dse.f4_oracle + dse_f4_worker (direct|amg|bicg|ras|krylov/MOR)",
        "note": "DirectLU restamp on named extract; AMG, RAS, and rational Krylov/MOR are MF residuals; GCD gold 45.298 mV unrestamped",
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
        "via": "dse.openroad_f2.evaluate_grt + evaluate_f5_drt + evaluate_f5_cts + evaluate_f5_local",
        "note": "GRT + F5-lite + F5-CTS + F5-local SPEF on cell/net + F5-port SPEF on port-net; not make finish",
    },
    "timing": {
        "via": "dse.sta_f3",
        "note": "OpenSTA ideal / GRT SDF / OpenRCX SPEF / CTS SPEF with set_propagated_clock; not finish launch",
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
    out["cell"]["ready"] = bool(sta_ok())
    out["net"]["ready"] = bool(sta_ok())
    out["active"]["ready"] = True
    return out
