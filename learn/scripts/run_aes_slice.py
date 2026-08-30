#!/usr/bin/env python3
"""Pay a real aes F1 + F2-fast slice. Separate memory from GCD flowlab.

Does not ingest gcd Dynamic IR, does not restamp gold 45.298 mV, does not
invent dpath/ctrl. Writes learn/sim/dse/memory_aes.jsonl and
learn/sim/reports/dse_aes.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))

from dse.designs import resolve  # noqa: E402
from dse.fidelity import evaluate_f1_abc, evaluate_f2_fast, liberty_path  # noqa: E402
from dse.memory import DesignMemory  # noqa: E402


def main() -> int:
    spec = resolve("aes")
    mem_path = REPO / "learn" / "sim" / "dse" / "memory_aes.jsonl"
    mem = DesignMemory(mem_path)
    lib = liberty_path()
    knobs = {"name": "liberty_default", "abc_args": [], "abc_ops": [], "abc_script": "file"}
    already = [
        c
        for c in mem.by_level("logic")
        if c.status == "ok" and (c.knobs or {}).get("name") == "liberty_default"
    ]
    if already:
        f1 = already[-1]
        print(f"reuse F1 {f1.id} area={f1.qor.area_um2} cells={f1.qor.n_cells}")
    else:
        f1 = evaluate_f1_abc(
            rtl=spec.rtl,
            liberty=lib,
            knobs=knobs,
            mem=mem,
            design_id="aes",
            level="logic",
            top=spec.top,
            timeout_s=spec.f1_timeout_s,
        )
        print(
            f"F1 {f1.id} status={f1.status} area={f1.qor.area_um2} "
            f"cells={f1.qor.n_cells} cost={f1.cost_s:.1f}s fail={f1.failure}"
        )
        if f1.status != "ok":
            return 1
    f2 = evaluate_f2_fast(f1, mem, design_id="aes")
    if f2 is None:
        print("F2-fast skipped")
        return 1
    print(
        f"F2 {f2.id} cong={f2.qor.congestion} hpwl={(f2.artifacts or {}).get('hpwl')} "
        f"cost={f2.cost_s:.2f}s"
    )
    report = {
        "ok": f1.status == "ok" and f2.status == "ok",
        "kind": "dse",
        "engine": "aes-slice",
        "design_id": "aes",
        "top": spec.top,
        "n_candidates": len(mem),
        "f1_id": f1.id,
        "f1_area_um2": f1.qor.area_um2,
        "f1_n_cells": f1.qor.n_cells,
        "f2_id": f2.id,
        "f2_congestion": f2.qor.congestion,
        "not": [
            "gcd dpath/ctrl",
            "gold 45.298 restamp",
            "flattened cell+PDN vector",
        ],
        "memory": str(mem_path),
    }
    dest = REPO / "learn" / "sim" / "reports" / "dse_aes.json"
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {dest}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
