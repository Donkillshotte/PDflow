"""Phase-1 gate: frame adapter reproduces the legacy refine chain exactly.

Runs against the committed golden memory (112 candidates, pre catalog shot)
and the live memory when present. No oracle, no network — read-only.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))

from dse.frame import (  # noqa: E402
    base_sized_cells,
    leftover_cells,
    next_stage,
    refine_cell_source,
    refine_chain,
    refine_extract_source,
    refine_pdn_via,
    sized_through,
)
from dse.memory import DesignMemory  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        FAILS.append(msg)


def legacy_sized_union(mem: DesignMemory) -> set[str]:
    """The exact union the legacy pay gates subtract (host functions)."""
    from dse.active import (
        ir_cell_champ_cone_host,
        ir_cell_champ_host,
        ir_cell_host,
        winning_ir_region_cell_host,
        winning_ir_region_cell_leftover_host,
        winning_ir_region_cell_leftover2_host,
    )

    out: set[str] = set()
    for host in (
        ir_cell_host(mem),
        ir_cell_champ_host(mem),
        ir_cell_champ_cone_host(mem),
        winning_ir_region_cell_host(mem),
        winning_ir_region_cell_leftover_host(mem),
        winning_ir_region_cell_leftover2_host(mem),
    ):
        if host is not None:
            out.update(str(x) for x in (host.knobs or {}).get("cells") or [])
    return out


def main() -> int:
    check(refine_cell_source(0) == "cell_size_ir_winning_region", "depth 0 maps to the legacy region source")
    check(refine_cell_source(1) == "cell_size_ir_winning_region_leftover", "depth 1 maps to the legacy leftover source")
    check(refine_cell_source(2) == "cell_size_ir_winning_region_leftover2", "depth 2 maps to the legacy leftover2 source")
    check(refine_cell_source(3) == "cell_size_ir_winning_region_leftover3", "depth 3 needs no new code, only a suffix")
    check(refine_extract_source(2) == "f4_winning_ir_region_cell_leftover2_extract", "depth 2 extract source matches legacy")
    check(refine_pdn_via(2) == "active_f4_winning_ir_region_cell_leftover2_pdn", "depth 2 PDN via matches legacy")

    golden = REPO / "learn" / "sim" / "dse" / "golden" / "memory_flowlab.golden.jsonl"
    check(golden.is_file(), "golden memory fixture exists")
    mem = DesignMemory(golden)
    check(len(mem) == 112, f"golden memory has 112 candidates, got {len(mem)}")

    chain = refine_chain(mem)
    check([f.depth for f in chain] == [0, 1, 2], f"golden chain is depth 0..2, got {[f.depth for f in chain]}")

    d0, d1, d2 = chain
    check(set(d0.cells) == {"dpath/b_mux/_44_", "dpath/b_mux/_51_"}, f"depth 0 cells match legacy, got {d0.cells}")
    check(set(d1.cells) == {"dpath/sub/_192_", "dpath/sub/_196_"}, f"depth 1 cells match legacy, got {d1.cells}")
    check(len(d2.cells) == 5 and "dpath/b_reg/_075_" in d2.cells, f"depth 2 has the 5 sized cells, got {d2.cells}")
    check(d0.extract_id == "94a480758b54", f"depth 0 extract is the region-cell mesh, got {d0.extract_id}")
    check(d1.extract_id == "8f25a2a58f3f", f"depth 1 extract matches legacy, got {d1.extract_id}")
    check(d2.extract_id == "6d31d58ff9e7", f"depth 2 extract matches legacy, got {d2.extract_id}")
    check(d0.pdn is not None and d0.pdn.id == "c2c476288772", "depth 0 PDN restamp matches legacy")
    check(d1.pdn is not None and d1.pdn.id == "0513e1e43f03", "depth 1 PDN restamp matches legacy")
    check(d2.pdn is not None and d2.pdn.id == "80f73e635c78", "depth 2 PDN restamp matches legacy")
    check(d2.catalog == [], "golden memory has no depth 2 catalog shot yet")

    base = base_sized_cells(mem)
    check("ctrl/_14_" in base and "dpath/b_reg/_078_" in base, "base lineage includes IR-cell ctrl and cone dpath")
    check(sized_through(mem, 2) == legacy_sized_union(mem), "A/B: sized_through(2) equals the legacy host-function union")
    check(len(sized_through(mem, 2)) == 18, f"sized union is 18 cells (ctrl overlap ice∩icc = 4), got {len(sized_through(mem, 2))}")
    check(sized_through(mem, 0) < sized_through(mem, 2), "sized set grows with depth")

    check(leftover_cells(mem, 2) == [], "A/B: depth 3 leftover is empty (matches the live refusal)")
    lo1 = leftover_cells(mem, 1)
    check(set(lo1) <= set(d2.cells), f"depth 2 sizing came from the depth 1 join, got {lo1}")

    nxt = next_stage(mem)
    check(
        nxt is not None and nxt.get("stage") == "catalog" and nxt.get("depth") == 2,
        f"golden next stage is the depth 2 catalog (the action Phase 0 validated live), got {nxt}",
    )

    live = REPO / "learn" / "sim" / "dse" / "memory_flowlab.jsonl"
    if live.is_file():
        lmem = DesignMemory(live)
        lchain = refine_chain(lmem)
        check([f.depth for f in lchain] == [0, 1, 2], "live chain is still depth 0..2")
        check(len(lchain[-1].catalog) >= 1, "live depth 2 has the validated catalog shot")
        check(sized_through(lmem, 2) == legacy_sized_union(lmem), "A/B on live memory: sized union matches legacy")
        lnext = next_stage(lmem)
        check(
            lnext is None or lnext.get("stage") != "sizeup" or lnext.get("cells"),
            f"live next stage never proposes an empty size-up, got {lnext}",
        )

    if FAILS:
        print(f"{len(FAILS)} FAILED")
        return 1
    print("ALL test_frame PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
