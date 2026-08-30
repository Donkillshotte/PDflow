#!/usr/bin/env python3
"""Pay a real aes F1 + F2-fast + F3 + budgeted GPL slice.

Separate memory from GCD flowlab. Does not ingest gcd Dynamic IR, does not
restamp gold 45.298 mV, does not invent dpath/ctrl, does not borrow the
GCD 0.46 ns SDC. Writes learn/sim/dse/memory_aes.jsonl and
learn/sim/reports/dse_aes.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))

from dse.designs import resolve  # noqa: E402
from dse.fidelity import (  # noqa: E402
    evaluate_f1_abc,
    evaluate_f2_fast,
    evaluate_f2_gpl,
    evaluate_f3_sta,
    liberty_path,
)
from dse.memory import DesignMemory  # noqa: E402


def _reuse(mem: DesignMemory, level: str, **want) -> object | None:
    for c in reversed(list(mem.by_level(level))):
        if c.status != "ok":
            continue
        kn = c.knobs or {}
        if all(kn.get(k) == v for k, v in want.items()):
            return c
    return None


def main() -> int:
    spec = resolve("aes")
    mem_path = REPO / "learn" / "sim" / "dse" / "memory_aes.jsonl"
    mem = DesignMemory(mem_path)
    lib = liberty_path()
    knobs = {"name": "liberty_default", "abc_args": [], "abc_ops": [], "abc_script": "file"}
    f1 = _reuse(mem, "logic", name="liberty_default")
    if f1:
        if f1.qor.n_cells is None:
            f1.qor.n_cells = (f1.artifacts or {}).get("n_cells")
            mem.touch(f1)
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
        f"F2-fast {f2.id} cong={f2.qor.congestion} hpwl={(f2.artifacts or {}).get('hpwl')} "
        f"cost={f2.cost_s:.2f}s"
    )
    f3 = evaluate_f3_sta(f1, mem, design_id="aes")
    if f3 is None:
        print("F3 skipped")
        return 1
    print(
        f"F3 {f3.id} status={f3.status} wns={(f3.artifacts or {}).get('wns_ns')} "
        f"P={f3.qor.power_w} sdc={(f3.artifacts or {}).get('sdc')} cost={f3.cost_s:.1f}s"
    )
    if f3.status != "ok":
        return 1
    f2g = evaluate_f2_gpl(f1, mem, design_id="aes", timeout_s=180.0)
    if f2g is None:
        print("F2-GPL skipped")
        return 1
    print(
        f"F2-GPL {f2g.id} status={f2g.status} overflow={f2g.qor.congestion} "
        f"hpwl_um={(f2g.artifacts or {}).get('hpwl_um')} cost={f2g.cost_s:.1f}s "
        f"fail={f2g.failure}"
    )
    report = {
        "ok": f1.status == "ok" and f2.status == "ok" and f3.status == "ok" and f2g.status == "ok",
        "kind": "dse",
        "engine": "aes-slice",
        "design_id": "aes",
        "top": spec.top,
        "sdc": str(spec.constraint),
        "clk_period_ns": 0.82,
        "n_candidates": len(mem),
        "f1_id": f1.id,
        "f1_area_um2": f1.qor.area_um2,
        "f1_n_cells": f1.qor.n_cells,
        "f2_id": f2.id,
        "f2_congestion": f2.qor.congestion,
        "f3_id": f3.id,
        "f3_wns_ns": (f3.artifacts or {}).get("wns_ns"),
        "f3_power_w": f3.qor.power_w,
        "f3_sdc": (f3.artifacts or {}).get("sdc") or str(spec.constraint),
        "f2_gpl_id": f2g.id,
        "f2_gpl_overflow": f2g.qor.congestion,
        "f2_gpl_hpwl_um": (f2g.artifacts or {}).get("hpwl_um"),
        "not": [
            "gcd dpath/ctrl",
            "gcd 0.46 ns SDC",
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
