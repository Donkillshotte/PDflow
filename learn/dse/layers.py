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
            "attributed host; first shot on unconstrained host mesh, then "
            "winning host PDN after host IR-steer, then winning_ir_pdn "
            "(IR-cell-region-PDN) with extract STA — no invented RTL→ITerm map"
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
        "via": "dse.active.steer_from_residual + steer_from_port_residual + steer_from_ir_residual + steer_from_host_ir_residual + steer_from_winning_ir_catalog + iscale_host + order_local_hosts",
        "note": "F3→F5 residual picks cell|net|f5_local; F5-port residual steers SPEF hops; F4 I-scale picks the attributed host; F4 IR residual loops region-decap then unused pkg L; F4 host-region residual loops host-region-decap then unused host pkg L; unused Dynamic IR catalog on a strap/EM winning_ir extract (inherit pkg_r; C then L); I-scale-champ measures activity on winning_ir_pdn (not host-win); combo-heavy champ hotspot ODB-joins cells and re-pays size-up/extract/PDN when that extract moves; leftover cells on the champ extract (minus champ size-up) pay a cone size-up/extract/PDN residual vs the champ extract; a seq-heavy leftover-cone 1× bin ≠ champ extract pays a density cap (not more combo size-up) then |Δ| PDN, and re-pays when the residual hotspot leaves the capped bin (inspect loop); a seq-heavy winning-IR 1× bin ≠ leftover-cone / IR-cell-region pays a density cap on the IR-cell netlist then |Δ| PDN, and re-pays when the residual hotspot leaves the capped bin (inspect loop; not IR-cell-region rXY); leftover combo cells on that region PDN join (minus IR-cell / champ / leftover-cone) pay a size-up/extract/PDN residual vs the winning-IR-region extract (not leftover-cone flatten); AMG/RAS/Krylov-champ restamp that same 1× mesh; static IR is a separate 1× ranking that pays unused pkg_r then, on a null on-die residual, denser bumps then metal4 straps on the champ ODB (decap does not move DC); EM width residual is same-mesh vs strap J; not a mixed knob vector",
    },
    "synthesis": {
        "via": "dse.synthesis + dse.fidelity.evaluate_f1_synth",
        "note": "ORFS abc_speed.script (ABC_AREA=0) at F1; abc_area stays F0-only; not abc_ops",
    },
    "cell": {
        "via": "dse.cell_space.upsize_path_cells + dse.fidelity.evaluate_cell_size",
        "note": "attributed STA path drive-up (module-scoped), I-scale-win IR-hotspot ODB-join, I-scale-champ ODB-join + write_pg_spice residual vs IR-cell extract (re-paid per winning_ir extract), leftover champ-extract cone size-up + write_pg_spice residual vs IR-cell-champ extract, seq-heavy leftover-cone region density cap (not more combo size-up), seq-heavy winning-IR 1× rXY density cap on the IR-cell netlist (not leftover-cone rXY; re-paid when the residual hotspot leaves the capped bin, not IR-cell-region rXY), and leftover combo cells on the winning-IR-region PDN join (minus IR-cell / champ / leftover-cone) on the IR-cell netlist; not ABC ops, not a chip restart",
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
        "note": "DirectLU restamp on named extract; AMG, RAS, and rational Krylov/MOR are MF residuals on the candidate mesh and again on winning_ir_pdn (same DirectLU knobs; re-paid when the 1× extract moves to a new strap R-graph); unused Dynamic IR catalog (decap then pkg L, inherit host pkg_r) restamps that R-graph; static IR searches pkg_r then on-die bump pitch then metal4 straps; EM searches unused metal4 width on that pitch with a same-mesh strap-J residual (not flattened); GCD gold 45.298 mV unrestamped",
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
