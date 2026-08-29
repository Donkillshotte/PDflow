"""Budget-aware fidelity / transform picker.

inspect → choose (level, fidelity) → caller evaluates. Does not flatten
architecture, ABC, util, and PDN into one acquisition over a mixed vector.
"""

from __future__ import annotations

from .memory import DesignMemory


def should_pay_f2_gpl(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_gpl: int,
    gpl_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    if n_gpl >= gpl_max:
        return False, "GPL shot already spent this run"
    if budget_left < min_s:
        return False, "wall budget would not cover OpenROAD GPL"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok"
        and c.fidelity == "F1"
        and c.qor.area_um2 is not None
        and (c.artifacts or {}).get("mapped_v")
    ]
    if not winners:
        return False, "no F1 mapped netlist to place"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("physical")
        if (c.knobs or {}).get("source") == "f2_openroad_gpl" and c.status == "ok"
    }
    if all(w.id in have for w in winners):
        return False, "every F1 winner already has a GPL child"
    return True, "promote F1 winner to OpenROAD GPL (skip_io, not finish/F5)"


def should_pay_f2_fast(mem: DesignMemory, *, n_f2: int, f2_max: int = 4) -> tuple[bool, str]:
    if n_f2 >= f2_max:
        return False, "F2-fast budget exhausted"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
    ]
    if not winners:
        return False, "no F1 to score"
    return True, "barycenter HPWL/RUDY on the candidate netlist"


def should_pay_f3_sta(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_sta: int,
    sta_max: int = 8,
    min_s: float = 1.0,
) -> tuple[bool, str]:
    if n_sta >= sta_max:
        return False, "F3 STA budget exhausted"
    if budget_left < min_s:
        return False, "wall budget would not cover OpenSTA"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
    ]
    if not winners:
        return False, "no F1 to time"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.all()
        if (c.knobs or {}).get("source") == "f3_opensta_ideal" and c.status == "ok"
    }
    if all(w.id in have for w in winners):
        return False, "every F1 already has an ideal STA child"
    return True, "OpenSTA ideal WNS/power on the candidate (not SPEF, not IR)"


def should_pay_f3_sdf(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_sdf: int = 0,
    sdf_max: int = 1,
    min_s: float = 1.0,
) -> tuple[bool, str]:
    """Pay one OpenSTA + GRT SDF shot. Not OpenRCX SPEF, not finish/F5."""
    from pathlib import Path

    if n_sdf >= sdf_max:
        return False, "F3 SDF-GRT shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover OpenSTA+SDF"
    if any(
        (c.knobs or {}).get("source") == "f3_opensta_sdf_grt" and c.status == "ok" for c in mem.all()
    ):
        return False, "already have an OpenSTA+SDF child"
    for c in mem.all():
        art = c.artifacts or {}
        sdf, mapped = art.get("sdf"), art.get("mapped_v")
        if sdf and mapped and Path(sdf).is_file() and Path(mapped).is_file():
            return True, "OpenSTA + GRT SDF (not SPEF/OpenRCX, not finish/F5)"
    return False, "no GRT SDF on disk (write_spef after GRT needs OpenRCX / F5)"


def should_pay_f2_grt(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_grt: int,
    grt_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    if n_grt >= grt_max:
        return False, "GRT shot already spent this run"
    if budget_left < min_s:
        return False, "wall budget would not cover OpenROAD GRT"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok" and c.fidelity == "F1" and c.qor.area_um2 is not None
    ]
    if not winners:
        return False, "no F1 to route"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f2_openroad_grt" and c.status == "ok"
    }
    if all(w.id in have for w in winners):
        return False, "every F1 winner already has a GRT child"
    return True, "promote F1 winner to OpenROAD GRT (not detailed route/F5)"


