"""Physical / synthesis search *spaces* — separate from ABC sequences.

AutoDMP (ISPD'23) tunes placer parameters with MOTPE on WL / density /
congestion proxies, then promotes Pareto points to an expensive EDA flow.
We keep that *shape* without launching DREAMPlace or `make finish`:

  physical F0  — analytical RUDY-class congestion proxy
  physical F2  — ingest + GPL + IR-bin density cap (no make finish)
  physical F5  — F5-lite DRT/OpenRCX (controller refuses to launch finish)

Synthesis knobs (ABC_AREA) stay on the synthesis level.
"""

from __future__ import annotations

from .fingerprint import knobs_fp
from .memory import Candidate, DesignMemory
from .metrics import QoR


# Discrete AutoDMP-shaped catalog. Not mixed with rewrite/resub.
PHYSICAL_CATALOG: list[dict] = [
    {"name": "util30_den010", "coreUtilization": 30, "placeDensityAddon": 0.10},
    {"name": "util35_den020", "coreUtilization": 35, "placeDensityAddon": 0.20},
    {"name": "util40_den025", "coreUtilization": 40, "placeDensityAddon": 0.25},
    {"name": "util45_den030", "coreUtilization": 45, "placeDensityAddon": 0.30},
]

SYNTH_CATALOG: list[dict] = [
    {"name": "abc_area", "abcArea": 1},
    {"name": "abc_delay", "abcArea": 0},
]


def rudy_congestion(util_pct: float, density_addon: float) -> float:
    """Unitless RUDY-class demand proxy. Lower is better. Not GRT overflow."""
    util = max(float(util_pct), 1.0) / 100.0
    return float(util * (0.70 + max(float(density_addon), 0.0)))


def gpl_density(util_pct: float, density_addon: float) -> float:
    """ORFS-class place density: util/100 + addon. Not mixed with ABC ops."""
    d = float(util_pct) / 100.0 + max(float(density_addon), 0.0)
    return min(0.99, max(0.20, d))


def catalog_spec_key(spec: dict) -> tuple[float, float]:
    return (float(spec["coreUtilization"]), round(gpl_density(spec["coreUtilization"], spec["placeDensityAddon"]), 3))


def measured_gpl_keys(mem: DesignMemory) -> set[tuple[float, float]]:
    keys: set[tuple[float, float]] = set()
    for c in mem.by_level("physical"):
        if (c.knobs or {}).get("source") != "f2_openroad_gpl":
            continue
        u = (c.knobs or {}).get("util")
        d = (c.knobs or {}).get("density")
        if u is None or d is None:
            continue
        keys.add((float(u), round(float(d), 3)))
    return keys


def next_catalog_spec(mem: DesignMemory) -> dict | None:
    """Next AutoDMP-shaped (util, density) not yet measured with GPL."""
    have = measured_gpl_keys(mem)
    for spec in PHYSICAL_CATALOG:
        if catalog_spec_key(spec) not in have:
            return spec
    return None


def propose_physical_f0(mem: DesignMemory, design_id: str = "gcd") -> list[Candidate]:
    seen = mem.seen_knobs("physical")
    added: list[Candidate] = []
    for spec in PHYSICAL_CATALOG:
        knobs = {
            "name": spec["name"],
            "coreUtilization": spec["coreUtilization"],
            "placeDensityAddon": spec["placeDensityAddon"],
            "source": "autodmp_catalog_f0",
        }
        fp = knobs_fp("physical", knobs)
        if fp in seen:
            continue
        cong = rudy_congestion(spec["coreUtilization"], spec["placeDensityAddon"])
        c = Candidate(
            id=DesignMemory.new_id(),
            design_id=design_id,
            parent_id=None,
            level="physical",
            knobs=knobs,
            knobs_fp=fp,
            rtl_fp=None,
            netlist_fp=None,
            fidelity="F0",
            qor=QoR(
                congestion=cong,
                fidelity="F0",
                note="RUDY-class util×density proxy — not a place, not IR",
            ),
            cost_s=0.0,
            note="AutoDMP-shaped physical proposal; F5 P&R not launched",
        )
        added.append(mem.add(c))
    return added


def propose_synthesis_f0(mem: DesignMemory, design_id: str = "gcd", current_abc_area: int | None = 1) -> list[Candidate]:
    seen = mem.seen_knobs("synthesis")
    added: list[Candidate] = []
    for spec in SYNTH_CATALOG:
        knobs = {
            "name": spec["name"],
            "abcArea": spec["abcArea"],
            "source": "orfs_abc_area",
            "current": spec["abcArea"] == current_abc_area,
        }
        fp = knobs_fp("synthesis", knobs)
        if fp in seen:
            continue
        c = Candidate(
            id=DesignMemory.new_id(),
            design_id=design_id,
            parent_id=None,
            level="synthesis",
            knobs=knobs,
            knobs_fp=fp,
            rtl_fp=None,
            netlist_fp=None,
            fidelity="F0",
            qor=QoR(fidelity="F0", note="ORFS ABC_AREA knob — not flattened into ABC ops"),
            cost_s=0.0,
            note="synthesis-level proposal; no P&R, no ABC sequence",
        )
        added.append(mem.add(c))
    return added
