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
from dse.metrics import QoR, dominates, pareto_front, wns_cost_from_slack_ns
from dse.mo import ehvi_2d, hypervolume_2d
from dse.physical_space import PHYSICAL_CATALOG, gpl_density, next_catalog_spec, rudy_congestion
from dse.pdn_space import PDN_CATALOG, next_pdn_spec


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
    check(any(s["level"] == "f4_amg" for s in planned["steps"]), "planner schedules AMG residual")
    check(any(s["level"] == "f4_ras" for s in planned["steps"]), "planner schedules RAS residual")
    check(any(s["level"] == "f4_krylov" for s in planned["steps"]), "planner schedules Krylov/MOR residual")
    check(any(s["level"] == "synthesis" for s in planned["steps"]), "planner schedules synthesis F1")
    check(any(s["level"] == "cell" for s in planned["steps"]), "planner schedules cell-local size-up")
    check(any(s["level"] == "net" for s in planned["steps"]), "planner schedules net-local BUF")
    check(any(s["level"] == "net_port" for s in planned["steps"]), "planner schedules port-net BUF")
    check(any(s["level"] == "routing" for s in planned["steps"]), "planner schedules routing GRT")
    check(any(s["level"] == "f4_extract" for s in planned["steps"]), "planner schedules candidate write_pg_spice")
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
    check(next_fidelity(level="f4_scale", pred=None, budget_left=20, cost_hint={}) == "F4", "attributed I-scale measures at F4")
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
        check((arr.get("n_inst") or 0) > 0, f"arrivals cover instances, n_inst={arr.get('n_inst')}")
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
        should_pay_f4_scale,
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
    from dse.surrogate import residual_f4_knob, residual_f4_mesh, residual_f4_region

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
        check(abs(float(base["worst_droop_mv"]) - GOLD_MV) < 0.05, f"i_scale=1 reproduces gold {base.get('worst_droop_mv')}")
        amg = solve_f4(variant="flowlab", solver="amg")
        check(amg.get("status") == "ok", f"F4 AMG residual ({amg.get('reason')})")
        check(amg.get("gold") is False, "AMG residual is not marked gold")
        check(amg.get("solver_kind") == "amg", f"AMG solver_kind, got {amg.get('solver_kind')}")
        check(abs(float(amg["worst_droop_mv"]) - GOLD_MV) < 0.05, f"AMG reproduces gold droop {amg.get('worst_droop_mv')}")
        print(f"    F4 AMG {amg['worst_droop_mv']:.3f} mV vs DirectLU {base['worst_droop_mv']:.3f} mV ({amg.get('cost_s', 0):.2f}s)")
        ras = solve_f4(variant="flowlab", solver="ras")
        check(ras.get("status") == "ok", f"F4 RAS residual ({ras.get('reason')})")
        check(ras.get("gold") is False, "RAS residual is not marked gold")
        check(ras.get("solver_kind") == "ras", f"RAS solver_kind, got {ras.get('solver_kind')}")
        check(abs(float(ras["worst_droop_mv"]) - GOLD_MV) < 0.05, f"RAS reproduces gold droop {ras.get('worst_droop_mv')}")
        print(f"    F4 RAS {ras['worst_droop_mv']:.3f} mV vs DirectLU {base['worst_droop_mv']:.3f} mV ({ras.get('cost_s', 0):.2f}s)")
        kry = solve_f4(variant="flowlab", solver="krylov")
        check(kry.get("status") == "ok", f"F4 Krylov/MOR residual ({kry.get('reason')})")
        check(kry.get("gold") is False, "Krylov residual is not marked gold")
        check(kry.get("solver_kind") == "krylov", f"Krylov solver_kind, got {kry.get('solver_kind')}")
        check((kry.get("m") or 0) >= 1, f"Krylov reports reduced order m, got {kry.get('m')}")
        check(
            abs(float(kry["worst_droop_mv"]) - GOLD_MV) < 5.0,
            f"Krylov/MOR stays within 5 mV of gold {kry.get('worst_droop_mv')}",
        )
        print(
            f"    F4 Krylov {kry['worst_droop_mv']:.3f} mV m={kry.get('m')} "
            f"vs DirectLU {base['worst_droop_mv']:.3f} mV ({kry.get('cost_s', 0):.2f}s)"
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
