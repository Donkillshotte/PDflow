#!/usr/bin/env python3
"""Pay a real aes F1 + F2-fast + F3 + budgeted GPL slice.

Separate memory from GCD flowlab. Does not ingest gcd Dynamic IR, does not
restamp gold 45.298 mV, does not invent dpath/ctrl, does not borrow the
GCD 0.46 ns SDC. Writes learn/sim/dse/memory_aes.jsonl and
learn/sim/reports/dse_aes.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))
sys.path.insert(0, str(REPO / "learn" / "scripts"))

from heavy_analysis import require_heavy  # noqa: E402
from dse.designs import resolve  # noqa: E402
from dse.fidelity import (  # noqa: E402
    ensure_mapped_netlist,
    evaluate_f1_abc,
    evaluate_f2_fast,
    evaluate_f2_gpl,
    evaluate_f3_sta,
    evaluate_f4_extract,
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
    require_heavy("AES F1–F3/GPL slice")
    spec = resolve("aes")
    mem_path = REPO / "learn" / "sim" / "dse" / "memory_aes.jsonl"
    mem = DesignMemory(mem_path)
    lib = liberty_path()
    knobs = {"name": "liberty_default", "abc_args": [], "abc_ops": [], "abc_script": "file"}
    f1 = _reuse(mem, "logic", name="liberty_default")
    mapped = (f1.artifacts or {}).get("mapped_v") if f1 else None
    if f1 and mapped and Path(mapped).is_file():
        if f1.qor.n_cells is None:
            f1.qor.n_cells = (f1.artifacts or {}).get("n_cells")
            mem.touch(f1)
        print(f"reuse F1 {f1.id} area={f1.qor.area_um2} cells={f1.qor.n_cells}")
    elif f1:
        print(f"F1 {f1.id} netlist missing — remapping")
        f1 = ensure_mapped_netlist(
            f1, rtl=spec.rtl, liberty=lib, top=spec.top, timeout_s=spec.f1_timeout_s
        )
        mapped = (f1.artifacts or {}).get("mapped_v")
        if not mapped or not Path(mapped).is_file():
            print("remap failed")
            return 1
        if f1.qor.n_cells is None:
            f1.qor.n_cells = (f1.artifacts or {}).get("n_cells")
            mem.touch(f1)
        print(f"remapped F1 {f1.id} cells={f1.qor.n_cells}")
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
    skip_f4 = os.environ.get("AES_SLICE_SKIP_F4") == "1"
    f4 = None
    if skip_f4:
        print("AES_SLICE_SKIP_F4=1 — F4 left to run_aes_f4_cloud.sh")
    else:
        f4 = evaluate_f4_extract(f1, mem, design_id="aes", variant="aes", timeout_s=300.0)
        if f4 is None:
            print("F4 extract skipped")
            return 1
        print(
            f"F4 {f4.id} status={f4.status} droop={f4.qor.dynamic_ir_mv} "
            f"n_r={(f4.artifacts or {}).get('n_r')} sdc={(f4.artifacts or {}).get('sdc')} "
            f"cost={f4.cost_s:.1f}s fail={f4.failure}"
        )
    report = {
        "ok": (
            f1.status == "ok"
            and f2.status == "ok"
            and f3.status == "ok"
            and f2g.status == "ok"
            and (skip_f4 or (f4 is not None and f4.status == "ok"))
        ),
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
    if f4 is not None:
        report.update(
            {
                "f4_id": f4.id,
                "f4_dynamic_ir_mv": f4.qor.dynamic_ir_mv,
                "f4_n_r": (f4.artifacts or {}).get("n_r"),
                "f4_sdc": (f4.artifacts or {}).get("sdc"),
            }
        )
    dest = REPO / "learn" / "sim" / "reports" / "dse_aes.json"
    prior = json.loads(dest.read_text()) if dest.is_file() else {}
    merged = dict(prior)
    merged.update(report)
    dest.write_text(json.dumps(merged, indent=2) + "\n")
    print(f"wrote {dest}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
