#!/usr/bin/env python3
"""Candidate schema + SolveResult + admit_solve. No AES Krylov, no 73k rewrite."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
import sys

if str(_ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn"))
if str(_ROOT / "learn" / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn" / "scripts"))

from dse.f4_oracle import solve_f4, solver_devices
from dse.fingerprint import knobs_fp
from dse.memory import Candidate, DesignMemory
from dse.metrics import QoR, baseline_delta_of, qor_delta
from dse.resources import admit_solve
from dse.solve_result import (
    ACTIVITY_ABSENT,
    ACTIVITY_PARTIAL,
    ACTIVITY_REAL,
    ACTIVITY_SYNTHETIC,
    activity_status_of,
    from_dynamic_ir_report,
    normalize_solve,
)
from heavy_analysis import AES_F4_N_NODES, AES_F4_N_R


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def _cand(**kw) -> Candidate:
    base = dict(
        design_id="gcd",
        parent_id=None,
        level="pdn",
        knobs={"source": "test"},
        knobs_fp=knobs_fp("pdn", {"source": "test"}),
        rtl_fp="x",
        netlist_fp=None,
        fidelity="F4",
        qor=QoR(),
        cost_s=0.0,
    )
    base.update(kw)
    if "id" not in base:
        base["id"] = DesignMemory.new_id()
    return Candidate(**base)


def main() -> int:
    # --- delta vs parent: missing axes omitted, not zero ---
    parent_q = QoR(dynamic_ir_mv=10.0, area_um2=100.0, fidelity="F4")
    child_q = QoR(dynamic_ir_mv=8.0, fidelity="F4")
    d = qor_delta(child_q, parent_q)
    check(abs(d["dynamic_ir_mv"] - (-2.0)) < 1e-12, f"IR improvement is -2 mV, got {d}")
    check("area_um2" not in d, "unobserved child area is omitted, not 0")
    check(qor_delta(child_q, None) == {}, "no parent → empty delta")

    tmp = Path(tempfile.mkdtemp(prefix="dse-schema-")) / "m.jsonl"
    mem = DesignMemory(tmp)
    p = mem.add(_cand(id="p1", qor=parent_q, artifacts={"raw": 1}, attr={"region": "r01"}, pred={"wns": 0.1}))
    c = mem.add(_cand(id="c1", parent_id=p.id, qor=child_q, knobs={"source": "f4_restamp"}))
    check(c.delta.get("dynamic_ir_mv") == -2.0, f"add() fills delta, got {c.delta}")
    check(p.artifacts.get("raw") == 1 and p.attr.get("region") == "r01" and p.pred.get("wns") == 0.1,
          "artifacts/attr/pred stay distinct")
    mem2 = DesignMemory(tmp)
    check(mem2.get("c1").delta.get("dynamic_ir_mv") == -2.0, "delta survives JSONL reload")
    # old row without delta
    raw = json.dumps({
        "id": "legacy",
        "design_id": "gcd",
        "parent_id": None,
        "level": "logic",
        "knobs": {},
        "knobs_fp": "k",
        "rtl_fp": None,
        "netlist_fp": None,
        "fidelity": "F1",
        "qor": {"area_um2": 1.0, "fidelity": "F1"},
        "cost_s": 0,
        "status": "ok",
    })
    legacy = Candidate.from_dict(json.loads(raw))
    check(legacy.delta == {}, "pre-delta JSONL loads with empty delta")

    # --- baseline-delta vs parent-delta: qor_delta payload, Candidate.delta untouched ---
    from dse.controller import _attach_delta

    check(baseline_delta_of({"delta": {"vs": "old", "area_um2": 1.5}}).get("area_um2") == 1.5,
          "dual-read historical attr.delta")
    check(baseline_delta_of({"delta_vs_baseline": {"area_um2": -2.0}, "delta": {"area_um2": 9.0}}).get("area_um2") == -2.0,
          "prefers delta_vs_baseline over historical delta")
    check(baseline_delta_of({}) == {}, "empty attr has no baseline delta")

    tmpb = Path(tempfile.mkdtemp(prefix="dse-schema-base-")) / "m.jsonl"
    memb = DesignMemory(tmpb)
    base = memb.add(_cand(
        id="libdef",
        level="logic",
        knobs={"name": "liberty_default"},
        knobs_fp=knobs_fp("logic", {"name": "liberty_default"}),
        fidelity="F1",
        qor=QoR(area_um2=100.0, n_cells=10.0, fidelity="F1"),
        parent_id=None,
    ))
    parent = memb.add(_cand(
        id="parent_arch",
        level="architecture",
        fidelity="F1",
        qor=QoR(area_um2=90.0, fidelity="F1"),
        parent_id=base.id,
    ))
    child = memb.add(_cand(
        id="extract1",
        level="architecture",
        parent_id=parent.id,
        fidelity="F1",
        qor=QoR(area_um2=95.0, n_cells=12.0, fidelity="F1"),
        attr={"transform": "lt"},
    ))
    parent_delta_before = dict(child.delta)
    _attach_delta(child, memb)
    vs_base = qor_delta(child.qor, base.qor)
    bd = (child.attr or {}).get("delta_vs_baseline") or {}
    check(bd.get("vs") == base.id, f"baseline vs liberty_default id, got {bd.get('vs')}")
    check(abs(float(bd.get("area_um2")) - vs_base["area_um2"]) < 1e-12, "baseline area uses qor_delta")
    check(abs(float(bd.get("n_cells")) - 2.0) < 1e-12, "baseline n_cells from qor_delta, not area-only")
    check("delta" not in (child.attr or {}), "new rows do not write attr.delta")
    check(child.delta == parent_delta_before, "Candidate.delta (vs parent) is not overwritten")
    check(baseline_delta_of(child.attr).get("area_um2") == bd.get("area_um2"), "helper reads new key")

    # --- activity_status ---
    check(activity_status_of(None) == ACTIVITY_ABSENT, "no t50 is ABSENT")
    check(activity_status_of({"synthetic": 10}) == ACTIVITY_SYNTHETIC, "pure synthetic")
    check(activity_status_of({"sta_arrival": 622, "synthetic": 0}) == ACTIVITY_REAL, "STA t50 is REAL")
    check(activity_status_of({"vcd_name_join": 4}) == ACTIVITY_REAL, "VCD name-join is REAL")
    check(activity_status_of({"sta_arrival": 10, "synthetic": 2}) == ACTIVITY_PARTIAL, "mix is PARTIAL")
    check(activity_status_of({"sta_arrival": 10}, n_saif_idle=3) == ACTIVITY_PARTIAL, "SAIF idle-zero is PARTIAL")

    # --- SolveResult from synthetic A / C ---
    a = normalize_solve({
        "status": "ok",
        "solver": "A_direct_be",
        "solver_kind": "direct",
        "worst_droop_mv": 6.075,
        "static_ir_mv": 3.094,
        "rel_res_max": 6.5e-11,
        "backend": "native",
        "n_r": 5816,
        "n_i": 622,
        "t50_via": {"sta_arrival": 622, "synthetic": 0, "vcd_name_join": 0},
        "gold": False,
        "steps": 74,
    })
    check(a.role == "reference" and a.status == "ok", f"A is reference, got {a.role} {a.status}")
    check(abs((a.droop_mv or 0) - 6.075) < 1e-9, f"A droop, got {a.droop_mv}")
    check(a.activity_status == ACTIVITY_REAL, f"GCD STA 622/622 is REAL, got {a.activity_status}")
    check(a.gold is False, "candidate solve is not gold")
    c_sol = normalize_solve(
        {
            "ok": True,
            "solver": "C_rational_krylov_rlc",
            "worst_droop_mv": 6.092,
            "abs_err_vs_A_mv": 0.017,
            "rel_res_max": 1.7e-4,
            "m": 96,
            "backend": "native",
        },
        reference_droop_mv=6.075,
    )
    check(c_sol.role == "accelerator" and c_sol.solver_kind == "krylov", f"C role/kind {c_sol.role} {c_sol.solver_kind}")
    check(abs((c_sol.abs_err_vs_reference_mv or 0) - 0.017) < 1e-9, f"|A-C|, got {c_sol.abs_err_vs_reference_mv}")
    check(c_sol.relative_error is not None and c_sol.relative_error > 0, "relative error vs A")

    # live GCD report if present — normalize only, do not re-solve
    live = _ROOT / "learn" / "sim" / "reports" / "dynamic_ir_flowlab_krylov.json"
    if live.is_file():
        rows = from_dynamic_ir_report(json.loads(live.read_text()))
        kinds = {r.solver_kind: r for r in rows}
        check("direct" in kinds and "krylov" in kinds, f"live report yields A and C, got {list(kinds)}")
        check(abs((kinds["direct"].droop_mv or 0) - 6.075) < 0.01, f"live A ~6.075, got {kinds['direct'].droop_mv}")
        err = kinds["krylov"].abs_err_vs_reference_mv
        check(err is not None and abs(err - 0.017) < 0.005, f"live |A-C|~0.017, got {err}")
        check(kinds["direct"].n_r == 5816, f"live n_r 5816, got {kinds['direct'].n_r}")

    # --- admit_solve: GCD ok, AES Krylov refused, no fake GPU ---
    os.environ.pop("ALLOW_HEAVY_ANALYSIS", None)
    os.environ.pop("ALLOW_OOM_ANALYSIS", None)
    os.environ["PDN_FAKE_RAM_BYTES"] = str(15 * (1 << 30))
    gcd = admit_solve(5816, n_nodes=4453, solver="direct")
    check(gcd["admitted"] is True and gcd["solver"] == "direct", f"GCD DirectLU admitted, got {gcd}")
    gcd_k = admit_solve(5816, n_nodes=4453, solver="krylov")
    check(gcd_k["admitted"] is True, f"GCD-sized Krylov admitted (n_r<20k), got {gcd_k}")
    aes_k = admit_solve(AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver="krylov")
    check(aes_k["admitted"] is False, f"AES Krylov refused on 15 GiB, got {aes_k}")
    check("estimated RSS" in str(aes_k.get("reason") or "") or "REFUSED" in str(aes_k.get("reason") or ""),
          f"AES Krylov reason names RSS/refuse, got {aes_k.get('reason')}")
    no_n = admit_solve(n_r=None, solver="krylov")
    check(no_n["admitted"] is False, "Krylov without n_r is refused")

    from dse.controller import admit_paid_f4
    from dse.f4_oracle import n_r_from_spice
    from dse.solve_result import residual_vs_reference_mv, stamp_f4_candidate

    logs: list[dict] = []

    def _step(kind: str, **kw):
        logs.append({"kind": kind, **kw})

    tmpa = Path(tempfile.mkdtemp(prefix="dse-admit-")) / "m.jsonl"
    mema = DesignMemory(tmpa)
    g_ok = admit_paid_f4(mema, solver="direct", n_r=5816, n_nodes=4453, step=_step)
    check(g_ok["admitted"] is True, f"controller admits GCD DirectLU, got {g_ok}")
    check(any(x.get("kind") == "admit" and x.get("pay") for x in logs), "admit step logs pay=True")
    logs.clear()
    g_ref = admit_paid_f4(mema, solver="krylov", n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, step=_step)
    check(g_ref["admitted"] is False, f"controller refuses AES Krylov, got {g_ref}")
    check(any("REFUSED" in str(x.get("why") or "") for x in logs), f"admit why names REFUSED, got {logs}")

    err = residual_vs_reference_mv(
        {"solve": {"abs_err_vs_reference_mv": 0.017}},
        fallback_child_mv=6.092,
        fallback_ref_mv=6.075,
    )
    check(abs((err or 0) - 0.017) < 1e-12, f"solver-compare uses abs_err with sign, got {err}")
    err_old = residual_vs_reference_mv({}, fallback_child_mv=8.0, fallback_ref_mv=10.0)
    check(abs((err_old or 0) - (-2.0)) < 1e-12, "historical residual falls back to signed QoR")
    fc = _cand(artifacts={"solve": {"activity_status": "REAL", "role": "reference"}}, attr={})
    stamp_f4_candidate(fc)
    check(fc.attr.get("activity_status") == "REAL", f"activity_status propagated to attr, got {fc.attr}")
    gcd_sp = _ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/pdn/pg_vdd_bumps.sp"
    if gcd_sp.is_file():
        nr = n_r_from_spice(gcd_sp)
        check(nr is not None and 5000 < nr < 7000, f"GCD finish spice n_r ~5816, got {nr}")

    from dse.stages import STAGE_F2_FAST, STAGE_F3_STA, planned, should_pay_generic

    pay_g, why_g = should_pay_generic(
        n_have=4,
        max_shots=4,
        parents_ok=True,
        exhausted_why="F2-fast budget exhausted",
        budget_why="",
        no_parent_why="no F1 to score",
        ok_why="barycenter HPWL/RUDY on the candidate netlist",
    )
    check(pay_g is False and why_g == "F2-fast budget exhausted", f"generic exhausted, got {why_g}")
    pay_p, why_p = should_pay_generic(
        n_have=0,
        max_shots=4,
        parents_ok=False,
        exhausted_why="F2-fast budget exhausted",
        budget_why="",
        no_parent_why="no F1 to score",
        ok_why="barycenter HPWL/RUDY on the candidate netlist",
    )
    check(pay_p is False and why_p == "no F1 to score", f"generic no-parent, got {why_p}")
    check(planned({"steps": [{"level": "f2_fast"}]}, "f2_fast"), "planned sees f2_fast")
    check(STAGE_F2_FAST.level == "f2_fast" and STAGE_F3_STA.level == "f3_sta", "3a stage names")

    aes_launch = solve_f4(solver="krylov", n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES)
    check(aes_launch.get("status") != "ok" and aes_launch.get("gold") is False,
          f"solve_f4 AES Krylov does not launch, got {aes_launch.get('status')} {aes_launch.get('reason')}")
    check((aes_launch.get("admit") or {}).get("admitted") is False, "solve_f4 stamps admit refused")

    os.environ["ALLOW_HEAVY_ANALYSIS"] = "1"
    aes_a = admit_solve(AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver="direct")
    check(aes_a["admitted"] is True and aes_a["solver"] == "direct",
          f"AES DirectLU admitted when heavy allowed, got {aes_a}")
    os.environ.pop("ALLOW_HEAVY_ANALYSIS", None)
    os.environ.pop("PDN_FAKE_RAM_BYTES", None)

    cuda_gate = admit_solve(n_r=5816, device="cuda") if not solver_devices().get("cuda") else None
    if cuda_gate is not None:
        check(cuda_gate["admitted"] is False and cuda_gate["status"] == "GAP",
              f"cuda admit is GAP, got {cuda_gate}")
        check(cuda_gate["backend_requested"] == "cuda" and cuda_gate["backend_actual"] == "cpu",
              "CUDA GAP keeps requested vs actual")
        gap = solve_f4(device="cuda")
        check(gap.get("status") == "GAP" and gap.get("gold") is False, f"solve_f4 CUDA still GAP, got {gap}")
        check(gap.get("solve", {}).get("backend_requested") == "cuda", f"stamped solve carries requested, got {gap.get('solve')}")
        # GAP CUDA must not look like a DirectLU reference
    check(gap.get("solve", {}).get("role") != "reference" or gap.get("solve", {}).get("droop_mv") is not None,
          "CUDA GAP is not a fake DirectLU reference")

    # --- 73k pin: read-only, do not rewrite ---
    aes_mem = _ROOT / "learn" / "sim" / "dse" / "memory_aes.jsonl"
    if aes_mem.is_file():
        before = hashlib.sha256(aes_mem.read_bytes()).hexdigest()
        am = DesignMemory(aes_mem)
        legacy = [c for c in am.all() if int((c.artifacts or {}).get("n_r") or 0) == 73139]
        check(bool(legacy), "73k-R row still present")
        ir = legacy[-1].qor.static_ir_mv
        check(ir is not None and abs(float(ir) - 6.954) < 0.05, f"73k static still 6.954, got {ir}")
        after = hashlib.sha256(aes_mem.read_bytes()).hexdigest()
        check(before == after, "reading DesignMemory does not rewrite memory_aes.jsonl")

    print("SCHEMA_CONTRACT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
