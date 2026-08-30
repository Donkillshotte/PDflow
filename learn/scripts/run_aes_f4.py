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

from dse.designs import resolve  # noqa: E402
from dse.f4_oracle import solve_f4  # noqa: E402
from dse.fidelity import ensure_mapped_netlist, liberty_path  # noqa: E402
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
    existing = [
        c
        for c in mem.by_level("pdn")
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_candidate_extract"
    ]
    if existing:
        print(f"reuse F4 {existing[-1].id} droop={existing[-1].qor.dynamic_ir_mv}")
        return 0
    cid = DesignMemory.new_id()
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
    print(
        f"extract status={ext.get('status')} n_r={ext.get('n_r')} n_i={ext.get('n_i')} "
        f"sdc={ext.get('sdc')} cost={ext.get('cost_s')} fail={ext.get('reason')}"
    )
    n_r = int(ext.get("n_r") or 0)
    dyn: dict = {}
    if ext.get("status") == "ok" and n_r and n_r <= MAX_R_DIRECT:
        dyn = solve_f4(
            variant="aes",
            spice=ext.get("spice"),
            insts=ext.get("insts"),
            extract_kind="candidate",
            design_id="aes",
            timeout_s=90.0,
        )
        print(
            f"solve status={dyn.get('status')} droop={dyn.get('worst_droop_mv')} "
            f"gold={dyn.get('gold')} cost={dyn.get('cost_s')}"
        )
    elif ext.get("status") == "ok" and n_r > MAX_R_DIRECT:
        dyn = {
            "status": "GAP",
            "reason": f"aes mesh n_r={n_r} exceeds DirectLU bound {MAX_R_DIRECT} — not a fake droop",
            "gold": False,
            "via": "aes-f4-bound",
        }
        print(dyn["reason"])
    art = {**ext, **{k: v for k, v in dyn.items() if k != "cost_s"}}
    droop = dyn.get("worst_droop_mv")
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
            "extract_id": cid,
            "name": "extract_liberty_default",
        },
        knobs_fp=f"aes_extract_{cid}",
        rtl_fp=f1.rtl_fp,
        netlist_fp=f1.netlist_fp,
        fidelity="F4",
        qor=QoR(
            area_um2=f1.qor.area_um2,
            n_cells=f1.qor.n_cells or (f1.artifacts or {}).get("n_cells"),
            dynamic_ir_mv=float(droop) if droop is not None else None,
            fidelity="F4",
            note="aes candidate write_pg_spice — not gold 45.298, not GCD SDC",
        ),
        cost_s=float(ext.get("cost_s") or 0.0) + float(dyn.get("cost_s") or 0.0),
        artifacts=art,
        status="ok" if dyn.get("status") == "ok" else ("ok" if ext.get("status") == "ok" and droop is None else "fail"),
        failure=dyn.get("reason") or ext.get("reason"),
        note=f"aes F4 extract n_r={n_r} droop={droop}",
    )
    if droop is not None:
        c.status = "ok"
        c.failure = None
    elif ext.get("status") == "ok" and n_r > MAX_R_DIRECT:
        c.status = "fail"
        c.failure = dyn.get("reason")
    elif ext.get("status") != "ok":
        c.status = "fail"
        c.failure = ext.get("reason")
    mem.add(c)
    report_path = REPO / "learn" / "sim" / "reports" / "dse_aes.json"
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    report.update(
        {
            "ok": c.status == "ok" and droop is not None,
            "design_id": "aes",
            "top": spec.top,
            "sdc": str(spec.constraint),
            "n_candidates": len(mem),
            "f4_id": c.id,
            "f4_dynamic_ir_mv": c.qor.dynamic_ir_mv,
            "f4_n_r": n_r,
            "f4_sdc": ext.get("sdc"),
            "f4_status": c.status,
            "f4_failure": c.failure,
            "not": [
                "gcd dpath/ctrl",
                "gcd 0.46 ns SDC",
                "gold 45.298 restamp",
                "flattened cell+PDN vector",
            ],
        }
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {report_path} status={c.status}")
    return 0 if ext.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
