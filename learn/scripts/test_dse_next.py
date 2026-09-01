"""Next-level DSE: feasibility, F6 ingest, funnel, scheduler, provenance."""

from __future__ import annotations

import tempfile
from pathlib import Path

from dse.arch_plugins import classify, plugin
from dse.campaign import f6_hv_points, gated_hv_f6, run_campaign, suggest_ref
from dse.contracts import ConstraintContract, GeometryContract, SemanticContract, stamp_evidence
from dse.exporter import mark_export
from dse.f6_finish import ingest_finish, parse_6_report, qor_from_finish, refuse_locked_variant
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


if __name__ == "__main__":
    def _check(ok: bool, msg: str) -> None:
        if not ok:
            raise SystemExit(f"FAIL {msg}")
        print(f"ok  {msg}")

    check_next_level(_check, Path(__file__).resolve().parents[2])
    print("ALL test_dse_next PASSED")

