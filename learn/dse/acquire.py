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


def should_pay_f2_region(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_region: int = 0,
    region_max: int = 1,
    min_s: float = 4.0,
    region: str | None = None,
    x_dbu: float | None = None,
    y_dbu: float | None = None,
) -> tuple[bool, str]:
    """Pay one GPL with an IR-bin density cap. Not more ABC, not finish."""
    if n_region >= region_max:
        return False, "region GPL shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover region GPL"
    if x_dbu is None and not region:
        return False, "no IR region / hotspot to place against"
    from .openroad_f2 import available as gpl_ok

    if not gpl_ok():
        return False, "openroad missing — not launching finish"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok"
        and c.fidelity == "F1"
        and c.qor.area_um2 is not None
        and (c.artifacts or {}).get("mapped_v")
    ]
    if not winners:
        return False, "no F1 mapped netlist for region GPL"
    have = any(
        (c.knobs or {}).get("source") == "f2_openroad_gpl_region" and c.status == "ok"
        for c in mem.by_level("physical")
    )
    if have:
        return False, "already have a region-local GPL child"
    tag = region or f"xy={x_dbu:.0f},{y_dbu:.0f}"
    return True, f"OpenROAD density cap on IR bin {tag} — region-local place, not more ABC"


def should_pay_f4_region_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
    region: str | None = None,
    x_dbu: float | None = None,
    y_dbu: float | None = None,
) -> tuple[bool, str]:
    """Pay one write_pg_spice under the IR-bin density cap. Not gold."""
    if n_extract >= extract_max:
        return False, "region PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover region write_pg_spice"
    if x_dbu is None and not region:
        return False, "no IR region / hotspot to extract against"
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
        return False, "no F1 mapped netlist for region extract"
    have = any(
        (c.knobs or {}).get("source") == "f4_region_extract" and c.status == "ok"
        for c in mem.by_level("pdn")
    )
    if have:
        return False, "already have a region-local extract"
    tag = region or f"xy={x_dbu:.0f},{y_dbu:.0f}"
    return True, f"write_pg_spice under IR-bin density cap {tag} — new mesh, not gold"


