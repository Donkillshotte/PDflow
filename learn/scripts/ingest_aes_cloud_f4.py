#!/usr/bin/env python3
"""Record the Cloud Agent AES DirectLU F4 as a *new* PDN candidate.

Does not overwrite the 73k-R / 6.954 mV row. Reads the gitignored extract
under learn/sim/dse/extracts/cloud_timeout and dse_aes.json cloud_agent_f4.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))
sys.path.insert(0, str(REPO / "learn" / "scripts"))

from heavy_analysis import require_heavy  # noqa: E402
from dse.attribute import inspect_f4  # noqa: E402
from dse.memory import Candidate, DesignMemory  # noqa: E402
from dse.metrics import QoR  # noqa: E402


def main() -> int:
    require_heavy("ingest AES Cloud Agent DirectLU F4")
    report = json.loads((REPO / "learn" / "sim" / "reports" / "dse_aes.json").read_text())
    cloud = report.get("cloud_agent_f4") or {}
    if not cloud.get("dynamic_ir_mv"):
        print("no cloud_agent_f4 dynamic_ir_mv")
        return 1
    ext_dir = REPO / "learn" / "sim" / "dse" / "extracts" / "cloud_timeout"
    spice = ext_dir / "pg_vdd_bumps.sp"
    insts = ext_dir / "inst_power_map.json"
    if not spice.is_file() or not insts.is_file():
        print(f"extract missing under {ext_dir}")
        return 1
    mem = DesignMemory(REPO / "learn" / "sim" / "dse" / "memory_aes.jsonl")
    n_r = int(cloud["n_r"])
    if n_r == 73139:
        print("REFUSED: will not ingest onto the 73k-R / 6.954 mV row")
        return 2
    for c in mem.by_level("pdn"):
        if c.status == "ok" and int((c.artifacts or {}).get("n_r") or 0) == n_r and c.qor.dynamic_ir_mv is not None:
            print(f"already have {c.id} n_r={n_r} droop={c.qor.dynamic_ir_mv}")
            return 0
    f1 = None
    for c in reversed(list(mem.by_level("logic"))):
        if c.status == "ok" and (c.knobs or {}).get("name") == "liberty_default":
            f1 = c
            break
    if f1 is None:
        print("no aes F1")
        return 1
    cid = DesignMemory.new_id()
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
            "name": "extract_liberty_default_cloud_direct",
            "solver": "direct",
            "clk_period_ns": 0.82,
            "via": "cloud_agent_directlu",
        },
        knobs_fp=f"aes_extract_cloud_direct_{n_r}",
        rtl_fp=f1.rtl_fp,
        netlist_fp=f1.netlist_fp,
        fidelity="F4",
        qor=QoR(
            area_um2=f1.qor.area_um2,
            n_cells=f1.qor.n_cells,
            static_ir_mv=float(cloud["static_ir_mv"]),
            dynamic_ir_mv=float(cloud["dynamic_ir_mv"]),
            fidelity="F4",
            note="Cloud Agent DirectLU — not 73k-R 6.954, not gold 45.298",
        ),
        cost_s=float(cloud.get("cost_s") or 0.0),
        artifacts={
            "spice": str(spice),
            "insts": str(insts),
            "odb": str(ext_dir / "candidate.odb"),
            "n_r": n_r,
            "n_i": int(cloud.get("n_i") or 0),
            "n_nodes": int(cloud.get("n_nodes") or 0),
            "solver": cloud.get("solver"),
            "sdc": str(report.get("sdc") or ""),
        },
        status="ok",
        note=f"aes F4 direct n_r={n_r} droop={cloud['dynamic_ir_mv']}",
    )
    inspect_f4(c, design_id="aes")
    mem.add(c)
    report["cloud_agent_f4_id"] = c.id
    (REPO / "learn" / "sim" / "reports" / "dse_aes.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"ingested {c.id} droop={c.qor.dynamic_ir_mv} static={c.qor.static_ir_mv} n_r={n_r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
