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
from dse.arch_space import emit_gcd_variant, plan_dpath_extracts
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
    check(local_scope(attr)["hierarchy"][-1] == "logic_cone", "hierarchy ends at the cone")

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
    check("coreUtilization" not in (mo_pick or {}), "EHVI proposal does not flatten physical knobs")
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
    check(any(s["level"] == "routing" for s in planned["steps"]), "planner schedules routing GRT")
    check(any(s["level"] == "f4_extract" for s in planned["steps"]), "planner schedules candidate write_pg_spice")
    check(
        knobs_fp("routing", {"source": "f2_openroad_grt"})
        != knobs_fp("physical", {"source": "f2_openroad_grt"}),
        "routing GRT is not flattened into the physical fingerprint",
    )
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

    from dse.sta_f3 import available as sta_available, evaluate_sta
    from dse.openroad_f2 import evaluate_grt
    from dse.attribute import attribute_sta

    if sta_available() and mapped_ok.is_file():
        sta = evaluate_sta(mapped_ok)
        check(sta.get("status") == "ok", f"OpenSTA F3 on mapped F1 ({sta.get('reason')})")
        check(sta.get("wns_ns") is not None, "F3 reports WNS")
        check((sta.get("power_w") or 0) > 0, f"F3 reports power, got {sta.get('power_w')}")
        print(f"    F3 STA WNS={sta['wns_ns']:.3f} ns P={sta['power_w']:.4e} W ({sta['cost_s']:.2f}s)")
        sattr = attribute_sta(sta, inherit={"modules": ["dpath"], "scope": "logic_cone"})
        check(sattr["restart_chip"] is False, "STA attribution refuses a chip restart")
        check("dpath" in (sattr.get("modules") or []), "STA inherit keeps the dpath cone")

    if gpl_available() and mapped_ok.is_file():
        grt = evaluate_grt(mapped_ok, timeout_s=40)
        check(grt.get("status") == "ok", f"OpenROAD GRT on mapped F1 ({grt.get('reason')})")
        check(grt.get("wns_ns") is not None, "GRT+parasitics reports WNS")
        check("detailed" not in (grt.get("via") or "").lower() or "not detailed" in (grt.get("via") or ""),
              "GRT via states it is not detailed route")
        print(f"    F2 GRT WNS={grt['wns_ns']:.3f} ns overflow={grt.get('overflow')} ({grt['cost_s']:.2f}s)")

    props = dse_propose(mem2, focus="dpath", attr=attr)
    check(props, "symbolic proposer returns at least one idea")
    check(all("pkg_l" not in p and "coreUtilization" not in p for p in props), "proposer stays off PDN/physical knobs")
    check("gold" in (adapter_status()["solver"]["note"] or "").lower(), "solver adapter keeps gold unrestamped")
    check("restamp" in (adapter_status()["solver"]["via"] or ""), "solver adapter can restamp on the cached extract")
    check(
        "write_pg_spice" in (adapter_status()["extraction"]["via"] or ""),
        "extraction adapter is write_pg_spice, not a flattened black-box",
    )

    from dse.controller import propose_logic

    knobs = propose_logic(mem2)
    check(knobs is not None and knobs.get("name"), "controller proposes a logic catalog entry")
    check("coreUtilization" not in knobs, "logic proposal does not smuggle physical knobs")
    check("pkg_l" not in knobs, "logic proposal does not smuggle PDN knobs")

    ir_p = _ROOT / "learn" / "sim" / "reports" / "dynamic_ir_flowlab.json"
    if ir_p.is_file():
        real = attribute_dynamic_ir(json.loads(ir_p.read_text()))
        check(real.get("droop_mv") and abs(float(real["droop_mv"]) - 45.298) < 0.02, "GCD IR attr keeps 45.298 gold")
        check("dpath" in (real.get("modules") or []), "GCD worst path attributes to dpath")
        print(f"    GCD IR cone {real.get('modules')} droop={real.get('droop_mv'):.3f} mV")

    import shutil

    if shutil.which("yosys") and rtl.is_file():
        from dse.fidelity import evaluate_f1_abc, liberty_path

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
            print(
                f"    F1 default {c0.qor.area_um2:.3f} vs fast {c1.qor.area_um2:.3f} vs "
                f"rewrite+balance {c2.qor.area_um2:.3f} vs eqz-arch {ca.qor.area_um2:.3f} µm²"
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

    gold_json = _ROOT / "learn/sim/reports/dynamic_ir_flowlab.json"
    gold_before = gold_json.read_text() if gold_json.is_file() else None
    if f4_ok("flowlab"):
        base = solve_f4(variant="flowlab")
        check(base.get("status") == "ok", f"F4 oracle Solver A ({base.get('reason')})")
        check(base.get("gold") is False, "candidate F4 is not marked gold")
        check(base.get("extract") == "finish", "default F4 uses the finish extract")
        check(abs(float(base["worst_droop_mv"]) - GOLD_MV) < 0.05, f"i_scale=1 reproduces gold {base.get('worst_droop_mv')}")
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
            cem = cand.get("em") or {}
            check(cem.get("j_absmax_a_m2") is not None, "candidate F4 reports EM J")
            print(
                f"    F4 candidate extract n_r={ext['n_r']} n_i={ext.get('n_i')} "
                f"droop={cand['worst_droop_mv']:.3f} mV J={cem.get('j_absmax_a_m2'):.3e} "
                f"({ext['cost_s']:.2f}+{cand.get('cost_s', 0):.2f}s)"
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