def should_pay_f5_drt(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_f5: int,
    f5_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay one detailed_route + OpenRCX SPEF. Not make finish."""
    from .openroad_f2 import f5_available

    if n_f5 >= f5_max:
        return False, "F5 DRT/RCX shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover detailed_route+OpenRCX"
    if not f5_available():
        return False, "OpenRCX rules missing — not launching make finish"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok"
        and c.fidelity == "F1"
        and c.qor.area_um2 is not None
        and (c.artifacts or {}).get("mapped_v")
    ]
    if not winners:
        return False, "no F1 mapped netlist to detailed-route"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
    }
    if all(w.id in have for w in winners):
        return False, "every F1 winner already has an F5 SPEF child"
    return True, "detailed_route + OpenRCX SPEF — F5-lite, not make finish"


def should_pay_f5_cts(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_f5_cts: int,
    f5_cts_max: int = 1,
    min_s: float = 25.0,
) -> tuple[bool, str]:
    """Pay one CTS + DRT + OpenRCX SPEF after F5-lite. Not make finish."""
    from .openroad_f2 import f5_available

    if n_f5_cts >= f5_cts_max:
        return False, "F5 CTS shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover CTS+DRT+OpenRCX"
    if not f5_available():
        return False, "OpenRCX rules missing — not launching make finish"
    have_lite = any(
        (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
        for c in mem.by_level("routing")
    )
    if not have_lite:
        return False, "F5-lite SPEF is the prerequisite — CTS is not the first F5 shot"
    have_cts = any(
        (c.knobs or {}).get("source") == "f5_openroad_cts_rcx" and c.status == "ok"
        for c in mem.by_level("routing")
    )
    if have_cts:
        return False, "already have a CTS SPEF child"
    winners = [
        c
        for c in mem.all()
        if c.status == "ok"
        and c.fidelity == "F1"
        and c.qor.area_um2 is not None
        and (c.artifacts or {}).get("mapped_v")
    ]
    if not winners:
        return False, "no F1 mapped netlist for CTS"
    return True, "CTS + DRT + OpenRCX SPEF — propagated clock, not make finish"


def should_pay_f3_spef(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_spef: int = 0,
    spef_max: int = 1,
    min_s: float = 1.0,
) -> tuple[bool, str]:
    from pathlib import Path

    if n_spef >= spef_max:
        return False, "F3 SPEF shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover OpenSTA+SPEF"
    if any((c.knobs or {}).get("source") == "f3_opensta_spef" and c.status == "ok" for c in mem.all()):
        return False, "already have an OpenSTA+SPEF child"
    for c in mem.all():
        art = c.artifacts or {}
        spef, mapped = art.get("spef"), art.get("mapped_v")
        if spef and mapped and Path(spef).is_file() and Path(mapped).is_file():
            return True, "OpenSTA + OpenRCX SPEF (not GRT SDF, not finish launch)"
    return False, "no OpenRCX SPEF on disk"


def should_pay_f4_amg(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_amg: int = 0,
    amg_max: int = 1,
    min_s: float = 6.0,
    variant: str = "flowlab",
    extract_id: str = "finish",
) -> tuple[bool, str]:
    """Pay one SA-AMG restamp on the named extract. Residual vs DirectLU, not gold."""
    if n_amg >= amg_max:
        return False, "AMG F4 scout already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover AMG restamp"
    have = any(
        (c.knobs or {}).get("source") == "f4_solver_amg"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
        and c.status == "ok"
        for c in mem.by_level("pdn")
    )
    if have:
        return False, "this extract already has an AMG child"
    if extract_id != "finish":
        if latest_ok_extract(mem) is None:
            return False, "no candidate extract for AMG residual"
    else:
        from .f4_oracle import available

        if not available(variant):
            return False, "no cached finish extract for AMG residual"
    return True, f"SA-AMG restamp on {extract_id} — MF solver residual, not gold"


def should_pay_f1_synth(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_f1: int,
    f1_max: int = 6,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay one ORFS delay-script F1. Not logic ``-fast``; not ``abc_ops``."""
    if any(c.level == "synthesis" and c.fidelity == "F1" for c in mem.all()):
        return False, "synthesis F1 already measured"
    if n_f1 >= f1_max:
        return False, "F1 budget exhausted"
    if budget_left < min_s:
        return False, "wall budget would not cover ORFS abc_speed"
    from .synthesis import available as synth_ok

    if not synth_ok():
        return False, "ORFS abc_speed.script missing"
    if not any(c.fidelity == "F1" and c.status == "ok" for c in mem.all()):
        return False, "no F1 teacher yet"
    return True, "ORFS abc_speed.script (ABC_AREA=0) — not logic -fast, not abc_ops"


def should_pay_cell_size(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_cell: int = 0,
    cell_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one drive-up on attributed worst-path cells. Not more ABC."""
    if n_cell >= cell_max:
        return False, "cell-local size shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover cell-local STA"
    if any((c.knobs or {}).get("source") == "cell_size_up" and c.status == "ok" for c in mem.by_level("cell")):
        return False, "already have a cell-local size child"
    cells = _attributed_path_cells(mem)
    if len(cells) < 2:
        return False, "no attributed STA path cells to size"
    return True, f"upsize {len(cells)} attributed worst-path cells — not ABC, not a chip restart"


def _attributed_path_cells(mem: DesignMemory) -> list[str]:
    for c in reversed(list(mem.all())):
        if c.status != "ok":
            continue
        art = c.artifacts or {}
        cells = list(art.get("path_cells") or [])
        if len(cells) >= 2:
            return cells
        attr = c.attr or {}
        cells = list(attr.get("cells") or [])
        if len(cells) >= 2 and attr.get("kind") == "sta_path":
            return cells
    return []


def should_pay_f4_ras(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_ras: int = 0,
    ras_max: int = 1,
    min_s: float = 8.0,
    variant: str = "flowlab",
    extract_id: str = "finish",
) -> tuple[bool, str]:
    """Pay one RAS restamp after AMG. Residual vs DirectLU, not a PDN-catalog consume."""
    if n_ras >= ras_max:
        return False, "RAS F4 scout already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover RAS restamp"
    have = any(
        (c.knobs or {}).get("source") == "f4_solver_ras"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
        and c.status == "ok"
        for c in mem.by_level("pdn")
    )
    if have:
        return False, "this extract already has a RAS child"
    if not any(
        (c.knobs or {}).get("source") == "f4_solver_amg" and c.status == "ok"
        for c in mem.by_level("pdn")
    ):
        return False, "AMG residual not yet measured"
    if extract_id != "finish":
        if latest_ok_extract(mem) is None:
            return False, "no candidate extract for RAS residual"
    else:
        from .f4_oracle import available

        if not available(variant):
            return False, "no cached finish extract for RAS residual"
    return True, f"RAS restamp on {extract_id} — domain-decomp MF residual, not gold"


def should_pay_f4_krylov(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_krylov: int = 0,
    krylov_max: int = 1,
    min_s: float = 10.0,
    variant: str = "flowlab",
    extract_id: str = "finish",
) -> tuple[bool, str]:
    """Pay one rational Krylov/MOR restamp after RAS. Residual vs DirectLU, not gold."""
    if n_krylov >= krylov_max:
        return False, "Krylov F4 scout already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover Krylov/MOR restamp"
    have = any(
        (c.knobs or {}).get("source") == "f4_solver_krylov"
        and str((c.knobs or {}).get("extract_id") or "finish") == extract_id
        and c.status == "ok"
        for c in mem.by_level("pdn")
    )
    if have:
        return False, "this extract already has a Krylov/MOR child"
    if not any(
        (c.knobs or {}).get("source") == "f4_solver_ras" and c.status == "ok"
        for c in mem.by_level("pdn")
    ):
        return False, "RAS residual not yet measured"
    if extract_id != "finish":
        if latest_ok_extract(mem) is None:
            return False, "no candidate extract for Krylov/MOR residual"
    else:
        from .f4_oracle import available

        if not available(variant):
            return False, "no cached finish extract for Krylov/MOR residual"
    return True, f"rational Krylov/MOR restamp on {extract_id} — reduced-order residual, not gold"


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
                "sta": art.get("sta_arrivals"),
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
    if level == "f3_spef":
        return "F3"
    if level == "f5_drt":
        return "F5"
    if level == "f5_cts":
        return "F5"
    if level == "f2_region":
        return "F2"
    if level == "f4_amg":
        return "F4"
    if level == "f4_ras":
        return "F4"
    if level in ("f4_krylov", "f4_mor"):
        return "F4"
    if level in ("pdn", "f4_extract", "f4_scale", "f4_region_extract"):
        return "F4"
    if level in ("synthesis", "f1_synth"):
        return "F1"
    if level in ("cell", "cell_size"):
        return "F3"
    need = float(cost_hint.get("F1", 2.0))
    if budget_left < need:
        return "F0"
    return "F1"
