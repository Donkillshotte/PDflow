"""Next-level DSE: feasibility, F6 ingest, funnel, scheduler, provenance."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from dse.arch_plugins import classify, plugin
from dse.campaign import f6_hv_points, gated_hv_f6, run_campaign, suggest_ref
from dse.contracts import ConstraintContract, GeometryContract, SemanticContract, stamp_evidence
from dse.exporter import mark_export
from dse.f6_finish import ingest_finish, parse_6_report, parse_grt, qor_from_finish, refuse_locked_variant
from dse.feasibility import constraint_dominates, feasibility_of, feasible_pareto, ir_comparable
from dse.fingerprint import knobs_fp
from dse.funnel import promote_or_reject
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR
from dse.next_level import run_next_level
from dse.pdn_provenance import same_extract_delta
from dse.place_finish_model import predict_finish_wns
from dse.scheduler import next_action


def _cand(mem_kwargs=None, **kw) -> Candidate:
    base = dict(
        id=kw.pop("id", DesignMemory.new_id()),
        design_id="gcd",
        parent_id=None,
        level="logic",
        knobs={"source": "test"},
        knobs_fp=knobs_fp("logic", {"source": "test"}),
        rtl_fp="x",
        netlist_fp=None,
        fidelity="F3",
        qor=QoR(area_um2=400, wns_cost=0.1, fidelity="F3"),
        cost_s=0.0,
        status="ok",
    )
    base.update(kw)
    q = base.get("qor")
    if "fidelity" not in kw and q is not None and getattr(q, "fidelity", None):
        base["fidelity"] = q.fidelity
    return Candidate(**base)


def check_next_level(check, root: Path) -> None:
    # --- schema: old JSONL still loads ---
    old = root / "learn/sim/dse/memory_flowlab.jsonl"
    mem = DesignMemory(old)
    check(len(mem) >= 100, f"legacy JSONL loads ({len(mem)} rows)")
    sample = next(iter(mem.all()))
    check(sample.schema_version >= 1, "schema_version defaulted")
    check(sample.finish_ready is False or sample.finish_ready is True, "finish_ready bool")

    # --- ideal cannot beat finish ---
    ideal = _cand(
        id="ideal",
        fidelity="F3",
        qor=QoR(area_um2=619, wns_cost=0.114, fidelity="F3"),
        artifacts={"wns_ns": -0.114, "wns_source": "ideal"},
        semantic_contract={"status": "pass"},
    )
    finish_a = _cand(
        id="finA",
        level="signoff",
        fidelity="F6",
        qor=QoR(area_um2=940.31, wns_cost=0.037167, power_w=0.00393, fidelity="F6"),
        artifacts={"finish_wns_ns": -0.037167, "finish_tns_ns": -0.595, "flow_errors": 0},
        semantic_contract={"status": "pass"},
        finish_ready=True,
        geometry_contract={"kind": "product", "die_um2": 1970.0, "core_um2": 1712.0},
    )
    stamp_evidence(finish_a, "wns", -0.037167, "finish")
    check(feasibility_of(ideal).feasible is False, "ideal STA is not feasible finish")
    check(feasibility_of(finish_a).feasible is False, "A finish WNS still negative → not timing-closed")
    check(constraint_dominates(finish_a, ideal), "finish evidence outranks ideal even if both open")
    check(not constraint_dominates(ideal, finish_a), "ideal must not dominate finish")

    closed = _cand(
        id="closed",
        level="signoff",
        fidelity="F6",
        qor=QoR(area_um2=1000, wns_cost=0.0, tns_cost=0.0, fidelity="F6"),
        artifacts={"finish_wns_ns": 0.001, "finish_tns_ns": 0.0, "flow_errors": 0},
        semantic_contract={"status": "pass"},
        finish_ready=True,
        geometry_contract={"kind": "product"},
    )
    stamp_evidence(closed, "wns", 0.001, "finish")
    stamp_evidence(closed, "tns", 0.0, "finish")
    check(feasibility_of(closed).feasible, "positive finish slack is feasible")
    check(constraint_dominates(closed, finish_a), "timing-closed dominates open finish")

    # --- funnel: B-like place-negative rejected; A-like place+12ps eligible ---
    b = _cand(
        id="Bplace",
        qor=QoR(area_um2=610, wns_cost=0.314, fidelity="F2"),
        artifacts={"place_wns_ns": -0.313564, "mapped_v": "x"},
        semantic_contract={"status": "pass"},
        attr={"equiv": "PASS"},
    )
    g_b = promote_or_reject(b)
    check(g_b.ok is False and "place_wns" in g_b.reason, f"B-like rejected at P2: {g_b.reason}")
    a_place = _cand(
        id="Aplace",
        qor=QoR(area_um2=684, wns_cost=-0.012, fidelity="F2"),
        artifacts={"place_wns_ns": 0.0123135, "flow_errors": 0},
        semantic_contract={"status": "pass"},
        attr={"equiv": "PASS"},
    )
    g_a = promote_or_reject(a_place)
    check(g_a.ok and g_a.stage == "F6", f"A-like place meeting is F6-eligible: {g_a}")

    pred_a = predict_finish_wns(a_place)
    pred_b = predict_finish_wns(b)
    check(pred_a.p_close > pred_b.p_close, f"model ranks A-like above B-like ({pred_a.p_close} vs {pred_b.p_close})")

    # --- PDN provenance ---
    host = _cand(
        id="irH",
        qor=QoR(dynamic_ir_mv=6.075, fidelity="F4"),
        artifacts={"extract_id": "finish_n_r_5816"},
        evidence={"dynamic_ir_mv": {"value": 6.075, "source": "directlu", "artifact": "finish_n_r_5816"}},
        geometry_contract={"kind": "product", "die_um2": 1970.0},
    )
    same = _cand(
        id="irC",
        qor=QoR(dynamic_ir_mv=4.156, fidelity="F4"),
        artifacts={"extract_id": "finish_n_r_5816"},
        evidence={"dynamic_ir_mv": {"value": 4.156, "source": "directlu", "artifact": "finish_n_r_5816"}},
        geometry_contract={"kind": "product", "die_um2": 1970.0},
    )
    other = _cand(
        id="irX",
        qor=QoR(dynamic_ir_mv=1.705, fidelity="F4"),
        artifacts={"extract_id": "strap_other"},
        evidence={"dynamic_ir_mv": {"value": 1.705, "source": "directlu", "artifact": "strap_other"}},
        geometry_contract={"kind": "product", "die_um2": 1304.0},
    )
    d_ok = same_extract_delta(host, same)
    d_bad = same_extract_delta(host, other)
    check(d_ok.ok and abs(d_ok.delta_mv - (-1.919)) < 0.01, f"same-extract decap delta, got {d_ok}")
    check(not d_bad.ok, f"cross-mesh IR refused: {d_bad.reason}")
    check(not ir_comparable(host, other), "IR not comparable across extracts")

    # --- F6 parse real ORFS reports ---
    a_rep = root / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab/6_report.json"
    b_rep = root / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab_dse_small/6_report.json"
    check(a_rep.is_file() and b_rep.is_file(), "A and B 6_report.json on disk")
    pa, pb = parse_6_report(a_rep), parse_6_report(b_rep)
    check(abs(float(pa["wns_setup_ns"]) + 0.037167) < 1e-6, f"parse A WNS {pa.get('wns_setup_ns')}")
    check(float(pb["wns_setup_ns"]) < -0.3, "parse B WNS still ~−338 ps")
    qa = qor_from_finish(pa)
    check(qa.fidelity == "F6" and qa.area_um2 and qa.area_um2 > 900, "F6 QoR from finish area")
    check(pa.get("psm_vdd_drop_v") is not None, "parse A IR VDD from 6_report")
    check(abs(float(pa["psm_vdd_drop_v"]) - 0.00666716) < 1e-8, f"parse A IR {pa.get('psm_vdd_drop_v')}")
    check(pa.get("psm_vdd_mean_drop_v") is not None, "parse A mean IR")
    check(abs(float(pa["psm_vdd_mean_drop_v"]) - 0.00264) < 5e-4, f"parse A mean IR {pa.get('psm_vdd_mean_drop_v')}")
    a_grt = root / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab/5_1_grt.json"
    check(a_grt.is_file(), "A 5_1_grt.json on disk")
    ga = parse_grt(a_grt)
    check(ga.get("grt_wl") is not None and int(ga["grt_wl"]) == 7589, f"parse A GRT WL {ga.get('grt_wl')}")

    tmp = Path(tempfile.mkdtemp(prefix="dse-nl-")) / "m.jsonl"
    mem_f = DesignMemory(tmp)
    parent = mem_f.add(_cand(id="parentA", semantic_contract={"status": "pass"}))
    f6a = ingest_finish(mem_f, variant="flowlab", parent=parent, geometry_kind="product")
    check(f6a.fidelity == "F6" and f6a.level == "signoff", "ingest A as F6")
    check(feasibility_of(f6a).timing_source == "finish", "ingested timing evidence is finish")
    raised = False
    try:
        refuse_locked_variant("flowlab")
    except ValueError:
        raised = True
    check(raised, "launch into flowlab refused")

    # --- scheduler ---
    b_sched = _cand(
        id="Bsched",
        qor=QoR(area_um2=610, wns_cost=0.314, fidelity="F2"),
        artifacts={"place_wns_ns": -0.313564, "mapped_v": "x"},
        semantic_contract={"status": "pass"},
        attr={"equiv": "PASS"},
    )
    mem_s = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-nl-s-")) / "s.jsonl")
    mem_s.add(b_sched)
    act = next_action(mem_s, budget_s=120, finish_shots_left=1)
    check(act.kind in ("reject", "equiv"), f"scheduler does not finish B-like, got {act}")
    a_sched = _cand(
        id="Asched",
        qor=QoR(area_um2=684, wns_cost=-0.012, fidelity="F2"),
        artifacts={"place_wns_ns": 0.0123135, "flow_errors": 0},
        semantic_contract={"status": "pass"},
        attr={"equiv": "PASS"},
    )
    mem_s2 = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-nl-s2-")) / "s.jsonl")
    mem_s2.add(a_sched)
    act2 = next_action(mem_s2, budget_s=120, finish_shots_left=1)
    check(act2.kind == "finish" and act2.candidate_id == a_sched.id, f"scheduler finishes A-like, got {act2}")

    def fake_runner(action, memory):
        if action.kind == "finish" and action.candidate_id:
            c = memory.get(action.candidate_id)
            c.artifacts = dict(c.artifacts or {}, finish_wns_ns=0.0, finish_tns_ns=0.0, flow_errors=0)
            c.fidelity = "F6"
            c.level = "signoff"
            c.qor = QoR(area_um2=c.qor.area_um2, wns_cost=0.0, tns_cost=0.0, fidelity="F6")
            stamp_evidence(c, "wns", 0.0, "finish")
            memory.touch(c)
        return {}

    mem_nl = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-nl-run-")) / "r.jsonl")
    a_run = _cand(
        id="Arun",
        qor=QoR(area_um2=684, wns_cost=-0.012, fidelity="F2"),
        artifacts={"place_wns_ns": 0.0123135, "flow_errors": 0},
        semantic_contract={"status": "pass"},
        attr={"equiv": "PASS"},
    )
    mem_nl.add(a_run)
    pre = next_action(DesignMemory(mem_nl.path), budget_s=90, finish_shots_left=1)
    check(pre.kind == "finish", f"precondition: reloaded A-run is finish, got {pre} n={len(DesignMemory(mem_nl.path))}")
    report = run_next_level(memory_path=mem_nl.path, wall_s=90.0, runner=fake_runner, finish_shots=1)
    check(report["ok"] and report["n_actions"] >= 1, f"next_level loop ran {report}")
    kinds = [a["kind"] for a in report["actions"]]
    check("finish" in kinds, f"next_level paid a finish action {kinds}")

    # --- F6 HV campaign stop ---
    def inner_add_f6(**kwargs):
        m = DesignMemory(kwargs["memory_path"])
        n = len(m)
        m.add(
            _cand(
                id=f"f6{n}",
                level="signoff",
                fidelity="F6",
                qor=QoR(area_um2=900 - n, wns_cost=0.05 - 0.001 * n, fidelity="F6"),
                artifacts={"finish_wns_ns": -0.05, "flow_errors": 0},
                semantic_contract={"status": "pass"},
            )
        )
        return {"ok": True}

    camp_path = Path(tempfile.mkdtemp(prefix="dse-nl-c-")) / "c.jsonl"
    DesignMemory(camp_path).add(
        _cand(
            id="seedf6",
            level="signoff",
            fidelity="F6",
            qor=QoR(area_um2=940, wns_cost=0.037, fidelity="F6"),
            artifacts={"finish_wns_ns": -0.037, "flow_errors": 0},
        )
    )
    pts = f6_hv_points(DesignMemory(camp_path))
    check(len(pts) == 1, f"f6_hv_points sees seed {pts}")
    camp = run_campaign(
        inner_runner=inner_add_f6,
        memory_path=camp_path,
        wall_s=10.0,
        inner_budget_s=1.0,
        max_inner=3,
        stop_metric="f6",
        hv_eps=1e-9,
    )
    check(camp["ok"] and camp["n_inner"] >= 1, f"F6 campaign ran {camp}")

    # --- plugins / exporter ---
    check(classify("sub_twos_complement") == "rtl_rewrite", "extracts are rtl_rewrite not architecture")
    check(plugin("gcd_binary").verify == "unsupported", "binary GCD is not a fake proof")
    rew = _cand(
        id="rew",
        knobs={"extract": "sub_twos_complement", "scope": "logic_cone", "source": "arch"},
        attr={"equiv": "PASS"},
        artifacts={},
    )
    mark_export(rew, netlist=None)
    check(rew.finish_ready is False, "unstitched rtl_rewrite is not finish_ready")

    geom = GeometryContract(kind="fixed", die_um2=1970.0, core_um2=1712.0, scene_hash="abc")
    geom2 = GeometryContract(kind="fixed", die_um2=1304.0, core_um2=1136.0, scene_hash="def")
    check(not geom.compatible(geom2), "fixed-geometry mismatch is incomparable")
    check(ConstraintContract(0.46).compatible(ConstraintContract(0.46)), "same SDC compatible")
    check(not ConstraintContract(0.46).compatible(ConstraintContract(0.82)), "aes clock is another scenario")

    front = feasible_pareto([closed, finish_a, ideal])
    check("closed" in front and "ideal" not in front, f"feasible_pareto prefers closed, got {front}")
    check("finA" in feasible_pareto([finish_a, ideal]), "open finish still ranks above ideal-only")
    check("ideal" not in feasible_pareto([finish_a, ideal]), "ideal is dominated by finish evidence")

    # --- folklore isolated ---
    from dse.folklore import folklore_enabled, folklore_report, gnn_report

    check(folklore_enabled() is False, "folklore off by default")
    check(gnn_report([]).get("skipped") is True, "GNN report skipped unless DSE_ENABLE_FOLKLORE")
    check(folklore_report()["consulted_by_next_level"] is False, "next-level does not consult folklore")
    sched_src = (root / "learn/dse/scheduler.py").read_text()
    check("bandit" not in sched_src and "gnn" not in sched_src.split("GNN/bandit")[-1][:200] or "GNN/bandit are not consulted" in sched_src, "scheduler names the isolation")

    # --- frozen A geometry from DEF ---
    from dse.f6_finish import BASELINE_6_REPORT_SHA, assert_baseline_frozen, parse_place_dp
    from dse.geometry import load_geometry_a, locked_contract_a, parse_def_geometry
    from dse.next_level import make_live_runner, seed_bakeoff

    frozen = assert_baseline_frozen()
    check(frozen["sha256_6_report"] == BASELINE_6_REPORT_SHA, "flowlab 6_report freeze holds")
    def_path = root / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.def"
    parsed = parse_def_geometry(def_path)
    ga = load_geometry_a()
    check(abs(parsed["die_um2"] - float(ga["die_um2"])) < 0.1, f"DEF die {parsed['die_um2']} vs freeze {ga['die_um2']}")
    check(parsed["die_area"].split()[:2] == ["0", "0"], "A die origin 0 0")
    check(locked_contract_a().kind == "fixed", "A lock is fixed geometry")

    b_place = parse_place_dp(root / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab_dse_small/3_5_place_dp.json")
    c_place = parse_place_dp(root / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab_dse_fast/3_5_place_dp.json")
    check(float(b_place["place_wns_ns"]) < -0.3, f"live B place WNS {b_place['place_wns_ns']}")
    check(float(c_place["place_wns_ns"]) < 0, f"live C place WNS {c_place['place_wns_ns']}")
    b_live = _cand(
        id="Blive",
        artifacts={"place_wns_ns": b_place["place_wns_ns"]},
        semantic_contract={"status": "pass"},
        qor=QoR(area_um2=610, wns_cost=0.31, fidelity="F2"),
    )
    check(promote_or_reject(b_live).ok is False, "real B place log is not F6-eligible")

    # --- Yosys equiv: identity + rtl_rewrite vs original RTL ---
    from dse.arch_plugins import plugin as arch_plugin
    from dse.equiv import equiv_rtl_pair

    gold = root / "learn/flowlab/gcd.v"
    ident = equiv_rtl_pair(gold, gold, top="gcd")
    check(ident.status == "pass", f"gcd.v proves equivalent to itself ({ident.status} log={ident.log})")
    dest = Path(tempfile.mkdtemp(prefix="dse-nl-rtl-")) / "sub.v"
    arch_plugin("sub_twos_complement").emit(gold, dest)
    sub_eq = equiv_rtl_pair(gold, dest, top="gcd")
    check(sub_eq.status == "pass", f"sub_twos_complement vs original RTL: {sub_eq.status} log={sub_eq.log}")

    # --- live runner seeds bake-off, never launches finish ---
    mem_seed = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-nl-seed-")) / "s.jsonl")
    seeded = seed_bakeoff(mem_seed)
    check("flowlab" in seeded.get("seeded", []), f"seeded A from logs {seeded}")
    check("flowlab_dse_small" in seeded.get("seeded", []), "seeded B from logs")
    report_live = run_next_level(
        memory_path=mem_seed.path,
        wall_s=15.0,
        runner=make_live_runner(launch_finish=False),
        finish_shots=1,
    )
    kinds_live = [a["kind"] for a in report_live["actions"]]
    check(report_live["ok"], f"bake-off next-level ok {report_live}")
    check("finish" not in kinds_live or report_live.get("stop") == "finish_skipped", f"no unpaid finish launch {kinds_live} stop={report_live.get('stop')}")
    check(assert_baseline_frozen()["sha256_6_report"] == BASELINE_6_REPORT_SHA, "flowlab freeze still holds after next-level seed")

    help_src = (root / "learn/scripts/run_dse.py").read_text()
    check("--next-level" in help_src and "make_live_runner" in help_src, "CLI wires --next-level to live runner")

    from eval_vs_base_flow import evaluate

    vs = evaluate(root)
    v = vs["verdict"]
    check(v["baseline_untouched"], "eval freeze A still holds")
    check(v["A_stays"], f"eval: no cook beats ORFS finish ({v['summary']})")
    check(v["ainj_reproduces_A"], "eval: A-injected matches A WNS+sha")
    check(v["any_timing_closed"] is False, "eval: nobody is timing-closed at 0.46 ns")
    check(v["funnel_would_skip_B_C_Bfix"], "eval: funnel skips B/C/Bfix")
    check(v["A_dominates_B"] and v["A_dominates_C"], "eval: A constraint-dominates B and C")
    dB = vs["delta_vs_A"]["B"]["d_wns_ps"]
    dC = vs["delta_vs_A"]["C"]["d_wns_ps"]
    dF = vs["delta_vs_A"]["Bfix"]["d_wns_ps"]
    check(dB is not None and dB < -200, f"eval: B at least 200 ps later than A ({dB})")
    check(dC is not None and dC < -100, f"eval: C at least 100 ps later than A ({dC})")
    check(dF is not None and dF < -200, f"eval: Bfix at least 200 ps later than A ({dF})")
    check(vs["delta_vs_A"]["Bfix"]["same_die_as_A"], "eval: Bfix die matches A")
    check(abs(vs["delta_vs_A"]["Ainj"]["d_wns_ps"]) < 1e-6, "eval: Ainj ΔWNS is 0")

    # --- campaign infra: wrapper refusal, registry, eval parse ---
    import os
    import subprocess
    from dse.experiments import Experiment, ExperimentLog
    from dse.experiments import refuse_locked_variant as refuse_campaign_variant
    from eval_campaign import evaluate as eval_campaign

    wrapper = root / "scripts" / "run_design_finish.sh"
    check(wrapper.is_file(), "run_design_finish.sh exists")
    env = {**os.environ, "DESIGN": "gcd", "FLOW_VARIANT": "flowlab"}
    r = subprocess.run(["bash", str(wrapper)], cwd=root, env=env, capture_output=True, text=True)
    check(r.returncode == 2 and "locked" in (r.stderr + r.stdout).lower(), f"wrapper refuses flowlab ({r.returncode} {r.stderr})")
    env["FLOW_VARIANT"] = "learn"
    r = subprocess.run(["bash", str(wrapper)], cwd=root, env=env, capture_output=True, text=True)
    check(r.returncode == 2, "wrapper refuses learn")
    env["FLOW_VARIANT"] = "base"
    r = subprocess.run(["bash", str(wrapper)], cwd=root, env=env, capture_output=True, text=True)
    check(r.returncode == 2, "wrapper refuses base")
    env["FLOW_VARIANT"] = "camp_gcd_krylov"
    r = subprocess.run(["bash", str(wrapper)], cwd=root, env=env, capture_output=True, text=True)
    check(r.returncode == 2, "wrapper refuses krylov variant")

    raised = False
    try:
        refuse_campaign_variant("flowlab")
    except ValueError:
        raised = True
    check(raised, "experiments.refuse_locked_variant(flowlab)")

    tmp = Path(tempfile.mkdtemp(prefix="dse-camp-")) / "e.jsonl"
    log = ExperimentLog(tmp)
    log.append(
        Experiment(
            id="synbase000001",
            phase="P0",
            design="toy",
            clock_ns=1.0,
            variant="camp_toy_base",
            role="base",
            status="done",
            finish_wns_ns=-0.04,
            place_wns_ns=0.01,
            stdcell_um2=100.0,
            stdcell_count=10,
            sha256_6_report="aaa",
        )
    )
    log.append(
        Experiment(
            id="synainj000001",
            phase="P0",
            design="toy",
            clock_ns=1.0,
            variant="camp_toy_ainj",
            role="ainj",
            status="done",
            finish_wns_ns=-0.04,
            place_wns_ns=0.01,
            stdcell_um2=100.0,
            stdcell_count=10,
            sha256_6_report="aaa",
        )
    )
    log.append(
        Experiment(
            id="syndse0000001",
            phase="P0",
            design="toy",
            clock_ns=1.0,
            variant="camp_toy_fast",
            role="dse_fast",
            status="done",
            finish_wns_ns=-0.20,
            place_wns_ns=-0.15,
            stdcell_um2=90.0,
            stdcell_count=8,
            proxy_wns_ns=-0.05,
            sha256_6_report="bbb",
        )
    )
    check(len(log) == 3, f"registry append 3 rows, got {len(log)}")
    reload = ExperimentLog(tmp)
    check(len(reload) == 3 and reload.all()[0].variant == "camp_toy_base", "registry JSONL reloads")
    camp = eval_campaign(reload)
    check(camp["n_done"] == 3, "eval_campaign parses synthetic JSONL")
    check("H6 supported" in camp["H6_oven_deterministic"]["verdict"], f"synthetic H6 match {camp['H6_oven_deterministic']}")
    check(camp["H1_proxy_inversion"]["slots"]["toy@1.000"]["inverted"] is True, "synthetic H1: proxy winner ≠ finish winner")
    check("incomplete" in camp["H2_place_dp_gate"]["verdict"], "synthetic H2 incomplete (n<15)")

    # P6 same-extract rows reuse role=base and have no 6_report; H6 must stay P0-only.
    log.append(
        Experiment(
            id="synp6pdn000001",
            phase="P6",
            design="toy",
            clock_ns=1.0,
            variant="camp_toy_p6_pdn",
            role="base",
            status="done",
            notes="P6 same-extract already on disk; no new 6_report",
        )
    )
    camp_p6 = eval_campaign(log)
    check(
        "H6 supported" in camp_p6["H6_oven_deterministic"]["verdict"],
        f"H6 ignores P6 base rows {camp_p6['H6_oven_deterministic']}",
    )
    check(
        all(p["base_variant"] != "camp_toy_p6_pdn" for p in camp_p6["H6_oven_deterministic"]["pairs"]),
        "H6 pairs are P0 base+ainj only",
    )

    from dse.knob_catalog import RECIPES, config_mk_for, parse_config_defaults, resolve, resolve_many, stages, titles_of
    from dse.recipe_labels import label_for, synth_method_from_exploration
    from eval_policy import evaluate as eval_policy, render_qor_md, spearman

    check(abs((spearman([1.0, 2.0, 3.0], [10.0, 20.0, 30.0]) or 0) - 1.0) < 1e-9, "spearman perfect +1")
    check(abs((spearman([1.0, 2.0, 3.0], [30.0, 20.0, 10.0]) or 0) + 1.0) < 1e-9, "spearman perfect -1")
    pol = eval_policy(reload)
    check("I5" in pol["I5_proxy_correlation"]["verdict"], f"eval_policy I5 {pol['I5_proxy_correlation']}")
    check("incomplete" in pol["I1_physical_knobs"]["verdict"], "eval_policy I1 incomplete without Q1")
    src = wrapper.read_text()
    check("PLACE_DENSITY_LB_ADDON" in src, "wrapper passes PLACE_DENSITY_LB_ADDON")

    from dse.experiments import enrich_power_from_logs
    from dse.fidelity_policy import decide as policy_decide

    stop = policy_decide(design="gcd", place_wns_ns=-0.30, baseline_finish_ns=-0.037)
    check(stop.action == "STOP", f"policy STOPs a clearly late place {stop}")
    go = policy_decide(design="gcd", place_wns_ns=0.012, baseline_finish_ns=-0.037)
    check(go.action == "EVALUATE", f"policy EVALUATEs near-base place {go}")

    q1_rep = root / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/camp_gcd_q1_d25u35/6_report.json"
    if q1_rep.is_file():
        blob = parse_6_report(q1_rep)
        check(blob.get("power_w") is not None and float(blob["power_w"]) > 0, f"6_report has finish power {blob.get('power_w')}")
        check(blob.get("leakage_w") is not None and float(blob["leakage_w"]) > 0, f"6_report has leakage {blob.get('leakage_w')}")
        check(blob.get("psm_vdd_drop_v") is not None, f"6_report has IR VDD {blob.get('psm_vdd_drop_v')}")
    n_enr = enrich_power_from_logs(log)
    check(True, f"enrich_power_from_logs ran ({n_enr} rows touched on synthetic log)")

    # QoR sheet must show the reference-flow numbers, not only Δ.
    for e in log.all():
        if e.variant == "camp_toy_base":
            e.ir_drop_v = 0.006667
            e.grt_wl = 7589.0
            e.power_w = 0.003932
            e.leakage_w = 2.56e-5
            e.fmax_hz = 2.01e9
            e.setup_violation_count = 38
        elif e.variant == "camp_toy_fast":
            e.ir_drop_v = 0.008257
            e.grt_wl = 9000.0
            e.power_w = 0.005527
            e.leakage_w = 2.50e-5
            e.fmax_hz = 1.55e9
            e.setup_violation_count = 46
    qor_md = render_qor_md(eval_policy(log))
    check("Reference flow" in qor_md, "QoR sheet has a Reference flow table")
    check("`camp_toy_base`" in qor_md, "QoR sheet names the reference variant")
    check("IR worst" in qor_md and "GRT WL" in qor_md, "QoR sheet includes IR and GRT WL")
    check("6.67" in qor_md and "7589" in qor_md, f"QoR sheet shows reference IR/WL absolutes")
    check("Side-by-side sheets" in qor_md, "QoR sheet has side-by-side reference columns")
    check("Recipes" in qor_md, "QoR sheet has a human recipe legend")
    check("IR mean" in qor_md and "Density" in qor_md, "QoR sheet has mean IR and density")

    win = label_for(type("E", (), {"variant": "camp_gcd_q1_d25u35", "role": "knob", "extra": {}})())
    check("denser" in win.title.lower() or "buffer" in win.title.lower(), f"win title is readable: {win.title}")
    check("d25u35" not in win.title, "win title is not the coded variant id")
    sm = synth_method_from_exploration()
    check(sm["abc"] == "area" and sm["ABC_SPEED"] == 0, f"explored synth method is ABC area {sm}")
    check("gcd" not in {r["id"] for r in RECIPES}, "knob catalog ids are not design-specific")
    check(set(stages()) >= {"synth", "floorplan", "place", "repair", "cts"}, f"catalog covers stages {stages()}")
    env = resolve("place_denser", {"PLACE_DENSITY_LB_ADDON": 0.20})
    check(abs(float(env["PLACE_DENSITY_LB_ADDON"]) - 0.25) < 1e-9, f"place_denser is +0.05 from default {env}")
    src = wrapper.read_text()
    check("TNS_END_PERCENT" in src and "CORE_ASPECT_RATIO" in src and "CTS_BUF_DISTANCE" in src, "wrapper passes multi-stage knobs")
    spi_def = parse_config_defaults(config_mk_for("spi"))
    check(abs(spi_def["CORE_UTILIZATION"] - 8.0) < 1e-9, f"spi util default {spi_def.get('CORE_UTILIZATION')}")
    check(abs(spi_def["PLACE_DENSITY_LB_ADDON"] - 0.20) < 1e-9, f"spi LB default {spi_def.get('PLACE_DENSITY_LB_ADDON')}")
    both = resolve_many(["place_denser", "repair_half_tns"], spi_def)
    check(abs(float(both["PLACE_DENSITY_LB_ADDON"]) - 0.25) < 1e-9, "combo keeps place_denser offset")
    check(both["TNS_END_PERCENT"] == "50", f"combo sets TNS 50 {both}")
    check("denser" in titles_of(["place_denser"]).lower(), f"titles_of {titles_of(['place_denser'])}")
    tagged = label_for(type("E", (), {"variant": "camp_spi_place_denser", "role": "knob", "extra": {"recipe_ids": ["place_denser"]}})())
    check("denser" in tagged.title.lower(), f"catalog title on extra.recipe_ids: {tagged.title}")
    spi_pd = label_for("camp_spi_place_denser")
    check("denser" in spi_pd.title.lower() and "d25u35" not in spi_pd.title, f"J1 place title {spi_pd.title}")
    check("transfer" in spi_pd.payoff.lower(), f"J1 place payoff is a transfer result: {spi_pd.payoff}")
    spi_rt = label_for("camp_spi_repair_half_tns")
    check("tns" in spi_rt.title.lower() or "repair" in spi_rt.title.lower(), f"J1 repair title {spi_rt.title}")
    check(
        "changes nothing" in spi_rt.payoff.lower()
        or "already met" in spi_rt.payoff.lower()
        or "no-op" in spi_rt.payoff.lower(),
        f"J1 repair payoff is honest: {spi_rt.payoff}",
    )
    spi_ct = label_for("camp_spi_core_tighter")
    check("tighter" in spi_ct.title.lower(), f"J2 core title {spi_ct.title}")
    check("win" not in spi_ct.payoff.lower() or "not enough" in spi_ct.payoff.lower(), f"J2 core payoff honest {spi_ct.payoff}")
    gcd_pad = label_for("camp_gcd_cell_pad_plus")
    check("padding" in gcd_pad.title.lower() or "site" in gcd_pad.title.lower(), f"C1 pad title {gcd_pad.title}")
    check("win" in gcd_pad.payoff.lower() and "ir" in gcd_pad.payoff.lower(), f"C1 pad payoff is a win: {gcd_pad.payoff}")
    gcd_hier = label_for("camp_gcd_synth_hier")
    check("lose" in gcd_hier.payoff.lower(), f"C1 hier payoff is a lose: {gcd_hier.payoff}")
    ibex_setup = label_for("camp_ibex_repair_setup_margin")
    check("win" in ibex_setup.payoff.lower() and "41" in ibex_setup.payoff, f"C1 ibex setup payoff {ibex_setup.payoff}")
    ibex_wide = label_for("camp_ibex_aspect_wide")
    check("lab" in ibex_wide.payoff.lower(), f"C1 ibex wide is lab {ibex_wide.payoff}")
    aes_cts = label_for("camp_aes_cts_closer_bufs")
    check("win" in aes_cts.payoff.lower(), f"C1 aes cts payoff {aes_cts.payoff}")
    aes_sp = label_for("camp_aes_place_sparser")
    check("win" in aes_sp.payoff.lower() and "ir" in aes_sp.payoff.lower(), f"C1 aes sparse payoff {aes_sp.payoff}")
    dn_loose = label_for("camp_dynamic_node_core_looser")
    check("lab" in dn_loose.payoff.lower(), f"C1 dn looser is lab {dn_loose.payoff}")
    dn_hier = label_for("camp_dynamic_node_synth_hier")
    check("stop" in dn_hier.payoff.lower() or "not finished" in dn_hier.payoff.lower(), f"C1 dn hier payoff {dn_hier.payoff}")
    cook_src = (root / "learn/dse/cook.py").read_text()
    cook_cli = (root / "learn/scripts/cook_recipe.py").read_text()
    check((root / "learn/scripts/cook_recipe.py").is_file(), "cook_recipe.py exists")
    check("needs_fresh_synth" in cook_src, "cook reruns Yosys for synth knobs")
    check("synth_hier" in cook_src or "stage" in cook_src, "fresh synth looks at recipe stage")
    check("official_box" in cook_src and "DIE_AREA" in cook_src, "cook pins DIE_AREA from the official DEF")
    check("FLOORPLAN_RECIPES" in cook_src and "refuse" in cook_src, "cook refuses floorplan recipes")
    check("--knobs" in cook_cli, "cook CLI accepts free knobs")
    check("tuner" in cook_cli and "tpe" in cook_cli, "knob cooks stamp extra.tuner=tpe")
    loose = resolve("core_looser", {"CORE_UTILIZATION": 8.0})
    check(abs(float(loose["CORE_UTILIZATION"]) - 5.0) < 1e-9, f"core_looser clamps spi 8-10 to 5, got {loose}")
    tight = resolve("core_tighter", {"CORE_UTILIZATION": 8.0})
    check(abs(float(tight["CORE_UTILIZATION"]) - 18.0) < 1e-9, f"core_tighter spi 8+10=18, got {tight}")
    remaining = {"place_sparser", "cell_pad_plus", "aspect_wide", "core_tighter", "core_looser", "repair_setup_margin", "cts_closer_bufs", "synth_hier"}
    check(remaining <= {r["id"] for r in RECIPES}, f"remaining catalog ids exist {remaining}")

    from dse.win_rule import verdict as prod_verdict
    from dse.recipe_select import (
        CHEAP_FIRST,
        CLOSED_IMPROVE,
        already_tried,
        combo_already_tried,
        floorplan_locked,
        inferred_recipe_ids,
        is_synth_delay_run,
        propose_deepen,
        propose_improve,
        recipes_still_open,
        select_recipes,
    )

    def _E(**kw):
        return type("E", (), kw)()

    base = _E(finish_wns_ns=-0.037, stdcell_um2=940.0, power_w=0.0039, leakage_w=2.56e-5, ir_drop_v=0.00667)
    gcd_win = _E(finish_wns_ns=-0.0384, stdcell_um2=842.0, power_w=0.00343, leakage_w=2.20e-5, ir_drop_v=0.00615)
    check(prod_verdict(gcd_win, base) == "win", f"gcd-like area/power/leak win {prod_verdict(gcd_win, base)}")
    leak_win = _E(finish_wns_ns=-0.037, stdcell_um2=940.0, power_w=0.0039, leakage_w=2.20e-5, ir_drop_v=0.00667)
    check(prod_verdict(leak_win, base) == "win", f"leak −14% is a product win {prod_verdict(leak_win, base)}")
    leak_lose = _E(finish_wns_ns=-0.037, stdcell_um2=842.0, power_w=0.00343, leakage_w=3.00e-5, ir_drop_v=0.00615)
    check(prod_verdict(leak_lose, base) == "lose", f"leak +17% is a product lose {prod_verdict(leak_lose, base)}")
    ir_worse = _E(finish_wns_ns=0.615, stdcell_um2=261.0, power_w=0.00030, ir_drop_v=0.00209)
    spi_base = _E(finish_wns_ns=0.612, stdcell_um2=268.0, power_w=0.00030, ir_drop_v=0.00098)
    check(prod_verdict(ir_worse, spi_base) == "lose", f"IR +100% is a product lose {prod_verdict(ir_worse, spi_base)}")
    slack_win = _E(finish_wns_ns=0.042, stdcell_um2=30700.0, power_w=0.108, ir_drop_v=0.086)
    ibex_base = _E(finish_wns_ns=0.022, stdcell_um2=30735.0, power_w=0.108, ir_drop_v=0.124)
    check(prod_verdict(slack_win, ibex_base) == "win", f"slack+IR win {prod_verdict(slack_win, ibex_base)}")

    spi_state = {"wns_ns": 0.612, "tns_ns": 0.0, "setup_viol": 0, "density": 0.094, "repair_buffer": 22, "ir_worst_v": 0.001, "cells": 238}
    check(select_recipes(spi_state) == [], f"closed sparse state picks nothing {select_recipes(spi_state)}")
    aes_state = {"wns_ns": -0.009, "tns_ns": -0.024, "setup_viol": 5, "density": 0.377, "repair_buffer": 0, "ir_worst_v": 0.081, "cells": 15960}
    aes_pick = select_recipes(aes_state, locked_floorplan=True)
    check("place_denser" in aes_pick, f"late unlocked-place picks place_denser {aes_pick}")
    check("core_tighter" not in aes_pick, f"locked floorplan skips core_tighter {aes_pick}")
    check("if design" not in (root / "learn/dse/recipe_select.py").read_text(), "selector has no design name branch")
    check(floorplan_locked(root / "tools/OpenROAD-flow-scripts/flow/designs/nangate45/aes/config.mk"), "aes config locks floorplan")
    check((root / "learn/scripts/run_recipe_loop.py").is_file(), "run_recipe_loop.py exists")
    check("Product" in qor_md or "product" in qor_md.lower() or "IR" in qor_md, "QoR sheet still renders")

    loop_src = (root / "learn/scripts/run_recipe_loop.py").read_text()
    check("--cover-all" in loop_src, "loop has --cover-all")
    check("--improve" in loop_src, "loop has --improve")
    check("def coordinate" in loop_src, "loop has a coordinator")
    check("propose_deepen" in loop_src, "coordinator can deepen winning axes")
    check("--deepen" in loop_src, "deepen stays an override")
    check("locked = True" in loop_src, "coordinator always pins the product floorplan")
    check('decision": "tune"' in loop_src, "coordinator default can decide tune")
    tpe_plan = (root / "learn/dse/tpe_plan.md").read_text()
    check("Plan only" in tpe_plan, "TPE plan is frozen before cooks")
    check("CORE_UTILIZATION" in tpe_plan and "Never in space" in tpe_plan, "TPE plan keeps util out of the search space")
    check("ask → cook_one → tell" in tpe_plan or "ask → cook_one" in tpe_plan, "TPE plan is serial ask/tell")
    check("tpe_plan.md" in (root / "learn/dse/product.md").read_text(), "product cycle points at the TPE plan")
    check(CHEAP_FIRST[0] == "gcd" and CHEAP_FIRST[-1] == "dynamic_node", f"cheap-first order {CHEAP_FIRST}")
    abc = _E(status="done", role="abc_speed", variant="camp_spi_abcspeed", extra={})
    check(is_synth_delay_run(abc), "abc_speed is a synth_delay run")
    check(already_tried([abc], "synth_delay", {}), "already_tried treats abc_speed as synth_delay")
    dse_fast = _E(status="done", role="dse_fast", variant="camp_gcd_dse_fast", extra={})
    check(already_tried([dse_fast], "synth_delay", {}), "already_tried treats dse_fast as synth_delay")
    pad = _E(status="done", role="knob", variant="camp_spi_cell_pad_plus", extra={"recipe_ids": ["cell_pad_plus"]})
    check(already_tried([pad], "cell_pad_plus", {}), "already_tried sees recipe_ids")
    open_ids = recipes_still_open(
        [abc, pad],
        {"CORE_UTILIZATION": 8.0, "PLACE_DENSITY_LB_ADDON": 0.20},
        locked_floorplan=True,
    )
    check("synth_area" not in open_ids, "cover skips default synth_area")
    check("synth_delay" not in open_ids, "cover skips already-measured synth_delay")
    check("cell_pad_plus" not in open_ids, "cover skips already-measured cell_pad_plus")
    check("core_tighter" not in open_ids, f"cover skips locked floorplan {open_ids}")
    open_unlocked = recipes_still_open(
        [abc, pad],
        {"CORE_UTILIZATION": 8.0, "PLACE_DENSITY_LB_ADDON": 0.20},
        locked_floorplan=False,
    )
    check("aspect_wide" not in open_unlocked and "core_tighter" not in open_unlocked, f"cover never offers floorplan {open_unlocked}")
    check("place_denser" in open_ids, f"cover still wants unmeasured place {open_ids}")
    check(propose_improve(product_wins=2) == [], "improve is silent when the slot already has a win")
    combos = propose_improve(product_wins=0, locked_floorplan=True)
    check(all("aspect_wide" not in c and "core_tighter" not in c for c in combos), f"locked die drops floorplan combos {combos}")
    check(any(c == ["place_denser", "repair_setup_margin"] for c in combos), f"improve proposes denser+setup {combos}")
    closed_imp = propose_improve(product_wins=0, wns_ns=0.612)
    check(closed_imp[:2] == [["place_notiming"], ["hold_margin"]], f"very-closed improve starts with unused knobs {closed_imp}")
    check(["cts_sparser"] in closed_imp and ["repair_skip"] in closed_imp, f"very-closed also tries sparse CTS and skip-repair {closed_imp}")
    check({"hold_margin", "place_notiming", "cts_sparser", "repair_skip"} <= {r["id"] for r in RECIPES}, "improve knobs are in the catalog")
    check(propose_improve(product_wins=0, wns_ns=0.612, already=set(CLOSED_IMPROVE)) == [], "exhausted closed-die knobs propose nothing")
    spi_nt = label_for("camp_spi_place_notiming")
    check("lose" in spi_nt.payoff.lower() and "ir" in spi_nt.payoff.lower(), f"I1 notiming payoff {spi_nt.payoff}")
    spi_sk = label_for("camp_spi_repair_skip")
    check("no-op" in spi_sk.payoff.lower() or "identical" in spi_sk.payoff.lower(), f"I1 skip-repair payoff {spi_sk.payoff}")
    gcd_deep = label_for("camp_gcd_core_looser_cell_pad_plus")
    check("lab" in gcd_deep.payoff.lower(), f"D1 looser+pad is lab {gcd_deep.payoff}")
    check("HOLD_SLACK_MARGIN" in src and "GPL_TIMING_DRIVEN" in src, "wrapper passes hold margin and timing-driven")
    combo_row = _E(
        status="done",
        role="knob",
        variant="camp_aes_place_denser_repair_setup_margin",
        extra={"recipe_ids": ["place_denser", "repair_setup_margin"]},
    )
    check(combo_already_tried([combo_row], ["place_denser", "repair_setup_margin"]), "combo already tried")
    win_ids = inferred_recipe_ids(
        _E(status="done", role="knob", variant="camp_x_aspect_wide", extra={"recipe_ids": ["aspect_wide"]}),
        {},
    )
    check(win_ids == ["aspect_wide"], f"inferred explicit recipe_ids {win_ids}")
    deep = propose_deepen(["aspect_wide", "place_denser", "cell_pad_plus", "core_tighter", "core_looser"])
    check(any(set(c) == {"place_denser", "cell_pad_plus"} for c in deep), f"deepen pairs same-die wins {deep}")
    check(all("aspect_wide" not in c and "core_tighter" not in c and "core_looser" not in c for c in deep), f"deepen never pairs floorplan {deep}")
    locked_deep = propose_deepen(["aspect_wide", "place_denser", "repair_setup_margin"], locked_floorplan=True)
    check(all("aspect_wide" not in c for c in locked_deep), f"deepen drops locked floorplan {locked_deep}")
    check(propose_deepen(["aspect_wide", "place_denser"], already_parts=[["aspect_wide", "place_denser"]]) == [], "deepen skips a combo already cooked")
    check("if design" not in (root / "learn/scripts/run_recipe_loop.py").read_text(), "coordinator has no design name branch")

    from dse.floorplan import FLOORPLAN_RECIPES, official_box, moves_floorplan

    check(FLOORPLAN_RECIPES == {"core_tighter", "core_looser", "aspect_wide"}, f"floorplan recipes {FLOORPLAN_RECIPES}")
    box = official_box("gcd")
    check(box is not None and "DIE_AREA" in box and "CORE_AREA" in box, f"official gcd box {box}")
    wide = _E(
        finish_wns_ns=-0.038,
        stdcell_um2=900.0,
        power_w=0.0035,
        leakage_w=2.2e-5,
        ir_drop_v=0.0026,
        extra={"recipe_ids": ["aspect_wide"], "knobs": {"CORE_ASPECT_RATIO": "2"}},
        variant="camp_gcd_aspect_wide",
        die_um2=1970.0,
    )
    check(prod_verdict(wide, base) == "wrong_die", f"aspect_wide is wrong_die {prod_verdict(wide, base)}")
    util_shift = _E(
        finish_wns_ns=-0.038,
        stdcell_um2=860.0,
        power_w=0.0035,
        leakage_w=2.2e-5,
        ir_drop_v=0.006,
        extra={"core_utilization": 45},
        variant="camp_gcd_q1_d25u45",
        die_um2=1550.0,
    )
    base_die = _E(finish_wns_ns=-0.037, stdcell_um2=940.0, power_w=0.0039, leakage_w=2.56e-5, ir_drop_v=0.00667, extra={"core_utilization": 35}, die_um2=1970.0)
    check(prod_verdict(util_shift, base_die) == "wrong_die", f"util shift is wrong_die {prod_verdict(util_shift, base_die)}")
    same_die = _E(
        finish_wns_ns=-0.0384,
        stdcell_um2=842.0,
        power_w=0.00343,
        leakage_w=2.20e-5,
        ir_drop_v=0.00615,
        extra={"core_utilization": 35, "recipe_ids": ["place_denser"]},
        die_um2=1970.0,
    )
    check(prod_verdict(same_die, base_die) == "win", f"same-die denser still wins {prod_verdict(same_die, base_die)}")
    check(moves_floorplan(wide, base_die), "moves_floorplan sees aspect_wide")
    check(not moves_floorplan(same_die, base_die), "same-die denser does not move floorplan")
    unlocked_pick = select_recipes(aes_state, locked_floorplan=False)
    check("core_tighter" not in unlocked_pick and "aspect_wide" not in unlocked_pick, f"selector never picks floorplan {unlocked_pick}")

    from dse.cook import cook_one as real_cook
    from dse.experiments import ExperimentLog
    from dse.tune_score import evaluate as tpe_eval
    from dse.tune_space import bounds as tpe_bounds
    from dse.tune_space import clamp_params, defaults_for, fingerprint, pin, to_env
    from dse.tune_warm import enqueue_params, preview_tune, warm_params
    import run_recipe_loop

    space_src = (root / "learn/dse/tune_space.py").read_text()
    score_src = (root / "learn/dse/tune_score.py").read_text()
    tpe_src = (root / "learn/scripts/run_tpe.py").read_text()
    check("import optuna" not in space_src and "import optuna" not in score_src, "space/score do not import Optuna")
    check("if design ==" not in tpe_src, "TPE has no design-name branch")
    check("if design ==" not in (root / "learn/dse/tune_warm.py").read_text(), "warm-start has no design-name branch")
    gcd_def = defaults_for("gcd")
    bnds = tpe_bounds(gcd_def)
    check("CORE_UTILIZATION" not in bnds and "CORE_ASPECT_RATIO" not in bnds, f"space has no floorplan keys {bnds.keys()}")
    check("DIE_AREA" not in bnds and "ABC_SPEED" not in bnds, "space does not sample die or ABC")
    pinned = pin("gcd", {"CORE_UTILIZATION": "45", "PLACE_DENSITY_LB_ADDON": "0.30"})
    check("DIE_AREA" in pinned and "CORE_AREA" in pinned, f"pin adds official box {pinned}")
    check("CORE_UTILIZATION" not in pinned and "CORE_ASPECT_RATIO" not in pinned, f"pin strips util {pinned}")
    from dse.floorplan import uses_floorplan_def

    check(uses_floorplan_def("aes") and not uses_floorplan_def("gcd") and not uses_floorplan_def("ibex"), "FLOORPLAN_DEF is read from config, not a design-name branch")
    aes_pin = pin("aes", {"CORE_UTILIZATION": "40", "PLACE_DENSITY_LB_ADDON": "0.30", "DIE_AREA": "0 0 1 1"})
    check("DIE_AREA" not in aes_pin and "CORE_AREA" not in aes_pin, f"aes pin keeps the official DEF, no DIE_AREA {aes_pin}")
    check("CORE_UTILIZATION" not in aes_pin, f"aes pin still strips util {aes_pin}")
    wrap_src = (root / "scripts/run_design_finish.sh").read_text()
    check("FLOORPLAN_DEF=" in wrap_src, "wrapper clears FLOORPLAN_DEF when DIE_AREA is set")
    import record_experiment

    restamp_dir = Path(tempfile.mkdtemp(prefix="dse-restamp-"))
    restamp_jsonl = restamp_dir / "campaign_experiments.jsonl"
    restamp_jsonl.write_text(
        json.dumps(
            {
                "id": "deadbeef0001",
                "phase": "T1",
                "design": "gcd",
                "clock_ns": 0.46,
                "variant": "camp_gcd_tpe_restamptest",
                "role": "knob",
                "status": "failed",
                "notes": "floorplan exclusive",
                "extra": {"tuner": "tpe"},
            }
        )
        + "\n"
    )
    rc1 = record_experiment.main(
        [
            "--phase",
            "T1",
            "--design",
            "gcd",
            "--variant",
            "camp_gcd_tpe_restamptest",
            "--role",
            "knob",
            "--status",
            "stopped_by_policy",
            "--jsonl",
            str(restamp_jsonl),
            "--freeze",
            str(restamp_dir / "freeze.json"),
        ]
    )
    check(rc1 == 0, f"restamp of failed T1 returns 0 {rc1}")
    restamp_rows = [json.loads(l) for l in restamp_jsonl.read_text().splitlines() if l.strip()]
    check(len(restamp_rows) == 1, f"restamp keeps one row {len(restamp_rows)}")
    check(restamp_rows[0]["status"] == "stopped_by_policy", f"failed T1 is replaced {restamp_rows[0]['status']}")
    rc2 = record_experiment.main(
        [
            "--phase",
            "T1",
            "--design",
            "gcd",
            "--variant",
            "camp_gcd_tpe_restamptest",
            "--role",
            "knob",
            "--status",
            "done",
            "--jsonl",
            str(restamp_jsonl),
            "--freeze",
            str(restamp_dir / "freeze2.json"),
        ]
    )
    check(rc2 == 0, f"skip of stopped T1 returns 0 {rc2}")
    restamp_rows2 = [json.loads(l) for l in restamp_jsonl.read_text().splitlines() if l.strip()]
    check(len(restamp_rows2) == 1, f"done restamp does not duplicate {len(restamp_rows2)}")
    check(restamp_rows2[0]["status"] == "stopped_by_policy", "kept row is still stopped_by_policy")
    omitted = to_env(
        {
            "PLACE_DENSITY_LB_ADDON": gcd_def.get("PLACE_DENSITY_LB_ADDON", 0.20),
            "cell_pad": 0,
            "TNS_END_PERCENT": 100,
            "SETUP_SLACK_MARGIN": 0.0,
            "HOLD_SLACK_MARGIN": 0.0,
            "CTS_BUF_DISTANCE": 100.0,
            "GPL_TIMING_DRIVEN": 1,
        },
        gcd_def,
    )
    check("HOLD_SLACK_MARGIN" not in omitted, f"omit HOLD at 0 {omitted}")
    check("SETUP_SLACK_MARGIN" not in omitted, f"omit SETUP at 0 {omitted}")
    check("GPL_TIMING_DRIVEN" not in omitted, f"omit GPL when default 1 {omitted}")
    forced = to_env({"CTS_BUF_DISTANCE": 80.0, "cell_pad": 2, "TNS_END_PERCENT": 0}, gcd_def)
    check(forced.get("CTS_BUF_DISTANCE") == "80.0" or forced.get("CTS_BUF_DISTANCE") == "80", f"CTS 80 is not the omit sentinel {forced}")
    check(forced.get("TNS_END_PERCENT") == "0", f"TNS 0 is explicit {forced}")
    p_a = clamp_params({"cell_pad": 2, "PLACE_DENSITY_LB_ADDON": 0.30}, gcd_def)
    p_b = clamp_params({"cell_pad": 2, "PLACE_DENSITY_LB_ADDON": 0.30}, gcd_def)
    check(fingerprint(p_a, gcd_def) == fingerprint(p_b, gcd_def), "fingerprint is stable")
    check(len(fingerprint(p_a, gcd_def)) == 12, "fingerprint is 12 hex")
    win_e = _E(
        status="done",
        finish_wns_ns=-0.0384,
        stdcell_um2=842.0,
        power_w=0.00343,
        leakage_w=2.20e-5,
        ir_drop_v=0.00615,
        extra={},
        die_um2=1970.0,
    )
    tie_e = _E(
        status="done",
        finish_wns_ns=-0.037,
        stdcell_um2=940.0,
        power_w=0.0039,
        leakage_w=2.56e-5,
        ir_drop_v=0.00667,
        extra={},
        die_um2=1970.0,
    )
    lose_e = _E(
        status="done",
        finish_wns_ns=-0.080,
        stdcell_um2=940.0,
        power_w=0.0039,
        leakage_w=2.56e-5,
        ir_drop_v=0.00667,
        extra={},
        die_um2=1970.0,
    )
    stop_e = _E(
        status="stopped_by_policy",
        finish_wns_ns=None,
        extra={"policy": {"pred_finish_ns": -0.10}},
        ir_drop_v=None,
    )
    base_e = _E(
        status="done",
        role="base",
        finish_wns_ns=-0.037,
        stdcell_um2=940.0,
        power_w=0.0039,
        leakage_w=2.56e-5,
        ir_drop_v=0.00667,
        extra={},
        die_um2=1970.0,
    )
    tw = tpe_eval(win_e, base_e)
    tt = tpe_eval(tie_e, base_e)
    tl = tpe_eval(lose_e, base_e)
    ts = tpe_eval(stop_e, base_e)
    tdie = tpe_eval(wide, base_die)
    check(tw.score < tt.score, f"score(win) < score(tie) {tw.score} {tt.score}")
    check(any(c > 0 for c in tl.constraints), f"lose has a constraint > 0 {tl.constraints}")
    check(any(c > 0 for c in tdie.constraints), f"wrong_die has a constraint > 0 {tdie.constraints}")
    check(ts.constraints[4] == 0.0, f"STOP does not invent IR {ts.constraints}")
    check(ts.constraints[-1] == 1.0, f"STOP is c_done=1 {ts.constraints}")
    check(tw.feasible and not tl.feasible and not tdie.feasible, "win feasible, lose/wrong_die not")
    refused = real_cook("gcd", recipes=["aspect_wide"])
    check(refused.get("refuse"), f"cook refuses floorplan recipes {refused}")
    xor = real_cook("gcd", recipes=["place_denser"], knobs={"PLACE_DENSITY_LB_ADDON": "0.3"})
    check(xor.get("refuse"), f"cook refuses recipes XOR knobs {xor}")
    wrong_row = _E(
        status="done",
        role="knob",
        finish_wns_ns=-0.038,
        extra={"recipe_ids": ["aspect_wide"], "knobs": {"CORE_ASPECT_RATIO": "2"}},
        die_um2=1000.0,
    )
    fresh_row = _E(
        status="done",
        role="knob",
        finish_wns_ns=-0.038,
        extra={"fresh_synth": True, "knobs": {"PLACE_DENSITY_LB_ADDON": "0.30"}},
        die_um2=1970.0,
    )
    check(warm_params(wrong_row, gcd_def, base_die) is None, "warm-start skips wrong_die")
    check(warm_params(fresh_row, gcd_def, base_e) is None, "warm-start skips fresh_synth")
    from dse.knob_catalog import titles_of
    from dse.tune_transfer import infer_walls, mechanism_sig, params_blocked, recipes_blocked, transfer_enqueue
    check("place_sparse_setup" in {r["id"] for r in RECIPES}, "promoted combo is in the catalog")
    check(
        titles_of(["place_sparse_setup"]) == "Sparser placement + setup margin",
        f"promoted title {titles_of(['place_sparse_setup'])}",
    )
    check("if design ==" not in (root / "learn/dse/tune_transfer.py").read_text(), "transfer has no design-name branch")
    def _xfer(**kw):
        extra = kw.pop("extra", {})
        return type(
            "E",
            (),
            {
                "role": kw.pop("role", "knob"),
                "status": kw.pop("status", "done"),
                "finish_wns_ns": kw.get("finish_wns_ns"),
                "stdcell_um2": kw.get("stdcell_um2", 1000.0),
                "power_w": kw.get("power_w", 0.1),
                "leakage_w": kw.get("leakage_w", 1e-4),
                "ir_drop_v": kw.get("ir_drop_v", 0.05),
                "die_um2": kw.get("die_um2", 1000.0),
                "design": kw.get("design", "toy"),
                "variant": kw.get("variant", "camp_toy_x"),
                "extra": extra,
            },
        )()

    b_a = _xfer(design="alpha", role="base", finish_wns_ns=-0.010, stdcell_um2=1000, power_w=0.1, leakage_w=1e-4, ir_drop_v=0.10, die_um2=1000)
    b_b = _xfer(design="beta", role="base", finish_wns_ns=-0.010, stdcell_um2=1000, power_w=0.1, leakage_w=1e-4, ir_drop_v=0.10, die_um2=1000)
    fail_a = _xfer(design="alpha", status="failed", finish_wns_ns=None, extra={"knobs": {"CELL_PAD_IN_SITES_GLOBAL_PLACEMENT": "2"}})
    fail_b = _xfer(design="beta", status="failed", finish_wns_ns=None, extra={"knobs": {"CELL_PAD_IN_SITES_GLOBAL_PLACEMENT": "2"}})
    walls = infer_walls([b_a, b_b, fail_a, fail_b])
    check(any(w.kind == "cell_pad" and w.value == 2 for w in walls), f"pad=2 is a wall after 2 designs fail {walls}")
    check(params_blocked({"cell_pad": 2}, walls) is not None, "pad=2 params are blocked")
    check(params_blocked({"cell_pad": 1}, walls) is None, "pad=1 is not a wall")
    hier_a = _xfer(design="alpha", status="done", finish_wns_ns=-0.020, extra={"recipe_ids": ["synth_hier"]})
    hier_b = _xfer(design="beta", status="done", finish_wns_ns=-0.020, extra={"recipe_ids": ["synth_hier"]})
    walls_h = infer_walls([b_a, b_b, hier_a, hier_b])
    check(recipes_blocked(["synth_hier"], walls_h) is not None, f"synth_hier is a wall after 2 loses {walls_h}")
    check(
        "synth_hier" not in recipes_still_open([], gcd_def, walls=walls_h),
        "cover skips a walled synth_hier",
    )
    win_knobs = {
        "PLACE_DENSITY_LB_ADDON": "0.15",
        "SETUP_SLACK_MARGIN": "0.05",
        "ABC_AREA": "1",
        "ABC_SPEED": "0",
    }
    win_a = _xfer(
        design="alpha",
        finish_wns_ns=0.020,
        ir_drop_v=0.09,
        die_um2=1000.0,
        extra={"knobs": win_knobs},
    )
    win_b = _xfer(
        design="beta",
        finish_wns_ns=0.020,
        ir_drop_v=0.09,
        die_um2=1000.0,
        extra={"knobs": win_knobs},
    )
    gamma_def = {"PLACE_DENSITY_LB_ADDON": 0.20, "TNS_END_PERCENT": 100.0, "CTS_BUF_DISTANCE": 100.0}
    xfer = transfer_enqueue(
        [b_a, b_b, win_a, win_b],
        "gamma",
        gamma_def,
        walls=infer_walls([fail_a, fail_b]),
    )
    check(xfer, f"cross-design enqueue is non-empty {xfer}")
    check(all(params_blocked(p, infer_walls([fail_a, fail_b])) is None for p in xfer), "transfer skips pad=2")
    check(any(mechanism_sig(p, gamma_def) == "sparse+setup" for p in xfer), f"transfer offers sparse+setup { [mechanism_sig(p, gamma_def) for p in xfer] }")
    replay_rows = [b_a, b_b, fail_a, fail_b, win_a, win_b]
    replay_walls = infer_walls([fail_a, fail_b])
    replay_ibex = enqueue_params(
        [],
        gamma_def,
        [],
        [],
        all_rows=replay_rows,
        design="gamma",
        walls=replay_walls,
    )
    check(bool(replay_ibex), f"enqueue_params returns transfer vectors {replay_ibex}")
    check(
        replay_ibex == transfer_enqueue(replay_rows, "gamma", gamma_def, walls=replay_walls),
        f"enqueue_params appends the same transfer vectors {replay_ibex}",
    )
    check(all(int(p.get("cell_pad", 0)) != 2 for p in replay_ibex), f"replay does not enqueue pad=2 {replay_ibex}")
    tpe_combo = _E(
        status="done",
        role="knob",
        variant="camp_aes_tpe_deadbeef",
        extra={"knobs": {"PLACE_DENSITY_LB_ADDON": "0.15", "SETUP_SLACK_MARGIN": "0.05"}},
    )
    check(
        already_tried([tpe_combo], "place_sparse_setup", {"PLACE_DENSITY_LB_ADDON": 0.20}),
        "already_tried sees TPE sparse+setup knobs as the promoted recipe",
    )
    live_walls = infer_walls(ExperimentLog().all())
    check(any(w.kind == "cell_pad" and w.value == 2 for w in live_walls), f"live registry has the pad=2 wall {live_walls}")
    dn_prev = preview_tune("dynamic_node")
    check(
        int(dn_prev.get("queue") or 0) >= 1,
        f"dynamic_node gets a cross-design enqueue after slot-base fix {dn_prev}",
    )
    wall_cook = real_cook(
        "gcd",
        knobs={
            "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT": "2",
            "CELL_PAD_IN_SITES_DETAIL_PLACEMENT": "2",
            "ABC_AREA": "1",
            "ABC_SPEED": "0",
        },
    )
    check(wall_cook.get("refuse") and "wall" in str(wall_cook.get("refuse")), f"cook refuses pad=2 wall {wall_cook}")
    g_prev = preview_tune("gcd")
    s_prev = preview_tune("spi")
    check(g_prev.get("admissible"), f"gcd is tune-admissible {g_prev}")
    check(not s_prev.get("admissible"), f"spi is not tune-admissible {s_prev}")
    coord = run_recipe_loop.coordinate(ExperimentLog(), list(CHEAP_FIRST))
    check(
        coord["decision"] == "cover",
        f"promoted combo is a catalog hole {coord.get('decision')} {coord.get('why')}",
    )
    cover_ids = [j.get("id") for j in (coord.get("jobs") or [])]
    check(
        "place_sparse_setup" in cover_ids,
        f"cover proposes Sparser placement + setup margin {cover_ids[:6]}",
    )
    deep_coord = run_recipe_loop.coordinate(ExperimentLog(), list(CHEAP_FIRST), deepen=True)
    check(
        deep_coord["decision"] == "cover",
        f"cover still outranks --deepen while the promoted combo is open {deep_coord['decision']}",
    )
    check("--deepen" in loop_src, "deepen stays an override")
    try:
        import optuna  # noqa: F401
        from optuna.distributions import CategoricalDistribution, FloatDistribution, IntDistribution
        from optuna.samplers import TPESampler

        def _cf(trial):
            return trial.user_attrs.get("constraints", (1.0,))

        sampler = TPESampler(constraints_func=_cf, n_startup_trials=1, seed=0)
        study = optuna.create_study(direction="minimize", sampler=sampler)
        dists = {
            "PLACE_DENSITY_LB_ADDON": FloatDistribution(0.10, 0.30),
            "cell_pad": IntDistribution(0, 2),
            "TNS_END_PERCENT": IntDistribution(0, 100),
            "SETUP_SLACK_MARGIN": FloatDistribution(0.0, 0.08),
            "HOLD_SLACK_MARGIN": FloatDistribution(0.0, 0.05),
            "CTS_BUF_DISTANCE": FloatDistribution(80.0, 200.0),
            "GPL_TIMING_DRIVEN": CategoricalDistribution([0, 1]),
        }
        lose_params = {
            "PLACE_DENSITY_LB_ADDON": 0.10,
            "cell_pad": 0,
            "TNS_END_PERCENT": 0,
            "SETUP_SLACK_MARGIN": 0.0,
            "HOLD_SLACK_MARGIN": 0.0,
            "CTS_BUF_DISTANCE": 80.0,
            "GPL_TIMING_DRIVEN": 0,
        }
        study.add_trial(
            optuna.trial.create_trial(
                params=lose_params,
                distributions=dists,
                value=1.0,
                user_attrs={"constraints": (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)},
                system_attrs={"constraints": (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)},
            )
        )
        nxt = study.ask(fixed_distributions=dists)
        check(dict(nxt.params) != lose_params, f"TPE second point leaves the lose corner {nxt.params}")
        study.tell(nxt, 0.0)
    except ImportError:
        print("skip optuna fake TPE (not installed)")

    _check_enterprise_docs(check, root)


def _check_enterprise_docs(check, root: Path) -> None:
    """The repo docs map covers product, lab, and course — and stays linked."""
    required = (
        "docs/README.md",
        "docs/prodotto.md",
        "docs/operazioni.md",
        "docs/risultati.md",
        "docs/architettura.md",
        "docs/laboratorio.md",
        "docs/corso.md",
        "docs/script.md",
        "docs/piani.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "scripts/README.md",
        "learn/dse/README.md",
        "learn/dse/product.md",
        "learn/dse/arch_review.md",
        "learn/dse/tpe_plan.md",
        "learn/dse/win_rule.py",
    )
    for rel in required:
        path = root / rel
        check(path.is_file(), f"docs map has {rel}")
        check(path.stat().st_size > 80, f"docs map sized {rel}")
    index = (root / "docs/README.md").read_text()
    for needle in (
        "docs/prodotto.md",
        "architettura.md",
        "laboratorio.md",
        "corso.md",
        "script.md",
        "piani.md",
        "win_rule.py",
    ):
        check(needle in index or needle.replace("docs/", "") in index, f"docs index cites {needle}")
    product = (root / "docs/prodotto.md").read_text()
    check("learn/dse/product.md" in product, "prodotto.md points at frozen product.md")
    check("win_rule.py" in product, "prodotto.md points at win_rule")
    agents = (root / "AGENTS.md").read_text()
    check("Forbidden" in agents or "Refuse" in agents, "AGENTS.md has refuse rules")
    check("test_dse_next.py" in agents, "AGENTS.md names the fast suite")
    dse = (root / "learn/dse/README.md").read_text()
    check("win_rule.py" in dse, "dse README names win_rule")
    check("tune_transfer.py" in dse, "dse README names transfer")
    root_readme = (root / "README.md").read_text()
    check("docs/README.md" in root_readme, "root README points at docs index")
    check("win_rule.py" in root_readme, "root README names win_rule")
    contrib = (root / "CONTRIBUTING.md").read_text()
    check("test_dse_next.py" in contrib, "CONTRIBUTING names the fast suite")
    check("45.298" in contrib, "CONTRIBUTING protects GCD IR gold")
    arch = (root / "docs/architettura.md").read_text()
    check("camp_{design}" in arch or "camp_" in arch, "architettura names camp variants")
    check("if design ==" in (root / "AGENTS.md").read_text(), "AGENTS forbids design-name branches")


if __name__ == "__main__":
    def _check(ok: bool, msg: str) -> None:
        if not ok:
            raise SystemExit(f"FAIL {msg}")
        print(f"ok  {msg}")

    check_next_level(_check, Path(__file__).resolve().parents[2])
    print("ALL test_dse_next PASSED")

