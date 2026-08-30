"""Phase-2 gate: generic refine actions ≡ legacy per-layer steer/pay pairs.

A/B on the golden memory (112 candidates) plus a synthetic depth-3 case
proving a deeper layer needs zero new code. Read-only — no oracle runs.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))

from dse.actions import (  # noqa: E402
    should_pay_refine_catalog,
    should_pay_refine_extract,
    should_pay_refine_pdn,
    should_pay_refine_sizeup,
    steer_refine_catalog,
    steer_refine_pdn,
    steer_refine_sizeup,
)
from dse.memory import Candidate, DesignMemory  # noqa: E402
from dse.metrics import QoR  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        FAILS.append(msg)


def same_steer(a: dict | None, b: dict | None, fields: tuple[str, ...]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return all(a.get(f) == b.get(f) for f in fields)


JOIN_FIELDS = ("cells", "extract_id", "host_source", "region", "modules")
PDN_FIELDS = ("spec", "extract_id", "host_source")


def main() -> int:
    golden = REPO / "learn" / "sim" / "dse" / "golden" / "memory_flowlab.golden.jsonl"
    mem = DesignMemory(golden)
    check(len(mem) == 112, f"golden memory has 112 candidates, got {len(mem)}")

    from dse.active import (
        steer_from_winning_ir_region_cell_leftover2_catalog,
        steer_from_winning_ir_region_cell_leftover2_residual,
        steer_from_winning_ir_region_cell_leftover_pdn_hotspot,
        steer_from_winning_ir_region_cell_pdn_hotspot,
        steer_from_winning_ir_region_pdn_hotspot,
    )

    # --- size-up steers, depth 0..2, field-by-field vs legacy ---
    check(
        same_steer(steer_refine_sizeup(mem, 0), steer_from_winning_ir_region_pdn_hotspot(mem), JOIN_FIELDS),
        "A/B depth 0 size-up steer equals legacy region-PDN hotspot (both None: seq-heavy join)",
    )
    g1 = steer_refine_sizeup(mem, 1)
    l1 = steer_from_winning_ir_region_cell_pdn_hotspot(mem)
    check(same_steer(g1, l1, JOIN_FIELDS), f"A/B depth 1 size-up steer equals legacy, got {g1} vs {l1}")
    g2 = steer_refine_sizeup(mem, 2)
    l2 = steer_from_winning_ir_region_cell_leftover_pdn_hotspot(mem)
    check(same_steer(g2, l2, JOIN_FIELDS), f"A/B depth 2 size-up steer equals legacy, got {g2} vs {l2}")
    check(g2 is not None and g2["level"] == "winning_ir_region_cell_leftover2", "depth 2 keeps the legacy level string")
    check(steer_refine_sizeup(mem, 3) is None, "depth 3 size-up refuses: join fully sized (matches live refusal)")

    # --- PDN restamp steers ---
    gp2 = steer_refine_pdn(mem, 2)
    lp2 = steer_from_winning_ir_region_cell_leftover2_residual(mem)
    check(same_steer(gp2, lp2, PDN_FIELDS), f"A/B depth 2 PDN steer equals legacy (both None: decap measured), got {gp2} vs {lp2}")

    # --- catalog steers ---
    gc2 = steer_refine_catalog(mem, 2)
    lc2 = steer_from_winning_ir_region_cell_leftover2_catalog(mem)
    check(same_steer(gc2, lc2, PDN_FIELDS), f"A/B depth 2 catalog steer equals legacy, got {gc2} vs {lc2}")
    check(gc2 is not None and gc2["spec"]["name"] == "pkg_l_100p", "depth 2 catalog proposes unused pkg L on golden")
    check(steer_refine_catalog(mem, 1) is None or steer_refine_catalog(mem, 1)["spec"]["name"] == "pkg_l_100p",
          "depth 1 catalog only ever proposes Dynamic IR points")

    # --- pays on golden: already-spent stages refuse, catalog pays ---
    pay2, why2 = should_pay_refine_sizeup(mem, depth=2, budget_left=80, steer=g2)
    check(not pay2, f"depth 2 size-up refuses once sized on that extract ({why2})")
    paye2, whye2 = should_pay_refine_extract(mem, depth=2, budget_left=80)
    check(not paye2, f"depth 2 extract refuses once measured ({whye2})")
    payp2, whyp2 = should_pay_refine_pdn(mem, depth=2, budget_left=80, steer=gp2)
    check(not payp2, f"depth 2 PDN refuses without a fresh residual ({whyp2})")
    payc2, whyc2 = should_pay_refine_catalog(mem, depth=2, budget_left=80, steer=gc2)
    check(payc2, f"depth 2 catalog is paid on golden — the exact action Phase 0 validated live ({whyc2})")
    fake = dict(gc2)
    fake["spec"] = {"name": "m4_width_96", "m4_width": 0.96, "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 2e-13}
    payw, whyw = should_pay_refine_catalog(mem, depth=2, budget_left=80, steer=fake)
    check(not payw, f"catalog refuses a width point ({whyw})")
    fake2 = dict(gc2)
    fake2["host_source"] = "f4_em_strap_extract"
    payf, whyf = should_pay_refine_catalog(mem, depth=2, budget_left=80, steer=fake2)
    check(not payf, f"catalog refuses a foreign extract ({whyf})")
    payn, whyn = should_pay_refine_catalog(mem, depth=2, budget_left=80, steer=gc2, n_steer=2)
    check(not payn, f"catalog caps at decap + pkg L ({whyn})")

    # --- synthetic depth 3: zero new code ---
    tmp = Path(tempfile.mkdtemp(prefix="dse-frame3-")) / "m.jsonl"
    shutil.copy(golden, tmp)
    mem3 = DesignMemory(tmp)
    mem3.add(
        Candidate(
            id="synth3pdn",
            design_id="gcd",
            parent_id="6d31d58ff9e7",
            level="pdn",
            knobs={
                "source": "f4_solver_a",
                "name": "decap_200f",
                "extract_id": "6d31d58ff9e7",
                "pkg_r": 0.05,
                "pkg_l": 2e-10,
                "c_decap": 2e-13,
                "i_scale": 1.0,
            },
            knobs_fp="synth3pdn",
            rtl_fp="x",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=3.942, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "active_f4_winning_ir_region_cell_leftover2_pdn",
                "region": "r00",
                "combo_frac": 0.8,
                "cells": ["dpath/b_mux/_99_", "dpath/b_reg/_075_"],
            },
        )
    )
    g3 = steer_refine_sizeup(mem3, 3)
    check(g3 is not None and g3["cells"] == ["dpath/b_mux/_99_"], f"depth 3 steer drops sized _075_ and keeps _99_, got {g3}")
    check(g3["level"] == "winning_ir_region_cell_leftover3", "depth 3 level is derived by suffix, no new function")
    check(g3["host_source"] == "f4_winning_ir_region_cell_leftover2_extract", "depth 3 joins on the depth 2 extract")
    pay3, why3 = should_pay_refine_sizeup(mem3, depth=3, budget_left=80, steer=g3)
    host2 = next(c for c in mem3.by_level("cell") if (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover2")
    mapped2 = (host2.artifacts or {}).get("mapped_v")
    if mapped2 and Path(mapped2).is_file():
        check(pay3, f"depth 3 size-up is paid with zero new code ({why3})")
    else:
        check(not pay3 and "netlist missing" in why3, f"depth 3 refuses cleanly when the host netlist is absent ({why3})")
    payb, whyb = should_pay_refine_sizeup(mem3, depth=3, budget_left=1, steer=g3)
    check(not payb, f"depth 3 respects the wall budget ({whyb})")

    if FAILS:
        print(f"{len(FAILS)} FAILED")
        return 1
    print("ALL test_actions PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
