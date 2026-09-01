"""Next-level DSE: feasibility, F6 ingest, funnel, scheduler, provenance."""

from __future__ import annotations

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
    check("Ricette" in qor_md, "QoR sheet has a human recipe legend")
    check("IR mean" in qor_md and "Density" in qor_md, "QoR sheet has mean IR and density")

    win = label_for(type("E", (), {"variant": "camp_gcd_q1_d25u35", "role": "knob", "extra": {}})())
    check("denso" in win.title.lower() or "buffer" in win.title.lower(), f"win title is readable: {win.title}")
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
    check("Place" in titles_of(["place_denser"]), f"titles_of {titles_of(['place_denser'])}")
    tagged = label_for(type("E", (), {"variant": "camp_spi_place_denser", "role": "knob", "extra": {"recipe_ids": ["place_denser"]}})())
    check("denso" in tagged.title.lower(), f"catalog title on extra.recipe_ids: {tagged.title}")
    spi_pd = label_for("camp_spi_place_denser")
    check("denso" in spi_pd.title.lower() and "d25u35" not in spi_pd.title, f"J1 place title {spi_pd.title}")
    check("transfer" in spi_pd.payoff.lower(), f"J1 place payoff is a transfer result: {spi_pd.payoff}")
    spi_rt = label_for("camp_spi_repair_half_tns")
    check("tns" in spi_rt.title.lower() or "repair" in spi_rt.title.lower(), f"J1 repair title {spi_rt.title}")
    check("non cambia" in spi_rt.payoff.lower() or "orario" in spi_rt.payoff.lower() or "no-op" in spi_rt.payoff.lower(), f"J1 repair payoff is honest: {spi_rt.payoff}")
    spi_ct = label_for("camp_spi_core_tighter")
    check("stretto" in spi_ct.title.lower(), f"J2 core title {spi_ct.title}")
    check("win" not in spi_ct.payoff.lower() or "non basta" in spi_ct.payoff.lower(), f"J2 core payoff honest {spi_ct.payoff}")
    cook_src = (root / "learn/scripts/cook_recipe.py").read_text()
    check((root / "learn/scripts/cook_recipe.py").is_file(), "cook_recipe.py exists")
    check("_needs_fresh_synth" in cook_src, "cook_recipe reruns Yosys for synth knobs")
    check("synth_hier" in cook_src or "stage" in cook_src, "fresh synth looks at recipe stage")
    loose = resolve("core_looser", {"CORE_UTILIZATION": 8.0})
    check(abs(float(loose["CORE_UTILIZATION"]) - 5.0) < 1e-9, f"core_looser clamps spi 8-10 to 5, got {loose}")
    tight = resolve("core_tighter", {"CORE_UTILIZATION": 8.0})
    check(abs(float(tight["CORE_UTILIZATION"]) - 18.0) < 1e-9, f"core_tighter spi 8+10=18, got {tight}")
    remaining = {"place_sparser", "cell_pad_plus", "aspect_wide", "core_tighter", "core_looser", "repair_setup_margin", "cts_closer_bufs", "synth_hier"}
    check(remaining <= {r["id"] for r in RECIPES}, f"remaining catalog ids exist {remaining}")

    from dse.win_rule import verdict as prod_verdict
    from dse.recipe_select import floorplan_locked, select_recipes

    def _E(**kw):
        return type("E", (), kw)()

    base = _E(finish_wns_ns=-0.037, stdcell_um2=940.0, power_w=0.0039, ir_drop_v=0.00667)
    gcd_win = _E(finish_wns_ns=-0.0384, stdcell_um2=842.0, power_w=0.00343, ir_drop_v=0.00615)
    check(prod_verdict(gcd_win, base) == "win", f"gcd-like area/power win {prod_verdict(gcd_win, base)}")
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
    check("Prodotto" in qor_md or "product" in qor_md.lower() or "IR" in qor_md, "QoR sheet still renders")


if __name__ == "__main__":
    def _check(ok: bool, msg: str) -> None:
        if not ok:
            raise SystemExit(f"FAIL {msg}")
        print(f"ok  {msg}")

    check_next_level(_check, Path(__file__).resolve().parents[2])
    print("ALL test_dse_next PASSED")

