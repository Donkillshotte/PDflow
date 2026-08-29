"""PDN search space — separate from ABC sequences and placer util.

c_decap / pkg L stay on the pdn level. A re-solve names the extract
(`finish` vs a candidate write_pg_spice id). It is not gold and not a new P&R.
"""

from __future__ import annotations

from .memory import DesignMemory

# Baseline (ingest gold) is pkg_l=2e-10, c_decap=50e-15, pkg_r=0.05.
# Catalog points are *deltas* from that teacher.
PDN_CATALOG: list[dict] = [
    {"name": "decap_200f", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15},
    {"name": "pkg_l_100p", "pkg_r": 0.05, "pkg_l": 1e-10, "c_decap": 50e-15},
]

GOLD_KNOBS = {"pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 50e-15}


def _extract_id(knobs: dict) -> str:
    return str(knobs.get("extract_id") or "finish")


def measured_pdn_keys(
    mem: DesignMemory, *, extract_id: str = "finish"
) -> set[tuple[float, float, float]]:
    keys: set[tuple[float, float, float]] = set()
    for c in mem.by_level("pdn"):
        k = c.knobs or {}
        if k.get("source") not in ("f4_solver_a", "ingest_pdn"):
            continue
        if _extract_id(k) != extract_id:
            continue
        if k.get("pkg_l") is None or k.get("c_decap") is None:
            continue
        keys.add((float(k.get("pkg_r") or 0.05), float(k["pkg_l"]), float(k["c_decap"])))
    return keys


def next_pdn_spec(mem: DesignMemory, *, extract_id: str = "finish") -> dict | None:
    have = measured_pdn_keys(mem, extract_id=extract_id)
    for spec in PDN_CATALOG:
        key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
        if key not in have:
            return spec
    return None
