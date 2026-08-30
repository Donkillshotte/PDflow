#!/usr/bin/env python3
"""Pay aes write_pg_spice, then Solver A only if the mesh is bounded.

Does not restamp gold 45.298, does not borrow the GCD SDC, does not flatten
knobs. Writes into memory_aes.jsonl / dse_aes.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))

from dse.attribute import inspect_f4  # noqa: E402
from dse.designs import resolve  # noqa: E402
from dse.f4_oracle import solve_f4  # noqa: E402
from dse.fidelity import ensure_mapped_netlist, liberty_path  # noqa: E402
from dse.inspect import inspect_and_choose  # noqa: E402
from dse.memory import Candidate, DesignMemory  # noqa: E402
from dse.metrics import QoR  # noqa: E402
from dse.openroad_f2 import extract_pdn  # noqa: E402


MAX_R_DIRECT = 40000


def _f1(mem: DesignMemory):
    for c in reversed(list(mem.by_level("logic"))):
        if c.status == "ok" and (c.knobs or {}).get("name") == "liberty_default":
            return c
    return None


def main() -> int:
    spec = resolve("aes")
    mem_path = REPO / "learn" / "sim" / "dse" / "memory_aes.jsonl"
    mem = DesignMemory(mem_path)
    f1 = _f1(mem)
    if f1 is None:
        print("no aes F1")
        return 1
    f1 = ensure_mapped_netlist(
        f1, rtl=spec.rtl, liberty=liberty_path(), top=spec.top, timeout_s=180
    )
    mapped = (f1.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        print("mapped netlist missing")
        return 1
    existing_ok = [
        c
        for c in mem.by_level("pdn")
        if c.status == "ok"
        and (c.knobs or {}).get("source") == "f4_candidate_extract"
        and c.qor.dynamic_ir_mv is not None
    ]
    if existing_ok:
        print(f"reuse F4 {existing_ok[-1].id} droop={existing_ok[-1].qor.dynamic_ir_mv}")
        return 0
    prior = [
        c
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_candidate_extract"
        and (c.artifacts or {}).get("spice")
        and Path((c.artifacts or {}).get("spice")).is_file()
    ]
    if prior:
        extract_id = str((prior[-1].knobs or {}).get("extract_id") or prior[-1].id)
        ext = dict(prior[-1].artifacts or {})
        print(f"reuse extract {extract_id} n_r={ext.get('n_r')} sdc={ext.get('sdc')}")
        cid = DesignMemory.new_id()
    else:
        cid = DesignMemory.new_id()
        extract_id = cid
        out_dir = REPO / "learn" / "sim" / "dse" / "extracts" / cid
        print(f"extract {cid} top={spec.top} sdc={spec.constraint}")
        ext = extract_pdn(
            Path(mapped),
            out_dir,
            top=spec.top,
            sdc=spec.constraint,
            util=35.0,
            density=0.55,
            timeout_s=240.0,
        )
    n_r = int(ext.get("n_r") or 0)
    spice_ok = bool(ext.get("spice") and Path(str(ext.get("spice"))).is_file() and n_r)
    print(
        f"extract spice_ok={spice_ok} n_r={n_r} n_i={ext.get('n_i')} "
        f"sdc={ext.get('sdc')} cost={ext.get('cost_s')} fail={ext.get('reason')}"
    )
    dyn: dict = {}
    solver = "direct" if n_r and n_r <= MAX_R_DIRECT else "krylov"
    if spice_ok:
        if n_r > MAX_R_DIRECT:
            print(
                f"n_r={n_r} > {MAX_R_DIRECT} — paying Krylov/MOR, not DirectLU, "
                f"period={spec.clk_period_ns} ns dt=40ps"
            )
        dyn = solve_f4(
            variant="aes",
            spice=ext.get("spice"),
            insts=ext.get("insts"),
            extract_kind="candidate",
            design_id="aes",
            solver=solver,
            dt_ps=40.0 if solver == "krylov" else 10.0,
            timeout_s=600.0 if solver == "krylov" else 180.0,
        )
        print(
            f"solve {solver} status={dyn.get('status')} droop={dyn.get('worst_droop_mv')} "
            f"gold={dyn.get('gold')} period_ns={spec.clk_period_ns} cost={dyn.get('cost_s')}"
        )
    art = {**ext, **{k: v for k, v in dyn.items() if k != "cost_s"}}
    droop = dyn.get("worst_droop_mv")
    static_mv = dyn.get("static_ir_mv")
    prior_static = [
        x
        for x in mem.by_level("pdn")
        if x.status == "ok" and x.qor.static_ir_mv is not None
    ]
    if static_mv is None and prior_static:
        static_mv = prior_static[-1].qor.static_ir_mv
    paid = dyn.get("status") == "ok" and droop is not None
    c = None
    if paid or not prior_static:
        c = Candidate(
            id=cid,
            design_id="aes",
            parent_id=f1.id,
            level="pdn",
            knobs={
                "source": "f4_candidate_extract",
                "parent_id": f1.id,
                "parent_name": "liberty_default",
                "util": 35.0,
                "density": 0.55,
                "extract_id": extract_id,
                "name": "extract_liberty_default",
                "solver": solver,
                "clk_period_ns": spec.clk_period_ns,
            },
            knobs_fp=f"aes_extract_{extract_id}_{solver}",
            rtl_fp=f1.rtl_fp,
            netlist_fp=f1.netlist_fp,
            fidelity="F4",
            qor=QoR(
                area_um2=f1.qor.area_um2,
                n_cells=f1.qor.n_cells or (f1.artifacts or {}).get("n_cells"),
                static_ir_mv=float(static_mv) if static_mv is not None else None,
                dynamic_ir_mv=float(droop) if droop is not None else None,
                fidelity="F4",
                note="aes candidate write_pg_spice — not gold 45.298, not GCD SDC",
            ),
            cost_s=float(ext.get("cost_s") or 0.0) + float(dyn.get("cost_s") or 0.0),
            artifacts=art,
            status="ok" if paid or static_mv is not None else "fail",
            failure=None if paid else (dyn.get("reason") or ext.get("reason")),
            note=f"aes F4 {solver} n_r={n_r} period={spec.clk_period_ns} ns droop={droop}",
        )
        if c.status == "ok":
            inspect_f4(c, design_id="aes")
        mem.add(c)
    else:
        c = prior_static[-1]
    chosen = inspect_and_choose(mem, design_id="aes")
    report_path = REPO / "learn" / "sim" / "reports" / "dse_aes.json"
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    report.update(
        {
            "ok": paid or bool(report.get("f4_static_ir_mv")),
            "design_id": "aes",
            "top": spec.top,
            "sdc": str(spec.constraint),
            "n_candidates": len(mem),
            "f4_id": c.id,
            "f4_dynamic_ir_mv": c.qor.dynamic_ir_mv,
            "f4_static_ir_mv": c.qor.static_ir_mv,
            "f4_n_r": n_r,
            "f4_sdc": ext.get("sdc"),
            "f4_solver": solver,
            "f4_clk_period_ns": spec.clk_period_ns,
            "f4_status": c.status,
            "f4_failure": c.failure,
            "inspect": {
                "candidate_id": chosen.get("candidate_id"),
                "region": (chosen.get("attr") or {}).get("region"),
                "modules": (chosen.get("attr") or {}).get("modules"),
                "n_cells": len((chosen.get("attr") or {}).get("cells") or []),
                "next_stage": chosen.get("next_stage"),
                "should_pay": chosen.get("should_pay"),
            },
            "not": [
                "gcd dpath/ctrl",
                "gcd 0.46 ns SDC",
                "gold 45.298 restamp",
                "flattened cell+PDN vector",
            ],
        }
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {report_path} status={c.status} next={chosen.get('next_stage')}")
    return 0 if spice_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