def should_pay_physical_catalog(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_catalog: int,
    catalog_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay one GPL shot on an unseen AutoDMP util/density — not F0 RUDY as truth."""
    if n_catalog >= catalog_max:
        return False, "physical catalog GPL shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover catalog GPL"
    from .physical_space import next_catalog_spec

    if next_catalog_spec(mem) is None:
        return False, "every AutoDMP catalog point already has a GPL child"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok"
        and c.fidelity == "F1"
        and c.qor.area_um2 is not None
        and (c.artifacts or {}).get("mapped_v")
    ]
    if not winners:
        return False, "no F1 mapped netlist for catalog GPL"
    return True, "measure AutoDMP catalog util/density with OpenROAD GPL (not F0-only)"


def should_pay_f4_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay one candidate write_pg_spice after legalized place. Not finish."""
    if n_extract >= extract_max:
        return False, "candidate PDN extract already spent this run"
    if budget_left < min_s:
        return False, "wall budget would not cover write_pg_spice"
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok"
        and c.fidelity == "F1"
        and c.qor.area_um2 is not None
        and (c.artifacts or {}).get("mapped_v")
    ]
    if not winners:
        return False, "no F1 mapped netlist to extract a PDN from"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_candidate_extract" and c.status == "ok"
    }
    if all(w.id in have for w in winners):
        return False, "every F1 winner already has a candidate extract"
    return True, "write_pg_spice on legalized GPL — new R-graph, not the finish mesh, not gold"


def should_pay_f4_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_pdn: int,
    pdn_max: int = 1,
    min_s: float = 8.0,
    variant: str = "flowlab",
    extract_id: str = "finish",
) -> tuple[bool, str]:
    if n_pdn >= pdn_max:
        return False, "PDN catalog F4 shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover Solver A restamp"
    from .f4_oracle import available
    from .pdn_space import next_pdn_spec

    if extract_id == "finish" and not available(variant):
        return False, "no cached write_pg_spice extract (not launching finish)"
    if next_pdn_spec(mem, extract_id=extract_id) is None:
        return False, "every PDN catalog point already has an F4 child on this extract"
    mesh = "candidate extract" if extract_id != "finish" else "cached finish extract"
    return True, f"Solver A restamp on {mesh} — PDN knobs only, not gold"


def should_pay_f4_scale(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_scale: int,
    scale_max: int = 1,
    min_s: float = 8.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    if n_scale >= scale_max:
        return False, "I(t)-scale F4 shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover scaled Solver A"
    from .f4_oracle import available
    from .mo import timing_of

    cand = latest_ok_extract(mem)
    if not available(variant) and cand is None:
        return False, "no write_pg_spice extract (not launching finish)"
    base = None
    for c in mem.by_level("logic"):
        if c.status == "ok" and c.knobs.get("name") == "liberty_default":
            _w, p = timing_of(mem, c)
            if p:
                base = p
                break
    if base is None:
        return False, "no F3 baseline power to form an I(t) scale"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_iscale" and c.status == "ok"
    }
    cands = []
    for c in mem.all():
        if c.status != "ok" or c.fidelity != "F1":
            continue
        _w, p = timing_of(mem, c)
        if p is None or c.id in have:
            continue
        if abs(float(p) / float(base) - 1.0) < 0.03:
            continue
        cands.append(c)
    if not cands:
        return False, "no F1 with a material F3 power delta to scale I(t)"
    mesh = "candidate extract" if cand else "cached finish extract"
    return True, f"Solver A with I(t)×P_F3/P_base on {mesh} — not a new VCD map"


def latest_ok_extract(mem: DesignMemory) -> dict | None:
    """Most recent successful candidate write_pg_spice (spice+insts on disk)."""
    from pathlib import Path

    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_candidate_extract":
            continue
        art = c.artifacts or {}
        spice, insts = art.get("spice"), art.get("insts")
        if spice and insts and Path(spice).is_file() and Path(insts).is_file():
            return {
                "spice": spice,
                "insts": insts,
                "extract_id": (c.knobs or {}).get("extract_id") or c.id,
                "parent_id": (c.knobs or {}).get("parent_id"),
                "n_r": art.get("n_r"),
                "candidate": c,
            }
    return None


def next_fidelity(*, level: str, pred: dict | None, budget_left: float, cost_hint: dict) -> str:
    """Cheap skip stays F0; otherwise the level's measuring oracle."""
    pred = pred or {}
    if level == "logic" and pred.get("skip"):
        return "F0"
    if level in ("physical", "f2_fast"):
        return "F2"
    if level == "f2_gpl":
        return "F2"
    if level in ("routing", "f2_grt"):
        return "F2"
    if level == "f3_sta":
        return "F3"
    if level == "f3_sdf":
        return "F3"
    if level in ("pdn", "f4_extract", "f4_scale"):
        return "F4"
    need = float(cost_hint.get("F1", 2.0))
    if budget_left < need:
        return "F0"
    return "F1"
