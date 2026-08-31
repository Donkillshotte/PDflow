"""DSE planner contracts: attribution, plan_search, F1 winners.

Extracted from test_dse.py (passo D.3). test_dse.main() still calls this.
Same check() messages as the inlined block.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from dse.arch_space import (
    CTRL_CONE_MODULES,
    CTRL_MODULE,
    DPATH_CONE_MODULES,
    DPATH_MODULE,
    emit_gcd_variant,
    is_cone_abc,
    leftover_modules,
    stamp_cone_knobs,
)
from dse.attribute import attribute_dynamic_ir, local_scope
from dse.boils import propose_logic_boils
from dse.fingerprint import knobs_fp
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR


def check_planner(check, *, root: Path, mem, mem2) -> None:
    _ROOT = root
    rtl = _ROOT / "learn/flowlab/gcd.v"

    attr = attribute_dynamic_ir(
        {
            "hotspot": {
                "node": "ITermNode_metal1_1_2",
                "droop_mv": 45.298,
                "x_dbu": 70896.0,
                "y_dbu": 39429.0,
                "contributors": {"seq_frac": 0.02, "combo_frac": 0.98},
                "timing": {"path_slack_ns": 0.04},
            },
            "activity_model": {
                "sta": {
                    "worst_path": {
                        "startpoint": "dpath.a_reg.out[5]$_DFFE_PP_",
                        "endpoint": "dpath.a_reg.out[7]$_DFFE_PP_",
                        "slack_ns": 0.04353,
                    }
                }
            },
            "em": {"j_absmax_a_m2": 1e11, "dT_mesh_absmax_k": 0.66},
        }
    )
    check(attr["status"] == "READY", "IR attribution READY")
    check(attr["modules"] == ["dpath"], f"path start/end map to dpath, got {attr['modules']}")
    check(attr.get("join") == "sta-path", f"STA names win over empty insts, got {attr.get('join')}")
    check(attr.get("region") == "r31", f"hotspot bins to a region, got {attr.get('region')}")
    check(attr["scope"] == "logic_cone", "attributed scope is logic_cone, not chip restart")
    check(local_scope(attr)["restart_chip"] is False, "local scope refuses a chip restart")
    check(local_scope(attr)["focus"] == "dpath", "focus is the attributed module")
    check(local_scope(attr)["hierarchy"][-1] == "net", "hierarchy ends at the attributed net")
    check("cell" in local_scope(attr)["hierarchy"], "hierarchy still includes the cell")
    check("logic_cone" in local_scope(attr)["hierarchy"], "hierarchy still includes the cone")

    from dse.planner import plan_search, rank_extracts
    from dse.policy import ucb_next_op
    from dse.netgraph import estimate_physical, is_gate_cell_netlist, parse_mapped_verilog, strip_verilog_comments
    from dse.gnn import graph_embedding, predict_hpwl
    from dse.proposer import propose as dse_propose
    from dse.layers import adapter_status

    planned = plan_search(attr, mem2, f2_cong=0.0)
    check(planned["restart_chip"] is False, "planner refuses a chip restart")
    check(planned["focus"] == "dpath", "planner focus is dpath")
    check(
        any(s["level"] == "architecture" for s in planned["steps"]),
        "combo IR on dpath schedules architecture extracts",
    )
    check(
        planned["steps"][0].get("extracts", [None])[0] == "lt_borrow",
        "combo-heavy IR prefers lt_borrow first",
    )
    mem_w = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-wns-")) / "w.jsonl")
    mem_w.add(
        Candidate(
            id="base",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "liberty_default", "abc_ops": []},
            knobs_fp=knobs_fp("logic", {"name": "liberty_default", "abc_ops": []}),
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=409.1, wns_cost=0.52, fidelity="F1"),
            cost_s=1.0,
        )
    )
    mem_w.add(
        Candidate(
            id="lt1",
            design_id="gcd",
            parent_id=None,
            level="architecture",
            knobs={"name": "lt_borrow", "extract": "lt_borrow", "abc_script": "file"},
            knobs_fp=knobs_fp("architecture", {"name": "lt_borrow", "extract": "lt_borrow"}),
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=410.4, wns_cost=0.59, fidelity="F1"),
            cost_s=1.0,
        )
    )
    ranked = rank_extracts(
        ["lt_borrow", "sub_twos_complement", "eqz_or_reduce"],
        mem_w,
        combo=0.98,
    )
    check(ranked[0] == "sub_twos_complement", f"F3-worse lt_borrow is deprioritized, got {ranked}")
    check("lt_borrow" not in ranked, "already-measured extract is not proposed again")
    mem_w.add(
        Candidate(
            id="rb",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "boils_rewrite_balance", "abc_ops": ["rewrite", "balance"]},
            knobs_fp=knobs_fp("logic", {"name": "boils_rewrite_balance", "abc_ops": ["rewrite", "balance"]}),
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=483.3, wns_cost=0.55, fidelity="F1"),
            cost_s=1.0,
        )
    )
    mo_pick = propose_logic_boils(mem_w, focus="dpath")
    check(mo_pick is not None, "MO BOiLS still proposes after two timed sequences")
    check((mo_pick or {}).get("acq", {}).get("via") == "ssk_gp_ehvi", f"acquisition is EHVI, got {mo_pick}")
    check((mo_pick or {}).get("cone") == "dpath", "IR focus dpath stamps cone ABC knobs")
    check((mo_pick or {}).get("cone_module") == DPATH_MODULE, "cone ABC names the dpath Yosys module")
    check("coreUtilization" not in (mo_pick or {}), "EHVI proposal does not flatten physical knobs")
    chip_rb = {"name": "boils_rewrite_balance", "abc_ops": ["rewrite", "balance"], "abc_script": "file"}
    check(
        knobs_fp("logic", chip_rb) != knobs_fp("logic", stamp_cone_knobs(chip_rb, "dpath")),
        "cone rewrite+balance is not the chip flatten-first fingerprint",
    )
    check(
        knobs_fp("logic", stamp_cone_knobs(chip_rb, "ctrl"))
        != knobs_fp("logic", stamp_cone_knobs(chip_rb, "dpath")),
        "ctrl cone is not flattened into the dpath cone fingerprint",
    )
    check(stamp_cone_knobs(chip_rb, "ctrl")["cone"] == "ctrl", "stamp_cone_knobs(ctrl) names the FSM")
    check(stamp_cone_knobs(chip_rb, "ctrl")["cone_module"] == CTRL_MODULE, "ctrl cone names GcdUnitCtrlRTL")
    check(is_cone_abc(stamp_cone_knobs(chip_rb, "ctrl")), "ctrl knobs are cone ABC")
    check(not is_cone_abc(chip_rb), "unstamped chip knobs are not cone ABC")
    check(CTRL_MODULE in leftover_modules(DPATH_CONE_MODULES), "dpath cone leftover still includes ctrl")
    check(DPATH_MODULE in leftover_modules(CTRL_CONE_MODULES), "ctrl cone leftover is the dpath modules")
    check(CTRL_MODULE not in leftover_modules(CTRL_CONE_MODULES), "paid ctrl module is not leftover of itself")
    from dse.controller import f1_area_winner, f1_wns_winner

    check(f1_area_winner(mem_w).id == "base", "area winner is liberty_default")
    check(f1_wns_winner(mem_w).id == "base", "among these two, baseline also has the better WNS")
    mem_w.add(
        Candidate(
            id="fastish",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "boils_resyn2ish", "abc_ops": ["balance", "rewrite"]},
            knobs_fp=knobs_fp("logic", {"name": "boils_resyn2ish", "abc_ops": ["balance", "rewrite"]}),
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=460.4, wns_cost=0.11, fidelity="F1"),
            cost_s=1.0,
        )
    )
    check(f1_area_winner(mem_w).id == "base", "larger faster netlist does not steal the area crown")
    check(f1_wns_winner(mem_w).id == "fastish", "WNS winner is the delay-improved sequence")
    check(any(s["level"] == "f3_sta" for s in planned["steps"]), "planner schedules F3 STA")
    check(any(s["level"] == "f3_sdf" for s in planned["steps"]), "planner schedules F3 SDF-GRT")
    check(any(s["level"] == "f5_drt" for s in planned["steps"]), "planner schedules F5-lite DRT/OpenRCX")
    check(any(s["level"] == "f3_spef" for s in planned["steps"]), "planner schedules F3 SPEF")
    check(any(s["level"] == "f5_cts" for s in planned["steps"]), "planner schedules F5-CTS")
    check(any(s["level"] == "f5_local" for s in planned["steps"]), "planner schedules F5-local SPEF")
    check(any(s["level"] == "residual_steer" for s in planned["steps"]), "planner schedules residual-steered next level")
    check(any(s["level"] == "f5_port" for s in planned["steps"]), "planner schedules F5-port SPEF on the port-net host")
    check(any(s["level"] == "port_steer" for s in planned["steps"]), "planner schedules F5-port residual steer")
    check(any(s["level"] == "ir_steer" for s in planned["steps"]), "planner schedules F4 IR residual steer")
    check(any(s["level"] == "host_ir_steer" for s in planned["steps"]), "planner schedules host IR residual steer")
    check(any(s["level"] == "f4_scale_win" for s in planned["steps"]), "planner schedules winning-host I-scale")
    check(any(s["level"] == "ir_cell" for s in planned["steps"]), "planner schedules IR-hotspot cell size-up")
    check(any(s["level"] == "ir_cell_extract" for s in planned["steps"]), "planner schedules IR-cell write_pg_spice")
    check(any(s["level"] == "ir_cell_pdn" for s in planned["steps"]), "planner schedules IR-cell PDN restamp")
    check(any(s["level"] == "ir_cell_region" for s in planned["steps"]), "planner schedules IR-cell-region density cap")
    check(any(s["level"] == "ir_cell_region_pdn" for s in planned["steps"]), "planner schedules IR-cell-region PDN restamp")
    check(any(s["level"] == "winning_ir_pdn" for s in planned["steps"]), "planner schedules unused Dynamic IR on winning_ir extract")
    check(any(s["level"] == "f4_scale_champ" for s in planned["steps"]), "planner schedules champion I-scale")
    check(any(s["level"] == "ir_cell_champ" for s in planned["steps"]), "planner schedules I-scale-champ cell size-up")
    check(any(s["level"] == "ir_cell_champ_extract" for s in planned["steps"]), "planner schedules IR-cell-champ write_pg_spice")
    check(any(s["level"] == "ir_cell_champ_pdn" for s in planned["steps"]), "planner schedules IR-cell-champ PDN restamp")
    check(any(s["level"] == "ir_cell_champ_cone" for s in planned["steps"]), "planner schedules leftover-cone cell size-up")
    check(any(s["level"] == "ir_cell_champ_cone_extract" for s in planned["steps"]), "planner schedules leftover-cone write_pg_spice")
    check(any(s["level"] == "ir_cell_champ_cone_pdn" for s in planned["steps"]), "planner schedules leftover-cone PDN restamp")
    check(any(s["level"] == "ir_cell_champ_cone_region" for s in planned["steps"]), "planner schedules leftover-cone-region density cap")
    check(any(s["level"] == "ir_cell_champ_cone_region_pdn" for s in planned["steps"]), "planner schedules leftover-cone-region PDN restamp")
    check(any(s["level"] == "winning_ir_region" for s in planned["steps"]), "planner schedules winning-IR-region density cap")
    check(any(s["level"] == "winning_ir_region_pdn" for s in planned["steps"]), "planner schedules winning-IR-region PDN restamp")
    check(any(s["level"] == "winning_ir_region_cell" for s in planned["steps"]), "planner schedules winning-IR-region leftover-combo size-up")
    check(any(s["level"] == "winning_ir_region_cell_extract" for s in planned["steps"]), "planner schedules winning-IR-region-cell write_pg_spice")
    check(any(s["level"] == "winning_ir_region_cell_pdn" for s in planned["steps"]), "planner schedules winning-IR-region-cell PDN restamp")
    check(any(s["level"] == "winning_ir_region_cell_leftover" for s in planned["steps"]), "planner schedules leftover-combo leftover size-up")
    check(any(s["level"] == "winning_ir_region_cell_leftover_extract" for s in planned["steps"]), "planner schedules leftover leftover write_pg_spice")
    check(any(s["level"] == "winning_ir_region_cell_leftover_pdn" for s in planned["steps"]), "planner schedules leftover leftover PDN restamp")
    check(any(s["level"] == "winning_ir_region_cell_leftover2" for s in planned["steps"]), "planner schedules leftover leftover leftover size-up")
    check(any(s["level"] == "winning_ir_region_cell_leftover2_extract" for s in planned["steps"]), "planner schedules leftover leftover leftover write_pg_spice")
    check(any(s["level"] == "winning_ir_region_cell_leftover2_pdn" for s in planned["steps"]), "planner schedules leftover leftover leftover PDN restamp")
    check(any(s["level"] == "winning_ir_region_cell_leftover2_catalog" for s in planned["steps"]), "planner schedules leftover leftover leftover unused catalog")
    check(any(s["level"] == "f4_amg_champ" for s in planned["steps"]), "planner schedules champion AMG residual")
    check(any(s["level"] == "f4_ras_champ" for s in planned["steps"]), "planner schedules champion RAS residual")
    check(any(s["level"] == "f4_krylov_champ" for s in planned["steps"]), "planner schedules champion Krylov/MOR residual")
    check(any(s["level"] == "static_ir_steer" for s in planned["steps"]), "planner schedules static-IR pkg_r steer")
    check(any(s["level"] == "static_mesh" for s in planned["steps"]), "planner schedules static-IR bump mesh")
    check(any(s["level"] == "static_straps" for s in planned["steps"]), "planner schedules static-IR metal4 straps")
    check(any(s["level"] == "em_straps" for s in planned["steps"]), "planner schedules EM metal4 width")
    check(any(s["level"] == "f4_amg" for s in planned["steps"]), "planner schedules AMG residual")
    check(any(s["level"] == "f4_ras" for s in planned["steps"]), "planner schedules RAS residual")
    check(any(s["level"] == "f4_krylov" for s in planned["steps"]), "planner schedules Krylov/MOR residual")
    check(any(s["level"] == "synthesis" for s in planned["steps"]), "planner schedules synthesis F1")
    check(any(s["level"] == "cell" for s in planned["steps"]), "planner schedules cell-local size-up")
    check(any(s["level"] == "net" for s in planned["steps"]), "planner schedules net-local BUF")
    check(any(s["level"] == "net_port" for s in planned["steps"]), "planner schedules port-net BUF")
    check(any(s["level"] == "routing" for s in planned["steps"]), "planner schedules routing GRT")
    check(any(s["level"] == "f4_extract" for s in planned["steps"]), "planner schedules candidate write_pg_spice")
    check(any(s["level"] == "f4_activity" for s in planned["steps"]), "planner schedules host report_arrival")
    check(any(s["level"] == "f4_host_extract" for s in planned["steps"]), "planner schedules host write_pg_spice")
    check(any(s["level"] == "f4_host_region" for s in planned["steps"]), "planner schedules host-region write_pg_spice")
    check(any(s["level"] == "f4_scale" for s in planned["steps"]), "planner schedules attributed I-scale")
    check(
        "attributed host" in next(s["reason"] for s in planned["steps"] if s["level"] == "f4_scale"),
        "I-scale reason names the attributed host, not synth-only",
    )
    check(any(s["level"] == "f2_region" for s in planned["steps"]), "planner schedules IR-bin region GPL")
    check(any(s["level"] == "f4_region_extract" for s in planned["steps"]), "planner schedules region write_pg_spice")
    attr_both = dict(attr)
    attr_both["modules"] = ["dpath", "ctrl"]
    planned_ctrl = plan_search(attr_both, mem2, f2_cong=0.0)
    check(planned_ctrl["focus"] == "dpath", "ctrl on the path does not steal dpath focus")
    check(
        any(s["level"] == "architecture" for s in planned_ctrl["steps"]),
        "dpath extracts still scheduled when ctrl is also on the path",
    )
    check(
        any(s["level"] == "logic_ctrl" and s.get("cone") == "ctrl" for s in planned_ctrl["steps"]),
        "planner schedules ctrl as a first-class cone, not leftover of dpath",
    )
    check(
        not any(s["level"] == "logic_ctrl" for s in planned["steps"]),
        "IR-only dpath attribution does not invent a ctrl-cone step",
    )
    check(
        knobs_fp("physical", {"source": "f2_openroad_gpl", "util": 35, "density": 0.55})
        != knobs_fp(
            "physical",
            {"source": "f2_openroad_gpl_region", "util": 35, "density": 0.55, "region": "r31"},
        ),
        "region GPL is not flattened into the global GPL fingerprint",
    )
    check(
        knobs_fp("routing", {"source": "f2_openroad_grt"})
        != knobs_fp("physical", {"source": "f2_openroad_grt"}),
        "routing GRT is not flattened into the physical fingerprint",
    )
    check(
        knobs_fp("routing", {"source": "f5_openroad_drt_rcx", "droute_end_iter": 2})
        != knobs_fp("routing", {"source": "f2_openroad_grt"}),
        "F5 DRT is not flattened into the GRT fingerprint",
    )
    check(
        knobs_fp("routing", {"source": "f5_openroad_cts_rcx", "clock": "propagated", "cts": 1})
        != knobs_fp("routing", {"source": "f5_openroad_drt_rcx", "clock": "ideal"}),
        "F5-CTS is not flattened into the F5-lite fingerprint",
    )
    check(
        knobs_fp("routing", {"source": "f5_openroad_local", "host_level": "net"})
        != knobs_fp("routing", {"source": "f5_openroad_drt_rcx", "clock": "ideal"}),
        "F5-local is not flattened into the F5-lite fingerprint",
    )
    check(
        knobs_fp("routing", {"source": "f5_openroad_local", "host_level": "cell", "parent_id": "cellh"})
        != knobs_fp("routing", {"source": "f5_openroad_local", "host_level": "net", "parent_id": "neth"}),
        "residual-steered cell SPEF is not flattened into the net F5-local fingerprint",
    )
    check(
        knobs_fp("routing", {"source": "f5_openroad_local", "host_level": "port", "parent_id": "porth"})
        != knobs_fp("routing", {"source": "f5_openroad_local", "host_level": "net", "parent_id": "neth"}),
        "port-net SPEF is not flattened into the intra-module net F5-local fingerprint",
    )
    check(
        knobs_fp("net", {"source": "net_buffer_spef", "spef_residual": 1, "parent_id": "porth"})
        != knobs_fp("net", {"source": "net_buffer", "parent_id": "neth"}),
        "F5-port residual BUF is not flattened into the first net BUF fingerprint",
    )
    from dse.acquire import next_fidelity

    check(next_fidelity(level="f5_drt", pred=None, budget_left=20, cost_hint={}) == "F5", "F5-lite is its own fidelity")
    check(next_fidelity(level="f5_cts", pred=None, budget_left=20, cost_hint={}) == "F5", "F5-CTS measures at F5")
    check(next_fidelity(level="f5_local", pred=None, budget_left=20, cost_hint={}) == "F5", "F5-local measures at F5")
    check(next_fidelity(level="residual_steer", pred=None, budget_left=20, cost_hint={}) == "F5", "residual steer measures at F5")
    check(next_fidelity(level="f5_port", pred=None, budget_left=20, cost_hint={}) == "F5", "F5-port measures at F5")
    check(next_fidelity(level="port_steer", pred=None, budget_left=20, cost_hint={}) == "F3", "F5-port residual steer measures at F3")
    check(next_fidelity(level="ir_steer", pred=None, budget_left=20, cost_hint={}) == "F4", "IR residual steer measures at F4")
    check(next_fidelity(level="host_ir_steer", pred=None, budget_left=20, cost_hint={}) == "F4", "host IR residual steer measures at F4")
    check(next_fidelity(level="f4_scale_win", pred=None, budget_left=20, cost_hint={}) == "F4", "winning-host I-scale measures at F4")
    check(next_fidelity(level="ir_cell", pred=None, budget_left=20, cost_hint={}) == "F3", "IR-hotspot cell size measures at F3")
    check(next_fidelity(level="ir_cell_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "IR-cell extract measures at F4")
    check(next_fidelity(level="ir_cell_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "IR-cell PDN restamp measures at F4")
    check(next_fidelity(level="ir_cell_region", pred=None, budget_left=20, cost_hint={}) == "F4", "IR-cell-region extract measures at F4")
    check(next_fidelity(level="ir_cell_region_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "IR-cell-region PDN restamp measures at F4")
    check(next_fidelity(level="winning_ir_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "winning-IR catalog measures at F4")
    check(next_fidelity(level="f4_scale_champ", pred=None, budget_left=20, cost_hint={}) == "F4", "champion I-scale measures at F4")
    check(next_fidelity(level="ir_cell_champ", pred=None, budget_left=20, cost_hint={}) == "F3", "I-scale-champ cell size measures at F3")
    check(next_fidelity(level="ir_cell_champ_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "IR-cell-champ extract measures at F4")
    check(next_fidelity(level="ir_cell_champ_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "IR-cell-champ PDN restamp measures at F4")
    check(next_fidelity(level="ir_cell_champ_cone", pred=None, budget_left=20, cost_hint={}) == "F3", "leftover-cone cell size measures at F3")
    check(next_fidelity(level="ir_cell_champ_cone_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover-cone extract measures at F4")
    check(next_fidelity(level="ir_cell_champ_cone_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover-cone PDN restamp measures at F4")
    check(next_fidelity(level="ir_cell_champ_cone_region", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover-cone-region extract measures at F4")
    check(next_fidelity(level="ir_cell_champ_cone_region_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover-cone-region PDN restamp measures at F4")
    check(next_fidelity(level="winning_ir_region", pred=None, budget_left=20, cost_hint={}) == "F4", "winning-IR-region extract measures at F4")
    check(next_fidelity(level="winning_ir_region_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "winning-IR-region PDN restamp measures at F4")
    check(next_fidelity(level="winning_ir_region_cell", pred=None, budget_left=20, cost_hint={}) == "F3", "winning-IR-region-cell size measures at F3")
    check(next_fidelity(level="winning_ir_region_cell_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "winning-IR-region-cell extract measures at F4")
    check(next_fidelity(level="winning_ir_region_cell_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "winning-IR-region-cell PDN restamp measures at F4")
    check(next_fidelity(level="winning_ir_region_cell_leftover", pred=None, budget_left=20, cost_hint={}) == "F3", "leftover leftover size measures at F3")
    check(next_fidelity(level="winning_ir_region_cell_leftover_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover leftover extract measures at F4")
    check(next_fidelity(level="winning_ir_region_cell_leftover_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover leftover PDN restamp measures at F4")
    check(next_fidelity(level="winning_ir_region_cell_leftover2", pred=None, budget_left=20, cost_hint={}) == "F3", "leftover leftover leftover size measures at F3")
    check(next_fidelity(level="winning_ir_region_cell_leftover2_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover leftover leftover extract measures at F4")
    check(next_fidelity(level="winning_ir_region_cell_leftover2_pdn", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover leftover leftover PDN restamp measures at F4")
    check(next_fidelity(level="winning_ir_region_cell_leftover2_catalog", pred=None, budget_left=20, cost_hint={}) == "F4", "leftover leftover leftover unused catalog measures at F4")
    check(next_fidelity(level="f4_amg_champ", pred=None, budget_left=20, cost_hint={}) == "F4", "champion AMG measures at F4")
    check(next_fidelity(level="f4_ras_champ", pred=None, budget_left=20, cost_hint={}) == "F4", "champion RAS measures at F4")
    check(next_fidelity(level="f4_krylov_champ", pred=None, budget_left=20, cost_hint={}) == "F4", "champion Krylov/MOR measures at F4")
    check(next_fidelity(level="static_ir_steer", pred=None, budget_left=20, cost_hint={}) == "F4", "static-IR pkg_r steer measures at F4")
    check(next_fidelity(level="static_mesh", pred=None, budget_left=20, cost_hint={}) == "F4", "static-IR bump mesh measures at F4")
    check(next_fidelity(level="static_straps", pred=None, budget_left=20, cost_hint={}) == "F4", "static-IR metal4 straps measure at F4")
    check(next_fidelity(level="em_straps", pred=None, budget_left=20, cost_hint={}) == "F4", "EM metal4 width measures at F4")
    check(next_fidelity(level="f4_scale", pred=None, budget_left=20, cost_hint={}) == "F4", "attributed I-scale measures at F4")
    check(next_fidelity(level="f4_activity", pred=None, budget_left=20, cost_hint={}) == "F3", "host arrivals measure at F3")
    check(next_fidelity(level="f4_host_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "host extract measures at F4")
    check(next_fidelity(level="f4_host_region", pred=None, budget_left=20, cost_hint={}) == "F4", "host-region extract measures at F4")
    check(next_fidelity(level="f2_region", pred=None, budget_left=20, cost_hint={}) == "F2", "region GPL stays on F2")
    check(next_fidelity(level="f4_region_extract", pred=None, budget_left=20, cost_hint={}) == "F4", "region extract stays on F4")
    check(next_fidelity(level="f4_amg", pred=None, budget_left=20, cost_hint={}) == "F4", "AMG stays on F4")
    check(next_fidelity(level="f4_ras", pred=None, budget_left=20, cost_hint={}) == "F4", "RAS stays on F4")
    check(next_fidelity(level="f4_krylov", pred=None, budget_left=20, cost_hint={}) == "F4", "Krylov/MOR stays on F4")
    check(
        knobs_fp("pdn", {"source": "f4_solver_krylov", "extract_id": "finish"})
        != knobs_fp("pdn", {"source": "f4_solver_ras", "extract_id": "finish"}),
        "Krylov residual is not flattened into the RAS fingerprint",
    )
    check(next_fidelity(level="synthesis", pred=None, budget_left=20, cost_hint={}) == "F1", "synthesis measures at F1")
    check(next_fidelity(level="cell", pred=None, budget_left=20, cost_hint={}) == "F3", "cell-local size is measured at F3")
    check(next_fidelity(level="net", pred=None, budget_left=20, cost_hint={}) == "F3", "net-local BUF is measured at F3")
    check(next_fidelity(level="net_port", pred=None, budget_left=20, cost_hint={}) == "F3", "port-net BUF is measured at F3")
    check(
        knobs_fp("cell", {"source": "cell_size_up", "cells": ["dpath/a_lt_b/_142_"]})
        != knobs_fp("logic", {"source": "cell_size_up", "cells": ["dpath/a_lt_b/_142_"]}),
        "cell-local knobs are not flattened into the logic fingerprint",
    )
    check(
        knobs_fp("cell", {"source": "cell_size_ir", "cells": ["ctrl/_11_"], "ir_join": 1})
        != knobs_fp("cell", {"source": "cell_size_up", "cells": ["dpath/a_lt_b/_142_"]}),
        "IR-hotspot cell knobs are not flattened into the STA cell size-up fingerprint",
    )
    check(
        knobs_fp("net", {"source": "net_buffer", "hops": ["_586_->_587_"], "buf": "BUF_X2"})
        != knobs_fp("cell", {"source": "net_buffer", "hops": ["_586_->_587_"], "buf": "BUF_X2"}),
        "net-local knobs are not flattened into the cell fingerprint",
    )
    check(
        knobs_fp("net", {"source": "net_buffer_port", "scope": "port", "cross_module": 1, "hops": ["dpath/u0->ctrl/u1"]})
        != knobs_fp("net", {"source": "net_buffer", "hops": ["dpath/u0->ctrl/u1"]}),
        "port-net knobs are not flattened into the intra-module net fingerprint",
    )
    check(
        knobs_fp("synthesis", {"name": "orfs_abc_speed", "abcArea": 0, "source": "orfs_abc_script"})
        != knobs_fp("logic", {"name": "orfs_abc_speed", "abcArea": 0, "source": "orfs_abc_script"}),
        "synthesis knobs are not flattened into the logic fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {"source": "f4_iscale", "parent_id": "psteer", "host_source": "net_buffer_spef", "i_scale": 4.21},
        )
        != knobs_fp(
            "pdn",
            {"source": "f4_iscale", "parent_id": "synp", "host_source": "orfs_abc_script", "i_scale": 2.31},
        ),
        "I-scale of the port-steer host is not flattened into the synth I-scale fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_iscale_win",
                "parent_id": "psteer",
                "extract_id": "hreg",
                "c_decap": 200e-15,
                "i_scale": 4.21,
            },
        )
        != knobs_fp(
            "pdn",
            {
                "source": "f4_iscale",
                "parent_id": "psteer",
                "extract_id": "hex",
                "c_decap": 50e-15,
                "i_scale": 4.21,
            },
        ),
        "winning-host I-scale is not flattened into the unconstrained I-scale fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_iscale_champ",
                "parent_id": "ircell",
                "extract_id": "icreg",
                "c_decap": 200e-15,
                "i_scale": 4.21,
            },
        )
        != knobs_fp(
            "pdn",
            {
                "source": "f4_iscale_win",
                "parent_id": "psteer",
                "extract_id": "hreg",
                "c_decap": 200e-15,
                "i_scale": 4.21,
            },
        ),
        "champion I-scale is not flattened into the winning-host I-scale fingerprint",
    )
    check(
        knobs_fp("cell", {"source": "cell_size_ir_champ", "cells": ["dpath/a_reg/_078_"], "ir_join": 1, "champ": 1})
        != knobs_fp("cell", {"source": "cell_size_ir", "cells": ["ctrl/_11_"], "ir_join": 1}),
        "I-scale-champ cell knobs are not flattened into the first IR-cell fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_ir_cell_champ_extract", "parent_id": "icchamp", "ir_join": 1, "champ": 1})
        != knobs_fp("pdn", {"source": "f4_ir_cell_extract", "parent_id": "ircell", "ir_join": 1}),
        "IR-cell-champ extract knobs are not flattened into the IR-cell extract fingerprint",
    )
    check(
        knobs_fp(
            "cell",
            {
                "source": "cell_size_ir_champ_cone",
                "cells": ["dpath/b_reg/_078_"],
                "ir_join": 1,
                "champ": 1,
                "champ_cone": 1,
            },
        )
        != knobs_fp(
            "cell",
            {"source": "cell_size_ir_champ", "cells": ["ctrl/_04_"], "ir_join": 1, "champ": 1},
        ),
        "leftover-cone cell knobs are not flattened into the champ size-up fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_ir_cell_champ_cone_extract",
                "parent_id": "iccone",
                "ir_join": 1,
                "champ": 1,
                "champ_cone": 1,
            },
        )
        != knobs_fp("pdn", {"source": "f4_ir_cell_champ_extract", "parent_id": "icchamp", "ir_join": 1, "champ": 1}),
        "leftover-cone extract knobs are not flattened into the champ extract fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_ir_cell_champ_cone_region_extract",
                "parent_id": "iccone",
                "region": "r03",
                "ir_join": 1,
                "champ_cone": 1,
            },
        )
        != knobs_fp(
            "pdn",
            {"source": "f4_ir_cell_region_extract", "parent_id": "ircell", "region": "r00", "ir_join": 1},
        ),
        "leftover-cone-region knobs are not flattened into the IR-cell-region fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_winning_ir_region_extract",
                "parent_id": "ircell",
                "region": "r30",
                "ir_join": 1,
            },
        )
        != knobs_fp(
            "pdn",
            {
                "source": "f4_ir_cell_champ_cone_region_extract",
                "parent_id": "iccone",
                "region": "r03",
                "ir_join": 1,
                "champ_cone": 1,
            },
        ),
        "winning-IR-region knobs are not flattened into the leftover-cone-region fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_winning_ir_region_extract",
                "parent_id": "ircell",
                "region": "r30",
                "ir_join": 1,
            },
        )
        != knobs_fp(
            "pdn",
            {"source": "f4_ir_cell_region_extract", "parent_id": "ircell", "region": "r00", "ir_join": 1},
        ),
        "winning-IR-region knobs are not flattened into the IR-cell-region fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_winning_ir_region_extract",
                "parent_id": "ircell",
                "region": "r30",
                "ir_join": 1,
            },
        )
        != knobs_fp(
            "pdn",
            {
                "source": "f4_winning_ir_region_extract",
                "parent_id": "ircell",
                "region": "r13",
                "ir_join": 1,
            },
        ),
        "winning-IR-region r30 knobs are not flattened into a second-bin r13 fingerprint",
    )
    check(
        knobs_fp(
            "cell",
            {
                "source": "cell_size_ir_winning_region",
                "parent_id": "ircell",
                "cells": ["dpath/b_mux/_44_", "dpath/b_mux/_51_"],
                "ir_join": 1,
                "winning_ir_region": 1,
            },
        )
        != knobs_fp(
            "cell",
            {
                "source": "cell_size_ir_champ_cone",
                "parent_id": "icchamp",
                "cells": ["dpath/b_reg/_078_", "dpath/b_mux/_46_"],
                "ir_join": 1,
                "champ_cone": 1,
            },
        ),
        "winning-IR-region-cell knobs are not flattened into leftover-cone size-up",
    )
    check(
        knobs_fp(
            "pdn",
            {
                "source": "f4_winning_ir_region_cell_extract",
                "parent_id": "wircell",
                "ir_join": 1,
                "winning_ir_region": 1,
            },
        )
        != knobs_fp(
            "pdn",
            {
                "source": "f4_winning_ir_region_extract",
                "parent_id": "ircell",
                "region": "r30",
                "ir_join": 1,
            },
        ),
        "winning-IR-region-cell extract knobs are not flattened into the region extract fingerprint",
    )
    check(
        knobs_fp(
            "cell",
            {
                "source": "cell_size_ir_winning_region_leftover",
                "parent_id": "wircell",
                "cells": ["dpath/sub/_192_", "dpath/sub/_196_"],
                "ir_join": 1,
                "winning_ir_region_leftover": 1,
            },
        )
        != knobs_fp(
            "cell",
            {
                "source": "cell_size_ir_winning_region",
                "parent_id": "ircell",
                "cells": ["dpath/b_mux/_44_", "dpath/b_mux/_51_"],
                "ir_join": 1,
                "winning_ir_region": 1,
            },
        ),
        "leftover leftover knobs are not flattened into leftover-combo size-up",
    )
    check(
        knobs_fp(
            "cell",
            {
                "source": "cell_size_ir_winning_region_leftover2",
                "parent_id": "wirclcell",
                "cells": ["dpath/b_reg/_075_", "dpath/b_mux/_41_"],
                "ir_join": 1,
                "winning_ir_region_leftover2": 1,
            },
        )
        != knobs_fp(
            "cell",
            {
                "source": "cell_size_ir_winning_region_leftover",
                "parent_id": "wircell",
                "cells": ["dpath/sub/_192_", "dpath/sub/_196_"],
                "ir_join": 1,
                "winning_ir_region_leftover": 1,
            },
        ),
        "leftover leftover leftover knobs are not flattened into leftover leftover size-up",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_a", "extract_id": "iccext", "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_a", "extract_id": "icreg", "c_decap": 200e-15}),
        "IR-cell-champ PDN restamp is not flattened into the IR-cell-region decap fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_amg", "extract_id": "icreg", "name": "amg_champ", "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_amg", "extract_id": "finish", "name": "amg_residual", "c_decap": 50e-15}),
        "champion AMG is not flattened into the candidate/finish AMG fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_ras", "extract_id": "icreg", "name": "ras_champ", "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_amg", "extract_id": "icreg", "name": "amg_champ", "c_decap": 200e-15}),
        "champion RAS is not flattened into the champion AMG fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_krylov", "extract_id": "icreg", "name": "krylov_champ", "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_ras", "extract_id": "icreg", "name": "ras_champ", "c_decap": 200e-15}),
        "champion Krylov is not flattened into the champion RAS fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_a", "name": "pkg_r_25m", "extract_id": "icreg", "pkg_r": 0.025, "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_a", "name": "decap_200f", "extract_id": "icreg", "pkg_r": 0.05, "c_decap": 200e-15}),
        "static-IR pkg_r is not flattened into the Dynamic IR decap fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_static_mesh_extract", "name": "bumps_80", "bump_dx": 80, "extract_id": "icreg"})
        != knobs_fp("pdn", {"source": "f4_solver_a", "name": "pkg_r_25m", "extract_id": "icreg", "pkg_r": 0.025, "c_decap": 200e-15}),
        "static-IR bump mesh is not flattened into the pkg_r fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_static_strap_extract", "name": "m4_pitch_8", "m4_pitch": 8, "extract_id": "icreg"})
        != knobs_fp("pdn", {"source": "f4_static_mesh_extract", "name": "bumps_80", "bump_dx": 80, "extract_id": "icreg"}),
        "static-IR metal4 straps are not flattened into the bump fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_em_strap_extract", "name": "m4_width_96", "m4_pitch": 8, "m4_width": 0.96, "extract_id": "icreg"})
        != knobs_fp("pdn", {"source": "f4_static_strap_extract", "name": "m4_pitch_8", "m4_pitch": 8, "m4_width": 0.48, "extract_id": "icreg"}),
        "EM metal4 width is not flattened into the pitch fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_host_arrivals", "parent_id": "psteer", "host_source": "net_buffer_spef"})
        != knobs_fp("pdn", {"source": "f4_iscale", "parent_id": "psteer", "host_source": "net_buffer_spef"}),
        "host arrivals knobs are not flattened into the I-scale fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_host_extract", "parent_id": "psteer"})
        != knobs_fp("pdn", {"source": "f4_candidate_extract", "parent_id": "synp"}),
        "host extract knobs are not flattened into the synth extract fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_ir_cell_extract", "parent_id": "ircell", "ir_join": 1})
        != knobs_fp("pdn", {"source": "f4_host_extract", "parent_id": "psteer"}),
        "IR-cell extract knobs are not flattened into the host extract fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_a", "extract_id": "icext", "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_a", "extract_id": "hreg", "c_decap": 200e-15}),
        "IR-cell PDN restamp is not flattened into the host-region decap fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_ir_cell_region_extract", "parent_id": "ircell", "region": "r00"})
        != knobs_fp("pdn", {"source": "f4_host_region_extract", "parent_id": "psteer", "region": "r02"}),
        "IR-cell-region knobs are not flattened into the host-region extract fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_ir_cell_region_extract", "parent_id": "ircell", "region": "r00"})
        != knobs_fp("pdn", {"source": "f4_ir_cell_extract", "parent_id": "ircell", "ir_join": 1}),
        "IR-cell-region knobs are not flattened into the unconstrained IR-cell extract fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_a", "extract_id": "icreg", "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_a", "extract_id": "icext", "c_decap": 200e-15}),
        "IR-cell-region PDN restamp is not flattened into the IR-cell 1× decap fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_host_region_extract", "parent_id": "psteer", "region": "r02"})
        != knobs_fp("pdn", {"source": "f4_host_extract", "parent_id": "psteer"}),
        "host-region extract knobs are not flattened into the unconstrained host extract fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_host_region_extract", "parent_id": "psteer", "region": "r02"})
        != knobs_fp("pdn", {"source": "f4_region_extract", "parent_id": "synp", "region": "r31"}),
        "host-region extract knobs are not flattened into the synth region extract fingerprint",
    )
    check(
        knobs_fp(
            "pdn",
            {"source": "f4_solver_a", "name": "decap_200f", "extract_id": "hreg", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15},
        )
        != knobs_fp(
            "pdn",
            {"source": "f4_solver_a", "name": "decap_200f", "extract_id": "regext", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15},
        ),
        "host-region decap restamp is not flattened into the synth-region decap fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_ras", "extract_id": "finish"})
        != knobs_fp("pdn", {"source": "f4_solver_amg", "extract_id": "finish"}),
        "RAS residual is not flattened into the AMG fingerprint",
    )
    check(
        knobs_fp("pdn", {"source": "f4_solver_a", "name": "decap_200f", "extract_id": "regionX", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15})
        != knobs_fp("pdn", {"source": "f4_solver_a", "name": "decap_200f", "extract_id": "candY", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15}),
        "region-mesh decap restamp is not flattened into the candidate-mesh decap fingerprint",
    )
    from dse.net_space import (
        _assign_port,
        buffer_path_nets,
        buffer_port_nets,
        find_port_crossing,
        hop_is_block_port,
        hop_is_cross_module,
    )
    from dse.cell_space import parse_modules

    check(not hop_is_cross_module("_586_->_587_"), "flatten hop is not cross-module")
    check(not hop_is_cross_module("dpath/_07_->dpath/_08_"), "same-instance prefix is intra-module")
    check(hop_is_cross_module("dpath/a_lt_b/_194_->ctrl/_06_"), "dpath↔ctrl hop is cross-module")
    check(hop_is_cross_module("dpath/a_lt_b/_142_->dpath/a_mux/_40_"), "dpath submodule hop is cross-module")
    check(hop_is_block_port("dpath/a_lt_b/_194_->ctrl/_06_"), "dpath↔ctrl is a block-port hop")
    check(not hop_is_block_port("dpath/a_lt_b/_142_->dpath/a_mux/_40_"), "same top instance is not a block-port hop")
    tiny_port = (
        "module ctrl(is_a_lt_b, z);\n"
        "  input is_a_lt_b;\n  output z;\n"
        "  INV_X1 u1 (.A(is_a_lt_b), .ZN(z));\n"
        "endmodule\n"
        "module dpath(is_a_lt_b);\n"
        "  output is_a_lt_b;\n"
        "  INV_X1 u0 (.A(1'b0), .ZN(is_a_lt_b));\n"
        "endmodule\n"
        "module gcd(z);\n"
        "  output z;\n  wire n1;\n"
        "  ctrl ctrl (.is_a_lt_b(n1), .z(z));\n"
        "  dpath dpath (.is_a_lt_b(n1));\n"
        "endmodule\n"
    )
    pintra = buffer_path_nets(tiny_port, ["dpath/u0->ctrl/u1"])
    check(pintra["n_changed"] == 0, "intra-module BUF still skips the port hop")
    pport = buffer_port_nets(tiny_port, ["dpath/u0->ctrl/u1"])
    check(pport["n_changed"] == 1, f"tiny port hop gets one parent BUF, got {pport['changed']}")
    check("BUF_X2 portbuf_0" in pport["text"], "tiny port hop inserts BUF_X2 in the parent")
    check(".is_a_lt_b(portbuf_w0)" in pport["text"], "tiny port hop retargets the sink instance pin")
    check("INV_X1 u0" in pport["text"] and "INV_X1 u1" in pport["text"], "port BUF leaves intra-module cells untouched")
    check("module ctrl" in pport["text"] and "module dpath" in pport["text"], "port BUF does not flatten the netlist")
    tiny_bus = (
        "module ctrl(sel);\n"
        "  output [1:0] sel;\n  wire [1:0] sel;\n"
        "  NOR2_X1 u0 (.A1(1'b0), .A2(1'b0), .ZN(sel[0]));\n"
        "  NOR2_X1 ux (.A1(1'b0), .A2(1'b0), .ZN(sel[1]));\n"
        "endmodule\n"
        "module dpath(sel);\n"
        "  input [1:0] sel;\n  wire [1:0] sel;\n  wire y;\n"
        "  INV_X1 u2 (.A(sel[0]), .ZN(y));\n"
        "endmodule\n"
        "module gcd();\n"
        "  wire [1:0] sel;\n"
        "  ctrl ctrl (.sel(sel));\n"
        "  dpath dpath (.sel(sel));\n"
        "endmodule\n"
    )
    cmod = next(m for m in parse_modules(tiny_bus) if m["name"] == "ctrl")
    check(_assign_port(cmod, "sel[0]") == "sel", f"bit-select walks to the bus port, got {_assign_port(cmod, 'sel[0]')}")
    xbus = find_port_crossing(tiny_bus, "ctrl/u0", "dpath/u2")
    check(xbus is not None and xbus.get("bit") == 0, f"return-style bus hop is found, got {xbus}")
    check("sel[0]" in str(xbus.get("net")), f"crossing names the bit, got {xbus.get('net')}")
    pbus = buffer_port_nets(tiny_bus, ["ctrl/u0->dpath/u2"])
    check(pbus["n_changed"] == 1, f"tiny bus-bit hop gets one parent BUF, got {pbus['changed']}")
    check(pbus["changed"][0].get("splice") is True, "bus-bit BUF splices the parent bus, not the whole vector")
    check(".sel(portbuf_b0)" in pbus["text"], "bus-bit BUF retargets the sink bus pin to the spliced vector")
    check(".sel(sel)" in pbus["text"], "bus-bit BUF leaves the source instance on the original bus")
    check("assign portbuf_b0[0] = portbuf_w0" in pbus["text"], "spliced bit 0 comes from the BUF")
    check("assign portbuf_b0[1] = sel[1]" in pbus["text"], "unrelated bus bit is copied through")
    check("NOR2_X1 u0" in pbus["text"] and "INV_X1 u2" in pbus["text"], "bus-bit BUF does not flatten cells")
    check(ucb_next_op(mem2, last="∅", focus="dpath") is None, "UCB is silent without transitions")

    banner = "/* Generated by Yosys 0.63 (git sha1 abc, g++ 13) [the-openroad-project/yosys] */\n"
    tiny = (
        banner
        + "module gcd(clk);\n  input clk;\n"
        + "  INV_X1 _0_ (\n    .A(clk),\n    .ZN(n1)\n  );\n"
        + "  INV_X1 _1_ (\n    .A(n1),\n    .ZN(n2)\n  );\n"
        + "endmodule\n"
    )
    check("Yosys" not in strip_verilog_comments(tiny), "comment strip drops the Yosys banner")
    fixture = Path(tempfile.mkdtemp(prefix="dse-v-")) / "tiny.v"
    fixture.write_text(tiny)
    gt = parse_mapped_verilog(fixture)
    check("Yosys" not in gt.types.values(), "parser does not invent a Yosys cell")
    check(gt.n_cells == 2 and gt.n_nets == 1, f"tiny netlist 2 cells / 1 net, got {gt.n_cells}/{gt.n_nets}")
    est_tiny = estimate_physical(fixture)
    check(est_tiny["hpwl"] > 0.1, f"tiny HPWL must not collapse, got {est_tiny['hpwl']}")
    check(0.0 <= est_tiny["congestion"] < 1.0, "F2-fast congestion is normalized to [0,1)")
    emb = graph_embedding(gt)
    check(len(emb) == 8, "GNN embedding is 8-D")
    gnn0 = predict_hpwl([], emb)
    check(gnn0["uncertainty"] == "high" and gnn0["n"] == 0, "GNN stays uncertain without teachers")

    yosys_v = _ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"
    if yosys_v.is_file():
        g = parse_mapped_verilog(yosys_v)
        check(g.n_cells > 20, f"parsed mapped netlist cells, got {g.n_cells}")
        est = estimate_physical(yosys_v)
        check(est["hpwl"] > 10, f"F2-fast HPWL is a real wirelength, got {est['hpwl']}")
        check(0.0 <= est["congestion"] < 1.0, "F2-fast RUDY congestion is normalized")
        print(f"    F2-fast ORFS yosys.v cells={g.n_cells} HPWL={est['hpwl']:.1f} cong={est['congestion']:.3f}")

    mapped_ok = _ROOT / "learn/sim/dse/netlists/4628a15dbc9a.v"
    mapped_assign = _ROOT / "learn/sim/dse/netlists/1bea95afcec2.v"
    if mapped_ok.is_file():
        check(is_gate_cell_netlist(mapped_ok), "liberty-mapped F1 is gate-cell")
        est_m = estimate_physical(mapped_ok)
        check(est_m["hpwl"] > 10, f"gate-cell F1 HPWL ≫ 0, got {est_m['hpwl']}")
        check(est_m["n_cells"] > 100, f"gate-cell F1 has liberty instances, got {est_m['n_cells']}")
    if mapped_assign.is_file():
        check(not is_gate_cell_netlist(mapped_assign), "assign-lowered write_verilog is not gate-cell")

    from dse.openroad_f2 import available as gpl_available, evaluate_gpl

    if gpl_available() and mapped_ok.is_file():
        gpl = evaluate_gpl(mapped_ok, timeout_s=40)
        check(gpl.get("status") == "ok", f"OpenROAD GPL on mapped F1 ({gpl.get('reason')})")
        check((gpl.get("hpwl_um") or 0) > 100, f"GPL HPWL in microns, got {gpl.get('hpwl_um')}")
        check(gpl.get("overflow") is not None, "GPL reports overflow")
        print(f"    F2 GPL HPWL={gpl['hpwl_um']:.1f} um overflow={gpl['overflow']:.3f} ({gpl['cost_s']:.2f}s)")
        gpl_r = evaluate_gpl(mapped_ok, timeout_s=40, x_dbu=70896.0, y_dbu=39429.0, region="r31")
        check(gpl_r.get("status") == "ok", f"region GPL on IR hotspot ({gpl_r.get('reason')})")
        check(gpl_r.get("region_bin"), f"region GPL names the bin, got {gpl_r.get('region_bin')}")
        check((gpl_r.get("hpwl_um") or 0) > 100, f"region GPL HPWL in microns, got {gpl_r.get('hpwl_um')}")
        print(
            f"    F2 region GPL bin={gpl_r.get('region_bin')} HPWL={gpl_r['hpwl_um']:.1f} um "
            f"overflow={gpl_r.get('overflow')} ({gpl_r['cost_s']:.2f}s)"
        )

    from dse.sta_f3 import available as sta_available, evaluate_sta, export_arrivals
    from dse.openroad_f2 import (
        evaluate_f5_cts as run_f5_cts,
        evaluate_f5_drt as run_f5_drt,
        evaluate_grt,
        f5_available,
    )
    from dse.attribute import attribute_sta

    slash = attribute_sta(
        {"path_start": "dpath/b_reg/_49_", "path_end": "dpath/sub/_122_", "wns_ns": -0.39}
    )
    check(slash["modules"] == ["dpath"], f"slash STA paths map to dpath, got {slash['modules']}")
    check("dpath/sub" in (slash.get("cones") or []), f"sub-cone from slash path, got {slash.get('cones')}")
    check("dpath/b_reg" in (slash.get("cones") or []), "register instance is a sub-cone")
    check(slash["status"] == "READY", "hier STA path is READY without inherit")

    if sta_available() and mapped_ok.is_file():
        sta = evaluate_sta(mapped_ok)
        check(sta.get("status") == "ok", f"OpenSTA F3 on mapped F1 ({sta.get('reason')})")
        check(sta.get("wns_ns") is not None, "F3 reports WNS")
        check((sta.get("power_w") or 0) > 0, f"F3 reports power, got {sta.get('power_w')}")
        print(f"    F3 STA WNS={sta['wns_ns']:.3f} ns P={sta['power_w']:.4e} W ({sta['cost_s']:.2f}s)")
        sattr = attribute_sta(sta, inherit={"modules": ["dpath"], "scope": "logic_cone"})
        check(sattr["restart_chip"] is False, "STA attribution refuses a chip restart")
        check("dpath" in (sattr.get("modules") or []), "STA inherit keeps the dpath cone")
        arr_p = Path(tempfile.mkdtemp(prefix="dse-arr-")) / "sta_arrivals.json"
        arr = export_arrivals(mapped_ok, arr_p)
        check(arr.get("status") == "ok", f"candidate STA arrivals ({arr.get('reason')})")
        check((arr.get("n_inst") or 0) > 50, f"arrivals cover the cell set, n_inst={arr.get('n_inst')}")
        check(arr_p.is_file(), "export_arrivals writes JSON")
        print(f"    F3 arrivals n_inst={arr.get('n_inst')} ({arr.get('cost_s', 0):.2f}s)")

    if gpl_available() and mapped_ok.is_file():
        sdf_p = Path(tempfile.mkdtemp(prefix="dse-sdf-")) / "cand.sdf"
        grt = evaluate_grt(mapped_ok, timeout_s=40, sdf_out=sdf_p)
        check(grt.get("status") == "ok", f"OpenROAD GRT on mapped F1 ({grt.get('reason')})")
        check(grt.get("wns_ns") is not None, "GRT+parasitics reports WNS")
        check(grt.get("sdf") and Path(grt["sdf"]).is_file(), "GRT persists SDF (not SPEF/OpenRCX)")
        check(grt.get("interconnect") == "sdf_grt", f"GRT interconnect is sdf_grt, got {grt.get('interconnect')}")
        check("detailed" not in (grt.get("via") or "").lower() or "not detailed" in (grt.get("via") or ""),
              "GRT via states it is not detailed route")
        print(f"    F2 GRT WNS={grt['wns_ns']:.3f} ns overflow={grt.get('overflow')} ({grt['cost_s']:.2f}s)")
        if sta_available() and sdf_p.is_file():
            sdf_sta = evaluate_sta(mapped_ok, sdf=sdf_p)
            check(sdf_sta.get("status") == "ok", f"OpenSTA + GRT SDF ({sdf_sta.get('reason')})")
            check(sdf_sta.get("interconnect") == "sdf_grt", "OpenSTA labels interconnect sdf_grt")
            if sta.get("wns_ns") is not None and sdf_sta.get("wns_ns") is not None:
                check(
                    abs(float(sdf_sta["wns_ns"]) - float(sta["wns_ns"])) > 0.05,
                    f"SDF WNS {sdf_sta['wns_ns']} must differ from ideal {sta['wns_ns']}",
                )
            print(f"    F3 SDF-GRT WNS={sdf_sta['wns_ns']:.3f} ns vs ideal {sta.get('wns_ns')} ns")

    if f5_available() and mapped_ok.is_file() and sta_available():
        ideal = evaluate_sta(mapped_ok)
        spef_p = Path(tempfile.mkdtemp(prefix="dse-spef-")) / "cand.spef"
        f5 = run_f5_drt(mapped_ok, timeout_s=45, spef_out=spef_p)
        check(f5.get("status") == "ok", f"F5-lite DRT+OpenRCX ({f5.get('reason')})")
        check(f5.get("spef") and Path(f5["spef"]).is_file(), "F5 writes a SPEF")
        check((f5.get("spef_bytes") or 0) > 1000, f"SPEF is non-trivial, {f5.get('spef_bytes')} B")
        check((f5.get("n_rc_segments") or 0) > 100, f"OpenRCX reports RC segments, got {f5.get('n_rc_segments')}")
        check(f5.get("clock") == "ideal", "F5-lite keeps the clock ideal (no CTS)")
        check("not make finish" in (f5.get("via") or ""), "F5 via states it is not make finish")
        spef_sta = evaluate_sta(mapped_ok, spef=Path(f5["spef"]))
        check(spef_sta.get("status") == "ok", f"OpenSTA + OpenRCX SPEF ({spef_sta.get('reason')})")
        check(spef_sta.get("interconnect") == "spef", f"OpenSTA labels interconnect spef, got {spef_sta.get('interconnect')}")
        check(
            ideal.get("wns_ns") is not None and spef_sta.get("wns_ns") is not None
            and abs(float(spef_sta["wns_ns"]) - float(ideal["wns_ns"])) > 0.05,
            f"SPEF WNS {spef_sta.get('wns_ns')} must differ from ideal {ideal.get('wns_ns')}",
        )
        print(
            f"    F5 SPEF WNS={spef_sta['wns_ns']:.3f} ns vs ideal {ideal['wns_ns']:.3f} ns "
            f"segs={f5.get('n_rc_segments')} ({f5['cost_s']:.2f}s)"
        )
        cts_spef = Path(tempfile.mkdtemp(prefix="dse-cts-")) / "cand_cts.spef"
        cts_v = Path(tempfile.mkdtemp(prefix="dse-cts-v-")) / "cand_cts.v"
        cts = run_f5_cts(mapped_ok, timeout_s=90, spef_out=cts_spef, verilog_out=cts_v)
        check(cts.get("status") == "ok", f"F5-CTS DRT+OpenRCX ({cts.get('reason')})")
        check(cts.get("clock") == "propagated", "F5-CTS marks the clock propagated")
        check((cts.get("n_clkbuf") or 0) >= 1, f"F5-CTS inserts CLKBUF, got {cts.get('n_clkbuf')}")
        check(cts.get("spef") and Path(cts["spef"]).is_file(), "F5-CTS writes a distinct SPEF")
        check(cts.get("cts_v") and Path(cts["cts_v"]).is_file(), "F5-CTS writes the post-CTS netlist")
        check("not make finish" in (cts.get("via") or ""), "F5-CTS via states it is not make finish")
        cts_sta = evaluate_sta(Path(cts["cts_v"]), spef=Path(cts["spef"]), propagated_clock=True)
        check(cts_sta.get("status") == "ok", f"OpenSTA + CTS SPEF ({cts_sta.get('reason')})")
        check(cts_sta.get("clock") == "propagated", "OpenSTA CTS shot uses set_propagated_clock")
        check(
            spef_sta.get("wns_ns") is not None
            and cts_sta.get("wns_ns") is not None
            and abs(float(cts_sta["wns_ns"]) - float(spef_sta["wns_ns"])) > 0.0,
            f"CTS SPEF WNS {cts_sta.get('wns_ns')} must differ from F5-lite {spef_sta.get('wns_ns')}",
        )
        check(
            "set_propagated_clock" in (cts_sta.get("via") or ""),
            "CTS STA via names set_propagated_clock",
        )
        check(f5.get("clock") == "ideal", "F5-lite stays ideal after the CTS shot")
        print(
            f"    F5-CTS SPEF WNS={cts_sta['wns_ns']:.3f} ns vs F5-lite {spef_sta['wns_ns']:.3f} ns "
            f"n_clkbuf={cts.get('n_clkbuf')} ({cts['cost_s']:.2f}s)"
        )

    props = dse_propose(mem2, focus="dpath", attr=attr)
    check(props, "symbolic proposer returns at least one idea")
    check(all("pkg_l" not in p and "coreUtilization" not in p for p in props), "proposer stays off PDN/physical knobs")
    check("gold" in (adapter_status()["solver"]["note"] or "").lower(), "solver adapter keeps gold unrestamped")
    check("restamp" in (adapter_status()["solver"]["note"] or "").lower() or "make_solver" in (adapter_status()["solver"]["via"] or ""), "solver adapter can restamp on the cached extract")
    check("amg" in (adapter_status()["solver"]["via"] or "").lower(), "solver adapter names AMG as a replaceable MF solver")
    check("ras" in (adapter_status()["solver"]["via"] or "").lower(), "solver adapter names RAS as a replaceable MF solver")
    check(
        "krylov" in (adapter_status()["solver"]["via"] or "").lower()
        or "mor" in (adapter_status()["solver"]["via"] or "").lower(),
        "solver adapter names Krylov/MOR as a replaceable MF solver",
    )
    check("abc_speed" in (adapter_status()["synthesis"]["note"] or ""), "synthesis adapter is ORFS abc_speed, not logic -fast")
    check("path" in (adapter_status()["cell"]["note"] or ""), "cell adapter is attributed-path drive-up")
    check("BUF" in (adapter_status()["net"]["note"] or ""), "net adapter is attributed-path BUF insert")
    check("port" in (adapter_status()["net"]["note"] or ""), "net adapter names parent-scoped port-net BUF")
    check("SPEF" in (adapter_status()["timing"]["note"] or ""), "timing adapter includes OpenRCX SPEF")
    check("f5" in (adapter_status()["routing"]["via"] or "").lower() or "OpenRCX" in (adapter_status()["routing"]["note"] or ""), "routing adapter includes F5-lite")
    check("cts" in (adapter_status()["routing"]["via"] or "").lower(), "routing adapter includes F5-CTS")
    check("local" in (adapter_status()["routing"]["via"] or "").lower(), "routing adapter includes F5-local")
    check("port" in (adapter_status()["routing"]["note"] or "").lower(), "routing adapter includes F5-port SPEF")
    check("F5-port residual" in (adapter_status()["active"]["note"] or ""), "active adapter steers from the F5-port residual")
    check("f5-local" in (adapter_status()["surrogate"]["note"] or "").lower() or "F3→F5" in (adapter_status()["surrogate"]["note"] or ""), "surrogate adapter names the F3→F5-local residual")
    check("residual" in (adapter_status()["active"]["note"] or ""), "active adapter steers from the F3→F5 residual")
    check("F4" in (adapter_status()["active"]["note"] or "") or "IR" in (adapter_status()["active"]["note"] or ""), "active adapter steers from the F4 IR residual")
    check(adapter_status()["active"].get("ready") is True, "active adapter is ready")
    check("propagated" in (adapter_status()["timing"]["note"] or ""), "timing adapter names propagated-clock CTS SPEF")
    check("arrival" in (adapter_status()["activity"]["via"] or "").lower(), "activity adapter is candidate STA arrivals")
    check(
        "write_pg_spice" in (adapter_status()["extraction"]["via"] or ""),
        "extraction adapter is write_pg_spice, not a flattened black-box",
    )

    from dse.controller import propose_logic

    knobs = propose_logic(mem2)
    check(knobs is not None and knobs.get("name"), "controller proposes a logic catalog entry")
    check("coreUtilization" not in knobs, "logic proposal does not smuggle physical knobs")
    check("pkg_l" not in knobs, "logic proposal does not smuggle PDN knobs")
    check(not knobs.get("cone"), "chip-focus proposal is flatten-first, not cone ABC")
    knobs_d = propose_logic(mem2, focus="dpath")
    check((knobs_d or {}).get("cone") == "dpath", "dpath-focus proposal stamps cone ABC")
    knobs_c = propose_logic(mem2, focus="ctrl")
    check((knobs_c or {}).get("cone") == "ctrl", "ctrl-focus proposal stamps the FSM cone")
    check((knobs_c or {}).get("cone_module") == CTRL_MODULE, "ctrl-focus names GcdUnitCtrlRTL")
    check("ctrl" in (adapter_status()["dse"]["note"] or ""), "DSE adapter names ctrl as a first-class cone")

    ir_p = _ROOT / "learn" / "sim" / "reports" / "dynamic_ir_flowlab.json"
    if ir_p.is_file():
        real = attribute_dynamic_ir(json.loads(ir_p.read_text()))
        check(real.get("droop_mv") and abs(float(real["droop_mv"]) - 45.298) < 0.02, "GCD IR attr keeps 45.298 gold")
        check("dpath" in (real.get("modules") or []), "GCD worst path attributes to dpath")
        print(f"    GCD IR cone {real.get('modules')} droop={real.get('droop_mv'):.3f} mV")

    import shutil

    if shutil.which("yosys") and rtl.is_file():
        from dse.fidelity import evaluate_f1_abc, evaluate_f1_synth, liberty_path

        lib = liberty_path()
        if lib.is_file():
            tdir = Path(tempfile.mkdtemp(prefix="dse-f1-"))
            mm = DesignMemory(tdir / "m.jsonl")
            k0 = {"name": "liberty_default", "abc_args": [], "abc_ops": [], "abc_script": "file"}
            k1 = {"name": "liberty_fast", "abc_args": ["-fast"], "abc_ops": [], "abc_script": "file"}
            k2 = {
                "name": "boils_rewrite_balance",
                "abc_args": [],
                "abc_ops": ["rewrite", "balance"],
                "abc_script": "file",
            }
            c0 = evaluate_f1_abc(rtl=rtl, liberty=lib, knobs=k0, mem=mm)
            c1 = evaluate_f1_abc(rtl=rtl, liberty=lib, knobs=k1, mem=mm)
            c2 = evaluate_f1_abc(rtl=rtl, liberty=lib, knobs=k2, mem=mm)
            check(c0.status == "ok" and c1.status == "ok", "F1 default and fast prove equiv")
            check(c2.status == "ok", f"F1 rewrite+balance proves equiv ({c2.failure})")
            check(c0.qor.area_um2 and c1.qor.area_um2 and c2.qor.area_um2, "F1 reports mapped area")
            check(
                abs(float(c0.qor.area_um2) - 409.108) < 1.0,
                f"chip flatten-first teacher stays ~409.108, got {c0.qor.area_um2}",
            )
            check(
                abs(c0.qor.area_um2 - c1.qor.area_um2) > 1.0,
                f"default vs -fast is a real area move ({c0.qor.area_um2} vs {c1.qor.area_um2})",
            )
            check(
                (c2.artifacts or {}).get("n_cells", 0) > 100,
                f"rewrite+balance writes liberty cells, not $lut soup ({c2.artifacts})",
            )
            dest = tdir / "gcd_eqz.v"
            emit_gcd_variant(rtl, "eqz_or_reduce", dest)
            ka = {
                "name": "eqz_or_reduce",
                "module": "dpath",
                "extract": "eqz_or_reduce",
                "scope": "logic_cone",
                "abc_script": "file",
            }
            ca = evaluate_f1_abc(rtl=dest, liberty=lib, knobs=ka, mem=mm, level="architecture")
            check(ca.status == "ok", f"architecture eqz extract proves equiv ({ca.failure})")
            check(ca.level == "architecture", "extract is recorded on the architecture level")
            check(not (ca.artifacts or {}).get("mapped_hier_v"), "architecture extract stays flatten-first")
            kc = {
                "name": "boils_rewrite_balance",
                "abc_args": [],
                "abc_ops": ["rewrite", "balance"],
                "abc_script": "file",
                "scope": "logic_cone",
                "cone": "dpath",
                "cone_module": DPATH_MODULE,
            }
            cc = evaluate_f1_abc(rtl=rtl, liberty=lib, knobs=kc, mem=mm)
            check(cc.status == "ok", f"cone rewrite+balance proves equiv ({cc.failure})")
            hier_p = (cc.artifacts or {}).get("mapped_hier_v")
            check(hier_p and Path(hier_p).is_file(), "cone F1 writes mapped_hier.v")
            check(
                abs(float(cc.qor.area_um2) - float(c2.qor.area_um2)) > 1.0,
                f"cone ABC ≠ chip flatten-first rewrite+balance ({cc.qor.area_um2} vs {c2.qor.area_um2})",
            )
            from dse.fidelity import _f1_yscript

            kctrl = stamp_cone_knobs(dict(k2), "ctrl")
            ys_ctrl = _f1_yscript(rtl, "gcd", str(lib), "abc -liberty LIB -script boils", Path("/tmp/n.v"), Path("/tmp/h.v"), kctrl)
            check(f"cd {CTRL_MODULE}" in ys_ctrl, "ctrl-cone Yosys cds into GcdUnitCtrlRTL")
            check(
                ys_ctrl.split(f"cd {CTRL_MODULE}")[1].split("cd ..")[0].count("boils") >= 1,
                "ctrl cone is paid with the BOiLS script",
            )
            check(f"cd {DPATH_MODULE}" in ys_ctrl, "dpath stays in the leftover default-map when ctrl is paid")
            kct = dict(k2)
            kct.update({"scope": "logic_cone", "cone": "ctrl", "cone_module": CTRL_MODULE, "cone_modules": list(CTRL_CONE_MODULES)})
            cctrl = evaluate_f1_abc(rtl=rtl, liberty=lib, knobs=kct, mem=mm)
            check(cctrl.status == "ok", f"ctrl-cone rewrite+balance proves equiv ({cctrl.failure})")
            hier_c = (cctrl.artifacts or {}).get("mapped_hier_v")
            check(hier_c and Path(hier_c).is_file(), "ctrl-cone F1 writes mapped_hier.v")
            check(
                abs(float(cctrl.qor.area_um2) - 409.108) > 1.0,
                f"ctrl cone ≠ chip flatten-first teacher ({cctrl.qor.area_um2})",
            )
            check(
                abs(float(cctrl.qor.area_um2) - float(cc.qor.area_um2)) > 1.0,
                f"ctrl cone ≠ dpath cone ({cctrl.qor.area_um2} vs {cc.qor.area_um2})",
            )
            print(
                f"    F1 ctrl-cone {cctrl.qor.area_um2:.3f} vs dpath-cone {cc.qor.area_um2:.3f} "
                f"vs flatten {c2.qor.area_um2:.3f} µm²"
            )
            if sta_available():
                hsta = evaluate_sta(Path(hier_p))
                check(hsta.get("status") == "ok", f"OpenSTA on hier cone netlist ({hsta.get('reason')})")
                path = (hsta.get("path_start") or "") + " " + (hsta.get("path_end") or "")
                check("dpath/" in path.replace(".", "/"), f"hier STA path keeps dpath/, got {path}")
                hattr = attribute_sta(hsta)
                check(hattr["status"] == "READY", "hier STA attribution is READY without inherit")
                check("dpath" in (hattr.get("modules") or []), "hier STA attributes to dpath")
                print(f"    F3 hier STA {hsta.get('path_start')} → {hsta.get('path_end')} WNS={hsta.get('wns_ns')}")
                check(
                    (hsta.get("path_cells") or []) and "dpath/" in " ".join(hsta.get("path_cells") or []),
                    f"STA path lists hierarchical cells, got {hsta.get('path_cells')}",
                )
                check((hsta.get("path_nets") or []) and len(hsta["path_nets"]) >= 2, "STA path lists net hops")
                from dse.cell_space import next_drive, upsize_path_cells
                from dse.fidelity import evaluate_cell_size, evaluate_net_buffer
                from dse.net_space import buffer_path_nets

                check(next_drive("AND2_X1") == "AND2_X2", "Nangate drive ladder X1→X2")
                check(next_drive("NOR3_X4") is None, "NOR3_X8 is not a LEF master — no illegal size-up")
                check(next_drive("DFF_X2") is None, "DFF_X4 is not a LEF master — no illegal size-up")
                tiny = (
                    "module left(a,z);\n  input a; output z;\n"
                    "  NOR3_X1 _07_ (.A1(a), .ZN(z));\nendmodule\n"
                    "module right(a,z);\n  input a; output z;\n"
                    "  NOR3_X1 _07_ (.A1(a), .ZN(z));\nendmodule\n"
                    "module gcd(a,z);\n  input a; output z;\n"
                    "  left ctrl (.A(a), .Z(n1));\n  right dpath (.A(n1), .Z(z));\nendmodule\n"
                )
                scoped = upsize_path_cells(tiny, ["ctrl/_07_"], top="gcd")
                check(scoped["n_changed"] == 1, f"module-scoped upsize hits one _07_, got {scoped['changed']}")
                check("NOR3_X2 _07_" in scoped["text"], "ctrl _07_ became NOR3_X2")
                check(scoped["text"].count("NOR3_X1 _07_") == 1, "dpath _07_ stays X1")
                cc.artifacts = dict(cc.artifacts or {})
                if hsta.get("path_cells"):
                    cc.attr = dict(cc.attr or {})
                    mm.add(
                        Candidate(
                            id="f3hier",
                            design_id="gcd",
                            parent_id=cc.id,
                            level="logic",
                            knobs={"source": "f3_opensta_ideal", "parent_id": cc.id, "parent_name": cc.knobs.get("name")},
                            knobs_fp="f3hier",
                            rtl_fp="x",
                            netlist_fp="y",
                            fidelity="F3",
                            qor=QoR(wns_cost=0.21, fidelity="F3"),
                            cost_s=0.1,
                            artifacts=hsta,
                            attr=hattr,
                        )
                    )
                csz = evaluate_cell_size(cc, mm, cells=list(hsta.get("path_cells") or []))
                check(csz is not None and csz.status == "ok", f"cell-local size-up STA ({csz.failure if csz else None})")
                check(csz.level == "cell", "size-up is recorded on the cell level")
                check((csz.artifacts or {}).get("n_changed", 0) >= 1, f"path cells were resized, {csz.artifacts}")
                check(
                    csz.qor.area_um2 is not None
                    and abs(float(csz.qor.area_um2) - float(cc.qor.area_um2 or 0)) > 0.1,
                    f"cell size-up must move area ({csz.qor.area_um2} vs {cc.qor.area_um2})",
                )
                print(
                    f"    cell size-up n={csz.artifacts.get('n_changed')} "
                    f"WNS={csz.artifacts.get('wns_ns')} vs hier {hsta.get('wns_ns')} "
                    f"area={csz.qor.area_um2}"
                )
                tiny_net = (
                    "module gcd(clk);\n  wire _118_;\n  wire _119_;\n"
                    "  XOR2_X1 _586_ (\n    .A(_063_),\n    .B(_047_),\n    .Z(_118_)\n  );\n"
                    "  AOI21_X1 _587_ (\n    .A(_118_),\n    .B1(_087_),\n    .B2(_056_),\n    .ZN(_119_)\n  );\n"
                    "endmodule\n"
                )
                nins = buffer_path_nets(tiny_net, ["_586_->_587_"])
                check(nins["n_changed"] == 1, f"tiny hop gets one BUF, got {nins['changed']}")
                check("BUF_X2 netbuf_0" in nins["text"], "tiny hop inserts BUF_X2")
                check(".A(netbuf_w0)" in nins["text"], "tiny hop retargets the sink pin")
                sta_flat = evaluate_sta(Path(c0.artifacts["mapped_v"]))
                nb = evaluate_net_buffer(c0, mm, hops=list(sta_flat.get("path_nets") or []))
                check(nb is not None and nb.status == "ok", f"net-local BUF STA ({nb.failure if nb else None})")
                check(nb.level == "net", "buffer insert is recorded on the net level")
                check((nb.artifacts or {}).get("n_changed", 0) >= 1, f"path hops were buffered, {nb.artifacts.get('n_changed')}")
                check("BUF_X2" in Path(nb.artifacts["mapped_v"]).read_text(), "buffered netlist contains BUF_X2")
                check(
                    sta_flat.get("wns_ns") is not None
                    and nb.artifacts.get("wns_ns") is not None
                    and abs(float(nb.artifacts["wns_ns"]) - float(sta_flat["wns_ns"])) >= 0.01,
                    f"net BUF WNS {nb.artifacts.get('wns_ns')} must move vs {sta_flat.get('wns_ns')}",
                )
                print(
                    f"    net BUF n={nb.artifacts.get('n_changed')} "
                    f"WNS={nb.artifacts.get('wns_ns')} vs flatten {sta_flat.get('wns_ns')} "
                    f"area={nb.qor.area_um2}"
                )
                from dse.fidelity import evaluate_net_port_buffer
                from dse.net_space import buffer_port_nets, hop_is_cross_module

                hier_hops = [h for h in (hsta.get("path_nets") or []) if hop_is_cross_module(h)]
                check(hier_hops, f"hier STA path has a ctrl↔dpath hop, got {hsta.get('path_nets')}")
                phier = buffer_port_nets(Path(hier_p).read_text(), list(hsta.get("path_nets") or []))
                check(phier["n_changed"] >= 1, f"live hier path gets a port BUF, hops={hier_hops} changed={phier['changed']}")
                check("portbuf_0" in phier["text"], "live hier inserts portbuf_0 at the parent")
                ret = [c for c in phier["changed"] if "a_mux" in str(c.get("hop"))]
                check(ret, f"return hop a_mux_sel[0] is buffered, changed={phier['changed']}")
                check(ret[0].get("bit") == 0 or ret[0].get("splice"), f"return hop splices bit 0, got {ret[0]}")
                npb = evaluate_net_port_buffer(cc, mm, hops=list(hsta.get("path_nets") or []))
                check(npb is not None and npb.status == "ok", f"port-net BUF STA ({npb.failure if npb else None})")
                check((npb.knobs or {}).get("source") == "net_buffer_port", "port-net uses net_buffer_port")
                check((npb.knobs or {}).get("scope") == "port", "port-net knobs name scope=port")
                check((npb.knobs or {}).get("cross_module") == 1, "port-net knobs are not intra-module")
                check((npb.artifacts or {}).get("n_changed", 0) >= 1, f"port hops were buffered, {npb.artifacts.get('n_changed')}")
                check(
                    npb.qor.area_um2 is not None
                    and (
                        abs(float(npb.qor.area_um2) - float(cc.qor.area_um2 or 0)) > 0.05
                        or (
                            npb.artifacts.get("wns_ns") is not None
                            and hsta.get("wns_ns") is not None
                            and abs(float(npb.artifacts["wns_ns"]) - float(hsta["wns_ns"])) >= 0.001
                        )
                    ),
                    f"port-net must move area or WNS ({npb.qor.area_um2}/{npb.artifacts.get('wns_ns')} vs {cc.qor.area_um2}/{hsta.get('wns_ns')})",
                )
                print(
                    f"    port-net BUF n={npb.artifacts.get('n_changed')} "
                    f"WNS={npb.artifacts.get('wns_ns')} vs hier {hsta.get('wns_ns')} "
                    f"area={npb.qor.area_um2} hops={hier_hops}"
                )
                from dse.fidelity import evaluate_f5_local
                from dse.openroad_f2 import f5_available as f5_ok_local
                from dse.surrogate import residual_f3_to_f5_local

                if f5_ok_local() and (nb.artifacts or {}).get("mapped_v"):
                    floc = evaluate_f5_local(nb, mm)
                    check(floc is not None and floc.status == "ok", f"F5-local SPEF ({floc.failure if floc else None})")
                    check((floc.knobs or {}).get("source") == "f5_openroad_local", "local SPEF uses f5_openroad_local")
                    check((floc.knobs or {}).get("host_level") == "net", "local SPEF names the net host")
                    check(floc.artifacts.get("clock") == "ideal", "F5-local keeps the clock ideal")
                    check(
                        (nb.artifacts or {}).get("spef_local")
                        and Path(nb.artifacts["spef_local"]).is_file(),
                        "local SPEF is stored on the net parent, not as a reused F1 SPEF",
                    )
                    check(
                        floc.artifacts.get("wns_ns") is not None
                        and nb.artifacts.get("wns_ns") is not None
                        and abs(float(floc.artifacts["wns_ns"]) - float(nb.artifacts["wns_ns"])) >= 0.01,
                        f"local SPEF WNS {floc.artifacts.get('wns_ns')} must differ from ideal {nb.artifacts.get('wns_ns')}",
                    )
                    res = residual_f3_to_f5_local(list(mm.all()))
                    check((res.get("n") or 0) >= 1, f"F3→F5-local residual has a pair, got {res}")
                    check(res.get("mean_residual_ns") is not None, "F3→F5-local residual reports a mean")
                    print(
                        f"    F5-local SPEF WNS={floc.artifacts.get('wns_ns')} vs ideal "
                        f"{nb.artifacts.get('wns_ns')} residual={res.get('mean_residual_ns')} "
                        f"({floc.cost_s:.2f}s)"
                    )
            cs = evaluate_f1_synth(rtl=rtl, liberty=lib, mem=mm)
            check(cs.status == "ok", f"synthesis F1 abc_speed proves equiv ({cs.failure})")
            check(cs.level == "synthesis", "ORFS abc_speed is recorded on the synthesis level")
            check(not cs.knobs.get("abc_ops"), "synthesis F1 does not carry abc_ops")
            check(
                abs(float(cs.qor.area_um2) - 409.108) > 1.0,
                f"synthesis abc_speed ≠ liberty_default 409.108, got {cs.qor.area_um2}",
            )
            check(
                knobs_fp("synthesis", cs.knobs) != knobs_fp("logic", k0),
                "synthesis F1 fingerprint is not the logic teacher",
            )
            print(
                f"    F1 default {c0.qor.area_um2:.3f} vs fast {c1.qor.area_um2:.3f} vs "
                f"rewrite+balance {c2.qor.area_um2:.3f} vs eqz-arch {ca.qor.area_um2:.3f} "
                f"vs cone-rb {cc.qor.area_um2:.3f} vs ctrl-cone {cctrl.qor.area_um2:.3f} "
                f"vs synth-speed {cs.qor.area_um2:.3f} µm²"
            )
        else:
            print("    skip F1 yosys (no liberty)")
    else:
        print("    skip F1 yosys")
