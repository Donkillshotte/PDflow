"""Phase-3 gate: refine dispatch is an action queue, not leftover leftover leftover leftover.

Replay on golden + live memory. No oracle — evaluators that fire are a failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))

from dse.acquire import next_fidelity  # noqa: E402
from dse.dispatch import run_next_refine  # noqa: E402
from dse.frame import leftover_cells, next_stage, refine_chain  # noqa: E402
from dse.memory import DesignMemory  # noqa: E402
from dse.planner import plan_search  # noqa: E402

FAILS: list[str] = []
CHAMP_ID = "5160afa733c5"
CHAMP_MV = 1.705


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        FAILS.append(msg)


def _boom(*_a, **_k):
    raise AssertionError("dispatch must not evaluate when the refine chain is closed")


def _champ(mem: DesignMemory):
    for c in mem.all():
        if c.id == CHAMP_ID:
            return c
    return None


def main() -> int:
    golden = REPO / "learn" / "sim" / "dse" / "golden" / "memory_flowlab.golden.jsonl"
    live = REPO / "learn" / "sim" / "dse" / "memory_flowlab.jsonl"
    mem_g = DesignMemory(golden)
    check(len(mem_g) == 112, f"golden memory has 112 candidates, got {len(mem_g)}")

    champ = _champ(mem_g)
    check(champ is not None, "golden still holds winning_ir_pdn 5160afa733c5")
    if champ is not None:
        check(
            champ.qor.dynamic_ir_mv is not None and abs(float(champ.qor.dynamic_ir_mv) - CHAMP_MV) < 0.001,
            f"gold champ stays {CHAMP_MV} mV, got {champ.qor.dynamic_ir_mv}",
        )
        check((champ.attr or {}).get("via") == "active_f4_winning_ir_pdn", "champ via stays winning_ir_pdn")

    chain = refine_chain(mem_g)
    check([f.depth for f in chain] == [0, 1, 2], f"golden chain is depth 0..2, got {[f.depth for f in chain]}")
    check(set(chain[0].cells) == {"dpath/b_mux/_44_", "dpath/b_mux/_51_"}, "depth 0 cells unchanged")
    check(set(chain[1].cells) == {"dpath/sub/_192_", "dpath/sub/_196_"}, "depth 1 cells unchanged")
    check(leftover_cells(mem_g, 2) == [], "depth 3 leftover stays empty — no leftover leftover leftover leftover")
    nxt = next_stage(mem_g)
    check(
        nxt is not None and nxt.get("stage") == "catalog" and nxt.get("depth") == 2,
        f"golden next stage is leftover2 unused catalog, got {nxt}",
    )

    planned = plan_search({}, mem_g, f2_cong=None)
    levels = {s["level"] for s in planned["steps"]}
    for lv in (
        "winning_ir_region_cell_leftover",
        "winning_ir_region_cell_leftover2",
        "winning_ir_region_cell_leftover2_extract",
        "winning_ir_region_cell_leftover2_pdn",
        "winning_ir_region_cell_leftover2_catalog",
        "winning_ir_region_cell_leftover3",
        "winning_ir_region_cell_leftover3_catalog",
    ):
        check(lv in levels, f"planner still emits {lv}")

    check(next_fidelity(level="winning_ir_region_cell_leftover3", pred=None, budget_left=20, cost_hint={}) == "F3",
          "depth 3 size-up is F3 with no new acquire case")
    check(next_fidelity(level="winning_ir_region_cell_leftover3_catalog", pred=None, budget_left=20, cost_hint={}) == "F4",
          "depth 3 catalog is F4 with no new acquire case")

    if live.is_file():
        mem_l = DesignMemory(live)
        lchamp = _champ(mem_l)
        check(lchamp is not None and lchamp.qor.dynamic_ir_mv is not None
              and abs(float(lchamp.qor.dynamic_ir_mv) - CHAMP_MV) < 0.001,
              f"live champ stays {CHAMP_ID} {CHAMP_MV} mV")
        lchain = refine_chain(mem_l)
        check([f.depth for f in lchain] == [0, 1, 2], "live chain is still depth 0..2")
        check(leftover_cells(mem_l, 2) == [], "live leftover at depth 2 is empty")
        lnxt = next_stage(mem_l)
        check(lnxt is None, f"live refine chain is closed (catalog exhausted), got {lnxt}")
        paid = run_next_refine(
            mem_l,
            budget_left=90.0,
            plan_levels=levels,
            design_id="gcd",
            variant="flowlab",
            rtl=None,
            liberty=None,
            step=lambda *_a, **_k: None,
            t_end=1e18,
            ensure_mapped_netlist=_boom,
            evaluate_cell_size=_boom,
            evaluate_f4_extract=_boom,
            evaluate_f4_pdn=_boom,
            extract_on_disk=_boom,
            persist_hotspot_join=_boom,
            flowlab_params=_boom,
            gpl_density=_boom,
            winning_host_pdn=_boom,
        )
        check(not paid, "dispatch does not spend when the chain is closed")
        check(len(mem_l) == 113, f"live memory is not restamped, got {len(mem_l)}")

    if FAILS:
        print(f"{len(FAILS)} FAILED")
        return 1
    print("ALL test_dispatch PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
