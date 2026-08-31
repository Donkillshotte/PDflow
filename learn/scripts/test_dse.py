#!/usr/bin/env python3
"""DSE contracts: layered knobs, Pareto, e-graph, SSK-GP, attribution, F1 equiv."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn"))

from dse.abc_space import CATALOG, BOILS_STD_OPS, abc_script_plus, min_kernel_to_seen, subsequence_kernel
from dse.arch_space import (
    CTRL_CONE_MODULES,
    CTRL_MODULE,
    DPATH_CONE_MODULES,
    DPATH_MODULE,
    emit_gcd_variant,
    is_cone_abc,
    leftover_modules,
    plan_dpath_extracts,
    stamp_cone_knobs,
)
from dse.attribute import attribute_dynamic_ir, local_scope
from dse.boils import ei_min, gp_predict, propose_logic_boils, should_pay_f1
from dse.egraph import gcd_dpath_egraph
from dse.fingerprint import knobs_fp
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR, dominates, pareto_front, wns_cost_from_slack_ns, dominates_with_fidelity, pareto_front_gated
from dse.mo import ehvi_2d, hypervolume_2d
from dse.physical_space import PHYSICAL_CATALOG, gpl_density, next_catalog_spec, rudy_congestion
from dse.pdn_space import (
    EM_STRAP_CATALOG,
    PDN_CATALOG,
    STATIC_MESH_CATALOG,
    STATIC_PDN_CATALOG,
    STATIC_STRAP_CATALOG,
    next_em_strap_spec,
    next_pdn_spec,
    next_winning_ir_pdn_spec,
    next_static_mesh_spec,
    next_static_pdn_spec,
    next_static_strap_spec,
)


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    a = QoR(area_um2=10, dynamic_ir_mv=40)
    b = QoR(area_um2=12, dynamic_ir_mv=40)
    c = QoR(area_um2=11, dynamic_ir_mv=30)
    check(dominates(a, b), "smaller area dominates equal IR")
    check(not dominates(b, a), "worse area does not dominate")
    check(not dominates(a, c), "trade-off is not domination")
    check(not dominates(c, a), "the other side of the trade-off neither")
    gap = QoR(area_um2=1.0)
    only_ir = QoR(dynamic_ir_mv=1.0)
    check(not dominates(gap, only_ir), "disjoint metrics do not dominate")
    rich = QoR(area_um2=12, dynamic_ir_mv=50)
    ir_only = QoR(dynamic_ir_mv=40)
    check(not dominates(ir_only, rich), "sparser F4 must not dominate a richer F2 point")
    check(wns_cost_from_slack_ns(0.04) == -0.04, "positive slack is a lower wns_cost")
    front = pareto_front([("a", a), ("b", b), ("c", c)])
    check(set(front) == {"a", "c"}, f"Pareto is a and c, got {front}")
    f1_wns = QoR(area_um2=10, wns_cost=0.1, fidelity="F1")
    f5_wns = QoR(area_um2=10, wns_cost=1.0, fidelity="F5")
    check(not dominates_with_fidelity(f1_wns, f5_wns), "F1 better WNS does not dominate F5")
    check(dominates_with_fidelity(QoR(area_um2=10, wns_cost=1.0, fidelity="F5"), QoR(area_um2=10, wns_cost=1.0, fidelity="F1")), "F5 dominates F1 at equal axes")
    check(dominates_with_fidelity(QoR(area_um2=8, fidelity="F1"), QoR(area_um2=12, fidelity="F5")), "area stays comparable across fidelity")
    check(set(pareto_front_gated([("f1", f1_wns), ("f5", f5_wns)])) == {"f1", "f5"}, "gated front keeps F1 and F5")

    tmp = Path(tempfile.mkdtemp(prefix="dse-mem-")) / "m.jsonl"
    mem = DesignMemory(tmp)
    parent = mem.add(
        Candidate(
            id="p1",
            design_id="gcd",
            parent_id=None,
            level="physical",
            knobs={"coreUtilization": 35},
            knobs_fp=knobs_fp("physical", {"coreUtilization": 35}),
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.298, fidelity="F4"),
            cost_s=0.0,
        )
    )
    child = mem.add(
        Candidate(
            id="c1",
            design_id="gcd",
            parent_id=parent.id,
            level="logic",
            knobs={"name": "liberty_default", "abc_ops": []},
            knobs_fp=knobs_fp("logic", {"name": "liberty_default", "abc_ops": []}),
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=409.1, fidelity="F1"),
            cost_s=1.0,
        )
    )
    mem2 = DesignMemory(tmp)
    check(len(mem2) == 2, "memory reloads two rows")
    check(mem2.get("c1").parent_id == "p1", "parent/child survives reload")
    check(child.level != parent.level, "child stays on a different level")

    logic_fp = knobs_fp("logic", {"abc_ops": ["rewrite"]})
    phys_fp = knobs_fp("physical", {"abc_ops": ["rewrite"], "coreUtilization": 35})
    check(logic_fp != phys_fp, "same ABC ops + util is not one flattened fingerprint")
    check("rewrite" in BOILS_STD_OPS, "BOiLS standard alphabet includes rewrite")
    check(len(CATALOG) >= 4, "ABC catalog has ≥4 named sequences")
    check(subsequence_kernel(["rewrite", "balance"], ["rewrite", "balance"]) > 0.99, "identical seq kernel ≈1")
    check(
        min_kernel_to_seen(["refactor"], [["rewrite", "balance"]])
        < subsequence_kernel(["rewrite", "balance"], ["rewrite", "balance"]),
        "unseen op is more diverse than a repeat",
    )
    plus = abc_script_plus(["rewrite", "rewrite -z", "balance"])
    check(plus is not None and "rewrite,-z" in plus, f"Yosys + form uses commas for spaces: {plus}")
    from dse.abc_space import write_abc_script

    abc_tmp = Path(tempfile.mkdtemp(prefix="dse-abc-")) / "m.abc"
    write_abc_script(["rewrite", "balance"], abc_tmp, map_liberty=True)
    check("map" in abc_tmp.read_text().splitlines()[-1], "liberty ABC script ends with map")

    eg, roots = gcd_dpath_egraph()
    check(eg.has_op(roots["sub"], "add"), "e-graph: sub ≡ add(inc(not))")
    check(eg.has_op(roots["eqz"], "not"), "e-graph: eqz ≡ not(or-reduce)")
    check(eg.has_op(roots["lt"], "borrow"), "e-graph: lt ≡ unsigned borrow")
    gop, gcost = eg.extract_greedy(roots["sub"])
    check(gop.op == "sub", f"greedy extract prefers native sub, got {gop.op}")
    check(gcost <= 16.0 + 1e-9, "native sub is cheaper than add+inc+not")
    _eg, _r, extracts, stats = plan_dpath_extracts()
    check(
        set(extracts) >= {"sub_twos_complement", "eqz_or_reduce", "lt_borrow"},
        f"named extracts discovered, got {extracts}",
    )
    check(stats["n_eclasses"] >= 3, "e-graph has multiple e-classes")
    soft = eg.extract_softmax(roots["sub"])
    check(soft.get("expected") is not None and soft.get("entropy") is not None, "SmoothE-inspired softmax extract")

    rtl = _ROOT / "learn/flowlab/gcd.v"
    if rtl.is_file():
        dest = Path(tempfile.mkdtemp(prefix="dse-rtl-")) / "gcd.v"
        meta = emit_gcd_variant(rtl, "eqz_or_reduce", dest)
        check(meta["cone"] == "dpath", "extract stays on the dpath cone")
        check("~(|in_)" in dest.read_text(), "eqz extract rewrote ZeroComparator")
        check("GcdUnitCtrlRTL" in dest.read_text(), "ctrl module is untouched")

    mu_seen, std_seen = gp_predict(
        [["rewrite", "balance"], ["balance"]],
        [200.0, 400.0],
        [["rewrite", "balance"]],
    )[0]
    mu_new, std_new = gp_predict(
        [["rewrite", "balance"], ["balance"]],
        [200.0, 400.0],
        [["refactor", "resub"]],
    )[0]
    check(std_new + 1e-9 >= std_seen * 0.5, "SSK-GP: unseen sequence is not overconfident")
    check(ei_min(250.0, 40.0, 200.0) < ei_min(180.0, 40.0, 200.0), "EI prefers a better mean")
    pay, _ = should_pay_f1({"mean": 900.0, "std": 5.0, "n": 5}, 200.0)
    check(not pay, "F0 skip when optimistic draw is still worse than incumbent")
    pay0, _ = should_pay_f1({"mean": 900.0, "std": 5.0, "n": 1}, 200.0)
    check(pay0, "n<3 still pays F1")
    pay_mo, _ = should_pay_f1(
        {"mean": 900.0, "std": 5.0, "n": 5},
        200.0,
        {"mean": 0.10, "std": 0.01},
        0.52,
    )
    check(pay_mo, "optimistic worse area but better WNS still pays F1")
    pay_dom, _ = should_pay_f1(
        {"mean": 900.0, "std": 5.0, "n": 5},
        200.0,
        {"mean": 0.80, "std": 0.01},
        0.52,
    )
    check(not pay_dom, "optimistic dominated on area and WNS skips F1")

    hv = hypervolume_2d([(1.0, 5.0), (3.0, 2.0)], (10.0, 10.0))
    hv_dom = hypervolume_2d([(1.0, 5.0), (3.0, 2.0), (4.0, 6.0)], (10.0, 10.0))
    check(hv > 50.0, f"2-D HV of a known front, got {hv}")
    check(abs(hv - hv_dom) < 1e-9, "dominated point does not change HV")
    front_aw = [(400.0, 0.52), (410.0, 0.40)]
    ehvi_good = ehvi_2d(390.0, 5.0, 0.38, 0.02, front_aw, seed=1)
    ehvi_bad = ehvi_2d(430.0, 5.0, 0.70, 0.02, front_aw, seed=1)
    check(ehvi_good > ehvi_bad, f"EHVI prefers a point that can grow the front ({ehvi_good} vs {ehvi_bad})")

    check(len(PHYSICAL_CATALOG) >= 3, "physical catalog has several AutoDMP-shaped points")
    check(rudy_congestion(45, 0.3) > rudy_congestion(30, 0.1), "higher util/density → higher proxy congestion")
    check(abs(gpl_density(35, 0.2) - 0.55) < 1e-9, "ORFS place density = util/100 + addon")
    check(next_catalog_spec(mem).get("name") == "util30_den010", "empty memory proposes first catalog point")
    check(len(PDN_CATALOG) >= 2, "PDN catalog has more than the gold knobs")
    check(next_pdn_spec(mem).get("name") == "decap_200f", "empty PDN memory proposes extra decap first")
    check(all(s["name"] != "pkg_r_25m" for s in PDN_CATALOG), "pkg_r is not flattened into the Dynamic IR catalog")
    check(STATIC_PDN_CATALOG[0]["name"] == "pkg_r_25m", "static-IR catalog starts with pkg_r_25m")
    check(all(s["name"] != "bumps_80" for s in PDN_CATALOG), "bump pitch is not flattened into the Dynamic IR catalog")
    check(all(s["name"] != "bumps_80" for s in STATIC_PDN_CATALOG), "bump pitch is not flattened into the pkg_r catalog")
    check(STATIC_MESH_CATALOG[0]["name"] == "bumps_80", "static-IR mesh catalog starts with bumps_80")
    check(all(s["name"] != "m4_pitch_8" for s in PDN_CATALOG), "metal4 pitch is not flattened into the Dynamic IR catalog")
    check(all(s["name"] != "m4_pitch_8" for s in STATIC_PDN_CATALOG), "metal4 pitch is not flattened into the pkg_r catalog")
    check(all(s["name"] != "m4_pitch_8" for s in STATIC_MESH_CATALOG), "metal4 pitch is not flattened into the bump catalog")
    check(STATIC_STRAP_CATALOG[0]["name"] == "m4_pitch_8", "static-IR strap catalog starts with m4_pitch_8")
    check(all(s["name"] != "m4_width_96" for s in STATIC_STRAP_CATALOG), "EM width is not flattened into the pitch catalog")
    check(all(s["name"] != "m4_width_96" for s in PDN_CATALOG), "EM width is not flattened into the Dynamic IR catalog")
    check(EM_STRAP_CATALOG[0]["name"] == "m4_width_96", "EM catalog starts with m4_width_96")
    check(
        knobs_fp("pdn", {"pkg_l": 2e-10, "c_decap": 50e-15})
        != knobs_fp("logic", {"pkg_l": 2e-10, "c_decap": 50e-15}),
        "PDN knobs are not flattened into the logic fingerprint",
    )
    check(
        knobs_fp("physical", {"coreUtilization": 35})
        != knobs_fp("logic", {"coreUtilization": 35}),
        "level is part of the knob fingerprint",
    )

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
            and abs(float(cts_sta["wns_ns"]) - float(spef_sta["wns_ns"])) >= 0.01,
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

    from dse.f4_oracle import GOLD_MV, available as f4_ok, solve_f4
    from dse.openroad_f2 import extract_available, extract_pdn
    from dse.pdn_space import next_pdn_spec as pdn_next
    from dse.fingerprint import knobs_fp as kfp

    check(
        kfp("pdn", {"pkg_l": 2e-10, "c_decap": 50e-15, "extract_id": "finish"})
        != kfp("pdn", {"pkg_l": 2e-10, "c_decap": 50e-15, "extract_id": "cand1"}),
        "same PDN knobs on a new extract is a different fingerprint",
    )
    mem_pdn = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-pdn-")) / "p.jsonl")
    mem_pdn.add(
        Candidate(
            id="fin",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_solver_a", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15, "extract_id": "finish"},
            knobs_fp="x",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=21.8, fidelity="F4"),
            cost_s=1.0,
        )
    )
    check(pdn_next(mem_pdn).get("name") == "pkg_l_100p", "finish catalog advances past decap_200f")
    check(pdn_next(mem_pdn, extract_id="cand1").get("name") == "decap_200f", "new extract still proposes decap")
    mem_amg = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-amg-")) / "a.jsonl")
    mem_amg.add(
        Candidate(
            id="amg0",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={
                "source": "f4_solver_amg",
                "name": "amg_residual",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 50e-15,
                "extract_id": "finish",
            },
            knobs_fp="amg",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.3, fidelity="F4"),
            cost_s=1.0,
        )
    )
    check(pdn_next(mem_amg).get("name") == "decap_200f", "AMG residual does not consume the PDN catalog")
    mem_ras = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-ras-")) / "r.jsonl")
    mem_ras.add(
        Candidate(
            id="ras0",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={
                "source": "f4_solver_ras",
                "name": "ras_residual",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 50e-15,
                "extract_id": "finish",
            },
            knobs_fp="ras",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.3, fidelity="F4"),
            cost_s=1.0,
        )
    )
    check(pdn_next(mem_ras).get("name") == "decap_200f", "RAS residual does not consume the PDN catalog")
    mem_kry = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-kry-")) / "k.jsonl")
    mem_kry.add(
        Candidate(
            id="kry0",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={
                "source": "f4_solver_krylov",
                "name": "krylov_residual",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 50e-15,
                "extract_id": "finish",
            },
            knobs_fp="kry",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.3, fidelity="F4"),
            cost_s=1.0,
        )
    )
    check(pdn_next(mem_kry).get("name") == "decap_200f", "Krylov residual does not consume the PDN catalog")
    from dse.acquire import (
        should_pay_f1_synth,
        should_pay_f4_krylov,
        should_pay_f4_ras,
        should_pay_ctrl_cone,
        should_pay_f5_cts,
        should_pay_f5_local,
        should_pay_f5_port,
        should_pay_port_steer,
        should_pay_net_buffer,
        should_pay_net_port,
        should_pay_residual_steer,
        should_pay_ir_steer,
        should_pay_host_ir_steer,
        should_pay_f4_scale,
        should_pay_f4_scale_win,
        should_pay_f4_scale_champ,
        should_pay_f4_amg_champ,
        champ_mf_n,
        should_pay_f4_ras_champ,
        should_pay_f4_krylov_champ,
        should_pay_static_ir_steer,
        should_pay_static_mesh,
        should_pay_static_straps,
        should_pay_em_straps,
        should_pay_winning_ir_catalog,
        should_pay_ir_cell_champ,
        should_pay_ir_cell_champ_extract,
        should_pay_ir_cell_champ_pdn,
        should_pay_ir_cell_champ_cone,
        should_pay_ir_cell_champ_cone_extract,
        should_pay_ir_cell_champ_cone_pdn,
        leftover_cone_region_next,
        winning_ir_region_next,
        should_pay_ir_cell_champ_cone_region,
        should_pay_ir_cell_champ_cone_region_pdn,
        should_pay_winning_ir_region,
        should_pay_winning_ir_region_pdn,
        should_pay_winning_ir_region_cell,
        should_pay_winning_ir_region_cell_extract,
        should_pay_winning_ir_region_cell_pdn,
        should_pay_winning_ir_region_cell_leftover,
        should_pay_winning_ir_region_cell_leftover_extract,
        should_pay_winning_ir_region_cell_leftover_pdn,
        should_pay_winning_ir_region_cell_leftover2,
        should_pay_winning_ir_region_cell_leftover2_extract,
        should_pay_winning_ir_region_cell_leftover2_pdn,
        should_pay_winning_ir_region_cell_leftover2_catalog,
        iscale_champ_sta,
        should_pay_ir_cell,
        should_pay_ir_cell_extract,
        should_pay_ir_cell_pdn,
        should_pay_ir_cell_region,
        should_pay_ir_cell_region_pdn,
        should_pay_host_arrivals,
        should_pay_f4_host_extract,
        should_pay_f4_host_region,
    )

    mem_pay = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-pay-")) / "p.jsonl")
    pay_s0, _ = should_pay_f1_synth(mem_pay, budget_left=80, n_f1=0)
    check(not pay_s0, "synthesis F1 waits for a teacher")
    mem_pay.add(
        Candidate(
            id="t0",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "liberty_default"},
            knobs_fp="t0",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=409.108, fidelity="F1"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay_s1, why_s1 = should_pay_f1_synth(mem_pay, budget_left=80, n_f1=1, f1_max=6)
    check(pay_s1, f"synthesis F1 is paid after teacher ({why_s1})")
    pay_ctrl0, why_ctrl0 = should_pay_ctrl_cone(mem_pay, budget_left=80)
    check(not pay_ctrl0, f"ctrl cone waits for the dpath cone teacher ({why_ctrl0})")
    mem_pay.add(
        Candidate(
            id="dpathc",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "boils_rewrite_balance", "cone": "dpath", "cone_module": DPATH_MODULE},
            knobs_fp="dpathc",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=554.344, fidelity="F1"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay_ctrl1, why_ctrl1 = should_pay_ctrl_cone(mem_pay, budget_left=80)
    check(not pay_ctrl1, f"ctrl cone waits for attributed ctrl hops ({why_ctrl1})")
    mem_pay.add(
        Candidate(
            id="f3ctrl",
            design_id="gcd",
            parent_id="dpathc",
            level="logic",
            knobs={"source": "f3_opensta_ideal", "parent_id": "dpathc"},
            knobs_fp="f3ctrl",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(wns_cost=0.21, fidelity="F3"),
            cost_s=0.1,
            status="ok",
            artifacts={"path_cells": ["dpath/b_reg/_127_", "ctrl/_07_", "dpath/a_reg/_112_"]},
            attr={"kind": "sta_path", "modules": ["dpath", "ctrl"], "cells": ["ctrl/_07_"]},
        )
    )
    pay_ctrl2, why_ctrl2 = should_pay_ctrl_cone(mem_pay, budget_left=80)
    check(pay_ctrl2, f"ctrl cone is paid after dpath cone + ctrl hops ({why_ctrl2})")
    pay_ctrl3, why_ctrl3 = should_pay_ctrl_cone(mem_pay, budget_left=80, n_ctrl=1)
    check(not pay_ctrl3, f"ctrl cone is a single shot ({why_ctrl3})")
    pay_r0, why_r0 = should_pay_f4_ras(mem_pay, budget_left=80, n_ras=0)
    check(not pay_r0, f"RAS waits for AMG ({why_r0})")
    mem_pay.add(
        Candidate(
            id="amg1",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_solver_amg", "extract_id": "finish"},
            knobs_fp="amg1",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.3, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay_r1, why_r1 = should_pay_f4_ras(mem_pay, budget_left=80, n_ras=0, variant="flowlab")
    check(pay_r1 or "cached finish" in why_r1 or "already" in why_r1, f"RAS acquire is well-formed ({why_r1})")
    pay_k0, why_k0 = should_pay_f4_krylov(mem_pay, budget_left=80, n_krylov=0)
    check(not pay_k0, f"Krylov waits for RAS ({why_k0})")
    mem_pay.add(
        Candidate(
            id="ras1",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_solver_ras", "extract_id": "finish"},
            knobs_fp="ras1",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.3, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay_k1, why_k1 = should_pay_f4_krylov(mem_pay, budget_left=80, n_krylov=0, variant="flowlab")
    check(pay_k1 or "cached finish" in why_k1 or "already" in why_k1, f"Krylov acquire is well-formed ({why_k1})")
    pay_c0, why_c0 = should_pay_f5_cts(mem_pay, budget_left=80, n_f5_cts=0)
    check(not pay_c0, f"CTS waits for F5-lite ({why_c0})")
    mem_pay.add(
        Candidate(
            id="f5lite",
            design_id="gcd",
            parent_id="t0",
            level="routing",
            knobs={"source": "f5_openroad_drt_rcx", "clock": "ideal"},
            knobs_fp="f5lite",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.64, fidelity="F5"),
            cost_s=1.0,
            status="ok",
        )
    )
    if mapped_ok.is_file():
        t0c = next(c for c in mem_pay.all() if c.id == "t0")
        t0c.artifacts = dict(t0c.artifacts or {})
        t0c.artifacts["mapped_v"] = str(mapped_ok)
        mem_pay.touch(t0c)
        pay_c1, why_c1 = should_pay_f5_cts(mem_pay, budget_left=80, n_f5_cts=0)
        check(pay_c1, f"CTS is paid after F5-lite ({why_c1})")
        pay_c2, why_c2 = should_pay_f5_cts(mem_pay, budget_left=80, n_f5_cts=1)
        check(not pay_c2, f"CTS is a single shot ({why_c2})")
    pay_n0, why_n0 = should_pay_net_buffer(mem_pay, budget_left=80, n_net=0)
    check(not pay_n0, f"net BUF waits for attributed hops ({why_n0})")
    mem_pay.add(
        Candidate(
            id="f3nets",
            design_id="gcd",
            parent_id="t0",
            level="logic",
            knobs={"source": "f3_opensta_ideal", "parent_id": "t0"},
            knobs_fp="f3nets",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(wns_cost=0.52, fidelity="F3"),
            cost_s=0.1,
            status="ok",
            artifacts={"path_nets": ["_586_->_587_", "_587_->_588_"]},
        )
    )
    pay_n1, why_n1 = should_pay_net_buffer(mem_pay, budget_left=80, n_net=0)
    check(pay_n1, f"net BUF is paid after path hops ({why_n1})")
    pay_n2, why_n2 = should_pay_net_buffer(mem_pay, budget_left=80, n_net=1)
    check(not pay_n2, f"net BUF is a single shot ({why_n2})")
    pay_p0, why_p0 = should_pay_net_port(mem_pay, budget_left=80, n_net=0, n_port=0)
    check(not pay_p0, f"port-net waits for the intra-module net shot ({why_p0})")
    pay_p1, why_p1 = should_pay_net_port(mem_pay, budget_left=80, n_net=1, n_port=0)
    check(not pay_p1, f"port-net waits for cross-module hops ({why_p1})")
    pay_l0, why_l0 = should_pay_f5_local(mem_pay, budget_left=80, n_f5_local=0)
    check(not pay_l0, f"F5-local waits for a cell/net host ({why_l0})")
    if mapped_ok.is_file():
        mem_pay.add(
            Candidate(
                id="net1",
                design_id="gcd",
                parent_id="t0",
                level="net",
                knobs={"source": "net_buffer", "hops": ["_586_->_587_"]},
                knobs_fp="net1",
                rtl_fp="x",
                netlist_fp="y",
                fidelity="F3",
                qor=QoR(wns_cost=0.60, fidelity="F3"),
                cost_s=0.2,
                status="ok",
                artifacts={"mapped_v": str(mapped_ok), "wns_ns": -0.60},
            )
        )
        pay_l1, why_l1 = should_pay_f5_local(mem_pay, budget_left=80, n_f5_local=0)
        check(pay_l1, f"F5-local is paid after F5-lite + net host ({why_l1})")
        pay_l2, why_l2 = should_pay_f5_local(mem_pay, budget_left=80, n_f5_local=1)
        check(not pay_l2, f"F5-local is a single shot ({why_l2})")
        mem_pay.add(
            Candidate(
                id="f3cross",
                design_id="gcd",
                parent_id="t0",
                level="logic",
                knobs={"source": "f3_opensta_ideal", "parent_id": "t0"},
                knobs_fp="f3cross",
                rtl_fp="x",
                netlist_fp="y",
                fidelity="F3",
                qor=QoR(wns_cost=0.21, fidelity="F3"),
                cost_s=0.1,
                status="ok",
                artifacts={"path_nets": ["dpath/a_lt_b/_194_->ctrl/_06_", "ctrl/_12_->dpath/a_mux/_40_"]},
            )
        )
        pay_p2, why_p2 = should_pay_net_port(mem_pay, budget_left=80, n_net=1, n_port=0)
        check(pay_p2, f"port-net is paid after intra-module net + crossing hops ({why_p2})")
        pay_p3, why_p3 = should_pay_net_port(mem_pay, budget_left=80, n_net=1, n_port=1)
        check(not pay_p3, f"port-net is a single shot ({why_p3})")
        pay_fp0, why_fp0 = should_pay_f5_port(mem_pay, budget_left=80, n_f5_port=0)
        check(not pay_fp0, f"F5-port waits for a port-net host ({why_fp0})")
        mem_pay.add(
            Candidate(
                id="porth",
                design_id="gcd",
                parent_id="t0",
                level="net",
                knobs={"source": "net_buffer_port", "scope": "port", "cross_module": 1},
                knobs_fp="porth",
                rtl_fp="x",
                netlist_fp="y",
                fidelity="F3",
                qor=QoR(wns_cost=0.23, fidelity="F3"),
                cost_s=0.2,
                status="ok",
                artifacts={"mapped_v": str(mapped_ok), "wns_ns": -0.228},
            )
        )
        from dse.acquire import local_hosts

        check(
            all((c.knobs or {}).get("source") != "net_buffer_port" for c in local_hosts(mem_pay)),
            "port-net host is not flattened into the intra-module F5-local host list",
        )
        pay_fp1, why_fp1 = should_pay_f5_port(mem_pay, budget_left=80, n_f5_port=0)
        check(pay_fp1, f"F5-port is paid after the port-net host ({why_fp1})")
        pay_fp2, why_fp2 = should_pay_f5_port(mem_pay, budget_left=80, n_f5_port=1)
        check(not pay_fp2, f"F5-port is a single shot ({why_fp2})")
        pay_ps0, why_ps0 = should_pay_port_steer(mem_pay, budget_left=80, steer=None)
        check(not pay_ps0, f"port-steer waits for an F5-port residual ({why_ps0})")
        from dse.acquire import _attributed_cross_module_nets

        mem_pay.add(
            Candidate(
                id="f3later",
                design_id="gcd",
                parent_id="t0",
                level="logic",
                knobs={"source": "f3_opensta_ideal", "parent_id": "t0"},
                knobs_fp="f3later",
                rtl_fp="x",
                netlist_fp="y",
                fidelity="F3",
                qor=QoR(wns_cost=0.20, fidelity="F3"),
                cost_s=0.1,
                status="ok",
                artifacts={"path_nets": ["dpath/b_reg/_49_->dpath/sub/_125_", "dpath/sub/_179_->dpath/a_mux/_084_"]},
            )
        )
        picked = _attributed_cross_module_nets(mem_pay)
        check(
            any(h.startswith("dpath/") and "->ctrl/" in h for h in picked),
            f"port-net acquire prefers ctrl↔dpath over later submodule hops, got {picked}",
        )

    from dse.active import order_local_hosts, steer_from_residual
    from dse.surrogate import residual_f3_to_f5_lite

    mem_al = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-al-")) / "a.jsonl")
    mapped_al = Path(tempfile.mkdtemp(prefix="dse-alv-")) / "g.v"
    mapped_al.write_text("module gcd; endmodule\n")
    mem_al.add(
        Candidate(
            id="f1al",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "liberty_default"},
            knobs_fp="f1al",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=409.108, wns_cost=0.522, fidelity="F1"),
            cost_s=1.0,
            status="ok",
            artifacts={"mapped_v": str(mapped_al), "wns_ns": -0.522},
        )
    )
    mem_al.add(
        Candidate(
            id="f5lite",
            design_id="gcd",
            parent_id="f1al",
            level="routing",
            knobs={"source": "f5_openroad_drt_rcx", "parent_id": "f1al", "clock": "ideal"},
            knobs_fp="f5lite",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.649, fidelity="F5"),
            cost_s=1.0,
            status="ok",
            artifacts={"wns_ns": -0.649},
        )
    )
    mem_al.add(
        Candidate(
            id="cellh",
            design_id="gcd",
            parent_id="f1al",
            level="cell",
            knobs={"source": "cell_size_up"},
            knobs_fp="cellh",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(wns_cost=0.12, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(mapped_al), "wns_ns": -0.119},
        )
    )
    mem_al.add(
        Candidate(
            id="neth",
            design_id="gcd",
            parent_id="cellh",
            level="net",
            knobs={"source": "net_buffer"},
            knobs_fp="neth",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(wns_cost=0.21, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(mapped_al), "wns_ns": -0.207},
        )
    )
    lite = residual_f3_to_f5_lite(list(mem_al.all()))
    check((lite.get("n") or 0) == 1, f"F3→F5-lite residual has a pair, got {lite}")
    check(abs(float(lite["mean_residual_ns"]) - (-0.127)) < 1e-6, f"lite residual -0.649−(−0.522), got {lite.get('mean_residual_ns')}")
    hosts_w, why_w = order_local_hosts(mem_al)
    check(hosts_w and hosts_w[0].level == "net", f"wire-dominated lite residual puts net host first, got {[h.level for h in hosts_w]}")
    check("wire" in (why_w.get("reason") or ""), f"host order reason names wire, got {why_w}")
    # Small residual → cell first
    f5c = next(c for c in mem_al.all() if c.id == "f5lite")
    f5c.artifacts = {"wns_ns": -0.530}
    mem_al.touch(f5c)
    hosts_c, why_c = order_local_hosts(mem_al)
    check(hosts_c and hosts_c[0].level == "cell", f"small lite residual puts cell host first, got {[h.level for h in hosts_c]}")
    check("small" in (why_c.get("reason") or ""), f"host order reason names small residual, got {why_c}")
    check(steer_from_residual(mem_al) is None, "no F5-local pair yet → no residual steer")
    mem_al.add(
        Candidate(
            id="f5locn",
            design_id="gcd",
            parent_id="neth",
            level="routing",
            knobs={"source": "f5_openroad_local", "parent_id": "neth", "host_level": "net"},
            knobs_fp="f5locn",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.232, fidelity="F5"),
            cost_s=1.0,
            status="ok",
            artifacts={"wns_ns": -0.232, "ideal_wns_ns": -0.207, "path_cells": ["dpath/a_reg/_112_"], "path_nets": ["a->b"]},
        )
    )
    st1 = steer_from_residual(mem_al)
    check(st1 is not None and st1.get("level") == "f5_local", f"high uncertainty steers the other host SPEF, got {st1}")
    check(st1.get("host_id") == "cellh", f"unmeasured host is the cell, got {st1}")
    pay_st0, why_st0 = should_pay_residual_steer(mem_al, budget_left=80, steer=None)
    check(not pay_st0, f"residual steer waits for a steer dict ({why_st0})")
    pay_st1, why_st1 = should_pay_residual_steer(mem_al, budget_left=80, steer=st1)
    check(pay_st1, f"residual steer is paid after F5-local ({why_st1})")
    pay_st2, why_st2 = should_pay_residual_steer(mem_al, budget_left=80, steer=st1, n_steer=1)
    check(not pay_st2, f"residual steer is a single shot ({why_st2})")
    mem_al.add(
        Candidate(
            id="f5locc",
            design_id="gcd",
            parent_id="cellh",
            level="routing",
            knobs={"source": "f5_openroad_local", "parent_id": "cellh", "host_level": "cell"},
            knobs_fp="f5locc",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.14, fidelity="F5"),
            cost_s=1.0,
            status="ok",
            artifacts={"wns_ns": -0.140, "ideal_wns_ns": -0.119, "path_cells": ["dpath/a_lt_b/_142_"], "path_nets": ["x->y"]},
        )
    )
    st2 = steer_from_residual(mem_al)
    check(st2 is not None and st2.get("level") == "cell", f"small local residual steers cell size-up, got {st2}")
    mem_al.add(
        Candidate(
            id="f5locw",
            design_id="gcd",
            parent_id="neth",
            level="routing",
            knobs={"source": "f5_openroad_local", "parent_id": "neth", "host_level": "net", "tag": "wire"},
            knobs_fp="f5locw",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.35, fidelity="F5"),
            cost_s=1.0,
            status="ok",
            artifacts={"wns_ns": -0.350, "ideal_wns_ns": -0.207, "path_cells": ["dpath/a_reg/_112_"], "path_nets": ["p->q"]},
        )
    )
    st3 = steer_from_residual(mem_al)
    check(st3 is not None and st3.get("level") == "net", f"wire local residual steers net BUF, got {st3}")
    check((st3.get("hops") or ["p->q"])[0], "wire steer names SPEF hops")

    from dse.active import steer_from_port_residual

    mem_ps = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-ps-")) / "p.jsonl")
    mem_ps.add(
        Candidate(
            id="porth2",
            design_id="gcd",
            parent_id=None,
            level="net",
            knobs={"source": "net_buffer_port", "scope": "port"},
            knobs_fp="porth2",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(wns_cost=0.228, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": "y", "wns_ns": -0.228},
        )
    )
    mem_ps.add(
        Candidate(
            id="f5p",
            design_id="gcd",
            parent_id="porth2",
            level="routing",
            knobs={"source": "f5_openroad_local", "host_level": "port", "parent_id": "porth2"},
            knobs_fp="f5p",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F5",
            qor=QoR(wns_cost=0.332, fidelity="F5"),
            cost_s=1.0,
            status="ok",
            artifacts={"wns_ns": -0.332, "ideal_wns_ns": -0.228},
            attr={
                "nets": [
                    "dpath/a_lt_b/_194_->portbuf_0",
                    "ctrl/_07_->portbuf_1",
                    "dpath/a_mux/_39_->dpath/a_mux/_59_",
                    "dpath/a_mux/_59_->dpath/a_mux/_61_",
                ]
            },
        )
    )
    st_ps = steer_from_port_residual(mem_ps)
    check(st_ps is not None and st_ps.get("level") == "net", f"wire F5-port residual steers net BUF, got {st_ps}")
    check(st_ps.get("host_id") == "porth2", f"port-steer host is the port-net parent, got {st_ps}")
    check(
        (st_ps.get("hops") or [""])[0] == "dpath/a_mux/_39_->dpath/a_mux/_59_",
        f"port-steer skips portbuf hops, got {st_ps.get('hops')}",
    )
    check("portbuf" not in " ".join(st_ps.get("hops") or []), "port-steer does not restamp portbuf hops")
    pay_ps1, why_ps1 = should_pay_port_steer(mem_ps, budget_left=80, steer=st_ps)
    check(pay_ps1, f"port-steer is paid after F5-port residual ({why_ps1})")
    pay_ps2, why_ps2 = should_pay_port_steer(mem_ps, budget_left=80, steer=st_ps, n_steer=1)
    check(not pay_ps2, f"port-steer is a single shot ({why_ps2})")

    from dse.active import iscale_host

    mem_is = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-is-")) / "i.jsonl")
    mem_is.add(
        Candidate(
            id="libp",
            design_id="gcd",
            parent_id=None,
            level="logic",
            knobs={"name": "liberty_default"},
            knobs_fp="libp",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=409.108, power_w=0.00126, wns_cost=0.522, fidelity="F1"),
            cost_s=1.0,
            status="ok",
        )
    )
    mem_is.add(
        Candidate(
            id="synp",
            design_id="gcd",
            parent_id=None,
            level="synthesis",
            knobs={"name": "orfs_abc_speed", "source": "orfs_abc_script"},
            knobs_fp="synp",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F1",
            qor=QoR(area_um2=618.982, power_w=0.00291, wns_cost=0.114, fidelity="F1"),
            cost_s=1.0,
            status="ok",
        )
    )
    h0 = iscale_host(mem_is)
    check(h0 is not None and h0.id == "synp", f"without a hierarchical host I-scale falls back to synth F1, got {h0}")
    mem_is.add(
        Candidate(
            id="psteer",
            design_id="gcd",
            parent_id="porth",
            level="net",
            knobs={"source": "net_buffer_spef", "spef_residual": 1},
            knobs_fp="psteer",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=560.728, power_w=0.00531, wns_cost=0.309, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            attr={"via": "active_f5_port"},
        )
    )
    h1 = iscale_host(mem_is)
    check(h1 is not None and h1.id == "psteer", f"I-scale prefers port-steer over synth, got {h1}")
    pay_ha0, why_ha0 = should_pay_host_arrivals(mem_is, budget_left=80, n_arr=0)
    check(not pay_ha0, f"host arrivals wait for a mapped netlist ({why_ha0})")
    dummy_v = Path(tempfile.mkdtemp(prefix="dse-arr-host-")) / "host.v"
    dummy_v.write_text("module gcd(clk); input clk; endmodule\n")
    psteer = next(c for c in mem_is.all() if c.id == "psteer")
    psteer.artifacts = dict(psteer.artifacts or {})
    psteer.artifacts["mapped_v"] = str(dummy_v)
    mem_is.touch(psteer)
    pay_ha1, why_ha1 = should_pay_host_arrivals(mem_is, budget_left=80, n_arr=0)
    check(pay_ha1, f"host arrivals are paid on the attributed mapped host ({why_ha1})")
    check("net_buffer_spef" in why_ha1, f"arrivals acquire names the port-steer host ({why_ha1})")
    check("VCD" in why_ha1, f"arrivals acquire refuses a VCD map ({why_ha1})")
    pay_ha2, why_ha2 = should_pay_host_arrivals(mem_is, budget_left=80, n_arr=1)
    check(not pay_ha2, f"host arrivals are a single shot ({why_ha2})")
    from dse.acquire import latest_host_arrivals

    mem_is.add(
        Candidate(
            id="arrh",
            design_id="gcd",
            parent_id="psteer",
            level="pdn",
            knobs={"source": "f4_host_arrivals", "parent_id": "psteer", "host_source": "net_buffer_spef"},
            knobs_fp="arrh",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"sta_arrivals": str(dummy_v), "n_inst": 12},
        )
    )
    hit = latest_host_arrivals(mem_is)
    check(hit is not None and hit.get("host_source") == "net_buffer_spef", f"latest host arrivals prefer the attributed JSON, got {hit}")
    pay_he0, why_he0 = should_pay_f4_host_extract(mem_is, budget_left=80, n_extract=0)
    check(pay_he0, f"host extract is paid on the attributed mapped host ({why_he0})")
    check("net_buffer_spef" in why_he0, f"host extract acquire names the port-steer host ({why_he0})")
    pay_he1, why_he1 = should_pay_f4_host_extract(mem_is, budget_left=80, n_extract=1)
    check(not pay_he1, f"host extract is a single shot ({why_he1})")
    pay_hr0, why_hr0 = should_pay_f4_host_region(mem_is, budget_left=80, n_extract=0)
    check(not pay_hr0, f"host-region waits for a host extract hotspot ({why_hr0})")
    mem_is.add(
        Candidate(
            id="goldr",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "ingest_pdn"},
            knobs_fp="goldr",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.298, fidelity="F4"),
            cost_s=0.0,
            status="ok",
            attr={"region": "r31", "seq_frac": 0.2, "combo_frac": 0.8},
        )
    )
    mem_is.add(
        Candidate(
            id="hext",
            design_id="gcd",
            parent_id="psteer",
            level="pdn",
            knobs={"source": "f4_host_extract", "parent_id": "psteer", "host_source": "net_buffer_spef"},
            knobs_fp="hext",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=10.07, fidelity="F4"),
            cost_s=0.6,
            status="ok",
            attr={"region": "r02", "x_dbu": 14709.0, "y_dbu": 58545.0, "seq_frac": 0.90, "via": "f4_host_extract"},
        )
    )
    pay_hr1, why_hr1 = should_pay_f4_host_region(mem_is, budget_left=80, n_extract=0)
    check(pay_hr1, f"host-region is paid when host bin ≠ gold ({why_hr1})")
    check("r02" in why_hr1 and "r31" in why_hr1, f"host-region acquire names both bins ({why_hr1})")
    check("combo ABC" in why_hr1, f"host-region acquire refuses more combo ABC ({why_hr1})")
    pay_hr2, why_hr2 = should_pay_f4_host_region(mem_is, budget_left=80, n_extract=1)
    check(not pay_hr2, f"host-region is a single shot ({why_hr2})")
    hext_same = next(c for c in mem_is.all() if c.id == "hext")
    hext_same.attr = dict(hext_same.attr or {})
    hext_same.attr["region"] = "r31"
    mem_is.touch(hext_same)
    pay_hr3, why_hr3 = should_pay_f4_host_region(mem_is, budget_left=80, n_extract=0)
    check(not pay_hr3, f"host-region skips when host bin matches gold ({why_hr3})")
    hext_same.attr["region"] = "r02"
    mem_is.touch(hext_same)
    pay_is0, why_is0 = should_pay_f4_scale(mem_is, budget_left=80, n_scale=0)
    check(pay_is0, f"attributed I-scale is paid ({why_is0})")
    check("net_buffer_spef" in why_is0, f"acquire names the port-steer host ({why_is0})")
    check("synth-only" in why_is0, f"acquire refuses a synth-only flatten ({why_is0})")
    pay_is1, why_is1 = should_pay_f4_scale(mem_is, budget_left=80, n_scale=1)
    check(not pay_is1, f"I-scale is a single shot ({why_is1})")
    mem_is.add(
        Candidate(
            id="isc",
            design_id="gcd",
            parent_id="psteer",
            level="pdn",
            knobs={"source": "f4_iscale", "parent_id": "psteer", "i_scale": 4.21},
            knobs_fp="isc",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=70.0, fidelity="F4"),
            cost_s=5.0,
            status="ok",
        )
    )
    h2 = iscale_host(mem_is)
    check(h2 is not None and h2.id == "synp", f"already-scaled port-steer falls back to unused synth, got {h2}")
    pay_is2, why_is2 = should_pay_f4_scale(mem_is, budget_left=80, n_scale=1)
    check(not pay_is2, f"acquire still spends only one I-scale shot ({why_is2})")

    from dse.active import steer_from_ir_residual
    from dse.surrogate import residual_f4_knob, residual_f4_mesh, residual_f4_region, residual_f4_host_region

    mem_ir = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-ir-")) / "i.jsonl")
    mem_ir.add(
        Candidate(
            id="gold",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "ingest_pdn"},
            knobs_fp="gold",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.298, fidelity="F4"),
            cost_s=0.0,
            status="ok",
        )
    )
    mem_ir.add(
        Candidate(
            id="candext",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_candidate_extract", "extract_id": "candext"},
            knobs_fp="candext",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=16.616, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    mesh_r = residual_f4_mesh(list(mem_ir.all()))
    check((mesh_r.get("n") or 0) == 1, f"F4 mesh residual has a pair, got {mesh_r}")
    check(abs(float(mesh_r["mean_residual_mv"]) - (16.616 - 45.298)) < 1e-6, f"mesh residual cand−gold, got {mesh_r.get('mean_residual_mv')}")
    mem_ir.add(
        Candidate(
            id="decapc",
            design_id="gcd",
            parent_id="candext",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "decap_200f",
                "extract_id": "candext",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
            },
            knobs_fp="decapc",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=8.842, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    knob_r = residual_f4_knob(list(mem_ir.all()))
    check((knob_r.get("n") or 0) == 1, f"F4 knob residual has a pair, got {knob_r}")
    check(abs(float(knob_r["mean_residual_mv"]) - (8.842 - 16.616)) < 1e-6, f"knob residual decap−base, got {knob_r.get('mean_residual_mv')}")
    mem_ir.add(
        Candidate(
            id="regext",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_region_extract", "extract_id": "regext", "region": "r32"},
            knobs_fp="regext",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=14.202, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    reg_r = residual_f4_region(list(mem_ir.all()))
    check((reg_r.get("n") or 0) == 1, f"F4 region residual has a pair, got {reg_r}")
    check(abs(float(reg_r["mean_residual_mv"]) - (14.202 - 16.616)) < 1e-6, f"region residual vs candidate, got {reg_r.get('mean_residual_mv')}")
    mem_hr = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-hr-")) / "h.jsonl")
    mem_hr.add(
        Candidate(
            id="hex",
            design_id="gcd",
            parent_id="psteer",
            level="pdn",
            knobs={"source": "f4_host_extract", "extract_id": "hex"},
            knobs_fp="hex",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=10.07, fidelity="F4"),
            cost_s=0.6,
            status="ok",
            attr={"region": "r02"},
        )
    )
    mem_hr.add(
        Candidate(
            id="hreg",
            design_id="gcd",
            parent_id="psteer",
            level="pdn",
            knobs={"source": "f4_host_region_extract", "extract_id": "hreg", "region": "r02"},
            knobs_fp="hreg",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=8.50, fidelity="F4"),
            cost_s=0.6,
            status="ok",
            attr={"region": "r02"},
        )
    )
    hr_r = residual_f4_host_region(list(mem_hr.all()))
    check((hr_r.get("n") or 0) == 1, f"F4 host-region residual has a pair, got {hr_r}")
    check(abs(float(hr_r["mean_residual_mv"]) - (8.50 - 10.07)) < 1e-6, f"host-region residual vs host, got {hr_r.get('mean_residual_mv')}")
    check(hr_r.get("host_bin") == "r02", f"host-region residual names the host bin, got {hr_r}")
    empty_hr = residual_f4_host_region(list(mem_ir.all()))
    check((empty_hr.get("n") or 0) == 0, "synth region residual is not a host-region pair")
    from dse.active import steer_from_host_ir_residual

    mem_hr.add(
        Candidate(
            id="hcand",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_candidate_extract", "extract_id": "hcand"},
            knobs_fp="hcand",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=16.616, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    mem_hr.add(
        Candidate(
            id="hdecap",
            design_id="gcd",
            parent_id="hcand",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "decap_200f",
                "extract_id": "hcand",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
            },
            knobs_fp="hdecap",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=8.842, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    st_hir = steer_from_host_ir_residual(mem_hr)
    check(st_hir is not None and (st_hir.get("spec") or {}).get("name") == "decap_200f", f"large host-region residual steers decap, got {st_hir}")
    check(st_hir.get("extract_id") == "hreg", f"host IR-steer restamps the host-region mesh, got {st_hir}")
    check(st_hir.get("host_source") == "f4_host_region_extract", "host IR-steer names the host-region extract")
    check(st_hir.get("extract_id") != "hcand", "host IR-steer does not pick the synth candidate extract")
    pay_hir0, why_hir0 = should_pay_host_ir_steer(mem_hr, budget_left=80, steer=None)
    check(not pay_hir0, f"host IR-steer waits for a steer dict ({why_hir0})")
    pay_hir1, why_hir1 = should_pay_host_ir_steer(mem_hr, budget_left=80, steer=st_hir)
    check(pay_hir1, f"host IR-steer is paid after host-region residual ({why_hir1})")
    mem_hr.add(
        Candidate(
            id="hdecapr",
            design_id="gcd",
            parent_id="hreg",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "decap_200f",
                "extract_id": "hreg",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
            },
            knobs_fp="hdecapr",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=6.80, static_ir_mv=7.639, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_host_ir"},
        )
    )
    pay_hsame, why_hsame = should_pay_host_ir_steer(mem_hr, budget_left=80, steer=st_hir, n_steer=1)
    check(not pay_hsame, f"same host-region decap point is not restamped ({why_hsame})")
    st_hir2 = steer_from_host_ir_residual(mem_hr)
    check(st_hir2 is not None and (st_hir2.get("spec") or {}).get("name") == "pkg_l_100p", f"after host-region decap, unused pkg L is next, got {st_hir2}")
    check(st_hir2.get("extract_id") == "hex", f"second host IR-steer stays on the unconstrained host extract, got {st_hir2}")
    check(st_hir2.get("host_source") == "f4_host_extract", "second host IR-steer names the unconstrained host extract")
    check(st_hir2.get("extract_id") != "hcand", "second host IR-steer does not pick the synth candidate")
    pay_hir2, why_hir2 = should_pay_host_ir_steer(mem_hr, budget_left=80, steer=st_hir2, n_steer=1)
    check(pay_hir2, f"second host IR-steer is paid after inspect ({why_hir2})")
    pay_hir3, why_hir3 = should_pay_host_ir_steer(mem_hr, budget_left=80, steer=st_hir2, n_steer=2)
    check(not pay_hir3, f"host IR-steer loop caps at host-region family + unused catalog ({why_hir3})")
    fake_cand = dict(st_hir2)
    fake_cand["host_source"] = "f4_candidate_extract"
    pay_href, why_href = should_pay_host_ir_steer(mem_hr, budget_left=80, steer=fake_cand, n_steer=1)
    check(not pay_href, f"host IR-steer refuses a candidate extract ({why_href})")
    from dse.active import winning_host_pdn

    win0 = winning_host_pdn(mem_hr)
    check(win0 is not None and win0.id == "hdecapr", f"winning host PDN is the host-region decap, got {win0}")
    pay_sw0, why_sw0 = should_pay_f4_scale_win(mem_hr, budget_left=80, n_scale=0)
    check(not pay_sw0, f"winning I-scale waits for the first I-scale ({why_sw0})")
    mem_hr.add(
        Candidate(
            id="isc0",
            design_id="gcd",
            parent_id="psteer",
            level="pdn",
            knobs={
                "source": "f4_iscale",
                "parent_id": "psteer",
                "extract_id": "hex",
                "c_decap": 50e-15,
                "pkg_l": 2e-10,
                "i_scale": 4.21,
            },
            knobs_fp="isc0",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=42.436, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay_sw1, why_sw1 = should_pay_f4_scale_win(mem_hr, budget_left=80, n_scale=0)
    check(pay_sw1, f"winning I-scale is paid when host-IR-steer mesh differs ({why_sw1})")
    check("unconstrained" in why_sw1 or "winning" in why_sw1, f"winning I-scale names the residual ({why_sw1})")
    pay_sw2, why_sw2 = should_pay_f4_scale_win(mem_hr, budget_left=80, n_scale=1)
    check(not pay_sw2, f"winning I-scale is a single shot ({why_sw2})")
    mem_same = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-sw-")) / "s.jsonl")
    for cid, src, eid, mv, extra in (
        (
            "h",
            "f4_host_extract",
            "h",
            10.07,
            {"pkg_l": 2e-10, "c_decap": 50e-15, "i_scale": 1.0},
        ),
        (
            "i",
            "f4_iscale",
            "h",
            42.4,
            {"parent_id": "psteer", "pkg_l": 2e-10, "c_decap": 50e-15, "i_scale": 4.21},
        ),
    ):
        kn = {"source": src, "extract_id": eid, **extra}
        mem_same.add(
            Candidate(
                id=cid,
                design_id="gcd",
                parent_id=None,
                level="pdn",
                knobs=kn,
                knobs_fp=cid,
                rtl_fp="x",
                netlist_fp=None,
                fidelity="F4",
                qor=QoR(dynamic_ir_mv=mv, fidelity="F4"),
                cost_s=0.1,
                status="ok",
            )
        )
    pay_same_m, why_same_m = should_pay_f4_scale_win(mem_same, budget_left=80, n_scale=0)
    check(not pay_same_m, f"winning I-scale skips when the host mesh already is the I-scale ({why_same_m})")
    from dse.attribute import join_hotspot_insts, persist_hotspot_join

    inst_dir = Path(tempfile.mkdtemp(prefix="dse-irj-"))
    inst_json = inst_dir / "inst_power_map.json"
    inst_json.write_text(
        json.dumps(
            {
                "insts": [
                    {"name": "ctrl/_11_", "cell": "NOR2_X1", "x": 38950, "y": 15400, "seq": False, "filler": False},
                    {"name": "ctrl/_14_", "cell": "AOI21_X1", "x": 40280, "y": 15400, "seq": False, "filler": False},
                    {"name": "dpath/a_lt_b/_142_", "cell": "NAND2_X1", "x": 1000, "y": 1000, "seq": False, "filler": False},
                    {"name": "FILLCELL_X1", "cell": "FILLCELL_X1", "x": 38755, "y": 14170, "seq": False, "filler": True},
                ]
            }
        )
        + "\n"
    )
    joined = join_hotspot_insts(inst_json, 38755.0, 14170.0, k=3, max_dbu=8000.0)
    check(joined.get("n") == 2, f"IR join skips filler and far dpath, got {joined}")
    check(joined.get("cells") == ["ctrl/_11_", "ctrl/_14_"], f"IR join prefers nearby ctrl combo, got {joined}")
    check(joined.get("modules") == ["ctrl"], f"IR join names ctrl, got {joined}")
    check("VCD" in str(joined.get("via") or joined.get("not")), f"IR join refuses a VCD remap ({joined})")
    attr_odb = attribute_dynamic_ir(
        {
            "hotspot": {
                "node": "ITermNode_metal1_38755_14170",
                "droop_mv": 7.187,
                "x_dbu": 38755.0,
                "y_dbu": 14170.0,
                "contributors": {"seq_frac": 0.04, "combo_frac": 0.96},
            },
            "insts": str(inst_json),
        }
    )
    check(attr_odb.get("join") == "odb-geom", f"combo-heavy F4 attr falls back to ODB join, got {attr_odb}")
    check(attr_odb.get("modules") == ["ctrl"], f"ODB-geom attr names ctrl, got {attr_odb}")
    check(attr_odb.get("cells") == ["ctrl/_11_", "ctrl/_14_"], f"ODB-geom attr keeps nearby combo, got {attr_odb}")
    check(attr_odb.get("scope") == "logic_cone", f"ODB-geom attr is a cone, not a chip restart, got {attr_odb}")
    check("ODB" in str(attr_odb.get("note") or ""), f"ODB-geom note names the join ({attr_odb.get('note')})")
    empty_join = Candidate(
        id="emptyjoin",
        design_id="gcd",
        parent_id=None,
        level="pdn",
        knobs={"source": "f4_em_strap_extract", "extract_id": "emptyjoin"},
        knobs_fp="emptyjoin",
        rtl_fp="x",
        netlist_fp="y",
        fidelity="F4",
        qor=QoR(dynamic_ir_mv=1.896, fidelity="F4"),
        cost_s=0.1,
        status="ok",
        attr={"x_dbu": 38755.0, "y_dbu": 14170.0, "region": "r10", "cells": []},
        artifacts={"insts": str(inst_json), "x_dbu": 38755.0, "y_dbu": 14170.0},
    )
    check(persist_hotspot_join(empty_join), "persist_hotspot_join fills empty IR cells from ODB-geom")
    check(empty_join.attr.get("join") == "odb-geom", f"persist join is odb-geom, got {empty_join.attr}")
    check(empty_join.attr.get("cells") == ["ctrl/_11_", "ctrl/_14_"], f"persist join keeps nearby combo, got {empty_join.attr}")
    check(not persist_hotspot_join(empty_join), "persist_hotspot_join does not overwrite filled cells")
    attr_sta_wins = attribute_dynamic_ir(
        {
            "hotspot": {
                "node": "ITermNode_metal1_38755_14170",
                "droop_mv": 7.187,
                "x_dbu": 38755.0,
                "y_dbu": 14170.0,
            },
            "activity_model": {
                "sta": {
                    "worst_path": {
                        "startpoint": "dpath.a_reg.out[5]$_DFFE_PP_",
                        "endpoint": "dpath.a_reg.out[7]$_DFFE_PP_",
                    }
                }
            },
            "insts": str(inst_json),
        }
    )
    check(attr_sta_wins.get("join") == "sta-path", f"STA names beat ODB fallback, got {attr_sta_wins}")
    check(attr_sta_wins.get("modules") == ["dpath"], f"STA-path attr stays dpath, got {attr_sta_wins}")
    pay_ic0, why_ic0 = should_pay_ir_cell(mem_hr, budget_left=80, n_cell=0)
    check(not pay_ic0, f"IR-cell waits for an I-scale-win inst map ({why_ic0})")
    dummy_host = inst_dir / "host.v"
    dummy_host.write_text("module gcd(clk); input clk; endmodule\n")
    mem_hr.add(
        Candidate(
            id="psteer",
            design_id="gcd",
            parent_id=None,
            level="net",
            knobs={"source": "net_buffer_spef"},
            knobs_fp="psteer2",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=560.728, power_w=0.00531, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(dummy_host)},
        )
    )
    mem_hr.add(
        Candidate(
            id="isw",
            design_id="gcd",
            parent_id="psteer",
            level="pdn",
            knobs={"source": "f4_iscale_win", "parent_id": "psteer", "extract_id": "hreg"},
            knobs_fp="isw",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=16.924, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"x_dbu": 38755.0, "y_dbu": 14170.0, "region": "r10", "combo_frac": 0.78, "via": "f4_iscale_win"},
            artifacts={"insts": str(inst_json), "x_dbu": 38755.0, "y_dbu": 14170.0},
        )
    )
    pay_ic1, why_ic1 = should_pay_ir_cell(mem_hr, budget_left=80, n_cell=0)
    check(pay_ic1, f"IR-cell is paid after I-scale-win join ({why_ic1})")
    check("ctrl" in why_ic1, f"IR-cell acquire names the joined module ({why_ic1})")
    check("STA path" in why_ic1, f"IR-cell acquire refuses STA-path flatten ({why_ic1})")
    pay_ic2, why_ic2 = should_pay_ir_cell(mem_hr, budget_left=80, n_cell=1)
    check(not pay_ic2, f"IR-cell is a single shot ({why_ic2})")
    pay_ice0, why_ice0 = should_pay_ir_cell_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_ice0, f"IR-cell extract waits for a sized netlist ({why_ice0})")
    mem_hr.add(
        Candidate(
            id="ircell",
            design_id="gcd",
            parent_id="psteer",
            level="cell",
            knobs={
                "source": "cell_size_ir",
                "cells": ["ctrl/_11_", "ctrl/_14_"],
                "ir_join": 1,
                "parent_id": "psteer",
            },
            knobs_fp="ircell",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=564.186, wns_cost=0.297, fidelity="F3"),
            cost_s=0.4,
            status="ok",
            artifacts={"mapped_v": str(dummy_host), "n_changed": 2},
            attr={"via": "active_f4_ir_cell"},
        )
    )
    pay_ice1, why_ice1 = should_pay_ir_cell_extract(mem_hr, budget_left=80, n_extract=0)
    check(pay_ice1, f"IR-cell extract is paid after IR-cell size-up ({why_ice1})")
    check("ctrl" in why_ice1, f"IR-cell extract acquire names the joined cone ({why_ice1})")
    check("host extract" in why_ice1, f"IR-cell extract residuals vs host extract ({why_ice1})")
    check("gold" in why_ice1 and "ABC" in why_ice1, f"IR-cell extract refuses gold/ABC flatten ({why_ice1})")
    pay_ice2, why_ice2 = should_pay_ir_cell_extract(mem_hr, budget_left=80, n_extract=1)
    check(not pay_ice2, f"IR-cell extract is a single shot ({why_ice2})")
    mem_hr.add(
        Candidate(
            id="icext",
            design_id="gcd",
            parent_id="ircell",
            level="pdn",
            knobs={"source": "f4_ir_cell_extract", "parent_id": "ircell", "ir_join": 1},
            knobs_fp="icext",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=9.40, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_ir_cell_extract",
                "residual_mv": -0.67,
                "residual_via": "ir_cell_vs_host_extract",
                "region": "r00",
                "x_dbu": 8363.0,
                "y_dbu": 19373.0,
                "combo_frac": 0.32,
                "seq_frac": 0.68,
            },
        )
    )
    win_ice = winning_host_pdn(mem_hr)
    check(win_ice is not None and win_ice.id != "icext", "winning host PDN does not steal the IR-cell extract")
    pay_ice3, why_ice3 = should_pay_ir_cell_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_ice3, f"IR-cell extract skips once measured ({why_ice3})")
    from dse.active import steer_from_ir_cell_residual

    st_icp = steer_from_ir_cell_residual(mem_hr)
    check(st_icp is not None and (st_icp.get("spec") or {}).get("name") == "decap_200f", f"IR-cell residual steers winning decap, got {st_icp}")
    check(st_icp.get("extract_id") == "icext", f"IR-cell PDN restamp stays on the sized mesh, got {st_icp}")
    check(st_icp.get("host_source") == "f4_ir_cell_extract", "IR-cell PDN names the IR-cell extract")
    check(st_icp.get("extract_id") != "hex", "IR-cell PDN does not restamp the unconstrained host")
    pay_icp0, why_icp0 = should_pay_ir_cell_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_icp0, f"IR-cell PDN waits for a residual steer ({why_icp0})")
    pay_icp1, why_icp1 = should_pay_ir_cell_pdn(mem_hr, budget_left=80, steer=st_icp)
    check(pay_icp1, f"IR-cell PDN is paid after the 1× residual ({why_icp1})")
    check("raised" in why_icp1 or "lowered" in why_icp1, f"IR-cell PDN names the residual sign ({why_icp1})")
    fake_host = dict(st_icp)
    fake_host["host_source"] = "f4_host_extract"
    pay_icp_ref, why_icp_ref = should_pay_ir_cell_pdn(mem_hr, budget_left=80, steer=fake_host)
    check(not pay_icp_ref, f"IR-cell PDN refuses a host extract ({why_icp_ref})")
    pay_icp2, why_icp2 = should_pay_ir_cell_pdn(mem_hr, budget_left=80, steer=st_icp, n_steer=1)
    check(not pay_icp2, f"IR-cell PDN is a single shot ({why_icp2})")
    from dse.active import steer_from_ir_cell_hotspot

    st_icr = steer_from_ir_cell_hotspot(mem_hr)
    check(st_icr is not None and st_icr.get("level") == "ir_cell_region", f"seq-heavy IR-cell bin steers a region cap, got {st_icr}")
    check(st_icr.get("region") == "r00", f"IR-cell region names r00, got {st_icr}")
    check(st_icr.get("host_region") == "r02", f"IR-cell region names the host bin, got {st_icr}")
    check("combo size-up" in (st_icr.get("reason") or ""), f"IR-cell region refuses more combo size-up ({st_icr})")
    pay_icr0, why_icr0 = should_pay_ir_cell_region(mem_hr, budget_left=80, steer=None)
    check(not pay_icr0, f"IR-cell region waits for a hotspot steer ({why_icr0})")
    pay_icr1, why_icr1 = should_pay_ir_cell_region(mem_hr, budget_left=80, steer=st_icr)
    check(pay_icr1, f"IR-cell region is paid after a seq-heavy bin residual ({why_icr1})")
    check("r00" in why_icr1 and "r02" in why_icr1, f"IR-cell region acquire names both bins ({why_icr1})")
    fake_host_r = dict(st_icr)
    fake_host_r["host_source"] = "f4_host_region_extract"
    pay_icr_ref, why_icr_ref = should_pay_ir_cell_region(mem_hr, budget_left=80, steer=fake_host_r)
    check(not pay_icr_ref, f"IR-cell region refuses a host-region extract ({why_icr_ref})")
    pay_icr2, why_icr2 = should_pay_ir_cell_region(mem_hr, budget_left=80, steer=st_icr, n_extract=1)
    check(not pay_icr2, f"IR-cell region is a single shot ({why_icr2})")
    ice_c = next(c for c in mem_hr.all() if c.id == "icext")
    ice_c.attr = dict(ice_c.attr or {})
    ice_c.attr["combo_frac"] = 0.78
    mem_hr.touch(ice_c)
    check(steer_from_ir_cell_hotspot(mem_hr) is None, "combo-heavy IR-cell hotspot does not steal a region cap")
    ice_c.attr["combo_frac"] = 0.32
    ice_c.attr["region"] = "r02"
    mem_hr.touch(ice_c)
    check(steer_from_ir_cell_hotspot(mem_hr) is None, "IR-cell region skips when the bin matches the host")
    ice_c.attr["region"] = "r00"
    mem_hr.touch(ice_c)
    from dse.active import steer_from_ir_cell_region_residual

    pay_icrp0, why_icrp0 = should_pay_ir_cell_region_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_icrp0, f"IR-cell-region PDN waits for a spatial residual ({why_icrp0})")
    mem_hr.add(
        Candidate(
            id="icreg",
            design_id="gcd",
            parent_id="ircell",
            level="pdn",
            knobs={"source": "f4_ir_cell_region_extract", "extract_id": "icreg", "region": "r00", "ir_join": 1},
            knobs_fp="icreg",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=9.356, static_ir_mv=6.178, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "f4_ir_cell_region_extract", "residual_mv": -4.652, "region": "r00"},
        )
    )
    st_icrp = steer_from_ir_cell_region_residual(mem_hr)
    check(st_icrp is not None and (st_icrp.get("spec") or {}).get("name") == "decap_200f", f"large IR-cell-region residual steers decap, got {st_icrp}")
    check(st_icrp.get("extract_id") == "icreg", f"IR-cell-region PDN stays on the capped mesh, got {st_icrp}")
    check(st_icrp.get("host_source") == "f4_ir_cell_region_extract", "IR-cell-region PDN names the region extract")
    check(st_icrp.get("extract_id") != "icext", "IR-cell-region PDN does not restamp the unconstrained 1× extract")
    pay_icrp1, why_icrp1 = should_pay_ir_cell_region_pdn(mem_hr, budget_left=80, steer=st_icrp)
    check(pay_icrp1, f"IR-cell-region PDN is paid after |Δ| ≥ 1 mV ({why_icrp1})")
    fake_1x = dict(st_icrp)
    fake_1x["host_source"] = "f4_ir_cell_extract"
    pay_icrp_ref, why_icrp_ref = should_pay_ir_cell_region_pdn(mem_hr, budget_left=80, steer=fake_1x)
    check(not pay_icrp_ref, f"IR-cell-region PDN refuses the 1× extract ({why_icrp_ref})")
    pay_icrp2, why_icrp2 = should_pay_ir_cell_region_pdn(mem_hr, budget_left=80, steer=st_icrp, n_steer=1)
    check(not pay_icrp2, f"IR-cell-region PDN is a single shot ({why_icrp2})")
    ice_small = next(c for c in mem_hr.all() if c.id == "icreg")
    ice_small.attr = dict(ice_small.attr or {})
    ice_small.attr["residual_mv"] = -0.2
    mem_hr.touch(ice_small)
    check(steer_from_ir_cell_region_residual(mem_hr) is None, "small IR-cell-region residual does not restamp PDN")
    ice_small.attr["residual_mv"] = -4.652
    mem_hr.touch(ice_small)
    from dse.active import winning_ir_pdn

    win_host = winning_host_pdn(mem_hr)
    check(win_host is not None and win_host.id == "hdecapr", f"winning_host_pdn stays host-only, got {win_host}")
    win_ir0 = winning_ir_pdn(mem_hr)
    check(win_ir0 is not None and win_ir0.id == "hdecapr", f"without IR-cell-region-PDN, winning_ir_pdn is still host-win, got {win_ir0}")
    pay_sc0, why_sc0 = should_pay_f4_scale_champ(mem_hr, budget_left=80, n_scale=0)
    check(not pay_sc0, f"champion I-scale refuses a host-only 1× point ({why_sc0})")
    sta0, via0 = iscale_champ_sta(None)
    check(sta0 is None and via0 == "f4_iscale_champ", f"empty champ STA is not host arrivals, got {via0}")
    sta1, via1 = iscale_champ_sta({"sta": "/tmp/extract/sta_arrivals.json"})
    check(via1 == "extract" and via1 != "f4_host_arrivals", f"champ STA is extract-only, got {via1}")
    check("host" not in via1, f"champ STA via refuses host flatten ({via1})")
    mem_hr.add(
        Candidate(
            id="icrp",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "decap_200f",
                "extract_id": "icreg",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
                "i_scale": 1.0,
            },
            knobs_fp="icrp",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.921, static_ir_mv=6.178, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_ir_cell_region_pdn", "residual_vs_host_win_mv": -0.095},
        )
    )
    win_ir1 = winning_ir_pdn(mem_hr)
    check(win_ir1 is not None and win_ir1.id == "icrp", f"winning_ir_pdn picks IR-cell-region-PDN 3.921, got {win_ir1}")
    check(winning_host_pdn(mem_hr).id == "hdecapr", "winning_host_pdn still does not steal the IR-cell-region-PDN mesh")
    pay_sc1, why_sc1 = should_pay_f4_scale_champ(mem_hr, budget_left=80, n_scale=0)
    check(pay_sc1, f"champion I-scale is paid on a different IR-cell mesh ({why_sc1})")
    check("not I-scale-win" in why_sc1 and "not host arrivals" in why_sc1, f"champion I-scale refuses host flatten ({why_sc1})")
    check("3.921" in why_sc1, f"champion I-scale names the 3.921 point ({why_sc1})")
    pay_sc2, why_sc2 = should_pay_f4_scale_champ(mem_hr, budget_left=80, n_scale=1)
    check(not pay_sc2, f"champion I-scale is a single shot ({why_sc2})")
    champ_inst = inst_dir / "champ_inst_power_map.json"
    champ_inst.write_text(
        json.dumps(
            {
                "insts": [
                    {"name": "dpath/a_reg/_078_", "cell": "DFF_X1", "x": 25400, "y": 19800, "seq": True, "filler": False},
                    {"name": "dpath/b_mux/_45_", "cell": "MUX2_X1", "x": 25600, "y": 19900, "seq": False, "filler": False},
                    {"name": "dpath/a_reg/_076_", "cell": "INV_X1", "x": 25200, "y": 19700, "seq": False, "filler": False},
                    {"name": "dpath/b_mux/_46_", "cell": "NAND2_X1", "x": 25800, "y": 20000, "seq": False, "filler": False},
                    {"name": "ctrl/_11_", "cell": "NOR2_X1", "x": 38950, "y": 15400, "seq": False, "filler": False},
                    {"name": "FILLCELL_X1", "cell": "FILLCELL_X1", "x": 25463, "y": 19826, "seq": False, "filler": True},
                ]
            }
        )
        + "\n"
    )
    mem_hr.add(
        Candidate(
            id="iscchamp",
            design_id="gcd",
            parent_id="ircell",
            level="pdn",
            knobs={"source": "f4_iscale_champ", "parent_id": "ircell", "extract_id": "icreg", "i_scale": 4.21},
            knobs_fp="iscchamp",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=16.52, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_iscale_champ",
                "x_dbu": 25463.0,
                "y_dbu": 19826.0,
                "region": "r10",
                "combo_frac": 0.86,
            },
            artifacts={"insts": str(champ_inst), "x_dbu": 25463.0, "y_dbu": 19826.0},
        )
    )
    pay_sc3, why_sc3 = should_pay_f4_scale_champ(mem_hr, budget_left=80, n_scale=0)
    check(not pay_sc3, f"champion I-scale skips once measured ({why_sc3})")
    check(winning_ir_pdn(mem_hr).id == "icrp", "scaled I-scale-champ does not steal the 1× champion")
    from dse.active import steer_from_iscale_champ_hotspot

    pay_icc0, why_icc0 = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=None)
    check(not pay_icc0, f"I-scale-champ cell waits for a hotspot steer ({why_icc0})")
    st_icc = steer_from_iscale_champ_hotspot(mem_hr)
    check(st_icc is not None and st_icc.get("level") == "ir_cell_champ", f"combo-heavy champ hotspot steers a cell size-up, got {st_icc}")
    check("dpath" in (st_icc.get("modules") or []), f"champ join names dpath, got {st_icc}")
    check("ctrl/_11_" not in (st_icc.get("cells") or []), f"champ join is not the first ctrl IR-cell set, got {st_icc}")
    check("first ctrl" in (st_icc.get("reason") or ""), f"champ steer refuses first ctrl flatten ({st_icc})")
    pay_icc1, why_icc1 = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=st_icc)
    check(pay_icc1, f"I-scale-champ cell is paid after a combo-heavy join ({why_icc1})")
    check("dpath" in why_icc1, f"I-scale-champ cell acquire names dpath ({why_icc1})")
    fake_ctrl = dict(st_icc)
    fake_ctrl["cells"] = ["ctrl/_11_", "ctrl/_14_"]
    pay_icc_ref, why_icc_ref = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=fake_ctrl)
    check(not pay_icc_ref, f"I-scale-champ cell refuses the first IR-cell set ({why_icc_ref})")
    pay_icc2, why_icc2 = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=st_icc, n_cell=1)
    check(not pay_icc2, f"I-scale-champ cell is a single shot ({why_icc2})")
    ice_c2 = next(c for c in mem_hr.all() if c.id == "iscchamp")
    ice_c2.attr = dict(ice_c2.attr or {})
    ice_c2.attr["combo_frac"] = 0.32
    mem_hr.touch(ice_c2)
    check(steer_from_iscale_champ_hotspot(mem_hr) is None, "seq-heavy I-scale-champ hotspot does not steal another combo size-up")
    ice_c2.attr["combo_frac"] = 0.86
    mem_hr.touch(ice_c2)
    from dse.active import ir_cell_champ_host, ir_cell_host, steer_from_ir_cell_champ_residual

    pay_icce0, why_icce0 = should_pay_ir_cell_champ_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_icce0, f"IR-cell-champ extract waits for a dpath-sized netlist ({why_icce0})")
    mem_hr.add(
        Candidate(
            id="icchamp",
            design_id="gcd",
            parent_id="ircell",
            level="cell",
            knobs={
                "source": "cell_size_ir_champ",
                "cells": ["dpath/a_reg/_078_", "dpath/b_mux/_45_"],
                "ir_join": 1,
                "champ": 1,
                "parent_id": "ircell",
                "extract_id": "icreg",
            },
            knobs_fp="icchamp",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=568.708, wns_cost=0.302, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(dummy_host), "n_changed": 2},
            attr={"via": "active_f4_ir_cell_champ"},
        )
    )
    check(ir_cell_champ_host(mem_hr) is not None and ir_cell_champ_host(mem_hr).id == "icchamp", "ir_cell_champ_host is the dpath size-up")
    check(ir_cell_host(mem_hr).id == "ircell", "ir_cell_host stays the first ctrl IR-cell")
    pay_icce1, why_icce1 = should_pay_ir_cell_champ_extract(mem_hr, budget_left=80, n_extract=0)
    check(pay_icce1, f"IR-cell-champ extract is paid after dpath size-up ({why_icce1})")
    check("dpath" in why_icce1, f"IR-cell-champ extract acquire names dpath ({why_icce1})")
    check("IR-cell extract" in why_icce1, f"IR-cell-champ extract residuals vs IR-cell extract ({why_icce1})")
    check("host extract" in why_icce1, f"IR-cell-champ extract refuses host flatten ({why_icce1})")
    pay_icce2, why_icce2 = should_pay_ir_cell_champ_extract(mem_hr, budget_left=80, n_extract=1)
    check(not pay_icce2, f"IR-cell-champ extract is a single shot ({why_icce2})")
    mem_hr.add(
        Candidate(
            id="iccext",
            design_id="gcd",
            parent_id="icchamp",
            level="pdn",
            knobs={
                "source": "f4_ir_cell_champ_extract",
                "parent_id": "icchamp",
                "extract_id": "iccext",
                "parent_extract_id": "icreg",
                "ir_join": 1,
                "champ": 1,
            },
            knobs_fp="iccext",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=12.40, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_ir_cell_champ_extract",
                "residual_mv": -1.68,
                "residual_via": "ir_cell_champ_vs_ir_cell_extract",
            },
        )
    )
    win_host2 = winning_host_pdn(mem_hr)
    check(win_host2 is not None and win_host2.id != "iccext", "winning_host_pdn does not steal the IR-cell-champ extract")
    pay_icce3, why_icce3 = should_pay_ir_cell_champ_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_icce3, f"IR-cell-champ extract skips once measured ({why_icce3})")
    st_iccp = steer_from_ir_cell_champ_residual(mem_hr)
    check(st_iccp is not None and (st_iccp.get("spec") or {}).get("name") == "decap_200f", f"IR-cell-champ residual steers winning decap, got {st_iccp}")
    check(st_iccp.get("extract_id") == "iccext", f"IR-cell-champ PDN stays on the dpath-sized mesh, got {st_iccp}")
    check(st_iccp.get("host_source") == "f4_ir_cell_champ_extract", "IR-cell-champ PDN names the champ extract")
    check(st_iccp.get("extract_id") != "icext", "IR-cell-champ PDN does not restamp the first IR-cell extract")
    pay_iccp0, why_iccp0 = should_pay_ir_cell_champ_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_iccp0, f"IR-cell-champ PDN waits for a residual steer ({why_iccp0})")
    pay_iccp1, why_iccp1 = should_pay_ir_cell_champ_pdn(mem_hr, budget_left=80, steer=st_iccp)
    check(pay_iccp1, f"IR-cell-champ PDN is paid after the 1× residual ({why_iccp1})")
    fake_ice = dict(st_iccp)
    fake_ice["host_source"] = "f4_ir_cell_extract"
    pay_iccp_ref, why_iccp_ref = should_pay_ir_cell_champ_pdn(mem_hr, budget_left=80, steer=fake_ice)
    check(not pay_iccp_ref, f"IR-cell-champ PDN refuses the first IR-cell extract ({why_iccp_ref})")
    pay_iccp2, why_iccp2 = should_pay_ir_cell_champ_pdn(mem_hr, budget_left=80, steer=st_iccp, n_steer=1)
    check(not pay_iccp2, f"IR-cell-champ PDN is a single shot ({why_iccp2})")
    pay_icc_same, why_icc_same = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=st_icc)
    check(not pay_icc_same, f"I-scale-champ cell refuses a second shot on the same extract ({why_icc_same})")
    check("this extract" in why_icc_same, f"I-scale-champ cell names the extract cap ({why_icc_same})")
    strap_inst = inst_dir / "strap_inst_power_map.json"
    strap_inst.write_text(
        json.dumps(
            {
                "insts": [
                    {"name": "ctrl/_04_", "cell": "NOR2_X1", "x": 38965, "y": 14055, "seq": False, "filler": False},
                    {"name": "ctrl/_07_", "cell": "AOI21_X1", "x": 39100, "y": 14100, "seq": False, "filler": False},
                    {"name": "ctrl/_08_", "cell": "INV_X1", "x": 38800, "y": 13900, "seq": False, "filler": False},
                    {"name": "dpath/a_reg/_078_", "cell": "OAI21_X1", "x": 25400, "y": 19800, "seq": False, "filler": False},
                    {"name": "FILLCELL_X1", "cell": "FILLCELL_X1", "x": 38965, "y": 14055, "seq": False, "filler": True},
                ]
            }
        )
        + "\n"
    )
    mem_hr.add(
        Candidate(
            id="iscstrap",
            design_id="gcd",
            parent_id="ircell",
            level="pdn",
            knobs={"source": "f4_iscale_champ", "parent_id": "ircell", "extract_id": "strap9", "i_scale": 4.21},
            knobs_fp="iscstrap",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=7.187, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_iscale_champ",
                "x_dbu": 38965.0,
                "y_dbu": 14055.0,
                "region": "r10",
                "combo_frac": 0.96,
                "join": "odb-geom",
                "modules": ["ctrl"],
                "cells": ["ctrl/_04_", "ctrl/_07_", "ctrl/_08_"],
            },
            artifacts={"insts": str(strap_inst), "x_dbu": 38965.0, "y_dbu": 14055.0},
        )
    )
    st_icc2 = steer_from_iscale_champ_hotspot(mem_hr)
    check(st_icc2 is not None and st_icc2.get("extract_id") == "strap9", f"new winning_ir extract steers a new champ join, got {st_icc2}")
    check("ctrl/_04_" in (st_icc2.get("cells") or []), f"strap champ join names ctrl/_04_, got {st_icc2}")
    check("ctrl/_11_" not in (st_icc2.get("cells") or []), f"strap champ join is not the first ctrl set, got {st_icc2}")
    pay_icc_new, why_icc_new = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=st_icc2)
    check(pay_icc_new, f"I-scale-champ cell re-pays when the extract moves ({why_icc_new})")
    check("ctrl" in why_icc_new, f"moved-extract champ cell names ctrl ({why_icc_new})")
    fake_first = dict(st_icc2)
    fake_first["cells"] = ["ctrl/_11_", "ctrl/_14_"]
    pay_icc_first, why_icc_first = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=fake_first)
    check(not pay_icc_first, f"moved-extract champ still refuses the first IR-cell set ({why_icc_first})")
    mem_hr.add(
        Candidate(
            id="icchamp2",
            design_id="gcd",
            parent_id="ircell",
            level="cell",
            knobs={
                "source": "cell_size_ir_champ",
                "cells": ["ctrl/_04_", "ctrl/_07_", "ctrl/_08_"],
                "ir_join": 1,
                "champ": 1,
                "parent_id": "ircell",
                "extract_id": "strap9",
            },
            knobs_fp="icchamp2",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=570.0, wns_cost=0.31, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(dummy_host), "n_changed": 3},
            attr={"via": "active_f4_ir_cell_champ"},
        )
    )
    pay_icc_spent, why_icc_spent = should_pay_ir_cell_champ(mem_hr, budget_left=80, steer=st_icc2)
    check(not pay_icc_spent, f"moved-extract champ cell skips once sized on that extract ({why_icc_spent})")
    pay_icce_new, why_icce_new = should_pay_ir_cell_champ_extract(mem_hr, budget_left=80, n_extract=0)
    check(pay_icce_new, f"IR-cell-champ extract re-pays on the new size-up ({why_icce_new})")
    check("ctrl" in why_icce_new, f"moved-extract champ extract names ctrl ({why_icce_new})")
    mem_hr.add(
        Candidate(
            id="iccext2",
            design_id="gcd",
            parent_id="icchamp2",
            level="pdn",
            knobs={
                "source": "f4_ir_cell_champ_extract",
                "parent_id": "icchamp2",
                "extract_id": "iccext2",
                "parent_extract_id": "strap9",
                "ir_join": 1,
                "champ": 1,
            },
            knobs_fp="iccext2",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=8.10, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_ir_cell_champ_extract",
                "residual_mv": -1.10,
                "residual_via": "ir_cell_champ_vs_ir_cell_extract",
            },
        )
    )
    pay_icce_spent, why_icce_spent = should_pay_ir_cell_champ_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_icce_spent, f"IR-cell-champ extract skips once measured on that extract ({why_icce_spent})")
    st_iccp2 = steer_from_ir_cell_champ_residual(mem_hr)
    check(st_iccp2 is not None and st_iccp2.get("extract_id") == "iccext2", f"new champ extract steers its own PDN, got {st_iccp2}")
    pay_iccp_new, why_iccp_new = should_pay_ir_cell_champ_pdn(mem_hr, budget_left=80, steer=st_iccp2, n_steer=0)
    check(pay_iccp_new, f"IR-cell-champ PDN re-pays on the new champ extract ({why_iccp_new})")
    from dse.active import (
        ir_cell_champ_cone_host,
        ir_cell_champ_extract_cand,
        steer_from_ir_cell_champ_cone_residual,
        steer_from_ir_cell_champ_extract_hotspot,
    )

    ice_c2x = next(c for c in mem_hr.all() if c.id == "iccext2")
    ice_c2x.attr = dict(ice_c2x.attr or {})
    ice_c2x.attr.update(
        {
            "join": "odb-geom",
            "combo_frac": 0.90,
            "region": "r00",
            "cells": [
                "ctrl/_04_",
                "ctrl/_11_",
                "dpath/b_reg/_078_",
                "dpath/b_mux/_46_",
                "dpath/b_reg/_077_",
            ],
            "modules": ["ctrl", "dpath"],
        }
    )
    mem_hr.touch(ice_c2x)
    pay_iccc0, why_iccc0 = should_pay_ir_cell_champ_cone(mem_hr, budget_left=80, steer=None)
    check(not pay_iccc0, f"leftover-cone cell waits for a hotspot residual ({why_iccc0})")
    st_iccc = steer_from_ir_cell_champ_extract_hotspot(mem_hr)
    check(st_iccc is not None and st_iccc.get("level") == "ir_cell_champ_cone", f"champ-extract leftover steers a cone size-up, got {st_iccc}")
    check(st_iccc.get("extract_id") == "iccext2", f"leftover-cone stays on the champ extract, got {st_iccc}")
    check("dpath" in (st_iccc.get("modules") or []), f"leftover-cone names dpath, got {st_iccc}")
    check("dpath/b_reg/_078_" in (st_iccc.get("cells") or []), f"leftover-cone keeps dpath/_078_, got {st_iccc}")
    check("dpath/b_mux/_46_" in (st_iccc.get("cells") or []), f"leftover-cone keeps dpath mux, got {st_iccc}")
    check("ctrl/_04_" not in (st_iccc.get("cells") or []), f"leftover-cone drops the champ size-up set, got {st_iccc}")
    check("champ size-up" in (st_iccc.get("reason") or ""), f"leftover-cone reason refuses champ flatten ({st_iccc})")
    pay_iccc1, why_iccc1 = should_pay_ir_cell_champ_cone(mem_hr, budget_left=80, steer=st_iccc)
    check(pay_iccc1, f"leftover-cone cell is paid after a combo-heavy residual ({why_iccc1})")
    check("dpath" in why_iccc1, f"leftover-cone acquire names dpath ({why_iccc1})")
    fake_cone_ctrl = dict(st_iccc)
    fake_cone_ctrl["cells"] = ["ctrl/_11_", "ctrl/_14_"]
    pay_iccc_first, why_iccc_first = should_pay_ir_cell_champ_cone(mem_hr, budget_left=80, steer=fake_cone_ctrl)
    check(not pay_iccc_first, f"leftover-cone refuses the first IR-cell set ({why_iccc_first})")
    fake_cone_champ = dict(st_iccc)
    fake_cone_champ["cells"] = ["ctrl/_04_", "ctrl/_07_", "ctrl/_08_"]
    pay_iccc_champ, why_iccc_champ = should_pay_ir_cell_champ_cone(mem_hr, budget_left=80, steer=fake_cone_champ)
    check(not pay_iccc_champ, f"leftover-cone refuses the champ size-up set ({why_iccc_champ})")
    pay_iccc2, why_iccc2 = should_pay_ir_cell_champ_cone(mem_hr, budget_left=80, steer=st_iccc, n_cell=1)
    check(not pay_iccc2, f"leftover-cone cell is a single shot ({why_iccc2})")
    ice_c2x.attr["combo_frac"] = 0.32
    mem_hr.touch(ice_c2x)
    check(steer_from_ir_cell_champ_extract_hotspot(mem_hr) is None, "seq-heavy champ-extract hotspot does not steal another leftover cone")
    ice_c2x.attr["combo_frac"] = 0.90
    mem_hr.touch(ice_c2x)
    pay_iccce0, why_iccce0 = should_pay_ir_cell_champ_cone_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_iccce0, f"leftover-cone extract waits for a leftover-cone netlist ({why_iccce0})")
    mem_hr.add(
        Candidate(
            id="iccone",
            design_id="gcd",
            parent_id="icchamp2",
            level="cell",
            knobs={
                "source": "cell_size_ir_champ_cone",
                "cells": ["dpath/b_reg/_078_", "dpath/b_mux/_46_", "dpath/b_reg/_077_"],
                "ir_join": 1,
                "champ": 1,
                "champ_cone": 1,
                "parent_id": "icchamp2",
                "extract_id": "iccext2",
            },
            knobs_fp="iccone",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=572.0, wns_cost=0.32, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(dummy_host), "n_changed": 3},
            attr={"via": "active_f4_ir_cell_champ_cone"},
        )
    )
    check(ir_cell_champ_cone_host(mem_hr) is not None and ir_cell_champ_cone_host(mem_hr).id == "iccone", "ir_cell_champ_cone_host is the leftover dpath size-up")
    check(ir_cell_champ_host(mem_hr).id == "icchamp2", "ir_cell_champ_host stays the champ ctrl size-up")
    check(ir_cell_host(mem_hr).id == "ircell", "ir_cell_host stays the first ctrl IR-cell")
    pay_iccce1, why_iccce1 = should_pay_ir_cell_champ_cone_extract(mem_hr, budget_left=80, n_extract=0)
    check(pay_iccce1, f"leftover-cone extract is paid after leftover size-up ({why_iccce1})")
    check("dpath" in why_iccce1, f"leftover-cone extract acquire names dpath ({why_iccce1})")
    check("IR-cell-champ extract" in why_iccce1, f"leftover-cone extract residuals vs champ extract ({why_iccce1})")
    check("host extract" in why_iccce1, f"leftover-cone extract refuses host flatten ({why_iccce1})")
    pay_iccce2, why_iccce2 = should_pay_ir_cell_champ_cone_extract(mem_hr, budget_left=80, n_extract=1)
    check(not pay_iccce2, f"leftover-cone extract is a single shot ({why_iccce2})")
    mem_hr.add(
        Candidate(
            id="icccxt",
            design_id="gcd",
            parent_id="iccone",
            level="pdn",
            knobs={
                "source": "f4_ir_cell_champ_cone_extract",
                "parent_id": "iccone",
                "extract_id": "icccxt",
                "parent_extract_id": "iccext2",
                "ir_join": 1,
                "champ": 1,
                "champ_cone": 1,
            },
            knobs_fp="icccxt",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=15.20, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_ir_cell_champ_cone_extract",
                "residual_mv": 7.10,
                "residual_via": "ir_cell_champ_cone_vs_ir_cell_champ_extract",
            },
        )
    )
    check(ir_cell_champ_extract_cand(mem_hr).id == "iccext2", "cone extract does not steal ir_cell_champ_extract_cand")
    check(winning_ir_pdn(mem_hr).id == "icrp", "high leftover-cone droop does not steal the 1× champion")
    pay_iccce3, why_iccce3 = should_pay_ir_cell_champ_cone_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_iccce3, f"leftover-cone extract skips once measured ({why_iccce3})")
    st_icccp = steer_from_ir_cell_champ_cone_residual(mem_hr)
    check(st_icccp is not None and (st_icccp.get("spec") or {}).get("name") == "decap_200f", f"leftover-cone residual steers winning decap, got {st_icccp}")
    check(st_icccp.get("extract_id") == "icccxt", f"leftover-cone PDN stays on the leftover mesh, got {st_icccp}")
    check(st_icccp.get("host_source") == "f4_ir_cell_champ_cone_extract", "leftover-cone PDN names the cone extract")
    check(st_icccp.get("extract_id") != "iccext2", "leftover-cone PDN does not restamp the champ extract")
    pay_icccp0, why_icccp0 = should_pay_ir_cell_champ_cone_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_icccp0, f"leftover-cone PDN waits for a residual steer ({why_icccp0})")
    pay_icccp1, why_icccp1 = should_pay_ir_cell_champ_cone_pdn(mem_hr, budget_left=80, steer=st_icccp)
    check(pay_icccp1, f"leftover-cone PDN is paid after the 1× residual ({why_icccp1})")
    fake_cone_ext = dict(st_icccp)
    fake_cone_ext["host_source"] = "f4_ir_cell_champ_extract"
    pay_icccp_ref, why_icccp_ref = should_pay_ir_cell_champ_cone_pdn(mem_hr, budget_left=80, steer=fake_cone_ext)
    check(not pay_icccp_ref, f"leftover-cone PDN refuses the champ extract ({why_icccp_ref})")
    pay_icccp2, why_icccp2 = should_pay_ir_cell_champ_cone_pdn(mem_hr, budget_left=80, steer=st_icccp, n_steer=1)
    check(not pay_icccp2, f"leftover-cone PDN is a single shot ({why_icccp2})")
    pay_iccc_same, why_iccc_same = should_pay_ir_cell_champ_cone(mem_hr, budget_left=80, steer=st_iccc)
    check(not pay_iccc_same, f"leftover-cone cell refuses a second shot on the same extract ({why_iccc_same})")
    check("this extract" in why_iccc_same, f"leftover-cone cell names the extract cap ({why_iccc_same})")
    from dse.active import (
        ir_cell_champ_cone_extract_cand,
        ir_cell_champ_cone_region_extract_cand,
        steer_from_ir_cell_champ_cone_hotspot,
        steer_from_ir_cell_champ_cone_region_hotspot,
        steer_from_ir_cell_champ_cone_region_residual,
    )

    ice_cx = next(c for c in mem_hr.all() if c.id == "icccxt")
    ice_cx.attr = dict(ice_cx.attr or {})
    ice_cx.attr.update(
        {
            "join": "odb-geom",
            "combo_frac": 0.16,
            "seq_frac": 0.84,
            "region": "r03",
            "x_dbu": 10529.0,
            "y_dbu": 80945.0,
            "modules": ["ctrl"],
            "cells": ["ctrl/state/_08_", "ctrl/_11_", "ctrl/state/_09_"],
        }
    )
    mem_hr.touch(ice_cx)
    pay_icccr0, why_icccr0 = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=None)
    check(not pay_icccr0, f"leftover-cone region waits for a seq-heavy bin residual ({why_icccr0})")
    st_icccr = steer_from_ir_cell_champ_cone_hotspot(mem_hr)
    check(st_icccr is not None and st_icccr.get("level") == "ir_cell_champ_cone_region", f"seq-heavy leftover-cone bin steers a region cap, got {st_icccr}")
    check(st_icccr.get("region") == "r03", f"leftover-cone region names r03, got {st_icccr}")
    check(st_icccr.get("champ_region") == "r00", f"leftover-cone region names the champ bin, got {st_icccr}")
    check(st_icccr.get("extract_id") == "icccxt", f"leftover-cone region stays on the cone extract, got {st_icccr}")
    check("combo size-up" in (st_icccr.get("reason") or ""), f"leftover-cone region refuses more combo size-up ({st_icccr})")
    pay_icccr1, why_icccr1 = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=st_icccr)
    check(pay_icccr1, f"leftover-cone region is paid after a seq-heavy bin residual ({why_icccr1})")
    nxt_icccr = leftover_cone_region_next(mem_hr, budget_left=80)
    check(nxt_icccr is not None and nxt_icccr.get("kind") == "extract", f"leftover-cone-region next is extract, got {nxt_icccr}")
    check((nxt_icccr.get("steer") or {}).get("region") == "r03", f"leftover-cone-region next names r03, got {nxt_icccr}")
    check("r03" in why_icccr1 and "r00" in why_icccr1, f"leftover-cone region acquire names both bins ({why_icccr1})")
    fake_icr = dict(st_icccr)
    fake_icr["host_source"] = "f4_ir_cell_region_extract"
    pay_icccr_ref, why_icccr_ref = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=fake_icr)
    check(not pay_icccr_ref, f"leftover-cone region refuses IR-cell-region flatten ({why_icccr_ref})")
    pay_icccr2, why_icccr2 = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=st_icccr, n_extract=1)
    check(not pay_icccr2, f"leftover-cone region is a single shot ({why_icccr2})")
    ice_cx.attr["combo_frac"] = 0.78
    mem_hr.touch(ice_cx)
    check(steer_from_ir_cell_champ_cone_hotspot(mem_hr) is None, "combo-heavy leftover-cone hotspot does not steal a region cap")
    ice_cx.attr["combo_frac"] = 0.16
    ice_cx.attr["region"] = "r00"
    mem_hr.touch(ice_cx)
    check(steer_from_ir_cell_champ_cone_hotspot(mem_hr) is None, "leftover-cone region skips when the bin matches the champ extract")
    ice_cx.attr["region"] = "r03"
    mem_hr.touch(ice_cx)
    mem_hr.add(
        Candidate(
            id="icccrxt",
            design_id="gcd",
            parent_id="iccone",
            level="pdn",
            knobs={
                "source": "f4_ir_cell_champ_cone_region_extract",
                "parent_id": "iccone",
                "extract_id": "icccrxt",
                "parent_extract_id": "icccxt",
                "region": "r03",
                "ir_join": 1,
                "champ": 1,
                "champ_cone": 1,
            },
            knobs_fp="icccrxt",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=14.10, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_ir_cell_champ_cone_region_extract",
                "residual_mv": -1.10,
                "residual_via": "ir_cell_champ_cone_region_vs_ir_cell_champ_cone_extract",
                "region": "r03",
            },
        )
    )
    check(ir_cell_champ_cone_region_extract_cand(mem_hr).id == "icccrxt", "region extract is the leftover-cone-region cand")
    check(ir_cell_champ_cone_extract_cand(mem_hr).id == "icccxt", "region extract does not steal ir_cell_champ_cone_extract_cand")
    check(winning_ir_pdn(mem_hr).id == "icrp", "high leftover-cone-region droop does not steal the 1× champion")
    pay_icccr3, why_icccr3 = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=st_icccr, n_extract=0)
    check(not pay_icccr3, f"leftover-cone region skips once measured on that extract ({why_icccr3})")
    st_icccrp = steer_from_ir_cell_champ_cone_region_residual(mem_hr)
    check(st_icccrp is not None and (st_icccrp.get("spec") or {}).get("name") == "decap_200f", f"leftover-cone-region residual steers winning decap, got {st_icccrp}")
    check(st_icccrp.get("extract_id") == "icccrxt", f"leftover-cone-region PDN stays on the capped mesh, got {st_icccrp}")
    check(st_icccrp.get("host_source") == "f4_ir_cell_champ_cone_region_extract", "leftover-cone-region PDN names the region extract")
    check(st_icccrp.get("extract_id") != "icccxt", "leftover-cone-region PDN does not restamp the unconstrained cone extract")
    pay_icccrp0, why_icccrp0 = should_pay_ir_cell_champ_cone_region_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_icccrp0, f"leftover-cone-region PDN waits for |Δ| ≥ 1 mV ({why_icccrp0})")
    pay_icccrp1, why_icccrp1 = should_pay_ir_cell_champ_cone_region_pdn(mem_hr, budget_left=80, steer=st_icccrp)
    check(pay_icccrp1, f"leftover-cone-region PDN is paid after |Δ| ≥ 1 mV ({why_icccrp1})")
    nxt_icccrp = leftover_cone_region_next(mem_hr, budget_left=80)
    check(nxt_icccrp is not None and nxt_icccrp.get("kind") == "pdn", f"leftover-cone-region next is PDN after r03 extract, got {nxt_icccrp}")
    fake_cone_r = dict(st_icccrp)
    fake_cone_r["host_source"] = "f4_ir_cell_champ_cone_extract"
    pay_icccrp_ref, why_icccrp_ref = should_pay_ir_cell_champ_cone_region_pdn(mem_hr, budget_left=80, steer=fake_cone_r)
    check(not pay_icccrp_ref, f"leftover-cone-region PDN refuses the unconstrained cone extract ({why_icccrp_ref})")
    pay_icccrp2, why_icccrp2 = should_pay_ir_cell_champ_cone_region_pdn(mem_hr, budget_left=80, steer=st_icccrp, n_steer=1)
    check(not pay_icccrp2, f"leftover-cone-region PDN is a single shot ({why_icccrp2})")
    ice_cr = next(c for c in mem_hr.all() if c.id == "icccrxt")
    ice_cr.attr = dict(ice_cr.attr or {})
    ice_cr.attr.update(
        {
            "join": "odb-geom",
            "combo_frac": 0.16,
            "seq_frac": 0.84,
            "region": "r13",
            "x_dbu": 25520.0,
            "y_dbu": 80993.0,
            "modules": ["dpath"],
            "cells": ["dpath/b_reg/_078_", "dpath/b_reg/_077_", "dpath/b_mux/_43_"],
        }
    )
    mem_hr.touch(ice_cr)
    st_icccr13 = steer_from_ir_cell_champ_cone_region_hotspot(mem_hr)
    check(st_icccr13 is not None and st_icccr13.get("region") == "r13", f"seq-heavy leftover-cone-region residual steers r13, got {st_icccr13}")
    check(st_icccr13.get("cap_region") == "r03", f"r13 steer names the capped bin, got {st_icccr13}")
    check(st_icccr13.get("host_source") == "f4_ir_cell_champ_cone_region_extract", "r13 steer names the leftover-cone-region extract")
    check(st_icccr13.get("extract_id") == "icccrxt", f"r13 steer stays on the capped mesh, got {st_icccr13}")
    check("combo size-up" in (st_icccr13.get("reason") or ""), f"r13 steer refuses more combo size-up ({st_icccr13})")
    pay_r13, why_r13 = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=st_icccr13)
    check(pay_r13, f"leftover-cone-region re-pays when the hotspot leaves the capped bin ({why_r13})")
    check("r13" in why_r13 and "r03" in why_r13, f"r13 acquire names both bins ({why_r13})")
    pay_r03_again, why_r03_again = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=st_icccr)
    check(not pay_r03_again, f"leftover-cone-region does not re-cap r03 ({why_r03_again})")
    ice_cr.attr["combo_frac"] = 0.78
    mem_hr.touch(ice_cr)
    check(steer_from_ir_cell_champ_cone_region_hotspot(mem_hr) is None, "combo-heavy leftover-cone-region hotspot does not steal another density cap")
    ice_cr.attr["combo_frac"] = 0.16
    ice_cr.attr["region"] = "r03"
    mem_hr.touch(ice_cr)
    check(steer_from_ir_cell_champ_cone_region_hotspot(mem_hr) is None, "leftover-cone-region skips when the hotspot matches the capped bin")
    ice_cr.attr["region"] = "r13"
    mem_hr.touch(ice_cr)
    mem_hr.add(
        Candidate(
            id="icccrxt2",
            design_id="gcd",
            parent_id="iccone",
            level="pdn",
            knobs={
                "source": "f4_ir_cell_champ_cone_region_extract",
                "parent_id": "iccone",
                "extract_id": "icccrxt2",
                "parent_extract_id": "icccrxt",
                "region": "r13",
                "ir_join": 1,
                "champ": 1,
                "champ_cone": 1,
            },
            knobs_fp="icccrxt2",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=10.00, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_ir_cell_champ_cone_region_extract",
                "residual_mv": -4.10,
                "residual_via": "ir_cell_champ_cone_region_vs_prior_region",
                "residual_vs": "icccrxt",
                "region": "r13",
            },
        )
    )
    check(ir_cell_champ_cone_region_extract_cand(mem_hr).id == "icccrxt2", "newest leftover-cone-region extract is the r13 cap")
    check(winning_ir_pdn(mem_hr).id == "icrp", "high leftover-cone-region r13 droop does not steal the 1× champion")
    pay_r13b, why_r13b = should_pay_ir_cell_champ_cone_region(mem_hr, budget_left=80, steer=st_icccr13, n_extract=0)
    check(not pay_r13b, f"leftover-cone-region skips once r13 is measured ({why_r13b})")
    st_icccrp13 = steer_from_ir_cell_champ_cone_region_residual(mem_hr)
    check(st_icccrp13 is not None and st_icccrp13.get("extract_id") == "icccrxt2", f"r13 residual steers PDN on the r13 mesh, got {st_icccrp13}")
    check(st_icccrp13.get("extract_id") != "icccrxt", "r13 PDN does not restamp the r03 mesh")
    pay_r13p, why_r13p = should_pay_ir_cell_champ_cone_region_pdn(mem_hr, budget_left=80, steer=st_icccrp13)
    check(pay_r13p, f"leftover-cone-region PDN re-pays on the r13 mesh ({why_r13p})")
    nxt_r13 = leftover_cone_region_next(mem_hr, budget_left=80)
    check(nxt_r13 is not None and nxt_r13.get("kind") == "pdn", f"leftover-cone-region next is r13 PDN, got {nxt_r13}")
    check((nxt_r13.get("steer") or {}).get("extract_id") == "icccrxt2", f"leftover-cone-region next PDN stays on r13, got {nxt_r13}")
    pay_amgc1, why_amgc1 = should_pay_f4_amg_champ(mem_hr, budget_left=80, n_amg=0)
    check(pay_amgc1, f"champion AMG is paid on winning_ir_pdn ({why_amgc1})")
    check("3.921" in why_amgc1, f"champion AMG names the 3.921 point ({why_amgc1})")
    check("not candidate AMG" in why_amgc1 and "not gold" in why_amgc1, f"champion AMG refuses candidate/gold flatten ({why_amgc1})")
    check("icreg" in why_amgc1, f"champion AMG names the IR-cell-region extract ({why_amgc1})")
    pay_amgc2, why_amgc2 = should_pay_f4_amg_champ(mem_hr, budget_left=80, n_amg=1)
    check(not pay_amgc2, f"champion AMG is a single shot ({why_amgc2})")
    pay_rasc0, why_rasc0 = should_pay_f4_ras_champ(mem_hr, budget_left=80, n_ras=0)
    check(not pay_rasc0, f"champion RAS waits for champion AMG on the same extract ({why_rasc0})")
    mem_hr.add(
        Candidate(
            id="amgfin",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_solver_amg", "extract_id": "finish", "name": "amg_residual"},
            knobs_fp="amgfin",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.3, fidelity="F4"),
            cost_s=1.0,
            status="ok",
        )
    )
    pay_rasc_fin, why_rasc_fin = should_pay_f4_ras_champ(mem_hr, budget_left=80, n_ras=0)
    check(not pay_rasc_fin, f"finish AMG does not unlock champion RAS ({why_rasc_fin})")
    mem_hr.add(
        Candidate(
            id="amgc",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={
                "source": "f4_solver_amg",
                "name": "amg_champ",
                "extract_id": "icreg",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
            },
            knobs_fp="amgc",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.920, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "f4_solver_amg_champ", "residual_vs_direct_mv": -0.001},
        )
    )
    pay_amgc3, why_amgc3 = should_pay_f4_amg_champ(mem_hr, budget_left=80, n_amg=0)
    check(not pay_amgc3, f"champion AMG skips once measured on that extract ({why_amgc3})")
    check(winning_ir_pdn(mem_hr).id == "icrp", "champion AMG does not steal the 1× DirectLU champion")
    pay_rasc1, why_rasc1 = should_pay_f4_ras_champ(mem_hr, budget_left=80, n_ras=0)
    check(pay_rasc1, f"champion RAS is paid after AMG on the same extract ({why_rasc1})")
    check("not candidate RAS" in why_rasc1 and "not gold" in why_rasc1, f"champion RAS refuses candidate/gold flatten ({why_rasc1})")
    pay_rasc2, why_rasc2 = should_pay_f4_ras_champ(mem_hr, budget_left=80, n_ras=1)
    check(not pay_rasc2, f"champion RAS is a single shot ({why_rasc2})")
    pay_kryc0, why_kryc0 = should_pay_f4_krylov_champ(mem_hr, budget_left=80, n_krylov=0)
    check(not pay_kryc0, f"champion Krylov waits for champion RAS on the same extract ({why_kryc0})")
    mem_hr.add(
        Candidate(
            id="rasc",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={
                "source": "f4_solver_ras",
                "name": "ras_champ",
                "extract_id": "icreg",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
            },
            knobs_fp="rasc",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.919, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "f4_solver_ras_champ", "residual_vs_direct_mv": -0.002},
        )
    )
    pay_kryc1, why_kryc1 = should_pay_f4_krylov_champ(mem_hr, budget_left=80, n_krylov=0)
    check(pay_kryc1, f"champion Krylov is paid after RAS on the same extract ({why_kryc1})")
    check("not candidate Krylov" in why_kryc1 and "not gold" in why_kryc1, f"champion Krylov refuses candidate/gold flatten ({why_kryc1})")
    pay_kryc2, why_kryc2 = should_pay_f4_krylov_champ(mem_hr, budget_left=80, n_krylov=1)
    check(not pay_kryc2, f"champion Krylov is a single shot ({why_kryc2})")
    mem_fin = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-mf-fin-")) / "f.jsonl")
    mem_fin.add(
        Candidate(
            id="goldwin",
            design_id="gcd",
            parent_id=None,
            level="pdn",
            knobs={
                "source": "f4_host_extract",
                "extract_id": "finish",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 50e-15,
                "i_scale": 1.0,
            },
            knobs_fp="goldwin",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=45.298, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "f4_host_extract"},
        )
    )
    pay_amg_fin, why_amg_fin = should_pay_f4_amg_champ(mem_fin, budget_left=80, n_amg=0)
    check(not pay_amg_fin, f"champion AMG refuses gold finish ({why_amg_fin})")
    check("finish" in why_amg_fin or "gold" in why_amg_fin, f"champion AMG names the gold refuse ({why_amg_fin})")
    from dse.active import winning_static_pdn, steer_from_static_ir_residual
    from dse.surrogate import residual_f4_static

    win_st = winning_static_pdn(mem_hr)
    check(win_st is not None and win_st.id == "icrp", f"winning_static_pdn tie-breaks to the 3.921 Dynamic IR point, got {win_st}")
    check(winning_ir_pdn(mem_hr).id == "icrp", "winning_ir_pdn stays the 3.921 Dynamic IR champ")
    check(winning_host_pdn(mem_hr).id == "hdecapr", "winning_host_pdn still does not steal the static-IR champ")
    st_sir = steer_from_static_ir_residual(mem_hr)
    check(st_sir is not None and (st_sir.get("spec") or {}).get("name") == "pkg_r_25m", f"static IR steers pkg_r, got {st_sir}")
    check(st_sir.get("extract_id") == "icreg", f"static IR stays on the static champ extract, got {st_sir}")
    check(abs(float((st_sir.get("spec") or {}).get("c_decap") or 0) - 200e-15) < 1e-18, "pkg_r inherits champ decap — residual is pkg_r-only")
    check((st_sir.get("spec") or {}).get("name") not in ("decap_200f", "pkg_l_100p"), "static IR does not consume the Dynamic IR catalog")
    pay_sir0, why_sir0 = should_pay_static_ir_steer(mem_hr, budget_left=80, steer=None)
    check(not pay_sir0, f"static IR waits for a pkg_r steer ({why_sir0})")
    pay_sir1, why_sir1 = should_pay_static_ir_steer(mem_hr, budget_left=80, steer=st_sir)
    check(pay_sir1, f"static IR pkg_r is paid on the 6.178 champ ({why_sir1})")
    check("not Dynamic IR-steer" in why_sir1 and "not gold" in why_sir1, f"static IR refuses Dynamic IR flatten ({why_sir1})")
    fake_decap = dict(st_sir)
    fake_decap["spec"] = {"name": "decap_200f", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15}
    pay_sir_ref, why_sir_ref = should_pay_static_ir_steer(mem_hr, budget_left=80, steer=fake_decap)
    check(not pay_sir_ref, f"static IR refuses a decap catalog point ({why_sir_ref})")
    pay_sir2, why_sir2 = should_pay_static_ir_steer(mem_hr, budget_left=80, steer=st_sir, n_steer=1)
    check(not pay_sir2, f"static IR pkg_r is a single shot ({why_sir2})")
    rstat = residual_f4_static(list(mem_hr.all()))
    check(rstat.get("metric") == "static_ir_mv", f"static residual is not Dynamic IR, got {rstat}")
    check(abs(float(rstat.get("winning_static_mv") or 0) - 6.178) < 1e-6, f"static residual names 6.178, got {rstat}")
    spec_st = next_static_pdn_spec(mem_hr, win_st)
    check(spec_st is not None and spec_st["name"] == "pkg_r_25m", f"next_static_pdn_spec proposes pkg_r, got {spec_st}")
    check(next_pdn_spec(mem_hr, extract_id="icreg") is not None, "Dynamic IR catalog is still independent of pkg_r")
    from dse.active import steer_from_static_mesh_residual

    check(steer_from_static_mesh_residual(mem_hr) is None, "static mesh waits for a null pkg_r residual")
    odb_sm = Path(tempfile.mkdtemp(prefix="dse-sm-")) / "candidate.odb"
    odb_sm.write_bytes(b"odb")
    ice_reg = next(c for c in mem_hr.all() if c.id == "icreg")
    ice_reg.artifacts = dict(ice_reg.artifacts or {})
    ice_reg.artifacts["odb"] = str(odb_sm)
    mem_hr.touch(ice_reg)
    mem_hr.add(
        Candidate(
            id="pkgr",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "pkg_r_25m",
                "extract_id": "icreg",
                "pkg_r": 0.025,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
                "i_scale": 1.0,
            },
            knobs_fp="pkgr",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.920, static_ir_mv=6.178, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_static_ir", "residual_vs_static_champ_mv": 0.0},
        )
    )
    st_sm = steer_from_static_mesh_residual(mem_hr)
    check(st_sm is not None and (st_sm.get("spec") or {}).get("name") == "bumps_80", f"null pkg_r residual steers bumps, got {st_sm}")
    check(st_sm.get("extract_id") == "icreg", f"static mesh stays on the static champ extract, got {st_sm}")
    check((st_sm.get("spec") or {}).get("name") not in ("decap_200f", "pkg_l_100p", "pkg_r_25m"), "static mesh does not consume pkg_r / Dynamic IR catalogs")
    check(st_sm.get("odb") == str(odb_sm), f"static mesh names the champ ODB, got {st_sm}")
    pay_sm0, why_sm0 = should_pay_static_mesh(mem_hr, budget_left=80, steer=None)
    check(not pay_sm0, f"static mesh waits for a bump steer ({why_sm0})")
    pay_sm1, why_sm1 = should_pay_static_mesh(mem_hr, budget_left=80, steer=st_sm)
    check(pay_sm1, f"static mesh bumps are paid after a null pkg_r residual ({why_sm1})")
    check("not Dynamic IR-steer" in why_sm1 and "not gold" in why_sm1, f"static mesh refuses Dynamic IR flatten ({why_sm1})")
    fake_pkg = dict(st_sm)
    fake_pkg["spec"] = {"name": "pkg_r_25m", "pkg_r": 0.025, "pkg_l": 2e-10, "c_decap": 200e-15}
    pay_sm_ref, why_sm_ref = should_pay_static_mesh(mem_hr, budget_left=80, steer=fake_pkg)
    check(not pay_sm_ref, f"static mesh refuses a pkg_r catalog point ({why_sm_ref})")
    pay_sm2, why_sm2 = should_pay_static_mesh(mem_hr, budget_left=80, steer=st_sm, n_steer=1)
    check(not pay_sm2, f"static mesh is a single shot ({why_sm2})")
    spec_sm = next_static_mesh_spec(mem_hr)
    check(spec_sm is not None and spec_sm["name"] == "bumps_80", f"next_static_mesh_spec proposes bumps_80, got {spec_sm}")
    mem_hr.add(
        Candidate(
            id="smfail",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={"source": "f4_static_mesh_extract", "name": "bumps_80", "bump_dx": 80.0, "bump_dy": 80.0},
            knobs_fp="smfail",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(fidelity="F4"),
            cost_s=0.2,
            status="fail",
        )
    )
    check(next_static_mesh_spec(mem_hr) is not None, "a failed bump extract does not consume the static-mesh catalog")
    from dse.active import steer_from_static_strap_residual

    check(steer_from_static_strap_residual(mem_hr) is None, "static straps wait for a null bump residual")
    mem_hr.add(
        Candidate(
            id="smok",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={
                "source": "f4_static_mesh_extract",
                "name": "bumps_80",
                "bump_dx": 80.0,
                "bump_dy": 80.0,
                "extract_id": "smok",
                "parent_extract_id": "icreg",
            },
            knobs_fp="smok",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.920, static_ir_mv=6.178, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_static_mesh", "residual_vs_static_champ_mv": 0.0},
        )
    )
    st_st = steer_from_static_strap_residual(mem_hr)
    check(st_st is not None and (st_st.get("spec") or {}).get("name") == "m4_pitch_8", f"null bump residual steers metal4, got {st_st}")
    check(st_st.get("extract_id") == "icreg", f"static straps stay on the static champ extract, got {st_st}")
    check((st_st.get("spec") or {}).get("name") not in ("decap_200f", "pkg_l_100p", "pkg_r_25m", "bumps_80"), "static straps do not consume bump / pkg_r / Dynamic IR catalogs")
    check(st_st.get("odb") == str(odb_sm), f"static straps name the champ ODB, got {st_st}")
    pay_st0, why_st0 = should_pay_static_straps(mem_hr, budget_left=80, steer=None)
    check(not pay_st0, f"static straps wait for a strap steer ({why_st0})")
    pay_st1, why_st1 = should_pay_static_straps(mem_hr, budget_left=80, steer=st_st)
    check(pay_st1, f"static straps are paid after a null bump residual ({why_st1})")
    check("not bumps" in why_st1 and "not gold" in why_st1, f"static straps refuse bump flatten ({why_st1})")
    fake_bump = dict(st_st)
    fake_bump["spec"] = {"name": "bumps_80", "bump_dx": 80.0, "bump_dy": 80.0}
    pay_st_ref, why_st_ref = should_pay_static_straps(mem_hr, budget_left=80, steer=fake_bump)
    check(not pay_st_ref, f"static straps refuse a bump catalog point ({why_st_ref})")
    pay_st2, why_st2 = should_pay_static_straps(mem_hr, budget_left=80, steer=st_st, n_steer=1)
    check(not pay_st2, f"static straps are a single shot ({why_st2})")
    spec_st = next_static_strap_spec(mem_hr)
    check(spec_st is not None and spec_st["name"] == "m4_pitch_8", f"next_static_strap_spec proposes m4_pitch_8, got {spec_st}")
    mem_hr.add(
        Candidate(
            id="stfail",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={"source": "f4_static_strap_extract", "name": "m4_pitch_8", "m4_pitch": 8.0},
            knobs_fp="stfail",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(fidelity="F4"),
            cost_s=0.2,
            status="fail",
        )
    )
    check(next_static_strap_spec(mem_hr) is not None, "a failed strap extract does not consume the static-strap catalog")
    from dse.active import winning_ir_pdn as _win_ir

    win_after_st = _win_ir(mem_hr)
    check(win_after_st is not None and win_after_st.id == "icrp", f"winning_ir_pdn ignores a failed strap extract, got {getattr(win_after_st, 'id', None)}")
    mem_hr.add(
        Candidate(
            id="stok",
            design_id="gcd",
            parent_id="icreg",
            level="pdn",
            knobs={
                "source": "f4_static_strap_extract",
                "name": "m4_pitch_8",
                "m4_pitch": 8.0,
                "m4_width": 0.48,
                "extract_id": "stok",
                "parent_extract_id": "icreg",
                "c_decap": 2e-13,
                "pkg_r": 0.025,
                "pkg_l": 2e-10,
                "i_scale": 1.0,
            },
            knobs_fp="stok",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=2.210, static_ir_mv=0.963, em_j_a_m2=9.22e9, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_static_straps", "residual_vs_static_champ_mv": -5.215},
            artifacts={"spice": "/tmp/x.sp", "insts": "/tmp/x.json", "n_r": 3649},
        )
    )
    win_strap = _win_ir(mem_hr)
    check(win_strap is not None and win_strap.id == "stok", f"a new strap R-graph can become winning_ir_pdn, got {getattr(win_strap, 'id', None)}")
    check(winning_host_pdn(mem_hr).id == "hdecapr", "winning_host_pdn stays host-only after a strap champ")
    check(champ_mf_n(mem_hr, "f4_solver_amg_champ") == 0, "AMG-champ on the old extract does not spend the new strap extract")
    pay_amg_st, why_amg_st = should_pay_f4_amg_champ(mem_hr, budget_left=80, n_amg=0)
    check(pay_amg_st, f"champion AMG is re-paid on the strap extract ({why_amg_st})")
    check("stok" in why_amg_st or "2.210" in why_amg_st or "m4_pitch_8" in why_amg_st, f"champion AMG names the strap champ ({why_amg_st})")
    pay_sc_st, why_sc_st = should_pay_f4_scale_champ(mem_hr, budget_left=80, n_scale=0)
    check(pay_sc_st, f"champion I-scale re-pays when winning_ir moves to the strap extract ({why_sc_st})")
    check("2.210" in why_sc_st or "m4_pitch_8" in why_sc_st or "stok" in why_sc_st, f"champion I-scale names the strap champ ({why_sc_st})")
    from dse.active import steer_from_em_width_residual, winning_em_pdn

    check(steer_from_em_width_residual(mem_hr) is not None or next_static_strap_spec(mem_hr) is None, "EM width sees a consumed pitch catalog")
    # pitch catalog is consumed by stok
    check(next_static_strap_spec(mem_hr) is None, "ok strap extract consumes the pitch catalog")
    st_em = steer_from_em_width_residual(mem_hr)
    check(st_em is not None and (st_em.get("spec") or {}).get("name") == "m4_width_96", f"strap pitch unlocks EM width, got {st_em}")
    check(abs(float((st_em.get("spec") or {}).get("m4_pitch") or 0) - 8.0) < 1e-9, "EM width inherits strap pitch 8")
    check((st_em.get("spec") or {}).get("name") not in ("m4_pitch_8", "bumps_80", "pkg_r_25m", "decap_200f"), "EM width does not consume pitch / bump / Dynamic IR catalogs")
    check(st_em.get("odb") == str(odb_sm), f"EM width names the place ODB, got {st_em}")
    pay_em0, why_em0 = should_pay_em_straps(mem_hr, budget_left=80, steer=None)
    check(not pay_em0, f"EM width waits for a width steer ({why_em0})")
    pay_em1, why_em1 = should_pay_em_straps(mem_hr, budget_left=80, steer=st_em)
    check(pay_em1, f"EM width is paid after strap pitch ({why_em1})")
    check("not pitch" in why_em1 and "not gold" in why_em1, f"EM width refuses pitch flatten ({why_em1})")
    fake_pitch = dict(st_em)
    fake_pitch["spec"] = {"name": "m4_pitch_8", "m4_pitch": 8.0, "m4_width": 0.48}
    pay_em_ref, why_em_ref = should_pay_em_straps(mem_hr, budget_left=80, steer=fake_pitch)
    check(not pay_em_ref, f"EM width refuses a pitch catalog point ({why_em_ref})")
    pay_em2, why_em2 = should_pay_em_straps(mem_hr, budget_left=80, steer=st_em, n_steer=1)
    check(not pay_em2, f"EM width is a single shot ({why_em2})")
    spec_em = next_em_strap_spec(mem_hr, next(c for c in mem_hr.all() if c.id == "stok"))
    check(spec_em is not None and spec_em["name"] == "m4_width_96", f"next_em_strap_spec proposes m4_width_96, got {spec_em}")
    win_em0 = winning_em_pdn(mem_hr)
    check(win_em0 is not None and win_em0.qor.em_j_a_m2 is not None, f"winning_em_pdn ranks J, got {win_em0}")
    from dse.active import steer_from_winning_ir_catalog

    check(
        steer_from_winning_ir_catalog(mem_ir) is None,
        "winning-IR catalog waits for a strap/EM R-graph",
    )
    stok_c = next(c for c in mem_hr.all() if c.id == "stok")
    spec_w = next_winning_ir_pdn_spec(mem_hr, stok_c)
    check(spec_w is not None and spec_w["name"] == "pkg_l_100p", f"unused Dynamic IR on strap mesh is pkg L, got {spec_w}")
    check(abs(float(spec_w["pkg_r"]) - 0.025) < 1e-12, "winning-IR catalog inherits host pkg_r — not gold 50 mΩ")
    check(abs(float(spec_w["c_decap"]) - 2e-13) < 1e-18, "winning-IR catalog inherits host 200 fF — inductance-only")
    check(abs(float(spec_w["pkg_l"]) - 1e-10) < 1e-18, "unused pkg L is 100 pH")
    st_w = steer_from_winning_ir_catalog(mem_hr)
    check(st_w is not None and (st_w.get("spec") or {}).get("name") == "pkg_l_100p", f"strap/EM champ unlocks unused pkg L, got {st_w}")
    check(st_w.get("extract_id") == "stok", f"winning-IR catalog restamps the strap extract, got {st_w}")
    check(
        (st_w.get("spec") or {}).get("name") not in ("m4_pitch_8", "m4_width_96", "bumps_80", "pkg_r_25m"),
        "winning-IR catalog does not consume pitch / width / bump / pkg_r catalogs",
    )
    pay_w0, why_w0 = should_pay_winning_ir_catalog(mem_hr, budget_left=80, steer=None)
    check(not pay_w0, f"winning-IR catalog waits for a steer ({why_w0})")
    pay_w1, why_w1 = should_pay_winning_ir_catalog(mem_hr, budget_left=80, steer=st_w)
    check(pay_w1, f"winning-IR catalog is paid on the strap extract ({why_w1})")
    check("not pitch" in why_w1 and "not gold" in why_w1, f"winning-IR catalog refuses flatten ({why_w1})")
    fake_w = dict(st_w)
    fake_w["spec"] = {"name": "m4_width_96", "m4_width": 0.96, "pkg_r": 0.025, "pkg_l": 2e-10, "c_decap": 2e-13}
    pay_w_ref, why_w_ref = should_pay_winning_ir_catalog(mem_hr, budget_left=80, steer=fake_w)
    check(not pay_w_ref, f"winning-IR catalog refuses a width catalog point ({why_w_ref})")
    mem_hr.add(
        Candidate(
            id="wirl",
            design_id="gcd",
            parent_id="stok",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "pkg_l_100p",
                "extract_id": "stok",
                "pkg_r": 0.025,
                "pkg_l": 1e-10,
                "c_decap": 2e-13,
                "i_scale": 1.0,
            },
            knobs_fp="wirl",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=1.700, static_ir_mv=0.963, em_j_a_m2=9.22e9, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_winning_ir_pdn", "residual_vs_winning_ir_mv": -0.510},
        )
    )
    win_l = _win_ir(mem_hr)
    check(win_l is not None and win_l.id == "wirl", f"unused pkg L on the strap mesh can become winning_ir_pdn, got {getattr(win_l, 'id', None)}")
    check(winning_host_pdn(mem_hr).id == "hdecapr", "winning_host_pdn stays host-only after winning-IR catalog")
    check(champ_mf_n(mem_hr, "f4_solver_amg_champ") == 0, "AMG-champ on the old extract does not spend the catalog extract")
    pay_amg_w, why_amg_w = should_pay_f4_amg_champ(mem_hr, budget_left=80, n_amg=0)
    check(pay_amg_w, f"champion AMG is re-paid after winning-IR catalog ({why_amg_w})")
    pay_sc_w, why_sc_w = should_pay_f4_scale_champ(mem_hr, budget_left=80, n_scale=0)
    check(pay_sc_w, f"champion I-scale re-pays after winning-IR catalog ({why_sc_w})")
    st_w2 = steer_from_winning_ir_catalog(mem_hr)
    check(st_w2 is None, f"Dynamic IR catalog on the strap extract is exhausted, got {st_w2}")
    pay_w2, why_w2 = should_pay_winning_ir_catalog(mem_hr, budget_left=80, steer=st_w, n_steer=2)
    check(not pay_w2, f"winning-IR catalog caps at decap + pkg L ({why_w2})")
    from dse.active import (
        steer_from_winning_ir_hotspot,
        steer_from_winning_ir_region_hotspot,
        steer_from_winning_ir_region_residual,
        winning_ir_extract_cand,
        winning_ir_region_extract_cand,
    )

    wir_inst = inst_dir / "winning_ir_inst_power_map.json"
    wir_inst.write_text(
        json.dumps(
            {
                "insts": [
                    {"name": "dpath/b_mux/_37_", "cell": "MUX2_X1", "x": 70800, "y": 3900, "seq": False, "filler": False},
                    {"name": "dpath/a_reg/_067_", "cell": "DFF_X1", "x": 70600, "y": 3800, "seq": True, "filler": False},
                    {"name": "dpath/a_reg/_069_", "cell": "INV_X1", "x": 71000, "y": 4000, "seq": False, "filler": False},
                    {"name": "dpath/b_mux/_35_", "cell": "NAND2_X1", "x": 71200, "y": 4100, "seq": False, "filler": False},
                    {"name": "dpath/b_reg/_070_", "cell": "DFF_X1", "x": 70400, "y": 3700, "seq": True, "filler": False},
                    {"name": "FILLCELL_X1", "cell": "FILLCELL_X1", "x": 70896, "y": 3942, "seq": False, "filler": True},
                ]
            }
        )
        + "\n"
    )
    stok_c = next(c for c in mem_hr.all() if c.id == "stok")
    stok_c.attr = dict(stok_c.attr or {})
    stok_c.attr.update(
        {
            "x_dbu": 70896.0,
            "y_dbu": 3942.0,
            "region": "r30",
            "combo_frac": 0.185,
            "seq_frac": 0.815,
            "cells": [],
        }
    )
    stok_c.artifacts = dict(stok_c.artifacts or {})
    stok_c.artifacts["insts"] = str(wir_inst)
    stok_c.artifacts["x_dbu"] = 70896.0
    stok_c.artifacts["y_dbu"] = 3942.0
    mem_hr.touch(stok_c)
    check(persist_hotspot_join(stok_c), "winning-IR 1× extract persists an ODB-geom join")
    check(stok_c.attr.get("join") == "odb-geom", f"winning-IR persist join is odb-geom, got {stok_c.attr}")
    check("dpath/b_mux/_37_" in (stok_c.attr.get("cells") or []), f"winning-IR join names dpath mux, got {stok_c.attr}")
    check(winning_ir_extract_cand(mem_hr) is not None and winning_ir_extract_cand(mem_hr).id == "stok", "winning-IR extract is the strap 1× R-graph")
    check(winning_ir_extract_cand(mem_hr).id != "icccxt", "winning-IR extract is not the leftover-cone mesh")
    pay_wir0, why_wir0 = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=None)
    check(not pay_wir0, f"winning-IR region waits for a seq-heavy bin residual ({why_wir0})")
    st_wir = steer_from_winning_ir_hotspot(mem_hr)
    check(st_wir is not None and st_wir.get("level") == "winning_ir_region", f"seq-heavy winning-IR bin steers a region cap, got {st_wir}")
    check(st_wir.get("region") == "r30", f"winning-IR region names r30, got {st_wir}")
    check(st_wir.get("ir_cell_region") == "r00", f"winning-IR region names the IR-cell-region bin, got {st_wir}")
    check(st_wir.get("extract_id") == "stok", f"winning-IR region stays on the winning-IR extract, got {st_wir}")
    check(st_wir.get("host_source") == "f4_static_strap_extract", f"winning-IR region names the strap extract, got {st_wir}")
    check("leftover-cone" in (st_wir.get("reason") or "") and "combo size-up" in (st_wir.get("reason") or ""), f"winning-IR region refuses leftover-cone flatten ({st_wir})")
    pay_wir1, why_wir1 = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=st_wir)
    check(pay_wir1, f"winning-IR region is paid after a seq-heavy bin residual ({why_wir1})")
    check("r30" in why_wir1, f"winning-IR region acquire names r30 ({why_wir1})")
    nxt_wir = winning_ir_region_next(mem_hr, budget_left=80)
    check(nxt_wir is not None and nxt_wir.get("kind") == "extract", f"winning-IR-region next is extract, got {nxt_wir}")
    check((nxt_wir.get("steer") or {}).get("region") == "r30", f"winning-IR-region next names r30, got {nxt_wir}")
    fake_cone_h = dict(st_wir)
    fake_cone_h["host_source"] = "f4_ir_cell_champ_cone_extract"
    pay_wir_ref, why_wir_ref = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=fake_cone_h)
    check(not pay_wir_ref, f"winning-IR region refuses leftover-cone flatten ({why_wir_ref})")
    fake_icr_h = dict(st_wir)
    fake_icr_h["host_source"] = "f4_ir_cell_region_extract"
    pay_wir_icr, why_wir_icr = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=fake_icr_h)
    check(not pay_wir_icr, f"winning-IR region refuses IR-cell-region flatten ({why_wir_icr})")
    pay_wir2, why_wir2 = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=st_wir, n_extract=1)
    check(not pay_wir2, f"winning-IR region is a single shot ({why_wir2})")
    stok_c.attr["combo_frac"] = 0.78
    mem_hr.touch(stok_c)
    check(steer_from_winning_ir_hotspot(mem_hr) is None, "combo-heavy winning-IR hotspot does not steal a region cap")
    stok_c.attr["combo_frac"] = 0.185
    stok_c.attr["region"] = "r00"
    mem_hr.touch(stok_c)
    check(steer_from_winning_ir_hotspot(mem_hr) is None, "winning-IR region skips when the bin matches IR-cell-region")
    stok_c.attr["region"] = "r30"
    mem_hr.touch(stok_c)
    mem_hr.add(
        Candidate(
            id="wirxt",
            design_id="gcd",
            parent_id="ircell",
            level="pdn",
            knobs={
                "source": "f4_winning_ir_region_extract",
                "parent_id": "ircell",
                "extract_id": "wirxt",
                "parent_extract_id": "stok",
                "region": "r30",
                "ir_join": 1,
            },
            knobs_fp="wirxt",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=11.906, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_winning_ir_region_extract",
                "residual_mv": 9.696,
                "residual_via": "winning_ir_region_vs_winning_ir_extract",
                "residual_vs": "stok",
                "region": "r30",
            },
        )
    )
    check(winning_ir_region_extract_cand(mem_hr).id == "wirxt", "region extract is the winning-IR-region cand")
    check(winning_ir_pdn(mem_hr).id == "wirl", "high winning-IR-region droop does not steal the 1× champion")
    pay_wir3, why_wir3 = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=st_wir, n_extract=0)
    check(not pay_wir3, f"winning-IR region skips once measured on that extract ({why_wir3})")
    st_wirp = steer_from_winning_ir_region_residual(mem_hr)
    check(st_wirp is not None and (st_wirp.get("spec") or {}).get("name") in ("decap_200f", "pkg_l_100p"), f"winning-IR-region residual steers the winning PDN family, got {st_wirp}")
    check(st_wirp.get("extract_id") == "wirxt", f"winning-IR-region PDN stays on the capped mesh, got {st_wirp}")
    check(st_wirp.get("host_source") == "f4_winning_ir_region_extract", "winning-IR-region PDN names the region extract")
    check(st_wirp.get("extract_id") != "stok", "winning-IR-region PDN does not restamp the unconstrained winning-IR extract")
    pay_wirp0, why_wirp0 = should_pay_winning_ir_region_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_wirp0, f"winning-IR-region PDN waits for |Δ| ≥ 1 mV ({why_wirp0})")
    pay_wirp1, why_wirp1 = should_pay_winning_ir_region_pdn(mem_hr, budget_left=80, steer=st_wirp)
    check(pay_wirp1, f"winning-IR-region PDN is paid after |Δ| ≥ 1 mV ({why_wirp1})")
    fake_stok_r = dict(st_wirp)
    fake_stok_r["host_source"] = "f4_static_strap_extract"
    pay_wirp_ref, why_wirp_ref = should_pay_winning_ir_region_pdn(mem_hr, budget_left=80, steer=fake_stok_r)
    check(not pay_wirp_ref, f"winning-IR-region PDN refuses the unconstrained strap extract ({why_wirp_ref})")
    pay_wirp2, why_wirp2 = should_pay_winning_ir_region_pdn(mem_hr, budget_left=80, steer=st_wirp, n_steer=1)
    check(not pay_wirp2, f"winning-IR-region PDN is a single shot ({why_wirp2})")
    nxt_wirp = winning_ir_region_next(mem_hr, budget_left=80)
    check(nxt_wirp is not None and nxt_wirp.get("kind") == "pdn", f"winning-IR-region next is PDN after r30 extract, got {nxt_wirp}")
    ice_wr = next(c for c in mem_hr.all() if c.id == "wirxt")
    ice_wr.attr = dict(ice_wr.attr or {})
    ice_wr.attr.update(
        {
            "join": "odb-geom",
            "combo_frac": 0.185,
            "seq_frac": 0.815,
            "region": "r13",
            "x_dbu": 25520.0,
            "y_dbu": 80993.0,
            "modules": ["dpath"],
            "cells": ["dpath/b_reg/_078_", "dpath/b_reg/_077_", "dpath/b_mux/_43_"],
        }
    )
    mem_hr.touch(ice_wr)
    st_wir13 = steer_from_winning_ir_region_hotspot(mem_hr)
    check(st_wir13 is not None and st_wir13.get("region") == "r13", f"seq-heavy winning-IR-region residual steers r13, got {st_wir13}")
    check(st_wir13.get("cap_region") == "r30", f"r13 winning-IR steer names the capped bin, got {st_wir13}")
    check(st_wir13.get("host_source") == "f4_winning_ir_region_extract", "r13 winning-IR steer names the region extract")
    check(st_wir13.get("extract_id") == "wirxt", f"r13 winning-IR steer stays on the capped mesh, got {st_wir13}")
    check(st_wir13.get("ir_cell_region") == "r00", f"r13 winning-IR steer names IR-cell-region, got {st_wir13}")
    check("combo size-up" in (st_wir13.get("reason") or ""), f"r13 winning-IR steer refuses more combo size-up ({st_wir13})")
    pay_wir13, why_wir13 = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=st_wir13)
    check(pay_wir13, f"winning-IR-region re-pays when the hotspot leaves the capped bin ({why_wir13})")
    check("r13" in why_wir13 and "r30" in why_wir13, f"r13 winning-IR acquire names both bins ({why_wir13})")
    nxt_wir13e = winning_ir_region_next(mem_hr, budget_left=80)
    check(nxt_wir13e is not None and nxt_wir13e.get("kind") == "extract", f"winning-IR-region next is r13 extract, got {nxt_wir13e}")
    check((nxt_wir13e.get("steer") or {}).get("region") == "r13", f"winning-IR-region next names r13, got {nxt_wir13e}")
    pay_wir30_again, why_wir30_again = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=st_wir)
    check(not pay_wir30_again, f"winning-IR-region does not re-cap r30 ({why_wir30_again})")
    ice_wr.attr["combo_frac"] = 0.78
    mem_hr.touch(ice_wr)
    check(steer_from_winning_ir_region_hotspot(mem_hr) is None, "combo-heavy winning-IR-region hotspot does not steal another density cap")
    ice_wr.attr["combo_frac"] = 0.185
    ice_wr.attr["region"] = "r30"
    mem_hr.touch(ice_wr)
    check(steer_from_winning_ir_region_hotspot(mem_hr) is None, "winning-IR-region skips when the hotspot matches the capped bin")
    ice_wr.attr["region"] = "r00"
    mem_hr.touch(ice_wr)
    check(steer_from_winning_ir_region_hotspot(mem_hr) is None, "winning-IR-region skips when the hotspot matches IR-cell-region")
    fake_r00 = dict(st_wir13)
    fake_r00["region"] = "r00"
    pay_wir_r00, why_wir_r00 = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=fake_r00)
    check(not pay_wir_r00, f"winning-IR-region pay refuses the IR-cell-region bin ({why_wir_r00})")
    ice_wr.attr["region"] = "r13"
    mem_hr.touch(ice_wr)
    mem_hr.add(
        Candidate(
            id="wirxt2",
            design_id="gcd",
            parent_id="ircell",
            level="pdn",
            knobs={
                "source": "f4_winning_ir_region_extract",
                "parent_id": "ircell",
                "extract_id": "wirxt2",
                "parent_extract_id": "wirxt",
                "region": "r13",
                "ir_join": 1,
            },
            knobs_fp="wirxt2",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=8.100, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_winning_ir_region_extract",
                "residual_mv": -3.806,
                "residual_via": "winning_ir_region_vs_prior_region",
                "residual_vs": "wirxt",
                "region": "r13",
            },
        )
    )
    check(winning_ir_region_extract_cand(mem_hr).id == "wirxt2", "newest winning-IR-region extract is the r13 cap")
    check(winning_ir_pdn(mem_hr).id == "wirl", "high winning-IR-region r13 droop does not steal the 1× champion")
    pay_wir13b, why_wir13b = should_pay_winning_ir_region(mem_hr, budget_left=80, steer=st_wir13, n_extract=0)
    check(not pay_wir13b, f"winning-IR-region skips once r13 is measured ({why_wir13b})")
    st_wirp13 = steer_from_winning_ir_region_residual(mem_hr)
    check(st_wirp13 is not None and st_wirp13.get("extract_id") == "wirxt2", f"r13 winning-IR residual steers PDN on the r13 mesh, got {st_wirp13}")
    check(st_wirp13.get("extract_id") != "wirxt", "r13 winning-IR PDN does not restamp the r30 mesh")
    pay_wir13p, why_wir13p = should_pay_winning_ir_region_pdn(mem_hr, budget_left=80, steer=st_wirp13)
    check(pay_wir13p, f"winning-IR-region PDN re-pays on the r13 mesh ({why_wir13p})")
    nxt_wir13 = winning_ir_region_next(mem_hr, budget_left=80)
    check(nxt_wir13 is not None and nxt_wir13.get("kind") == "pdn", f"winning-IR-region next is r13 PDN, got {nxt_wir13}")
    check((nxt_wir13.get("steer") or {}).get("extract_id") == "wirxt2", f"winning-IR-region next PDN stays on r13, got {nxt_wir13}")
    from dse.active import (
        steer_from_winning_ir_region_cell_residual,
        steer_from_winning_ir_region_pdn_hotspot,
        winning_ir_region_cell_extract_cand,
        winning_ir_region_cell_host,
    )

    pay_wirc0, why_wirc0 = should_pay_winning_ir_region_cell(mem_hr, budget_left=80, steer=None)
    check(not pay_wirc0, f"winning-IR-region-cell waits for leftover combo cells ({why_wirc0})")
    check(steer_from_winning_ir_region_pdn_hotspot(mem_hr) is None, "winning-IR-region-cell waits for a region PDN join")
    mem_hr.add(
        Candidate(
            id="wirp",
            design_id="gcd",
            parent_id="wirxt",
            level="pdn",
            knobs={
                "name": "decap_200f",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 2e-13,
                "i_scale": 1.0,
                "source": "f4_solver_a",
                "extract_id": "wirxt",
            },
            knobs_fp="wirp",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=5.570, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "active_f4_winning_ir_region_pdn",
                "region": "r00",
                "combo_frac": 0.85,
                "seq_frac": 0.15,
                "cells": [
                    "ctrl/_11_",
                    "dpath/b_mux/_46_",
                    "dpath/b_mux/_44_",
                    "dpath/b_reg/_077_",
                    "dpath/b_mux/_51_",
                ],
                "modules": ["ctrl", "dpath"],
            },
        )
    )
    st_wirc = steer_from_winning_ir_region_pdn_hotspot(mem_hr)
    check(st_wirc is not None and st_wirc.get("level") == "winning_ir_region_cell", f"combo-heavy region PDN steers leftover cells, got {st_wirc}")
    check(st_wirc.get("extract_id") == "wirxt", f"winning-IR-region-cell stays on the region extract, got {st_wirc}")
    check("dpath/b_mux/_44_" in (st_wirc.get("cells") or []) and "dpath/b_mux/_51_" in (st_wirc.get("cells") or []), f"winning-IR-region-cell names leftover mux, got {st_wirc}")
    check("dpath/b_mux/_46_" not in (st_wirc.get("cells") or []), f"winning-IR-region-cell drops leftover-cone cells, got {st_wirc}")
    check("ctrl/_11_" not in (st_wirc.get("cells") or []), f"winning-IR-region-cell drops first IR-cell ctrl, got {st_wirc}")
    check("dpath" in (st_wirc.get("modules") or []), f"winning-IR-region-cell names dpath, got {st_wirc}")
    check("leftover-cone" in (st_wirc.get("reason") or ""), f"winning-IR-region-cell refuses leftover-cone flatten ({st_wirc})")
    pay_wirc1, why_wirc1 = should_pay_winning_ir_region_cell(mem_hr, budget_left=80, steer=st_wirc)
    check(pay_wirc1, f"winning-IR-region-cell is paid after leftover combo cells ({why_wirc1})")
    fake_cone_c = dict(st_wirc)
    fake_cone_c["host_source"] = "f4_ir_cell_champ_cone_extract"
    pay_wirc_ref, why_wirc_ref = should_pay_winning_ir_region_cell(mem_hr, budget_left=80, steer=fake_cone_c)
    check(not pay_wirc_ref, f"winning-IR-region-cell refuses leftover-cone flatten ({why_wirc_ref})")
    pay_wirc2, why_wirc2 = should_pay_winning_ir_region_cell(mem_hr, budget_left=80, steer=st_wirc, n_cell=1)
    check(not pay_wirc2, f"winning-IR-region-cell is a single shot ({why_wirc2})")
    wirp_c = next(c for c in mem_hr.all() if c.id == "wirp")
    wirp_c.attr["combo_frac"] = 0.16
    mem_hr.touch(wirp_c)
    check(steer_from_winning_ir_region_pdn_hotspot(mem_hr) is None, "seq-heavy winning-IR-region PDN does not steal combo size-up")
    wirp_c.attr["combo_frac"] = 0.85
    mem_hr.touch(wirp_c)
    mem_hr.add(
        Candidate(
            id="wircell",
            design_id="gcd",
            parent_id="ircell",
            level="cell",
            knobs={
                "source": "cell_size_ir_winning_region",
                "cells": ["dpath/b_mux/_44_", "dpath/b_mux/_51_"],
                "ir_join": 1,
                "winning_ir_region": 1,
                "parent_id": "ircell",
                "extract_id": "wirxt",
            },
            knobs_fp="wircell",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=566.0, wns_cost=0.30, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(dummy_host), "n_changed": 2, "wns_ns": -0.301},
            attr={"via": "active_f4_winning_ir_region_cell"},
        )
    )
    check(winning_ir_region_cell_host(mem_hr).id == "wircell", "winning-IR-region-cell host is the leftover-combo size-up")
    pay_wirc3, why_wirc3 = should_pay_winning_ir_region_cell(mem_hr, budget_left=80, steer=st_wirc)
    check(not pay_wirc3, f"winning-IR-region-cell skips once sized on that extract ({why_wirc3})")
    pay_wirce0, why_wirce0 = should_pay_winning_ir_region_cell_extract(mem_hr, budget_left=80, n_extract=0)
    check(pay_wirce0, f"winning-IR-region-cell extract is paid after leftover-combo size-up ({why_wirce0})")
    check("leftover-cone" in why_wirce0 and "winning-IR-region" in why_wirce0, f"winning-IR-region-cell extract names both meshes ({why_wirce0})")
    pay_wirce1, why_wirce1 = should_pay_winning_ir_region_cell_extract(mem_hr, budget_left=80, n_extract=1)
    check(not pay_wirce1, f"winning-IR-region-cell extract is a single shot ({why_wirce1})")
    mem_hr.add(
        Candidate(
            id="wircxt",
            design_id="gcd",
            parent_id="wircell",
            level="pdn",
            knobs={
                "source": "f4_winning_ir_region_cell_extract",
                "parent_id": "wircell",
                "extract_id": "wircxt",
                "parent_extract_id": "wirxt",
                "ir_join": 1,
                "winning_ir_region": 1,
            },
            knobs_fp="wircxt",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=9.200, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_winning_ir_region_cell_extract",
                "residual_mv": -1.513,
                "residual_via": "winning_ir_region_cell_vs_winning_ir_region_extract",
                "residual_vs": "wirxt",
            },
        )
    )
    check(winning_ir_region_cell_extract_cand(mem_hr).id == "wircxt", "cell extract is the winning-IR-region-cell cand")
    check(winning_ir_pdn(mem_hr).id == "wirl", "high winning-IR-region-cell droop does not steal the 1× champion")
    pay_wirce2, why_wirce2 = should_pay_winning_ir_region_cell_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_wirce2, f"winning-IR-region-cell extract skips once measured ({why_wirce2})")
    st_wircp = steer_from_winning_ir_region_cell_residual(mem_hr)
    check(st_wircp is not None and (st_wircp.get("spec") or {}).get("name") in ("decap_200f", "pkg_l_100p"), f"winning-IR-region-cell residual steers the winning PDN family, got {st_wircp}")
    check(st_wircp.get("extract_id") == "wircxt", f"winning-IR-region-cell PDN stays on the leftover-combo mesh, got {st_wircp}")
    check(st_wircp.get("host_source") == "f4_winning_ir_region_cell_extract", "winning-IR-region-cell PDN names the cell extract")
    check(st_wircp.get("extract_id") != "wirxt", "winning-IR-region-cell PDN does not restamp the region extract")
    pay_wircp0, why_wircp0 = should_pay_winning_ir_region_cell_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_wircp0, f"winning-IR-region-cell PDN waits for a 1× residual ({why_wircp0})")
    pay_wircp1, why_wircp1 = should_pay_winning_ir_region_cell_pdn(mem_hr, budget_left=80, steer=st_wircp)
    check(pay_wircp1, f"winning-IR-region-cell PDN is paid after the 1× residual ({why_wircp1})")
    fake_reg_p = dict(st_wircp)
    fake_reg_p["host_source"] = "f4_winning_ir_region_extract"
    pay_wircp_ref, why_wircp_ref = should_pay_winning_ir_region_cell_pdn(mem_hr, budget_left=80, steer=fake_reg_p)
    check(not pay_wircp_ref, f"winning-IR-region-cell PDN refuses the region extract ({why_wircp_ref})")
    pay_wircp2, why_wircp2 = should_pay_winning_ir_region_cell_pdn(mem_hr, budget_left=80, steer=st_wircp, n_steer=1)
    check(not pay_wircp2, f"winning-IR-region-cell PDN is a single shot ({why_wircp2})")
    from dse.active import (
        steer_from_winning_ir_region_cell_leftover_residual,
        steer_from_winning_ir_region_cell_pdn_hotspot,
        winning_ir_region_cell_leftover_extract_cand,
        winning_ir_region_cell_leftover_host,
    )

    pay_wircl0, why_wircl0 = should_pay_winning_ir_region_cell_leftover(mem_hr, budget_left=80, steer=None)
    check(not pay_wircl0, f"leftover leftover waits for leftover combo cells ({why_wircl0})")
    check(steer_from_winning_ir_region_cell_pdn_hotspot(mem_hr) is None, "leftover leftover waits for a leftover-combo PDN join")
    mem_hr.add(
        Candidate(
            id="wircp",
            design_id="gcd",
            parent_id="wircxt",
            level="pdn",
            knobs={
                "name": "decap_200f",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 2e-13,
                "i_scale": 1.0,
                "source": "f4_solver_a",
                "extract_id": "wircxt",
            },
            knobs_fp="wircp",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=4.702, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "active_f4_winning_ir_region_cell_pdn",
                "region": "r10",
                "combo_frac": 0.86,
                "seq_frac": 0.14,
                "cells": [
                    "ctrl/_04_",
                    "ctrl/_14_",
                    "dpath/sub/_192_",
                    "ctrl/_07_",
                    "dpath/sub/_196_",
                ],
                "modules": ["ctrl", "dpath"],
            },
        )
    )
    st_wircl = steer_from_winning_ir_region_cell_pdn_hotspot(mem_hr)
    check(st_wircl is not None and st_wircl.get("level") == "winning_ir_region_cell_leftover", f"combo-heavy leftover-combo PDN steers leftover leftover cells, got {st_wircl}")
    check(st_wircl.get("extract_id") == "wircxt", f"leftover leftover stays on the leftover-combo extract, got {st_wircl}")
    check("dpath/sub/_192_" in (st_wircl.get("cells") or []) and "dpath/sub/_196_" in (st_wircl.get("cells") or []), f"leftover leftover names leftover sub, got {st_wircl}")
    check("dpath/b_mux/_44_" not in (st_wircl.get("cells") or []), f"leftover leftover drops leftover-combo mux, got {st_wircl}")
    check("ctrl/_14_" not in (st_wircl.get("cells") or []), f"leftover leftover drops first IR-cell ctrl, got {st_wircl}")
    check("dpath" in (st_wircl.get("modules") or []), f"leftover leftover names dpath, got {st_wircl}")
    check("leftover-combo" in (st_wircl.get("reason") or ""), f"leftover leftover refuses leftover-combo flatten ({st_wircl})")
    pay_wircl1, why_wircl1 = should_pay_winning_ir_region_cell_leftover(mem_hr, budget_left=80, steer=st_wircl)
    check(pay_wircl1, f"leftover leftover is paid after leftover leftover cells ({why_wircl1})")
    fake_combo_c = dict(st_wircl)
    fake_combo_c["host_source"] = "f4_winning_ir_region_extract"
    pay_wircl_ref, why_wircl_ref = should_pay_winning_ir_region_cell_leftover(mem_hr, budget_left=80, steer=fake_combo_c)
    check(not pay_wircl_ref, f"leftover leftover refuses region flatten ({why_wircl_ref})")
    pay_wircl2, why_wircl2 = should_pay_winning_ir_region_cell_leftover(mem_hr, budget_left=80, steer=st_wircl, n_cell=1)
    check(not pay_wircl2, f"leftover leftover is a single shot ({why_wircl2})")
    wircp_c = next(c for c in mem_hr.all() if c.id == "wircp")
    wircp_c.attr["combo_frac"] = 0.16
    mem_hr.touch(wircp_c)
    check(steer_from_winning_ir_region_cell_pdn_hotspot(mem_hr) is None, "seq-heavy leftover-combo PDN does not steal leftover leftover size-up")
    wircp_c.attr["combo_frac"] = 0.86
    mem_hr.touch(wircp_c)
    mem_hr.add(
        Candidate(
            id="wirclcell",
            design_id="gcd",
            parent_id="wircell",
            level="cell",
            knobs={
                "source": "cell_size_ir_winning_region_leftover",
                "cells": ["dpath/sub/_192_", "dpath/sub/_196_"],
                "ir_join": 1,
                "winning_ir_region_leftover": 1,
                "parent_id": "wircell",
                "extract_id": "wircxt",
            },
            knobs_fp="wirclcell",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=567.0, wns_cost=0.31, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(dummy_host), "n_changed": 2, "wns_ns": -0.305},
            attr={"via": "active_f4_winning_ir_region_cell_leftover"},
        )
    )
    check(winning_ir_region_cell_leftover_host(mem_hr).id == "wirclcell", "leftover leftover host is the leftover leftover size-up")
    pay_wircl3, why_wircl3 = should_pay_winning_ir_region_cell_leftover(mem_hr, budget_left=80, steer=st_wircl)
    check(not pay_wircl3, f"leftover leftover skips once sized on that extract ({why_wircl3})")
    pay_wircle0, why_wircle0 = should_pay_winning_ir_region_cell_leftover_extract(mem_hr, budget_left=80, n_extract=0)
    check(pay_wircle0, f"leftover leftover extract is paid after leftover leftover size-up ({why_wircle0})")
    check("leftover-combo" in why_wircle0 and "leftover" in why_wircle0, f"leftover leftover extract names both meshes ({why_wircle0})")
    pay_wircle1, why_wircle1 = should_pay_winning_ir_region_cell_leftover_extract(mem_hr, budget_left=80, n_extract=1)
    check(not pay_wircle1, f"leftover leftover extract is a single shot ({why_wircle1})")
    mem_hr.add(
        Candidate(
            id="wirclxt",
            design_id="gcd",
            parent_id="wirclcell",
            level="pdn",
            knobs={
                "source": "f4_winning_ir_region_cell_leftover_extract",
                "parent_id": "wirclcell",
                "extract_id": "wirclxt",
                "parent_extract_id": "wircxt",
                "ir_join": 1,
                "winning_ir_region_leftover": 1,
            },
            knobs_fp="wirclxt",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=11.200, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_winning_ir_region_cell_leftover_extract",
                "residual_mv": 2.000,
                "residual_via": "winning_ir_region_cell_leftover_vs_winning_ir_region_cell_extract",
                "residual_vs": "wircxt",
            },
        )
    )
    check(winning_ir_region_cell_leftover_extract_cand(mem_hr).id == "wirclxt", "leftover leftover extract is the leftover leftover cand")
    check(winning_ir_pdn(mem_hr).id == "wirl", "high leftover leftover droop does not steal the 1× champion")
    pay_wircle2, why_wircle2 = should_pay_winning_ir_region_cell_leftover_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_wircle2, f"leftover leftover extract skips once measured ({why_wircle2})")
    st_wirclp = steer_from_winning_ir_region_cell_leftover_residual(mem_hr)
    check(st_wirclp is not None and (st_wirclp.get("spec") or {}).get("name") in ("decap_200f", "pkg_l_100p"), f"leftover leftover residual steers the winning PDN family, got {st_wirclp}")
    check(st_wirclp.get("extract_id") == "wirclxt", f"leftover leftover PDN stays on the leftover leftover mesh, got {st_wirclp}")
    check(st_wirclp.get("host_source") == "f4_winning_ir_region_cell_leftover_extract", "leftover leftover PDN names the leftover leftover extract")
    check(st_wirclp.get("extract_id") != "wircxt", "leftover leftover PDN does not restamp the leftover-combo extract")
    pay_wirclp0, why_wirclp0 = should_pay_winning_ir_region_cell_leftover_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_wirclp0, f"leftover leftover PDN waits for a 1× residual ({why_wirclp0})")
    pay_wirclp1, why_wirclp1 = should_pay_winning_ir_region_cell_leftover_pdn(mem_hr, budget_left=80, steer=st_wirclp)
    check(pay_wirclp1, f"leftover leftover PDN is paid after the 1× residual ({why_wirclp1})")
    fake_combo_p = dict(st_wirclp)
    fake_combo_p["host_source"] = "f4_winning_ir_region_cell_extract"
    pay_wirclp_ref, why_wirclp_ref = should_pay_winning_ir_region_cell_leftover_pdn(mem_hr, budget_left=80, steer=fake_combo_p)
    check(not pay_wirclp_ref, f"leftover leftover PDN refuses the leftover-combo extract ({why_wirclp_ref})")
    pay_wirclp2, why_wirclp2 = should_pay_winning_ir_region_cell_leftover_pdn(mem_hr, budget_left=80, steer=st_wirclp, n_steer=1)
    check(not pay_wirclp2, f"leftover leftover PDN is a single shot ({why_wirclp2})")
    from dse.active import (
        steer_from_winning_ir_region_cell_leftover2_catalog,
        steer_from_winning_ir_region_cell_leftover2_residual,
        steer_from_winning_ir_region_cell_leftover_pdn_hotspot,
        winning_ir_region_cell_leftover2_extract_cand,
        winning_ir_region_cell_leftover2_host,
    )

    pay_wircl20, why_wircl20 = should_pay_winning_ir_region_cell_leftover2(mem_hr, budget_left=80, steer=None)
    check(not pay_wircl20, f"leftover leftover leftover waits for leftover leftover leftover cells ({why_wircl20})")
    check(steer_from_winning_ir_region_cell_leftover_pdn_hotspot(mem_hr) is None, "leftover leftover leftover waits for a leftover leftover PDN join")
    mem_hr.add(
        Candidate(
            id="wirclp",
            design_id="gcd",
            parent_id="wirclxt",
            level="pdn",
            knobs={
                "name": "decap_200f",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 2e-13,
                "i_scale": 1.0,
                "source": "f4_solver_a",
                "extract_id": "wirclxt",
            },
            knobs_fp="wirclp",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=4.684, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "active_f4_winning_ir_region_cell_leftover_pdn",
                "region": "r00",
                "combo_frac": 0.82,
                "seq_frac": 0.18,
                "cells": [
                    "dpath/b_reg/_075_",
                    "dpath/b_reg/_074_",
                    "dpath/b_mux/_41_",
                    "dpath/b_reg/_073_",
                    "dpath/b_mux/_43_",
                ],
                "modules": ["dpath"],
            },
        )
    )
    st_wircl2 = steer_from_winning_ir_region_cell_leftover_pdn_hotspot(mem_hr)
    check(st_wircl2 is not None and st_wircl2.get("level") == "winning_ir_region_cell_leftover2", f"combo-heavy leftover leftover PDN steers leftover leftover leftover cells, got {st_wircl2}")
    check(st_wircl2.get("extract_id") == "wirclxt", f"leftover leftover leftover stays on the leftover leftover extract, got {st_wircl2}")
    check("dpath/b_reg/_075_" in (st_wircl2.get("cells") or []) and "dpath/b_mux/_41_" in (st_wircl2.get("cells") or []), f"leftover leftover leftover names leftover leftover leftover mux/reg, got {st_wircl2}")
    check("dpath/sub/_192_" not in (st_wircl2.get("cells") or []), f"leftover leftover leftover drops leftover leftover sub, got {st_wircl2}")
    check("dpath" in (st_wircl2.get("modules") or []), f"leftover leftover leftover names dpath, got {st_wircl2}")
    pay_wircl21, why_wircl21 = should_pay_winning_ir_region_cell_leftover2(mem_hr, budget_left=80, steer=st_wircl2)
    check(pay_wircl21, f"leftover leftover leftover is paid after leftover leftover leftover cells ({why_wircl21})")
    fake_ll_c = dict(st_wircl2)
    fake_ll_c["host_source"] = "f4_winning_ir_region_cell_extract"
    pay_wircl2_ref, why_wircl2_ref = should_pay_winning_ir_region_cell_leftover2(mem_hr, budget_left=80, steer=fake_ll_c)
    check(not pay_wircl2_ref, f"leftover leftover leftover refuses leftover-combo flatten ({why_wircl2_ref})")
    pay_wircl22, why_wircl22 = should_pay_winning_ir_region_cell_leftover2(mem_hr, budget_left=80, steer=st_wircl2, n_cell=1)
    check(not pay_wircl22, f"leftover leftover leftover is a single shot ({why_wircl22})")
    wirclp_c = next(c for c in mem_hr.all() if c.id == "wirclp")
    wirclp_c.attr["combo_frac"] = 0.16
    mem_hr.touch(wirclp_c)
    check(steer_from_winning_ir_region_cell_leftover_pdn_hotspot(mem_hr) is None, "seq-heavy leftover leftover PDN does not steal leftover leftover leftover size-up")
    wirclp_c.attr["combo_frac"] = 0.82
    mem_hr.touch(wirclp_c)
    mem_hr.add(
        Candidate(
            id="wircl2cell",
            design_id="gcd",
            parent_id="wirclcell",
            level="cell",
            knobs={
                "source": "cell_size_ir_winning_region_leftover2",
                "cells": ["dpath/b_reg/_075_", "dpath/b_reg/_074_", "dpath/b_mux/_41_", "dpath/b_reg/_073_", "dpath/b_mux/_43_"],
                "ir_join": 1,
                "winning_ir_region_leftover2": 1,
                "parent_id": "wirclcell",
                "extract_id": "wirclxt",
            },
            knobs_fp="wircl2cell",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F3",
            qor=QoR(area_um2=568.0, wns_cost=0.31, fidelity="F3"),
            cost_s=0.2,
            status="ok",
            artifacts={"mapped_v": str(dummy_host), "n_changed": 5, "wns_ns": -0.307},
            attr={"via": "active_f4_winning_ir_region_cell_leftover2"},
        )
    )
    check(winning_ir_region_cell_leftover2_host(mem_hr).id == "wircl2cell", "leftover leftover leftover host is the leftover leftover leftover size-up")
    pay_wircl23, why_wircl23 = should_pay_winning_ir_region_cell_leftover2(mem_hr, budget_left=80, steer=st_wircl2)
    check(not pay_wircl23, f"leftover leftover leftover skips once sized on that extract ({why_wircl23})")
    pay_wircl2e0, why_wircl2e0 = should_pay_winning_ir_region_cell_leftover2_extract(mem_hr, budget_left=80, n_extract=0)
    check(pay_wircl2e0, f"leftover leftover leftover extract is paid after leftover leftover leftover size-up ({why_wircl2e0})")
    pay_wircl2e1, why_wircl2e1 = should_pay_winning_ir_region_cell_leftover2_extract(mem_hr, budget_left=80, n_extract=1)
    check(not pay_wircl2e1, f"leftover leftover leftover extract is a single shot ({why_wircl2e1})")
    mem_hr.add(
        Candidate(
            id="wircl2xt",
            design_id="gcd",
            parent_id="wircl2cell",
            level="pdn",
            knobs={
                "source": "f4_winning_ir_region_cell_leftover2_extract",
                "parent_id": "wircl2cell",
                "extract_id": "wircl2xt",
                "parent_extract_id": "wirclxt",
                "ir_join": 1,
                "winning_ir_region_leftover2": 1,
            },
            knobs_fp="wircl2xt",
            rtl_fp="x",
            netlist_fp="y",
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=13.100, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "f4_winning_ir_region_cell_leftover2_extract",
                "residual_mv": 0.629,
                "residual_via": "winning_ir_region_cell_leftover2_vs_winning_ir_region_cell_leftover_extract",
                "residual_vs": "wirclxt",
            },
        )
    )
    check(winning_ir_region_cell_leftover2_extract_cand(mem_hr).id == "wircl2xt", "leftover leftover leftover extract is the leftover leftover leftover cand")
    check(winning_ir_pdn(mem_hr).id == "wirl", "high leftover leftover leftover droop does not steal the 1× champion")
    pay_wircl2e2, why_wircl2e2 = should_pay_winning_ir_region_cell_leftover2_extract(mem_hr, budget_left=80, n_extract=0)
    check(not pay_wircl2e2, f"leftover leftover leftover extract skips once measured ({why_wircl2e2})")
    st_wircl2p = steer_from_winning_ir_region_cell_leftover2_residual(mem_hr)
    check(st_wircl2p is not None and (st_wircl2p.get("spec") or {}).get("name") in ("decap_200f", "pkg_l_100p"), f"leftover leftover leftover residual steers the winning PDN family, got {st_wircl2p}")
    check(st_wircl2p.get("extract_id") == "wircl2xt", f"leftover leftover leftover PDN stays on the leftover leftover leftover mesh, got {st_wircl2p}")
    check(st_wircl2p.get("host_source") == "f4_winning_ir_region_cell_leftover2_extract", "leftover leftover leftover PDN names the leftover leftover leftover extract")
    check(st_wircl2p.get("extract_id") != "wirclxt", "leftover leftover leftover PDN does not restamp the leftover leftover extract")
    pay_wircl2p0, why_wircl2p0 = should_pay_winning_ir_region_cell_leftover2_pdn(mem_hr, budget_left=80, steer=None)
    check(not pay_wircl2p0, f"leftover leftover leftover PDN waits for a 1× residual ({why_wircl2p0})")
    pay_wircl2p1, why_wircl2p1 = should_pay_winning_ir_region_cell_leftover2_pdn(mem_hr, budget_left=80, steer=st_wircl2p)
    check(pay_wircl2p1, f"leftover leftover leftover PDN is paid after the 1× residual ({why_wircl2p1})")
    fake_ll_p = dict(st_wircl2p)
    fake_ll_p["host_source"] = "f4_winning_ir_region_cell_leftover_extract"
    pay_wircl2p_ref, why_wircl2p_ref = should_pay_winning_ir_region_cell_leftover2_pdn(mem_hr, budget_left=80, steer=fake_ll_p)
    check(not pay_wircl2p_ref, f"leftover leftover leftover PDN refuses the leftover leftover extract ({why_wircl2p_ref})")
    pay_wircl2p2, why_wircl2p2 = should_pay_winning_ir_region_cell_leftover2_pdn(mem_hr, budget_left=80, steer=st_wircl2p, n_steer=1)
    check(not pay_wircl2p2, f"leftover leftover leftover PDN is a single shot ({why_wircl2p2})")
    check(
        steer_from_winning_ir_region_cell_leftover2_catalog(mem_hr) is None,
        "leftover leftover leftover catalog waits for leftover leftover leftover PDN",
    )
    mem_hr.add(
        Candidate(
            id="wircl2p",
            design_id="gcd",
            parent_id="wircl2xt",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "decap_200f",
                "extract_id": "wircl2xt",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 2e-13,
                "i_scale": 1.0,
            },
            knobs_fp="wircl2p",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.942, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_winning_ir_region_cell_leftover2_pdn"},
        )
    )
    check(winning_ir_pdn(mem_hr).id == "wirl", "leftover leftover leftover PDN does not steal the 1× champion")
    st_wircl2c = steer_from_winning_ir_region_cell_leftover2_catalog(mem_hr)
    check(
        st_wircl2c is not None and (st_wircl2c.get("spec") or {}).get("name") == "pkg_l_100p",
        f"leftover leftover leftover catalog unused L after winning family, got {st_wircl2c}",
    )
    check(st_wircl2c.get("extract_id") == "wircl2xt", f"leftover leftover leftover catalog stays on leftover leftover leftover extract, got {st_wircl2c}")
    check(abs(float((st_wircl2c.get("spec") or {}).get("pkg_r") or 0) - 0.05) < 1e-12, "leftover leftover leftover catalog inherits leftover leftover leftover PDN pkg_r")
    check(abs(float((st_wircl2c.get("spec") or {}).get("c_decap") or 0) - 2e-13) < 1e-18, "leftover leftover leftover catalog inherits leftover leftover leftover PDN 200 fF")
    check(
        (st_wircl2c.get("spec") or {}).get("name") not in ("m4_pitch_8", "m4_width_96", "bumps_80", "pkg_r_25m"),
        "leftover leftover leftover catalog does not consume pitch / width / bump / pkg_r catalogs",
    )
    pay_wircl2c0, why_wircl2c0 = should_pay_winning_ir_region_cell_leftover2_catalog(mem_hr, budget_left=80, steer=None)
    check(not pay_wircl2c0, f"leftover leftover leftover catalog waits for a steer ({why_wircl2c0})")
    pay_wircl2c1, why_wircl2c1 = should_pay_winning_ir_region_cell_leftover2_catalog(mem_hr, budget_left=80, steer=st_wircl2c)
    check(pay_wircl2c1, f"leftover leftover leftover catalog is paid after leftover leftover leftover PDN ({why_wircl2c1})")
    check("not winning_ir" in why_wircl2c1 and "not gold" in why_wircl2c1, f"leftover leftover leftover catalog refuses flatten ({why_wircl2c1})")
    fake_wircl2c = dict(st_wircl2c)
    fake_wircl2c["spec"] = {"name": "m4_width_96", "m4_width": 0.96, "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 2e-13}
    pay_wircl2c_ref, why_wircl2c_ref = should_pay_winning_ir_region_cell_leftover2_catalog(mem_hr, budget_left=80, steer=fake_wircl2c)
    check(not pay_wircl2c_ref, f"leftover leftover leftover catalog refuses a width catalog point ({why_wircl2c_ref})")
    fake_wir_c = dict(st_wircl2c)
    fake_wir_c["host_source"] = "f4_em_strap_extract"
    pay_wircl2c_wir, why_wircl2c_wir = should_pay_winning_ir_region_cell_leftover2_catalog(mem_hr, budget_left=80, steer=fake_wir_c)
    check(not pay_wircl2c_wir, f"leftover leftover leftover catalog refuses winning_ir catalog flatten ({why_wircl2c_wir})")
    pay_wircl2c2, why_wircl2c2 = should_pay_winning_ir_region_cell_leftover2_catalog(mem_hr, budget_left=80, steer=st_wircl2c, n_steer=2)
    check(not pay_wircl2c2, f"leftover leftover leftover catalog caps at decap + pkg L ({why_wircl2c2})")
    mem_hr.add(
        Candidate(
            id="wircl2l",
            design_id="gcd",
            parent_id="wircl2xt",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "pkg_l_100p",
                "extract_id": "wircl2xt",
                "pkg_r": 0.05,
                "pkg_l": 1e-10,
                "c_decap": 2e-13,
                "i_scale": 1.0,
            },
            knobs_fp="wircl2l",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.880, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "active_f4_winning_ir_region_cell_leftover2_catalog",
                "residual_vs_leftover2_pdn_mv": -0.062,
                "residual_via": "leftover2_catalog_vs_leftover2_pdn",
            },
        )
    )
    check(winning_ir_pdn(mem_hr).id == "wirl", "leftover leftover leftover unused L does not steal winning_ir_pdn")
    check(steer_from_winning_ir_region_cell_leftover2_catalog(mem_hr) is None, "leftover leftover leftover catalog is exhausted after unused L")
    st_ir = steer_from_ir_residual(mem_ir)
    check(st_ir is not None and (st_ir.get("spec") or {}).get("name") == "decap_200f", f"large knob residual steers decap, got {st_ir}")
    check(st_ir.get("extract_id") == "regext", f"large knob residual restamps the region mesh, got {st_ir}")
    check(st_ir.get("host_source") == "f4_region_extract", "IR steer names the region extract host")
    pay_ir0, why_ir0 = should_pay_ir_steer(mem_ir, budget_left=80, steer=None)
    check(not pay_ir0, f"IR steer waits for a steer dict ({why_ir0})")
    pay_ir1, why_ir1 = should_pay_ir_steer(mem_ir, budget_left=80, steer=st_ir)
    check(pay_ir1, f"IR steer is paid after F4 residuals ({why_ir1})")
    pay_dup, why_dup = should_pay_ir_steer(mem_ir, budget_left=80, steer=st_ir)
    check(pay_dup, f"first IR-steer is still paid ({why_dup})")
    mem_ir.add(
        Candidate(
            id="decapr",
            design_id="gcd",
            parent_id="regext",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "decap_200f",
                "extract_id": "regext",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 200e-15,
            },
            knobs_fp="decapr",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=7.507, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={"via": "active_f4_ir"},
        )
    )
    pay_same, why_same = should_pay_ir_steer(mem_ir, budget_left=80, steer=st_ir, n_steer=1)
    check(not pay_same, f"same region-decap point is not restamped ({why_same})")
    st_ir2 = steer_from_ir_residual(mem_ir)
    check(st_ir2 is not None and (st_ir2.get("spec") or {}).get("name") == "pkg_l_100p", f"after region decap, unused pkg L is next, got {st_ir2}")
    check(st_ir2.get("extract_id") == "candext", f"second IR-steer stays on the candidate extract, got {st_ir2}")
    check(st_ir2.get("host_source") == "f4_candidate_extract", "second IR-steer names the candidate extract host")
    pay_ir2, why_ir2 = should_pay_ir_steer(mem_ir, budget_left=80, steer=st_ir2, n_steer=1)
    check(pay_ir2, f"second IR-steer is paid after inspect ({why_ir2})")
    pay_ir3, why_ir3 = should_pay_ir_steer(mem_ir, budget_left=80, steer=st_ir2, n_steer=2)
    check(not pay_ir3, f"IR-steer loop caps at region family + unused catalog ({why_ir3})")
    # Small decap residual → unused pkg L on the candidate, not the region.
    mem_small = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-irs-")) / "s.jsonl")
    for cid, src, eid, mv, extra in (
        ("g", "ingest_pdn", "finish", 45.298, {}),
        ("c", "f4_candidate_extract", "c", 16.616, {}),
        (
            "d",
            "f4_solver_a",
            "c",
            16.500,
            {"name": "decap_200f", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15},
        ),
    ):
        kn = {"source": src, "extract_id": eid, **extra}
        mem_small.add(
            Candidate(
                id=cid,
                design_id="gcd",
                parent_id=None,
                level="pdn",
                knobs=kn,
                knobs_fp=cid,
                rtl_fp="x",
                netlist_fp=None,
                fidelity="F4",
                qor=QoR(dynamic_ir_mv=mv, fidelity="F4"),
                cost_s=0.1,
                status="ok",
            )
        )
    st_small = steer_from_ir_residual(mem_small)
    check(st_small is not None and (st_small.get("spec") or {}).get("name") == "pkg_l_100p", f"small knob residual steers pkg L, got {st_small}")
    check(st_small.get("extract_id") == "c", f"small knob residual stays on the candidate extract, got {st_small}")

    gold_json = _ROOT / "learn/sim/reports/dynamic_ir_flowlab.json"
    gold_before = gold_json.read_text() if gold_json.is_file() else None
    if f4_ok("flowlab"):
        base = solve_f4(variant="flowlab")
        check(base.get("status") == "ok", f"F4 oracle Solver A ({base.get('reason')})")
        check(base.get("gold") is False, "candidate F4 is not marked gold")
        check(base.get("extract") == "finish", "default F4 uses the finish extract")
        check(base.get("solver_kind") == "direct", f"default F4 solver is DirectLU, got {base.get('solver_kind')}")
        check(
            abs(float(base["worst_droop_mv"]) - GOLD_MV) > 1.0,
            f"current finish mesh is not the 45.298 reference_run, got {base.get('worst_droop_mv')}",
        )
        check(
            abs(float(base["worst_droop_mv"]) - 6.075) < 0.05,
            f"current FlowLab DirectLU ~6.075 mV, got {base.get('worst_droop_mv')}",
        )
        check(
            isinstance(base.get("solve"), dict) and base["solve"].get("role") == "reference",
            f"SolveResult stamps DirectLU as numerical reference, got {base.get('solve')}",
        )
        scen = base.get("current_scenario") or {}
        check(scen.get("source") == "sta_t50", f"GCD 6.075 uses sta_t50 scenario, got {scen}")
        check(
            ((base.get("solve") or {}).get("activity_via") or {}).get("scenario", {}).get("source") == "sta_t50",
            "SolveResult.activity_via points at the sta_t50 scenario",
        )
        amg = solve_f4(variant="flowlab", solver="amg")
        check(amg.get("status") == "ok", f"F4 AMG residual ({amg.get('reason')})")
        check(amg.get("gold") is False, "AMG residual is not marked gold")
        check(amg.get("solver_kind") == "amg", f"AMG solver_kind, got {amg.get('solver_kind')}")
        check(
            abs(float(amg["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 0.05,
            f"AMG matches DirectLU on this mesh, got {amg.get('worst_droop_mv')}",
        )
        print(f"    F4 AMG {amg['worst_droop_mv']:.3f} mV vs DirectLU {base['worst_droop_mv']:.3f} mV ({amg.get('cost_s', 0):.2f}s)")
        ras = solve_f4(variant="flowlab", solver="ras")
        check(ras.get("status") == "ok", f"F4 RAS residual ({ras.get('reason')})")
        check(ras.get("gold") is False, "RAS residual is not marked gold")
        check(ras.get("solver_kind") == "ras", f"RAS solver_kind, got {ras.get('solver_kind')}")
        check(
            abs(float(ras["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 0.05,
            f"RAS matches DirectLU on this mesh, got {ras.get('worst_droop_mv')}",
        )
        print(f"    F4 RAS {ras['worst_droop_mv']:.3f} mV vs DirectLU {base['worst_droop_mv']:.3f} mV ({ras.get('cost_s', 0):.2f}s)")
        kry = solve_f4(variant="flowlab", solver="krylov")
        check(kry.get("status") == "ok", f"F4 Krylov/MOR residual ({kry.get('reason')})")
        check(kry.get("gold") is False, "Krylov residual is not marked gold")
        check(kry.get("solver_kind") == "krylov", f"Krylov solver_kind, got {kry.get('solver_kind')}")
        check((kry.get("m") or 0) >= 1, f"Krylov reports reduced order m, got {kry.get('m')}")
        check(
            abs(float(kry["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 5.0,
            f"Krylov/MOR stays within 5 mV of DirectLU {kry.get('worst_droop_mv')}",
        )
        check(
            (kry.get("solve") or {}).get("abs_err_vs_reference_mv") is not None
            or abs(float(kry["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 5.0,
            "Krylov SolveResult can carry |A-C|",
        )
        print(
            f"    F4 Krylov {kry['worst_droop_mv']:.3f} mV m={kry.get('m')} "
            f"vs DirectLU {base['worst_droop_mv']:.3f} mV ({kry.get('cost_s', 0):.2f}s)"
        )
        from dse.controller import admit_paid_f4
        from heavy_analysis import AES_F4_N_NODES, AES_F4_N_R

        _alog: list[dict] = []

        def _admit_step(kind: str, **kw):
            _alog.append({"kind": kind, **kw})

        mem_gate = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-gate-")) / "m.jsonl")
        g_a = admit_paid_f4(mem_gate, solver="direct", n_r=int(base["n_r"]), step=_admit_step)
        check(
            g_a["admitted"] is True and (base.get("solve") or {}).get("role") == "reference",
            f"controller-paid DirectLU is reference, gate={g_a} solve={base.get('solve')}",
        )
        g_c = admit_paid_f4(mem_gate, solver="krylov", n_r=int(base["n_r"]), step=_admit_step)
        check(
            g_c["admitted"] is True and (kry.get("solve") or {}).get("role") == "accelerator",
            f"controller-paid Krylov is accelerator, gate={g_c} solve={kry.get('solve')}",
        )
        g_aes = admit_paid_f4(
            mem_gate, solver="krylov", n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, step=_admit_step
        )
        check(g_aes["admitted"] is False, f"controller gate still refuses AES Krylov, got {g_aes}")
        check(
            any(x.get("kind") == "admit" and x.get("pay") is False for x in _alog),
            "refused admit is logged on the controller step",
        )
        check(base.get("static_ir_mv") is not None, "F4 restamp reports static IR")
        check(float(base["static_ir_mv"]) > 1.0, f"static IR is a real mV drop, got {base.get('static_ir_mv')}")
        check(
            abs(float(base["static_ir_mv"]) - float(base["worst_droop_mv"])) > 0.5,
            "static IR is not a copy of dynamic droop",
        )
        em0 = base.get("em") or {}
        check(em0.get("j_absmax_a_m2") is not None, f"F4 restamp reports EM J ({em0})")
        extra_c = solve_f4(variant="flowlab", c_decap=200e-15)
        check(extra_c["worst_droop_mv"] < base["worst_droop_mv"] - 0.5, "more decap lowers droop on the same extract")
        hot = solve_f4(variant="flowlab", i_scale=1.2)
        check(hot["worst_droop_mv"] > base["worst_droop_mv"] + 0.5, "I(t)×1.2 raises droop (same spatial pattern)")
        print(
            f"    F4 oracle base {base['worst_droop_mv']:.3f}  decap200 {extra_c['worst_droop_mv']:.3f}  "
            f"iscale1.2 {hot['worst_droop_mv']:.3f} mV  J={em0.get('j_absmax_a_m2'):.3e} ({base['cost_s']:.2f}s)"
        )
        mapped_ext = _ROOT / "learn/sim/dse/netlists/ab9f115d5a67.v"
        if not mapped_ext.is_file() and mapped_ok.is_file():
            mapped_ext = mapped_ok
        if extract_available() and mapped_ext.is_file():
            dest = Path(tempfile.mkdtemp(prefix="dse-ext-"))
            ext = extract_pdn(mapped_ext, dest, timeout_s=60)
            check(ext.get("status") == "ok", f"candidate write_pg_spice ({ext.get('reason')})")
            check((ext.get("n_r") or 0) > 200, f"candidate spice has an R mesh, n_r={ext.get('n_r')}")
            check(ext.get("n_r") != base.get("n_r"), "candidate extract is not the finish mesh")
            check(ext.get("gold") is False, "candidate extract is not gold")
            cand = solve_f4(variant="flowlab", spice=ext["spice"], insts=ext["insts"])
            check(cand.get("status") == "ok", f"Solver A on candidate extract ({cand.get('reason')})")
            check(cand.get("extract") == "candidate", "override spice is labeled candidate")
            check(cand.get("gold") is False, "candidate solve is not gold")
            check(abs(float(cand["worst_droop_mv"]) - GOLD_MV) > 0.2, "candidate mesh droop is not the finish gold")
            check(cand.get("static_ir_mv") is not None, "candidate F4 reports static IR")
            cem = cand.get("em") or {}
            check(cem.get("j_absmax_a_m2") is not None, "candidate F4 reports EM J")
            print(
                f"    F4 candidate extract n_r={ext['n_r']} n_i={ext.get('n_i')} "
                f"droop={cand['worst_droop_mv']:.3f} mV J={cem.get('j_absmax_a_m2'):.3e} "
                f"({ext['cost_s']:.2f}+{cand.get('cost_s', 0):.2f}s)"
            )
            dest_r = Path(tempfile.mkdtemp(prefix="dse-rext-"))
            ext_r = extract_pdn(
                mapped_ext, dest_r, timeout_s=60, x_dbu=70896.0, y_dbu=39429.0, region="r31"
            )
            check(ext_r.get("status") == "ok", f"region write_pg_spice ({ext_r.get('reason')})")
            check(ext_r.get("region_bin"), f"region extract names the bin, got {ext_r.get('region_bin')}")
            check((ext_r.get("n_r") or 0) > 200, f"region spice has an R mesh, n_r={ext_r.get('n_r')}")
            check(ext_r.get("gold") is False, "region extract is not gold")
            check(ext_r.get("n_r") != base.get("n_r"), "region extract is not the finish mesh")
            print(
                f"    F4 region extract bin={ext_r.get('region_bin')} n_r={ext_r['n_r']} "
                f"({ext_r['cost_s']:.2f}s)"
            )
        else:
            print("    skip candidate PDN extract (no openroad or mapped netlist)")
    else:
        print("    skip F4 oracle (no cached extract)")
    if gold_before is not None:
        check(gold_json.read_text() == gold_before, "F4 oracle does not restamp dynamic_ir_flowlab.json gold")

    print("ALL test_dse PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
