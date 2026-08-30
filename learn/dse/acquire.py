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


def should_pay_f4_host_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay write_pg_spice on the attributed host netlist. Not the synth F1 mesh."""
    if n_extract >= extract_max:
        return False, "host PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover host write_pg_spice"
    from pathlib import Path

    from .active import iscale_host
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = iscale_host(mem)
    if host is None:
        return False, "no attributed host to extract a PDN from"
    mapped = (host.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, "attributed host has no mapped netlist for write_pg_spice"
    cand = latest_ok_extract(mem)
    if cand and str(cand.get("parent_id") or "") == host.id:
        return False, "host is already the candidate-extract parent"
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_host_extract" and c.status == "ok"
    }
    if host.id in have:
        return False, "attributed host already has a write_pg_spice mesh"
    host_src = (host.knobs or {}).get("source") or (host.knobs or {}).get("name") or host.level
    return True, (
        f"write_pg_spice on {host_src} — host R-graph, not the synth extract, not gold"
    )


def latest_host_extract_cand(mem: DesignMemory):
    """Newest host write_pg_spice candidate (hotspot/attr). Spice files optional."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_host_extract":
            return c
    return None


def _ingest_region(mem: DesignMemory) -> str | None:
    for c in mem.by_level("pdn"):
        if c.status != "ok" or (c.knobs or {}).get("source") != "ingest_pdn":
            continue
        r = (c.attr or {}).get("region")
        if r:
            return str(r)
    return None


def should_pay_f4_host_region(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay write_pg_spice under the host IR-bin density cap. Not gold rXY on synth."""
    if n_extract >= extract_max:
        return False, "host-region PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover host-region write_pg_spice"
    from pathlib import Path

    from .active import iscale_host
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host_ext = latest_host_extract_cand(mem)
    if host_ext is None:
        return False, "no host write_pg_spice to attribute a region from"
    hattr = host_ext.attr or {}
    region = hattr.get("region")
    x_dbu, y_dbu = hattr.get("x_dbu"), hattr.get("y_dbu")
    if x_dbu is None and not region:
        return False, "host extract has no IR hotspot / region"
    host = iscale_host(mem)
    mapped = (host.artifacts or {}).get("mapped_v") if host else None
    if not host or not mapped or not Path(mapped).is_file():
        return False, "attributed host has no mapped netlist for host-region extract"
    gold_r = _ingest_region(mem)
    if gold_r and region and str(region) == str(gold_r):
        return False, f"host IR region {region} already matches the gold bin"
    have = any(
        (c.knobs or {}).get("source") == "f4_host_region_extract" and c.status == "ok"
        for c in mem.by_level("pdn")
    )
    if have:
        return False, "attributed host already has a region-capped write_pg_spice"
    seq = float(hattr.get("seq_frac") or 0.0)
    tag = region or f"xy={float(x_dbu):.0f},{float(y_dbu):.0f}"
    gold_tag = gold_r or "unjoined"
    if seq >= 0.5:
        return True, (
            f"host IR bin {tag} ≠ gold {gold_tag}; seq_frac={seq:.2f} — "
            "density cap on the host netlist, not more combo ABC on dpath"
        )
    return True, (
        f"host IR bin {tag} ≠ gold {gold_tag} — density cap on the host netlist, "
        "not gold-region on synth F1, not more combo ABC"
    )


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
    from .active import iscale_host
    from .f4_oracle import available

    cand = latest_ok_extract(mem)
    if not available(variant) and cand is None:
        return False, "no write_pg_spice extract (not launching finish)"
    host = iscale_host(mem)
    if host is None:
        return False, "no attributed host with a material F3 power delta to scale I(t)"
    host_src = (host.knobs or {}).get("source") or (host.knobs or {}).get("name") or host.level
    mesh = "candidate extract" if cand else "cached finish extract"
    return True, (
        f"I(t)×P_F3/P_base of {host_src} on {mesh} — attributed host, "
        "not synth-only, not a new VCD map"
    )


def should_pay_f4_scale_win(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_scale: int = 0,
    scale_max: int = 1,
    min_s: float = 8.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """Re-scale I(t) on the winning host PDN point after host IR-steer. Not the first I-scale."""
    if n_scale >= scale_max:
        return False, "winning-host I-scale shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-host I-scale"
    from .active import iscale_parent, winning_host_pdn
    from .f4_oracle import available

    first = next(
        (
            c
            for c in reversed(list(mem.by_level("pdn")))
            if c.status == "ok" and (c.knobs or {}).get("source") == "f4_iscale"
        ),
        None,
    )
    if first is None:
        return False, "no first I-scale to compare a winning host mesh against"
    win = winning_host_pdn(mem)
    if win is None:
        return False, "no host extract / host-IR-steer point to re-scale"
    eid = str((win.knobs or {}).get("extract_id") or win.id)
    first_eid = str((first.knobs or {}).get("extract_id") or "")
    same_mesh = eid == first_eid
    same_knob = (
        abs(float((win.knobs or {}).get("c_decap") or 50e-15) - float((first.knobs or {}).get("c_decap") or 50e-15))
        < 1e-16
        and abs(float((win.knobs or {}).get("pkg_l") or 2e-10) - float((first.knobs or {}).get("pkg_l") or 2e-10))
        < 1e-16
    )
    if same_mesh and same_knob:
        return False, "winning host PDN is already the first I-scale mesh"
    if not extract_on_disk(mem, eid) and not available(variant):
        return False, "winning host extract is not on disk"
    host = iscale_parent(mem)
    if host is None and not (first.knobs or {}).get("parent_id"):
        return False, "first I-scale host is missing"
    have = any(
        (c.knobs or {}).get("source") == "f4_iscale_win" and c.status == "ok"
        for c in mem.by_level("pdn")
    )
    if have:
        return False, "winning-host I-scale already measured"
    src = (win.knobs or {}).get("name") or (win.attr or {}).get("via") or (win.knobs or {}).get("source")
    return True, (
        f"I(t)×P_F3/P_base of the attributed host on winning {src} "
        f"{float(win.qor.dynamic_ir_mv):.3f} mV — not the unconstrained I-scale, not VCD"
    )


def iscale_champ_sta(hit: dict | None) -> tuple[str | None, str]:
    """Champion I-scale uses extract STA. Never host arrivals (unsized netlist)."""
    sta = (hit or {}).get("sta") if hit else None
    if sta:
        return str(sta), "extract"
    return None, "f4_iscale_champ"


def should_pay_f4_scale_champ(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_scale: int = 0,
    scale_max: int = 1,
    min_s: float = 8.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """I(t)×P on winning_ir_pdn when that mesh is not the I-scale-win host.

    Host I-scale-win stays on winning_host_pdn. After IR-cell-region-PDN the
    1× champion is a different extract. Parent is ir_cell_host; arrivals
    come from the champ extract, never host arrivals.
    """
    if n_scale >= scale_max:
        return False, "champion I-scale shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover champion I-scale"
    from .active import ir_cell_host, winning_host_pdn, winning_ir_pdn
    from .f4_oracle import available

    win_scale = next(
        (
            c
            for c in reversed(list(mem.by_level("pdn")))
            if c.status == "ok" and (c.knobs or {}).get("source") == "f4_iscale_win"
        ),
        None,
    )
    if win_scale is None:
        return False, "no winning-host I-scale to compare a champion mesh against"
    champ = winning_ir_pdn(mem)
    host_win = winning_host_pdn(mem)
    if champ is None:
        return False, "no IR-family 1× champion to scale"
    if host_win is None:
        return False, "no host-win to refuse flattening onto"
    champ_id = str((champ.knobs or {}).get("extract_id") or champ.id)
    win_id = str((win_scale.knobs or {}).get("extract_id") or "")
    if champ_id == win_id:
        return False, "champion mesh is already the I-scale-win extract"
    via = (champ.attr or {}).get("via") or (champ.knobs or {}).get("source")
    if via not in (
        "f4_ir_cell_extract",
        "f4_ir_cell_region_extract",
        "active_f4_ir_cell_pdn",
        "active_f4_ir_cell_region_pdn",
        "f4_ir_cell_champ_extract",
        "active_f4_ir_cell_champ_pdn",
        "f4_ir_cell_champ_cone_extract",
        "active_f4_ir_cell_champ_cone_pdn",
        "f4_ir_cell_champ_cone_region_extract",
        "active_f4_ir_cell_champ_cone_region_pdn",
        "f4_winning_ir_region_extract",
        "active_f4_winning_ir_region_pdn",
        "f4_winning_ir_region_cell_extract",
        "active_f4_winning_ir_region_cell_pdn",
        "f4_winning_ir_region_cell_leftover_extract",
        "active_f4_winning_ir_region_cell_leftover_pdn",
        "f4_static_strap_extract",
        "active_f4_static_straps",
        "f4_em_strap_extract",
        "active_f4_em_straps",
        "active_f4_winning_ir_pdn",
    ):
        return False, "champion I-scale refuses a host-only 1× point"
    if ir_cell_host(mem) is None:
        return False, "IR-cell host missing — not flattening to unsized port-steer"
    if not extract_on_disk(mem, champ_id) and not available(variant):
        return False, "champion extract is not on disk"
    have = any(
        (c.knobs or {}).get("source") == "f4_iscale_champ"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == champ_id
        for c in mem.by_level("pdn")
    )
    if have:
        return False, "champion I-scale already measured on this extract"
    src = (champ.knobs or {}).get("name") or via
    return True, (
        f"I(t)×P_F3/P_base of the IR-cell host on champion {src} "
        f"{float(champ.qor.dynamic_ir_mv):.3f} mV — not I-scale-win, not host arrivals, not VCD"
    )


def latest_host_arrivals(mem: DesignMemory) -> dict | None:
    """Most recent report_arrival JSON on an attributed host. Not extract STA."""
    from pathlib import Path

    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_host_arrivals":
            continue
        p = (c.artifacts or {}).get("sta_arrivals")
        if p and Path(p).is_file():
            return {
                "sta": p,
                "parent_id": (c.knobs or {}).get("parent_id"),
                "n_inst": (c.artifacts or {}).get("n_inst"),
                "host_source": (c.knobs or {}).get("host_source"),
                "candidate": c,
            }
    return None


def should_pay_host_arrivals(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_arr: int = 0,
    arr_max: int = 1,
    min_s: float = 4.0,
) -> tuple[bool, str]:
    """Pay OpenSTA report_arrival on the I-scale host. Not extract STA, not VCD."""
    if n_arr >= arr_max:
        return False, "host arrivals shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover report_arrival"
    from pathlib import Path

    from .active import iscale_host
    from .sta_f3 import available as sta_ok

    if not sta_ok():
        return False, "opensta missing — not inventing t50"
    host = iscale_host(mem)
    if host is None:
        return False, "no attributed host to measure arrivals on"
    mapped = (host.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, "attributed host has no mapped netlist for report_arrival"
    host_src = (host.knobs or {}).get("source") or (host.knobs or {}).get("name") or host.level
    return True, (
        f"OpenSTA report_arrival on {host_src} — t50 of the attributed host, "
        "not the synth extract, not a VCD map"
    )


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


def local_hosts(mem: DesignMemory) -> list:
    """Net-buffered first, then cell-sized. Both must have a mapped netlist on disk."""
    from pathlib import Path

    out = []
    seen: set[str] = set()
    for level, src in (("net", "net_buffer"), ("cell", "cell_size_up")):
        for c in reversed(list(mem.by_level(level))):
            if c.status != "ok" or (c.knobs or {}).get("source") != src:
                continue
            mapped = (c.artifacts or {}).get("mapped_v")
            if mapped and Path(mapped).is_file() and c.id not in seen:
                out.append(c)
                seen.add(c.id)
    return out


def latest_local_host(mem: DesignMemory):
    """Prefer the net-buffered netlist, then the cell-sized one."""
    hosts = local_hosts(mem)
    return hosts[0] if hosts else None


def latest_port_host(mem: DesignMemory):
    """Parent-scoped port-net netlist. Not the intra-module net host."""
    from pathlib import Path

    for c in reversed(list(mem.by_level("net"))):
        if c.status != "ok" or (c.knobs or {}).get("source") != "net_buffer_port":
            continue
        mapped = (c.artifacts or {}).get("mapped_v")
        if mapped and Path(mapped).is_file():
            return c
    return None


def should_pay_f5_local(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_f5_local: int = 0,
    f5_local_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay OpenRCX SPEF on the cell/net netlist. Residual vs F1 F5-lite."""
    from .openroad_f2 import f5_available

    if n_f5_local >= f5_local_max:
        return False, "F5 local SPEF shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover local detailed_route+OpenRCX"
    if not f5_available():
        return False, "OpenRCX rules missing — not launching make finish"
    have_lite = any(
        (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
        for c in mem.by_level("routing")
    )
    if not have_lite:
        return False, "F5-lite on the F1 netlist is the baseline — local SPEF is the residual"
    if any(
        (c.knobs or {}).get("source") == "f5_openroad_local" and c.status == "ok"
        for c in mem.by_level("routing")
    ):
        return False, "already have a local-transform SPEF child"
    host = latest_local_host(mem)
    if host is None:
        return False, "no cell/net mapped netlist for local SPEF"
    return True, (
        f"OpenRCX SPEF on {host.level} { (host.knobs or {}).get('source') } "
        "— F3→F5 residual, not the F1 F5-lite SPEF, not make finish"
    )


def should_pay_f5_port(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_f5_port: int = 0,
    f5_port_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay OpenRCX SPEF on the port-net netlist. Not the intra-module net host."""
    from .openroad_f2 import f5_available

    if n_f5_port >= f5_port_max:
        return False, "F5 port-net SPEF shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover port-net detailed_route+OpenRCX"
    if not f5_available():
        return False, "OpenRCX rules missing — not launching make finish"
    if not any(
        (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
        for c in mem.by_level("routing")
    ):
        return False, "F5-lite on the F1 netlist is the baseline — port SPEF is the residual"
    if any(
        (c.knobs or {}).get("source") == "f5_openroad_local"
        and (c.knobs or {}).get("host_level") == "port"
        and c.status == "ok"
        for c in mem.by_level("routing")
    ):
        return False, "already have a port-net SPEF child"
    host = latest_port_host(mem)
    if host is None:
        return False, "no port-net mapped netlist for local SPEF"
    return True, (
        "OpenRCX SPEF on port net_buffer_port — F3→F5 residual on the "
        "ctrl↔dpath BUF netlist, not the intra-module net host, not make finish"
    )


def should_pay_port_steer(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one F5-port-residual local action. Not the first net BUF shot."""
    if n_steer >= steer_max:
        return False, "F5-port residual-steered shot already spent"
    if any((c.attr or {}).get("via") == "active_f5_port" and c.status == "ok" for c in mem.all()):
        return False, "already have an F5-port residual-steered child"
    if not steer or steer.get("level") != "net" or not steer.get("hops"):
        return False, "no F5-port residual action (need a wire-dominated port SPEF pair)"
    if budget_left < min_s:
        return False, "wall budget would not cover F5-port residual BUF"
    return True, str(steer.get("reason") or "F5-port residual steers intra-module BUF")


def should_pay_residual_steer(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one residual-steered local action. Not a mixed cell+net+ABC vector."""
    if n_steer >= steer_max:
        return False, "residual-steered shot already spent"
    if any((c.attr or {}).get("via") == "active_residual" and c.status == "ok" for c in mem.all()):
        return False, "already have a residual-steered child"
    if not steer or not steer.get("level"):
        return False, "no residual-steered action (need an F3→F5-local pair first)"
    need = 12.0 if steer["level"] == "f5_local" else max(min_s, 3.0)
    if budget_left < need:
        return False, "wall budget would not cover residual-steered shot"
    return True, str(steer.get("reason") or "F3→F5 residual steers the next level")


def should_pay_ir_steer(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 2,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the next F4 residual-steered PDN action. Not a mixed ABC+PDN vector.

    Shot 1: winning catalog on the region mesh. Shot 2: unused pkg L on the
    candidate extract after inspect. Same extract+catalog is not restamped.
    """
    if n_steer >= steer_max:
        return False, "IR-residual-steered budget spent (region family + unused catalog)"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-steered Solver A"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no IR-residual-steered PDN action (need candidate vs gold or a catalog pair)"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that IR-steered PDN point is already measured on this extract"
    return True, str(steer.get("reason") or "F4 IR residual steers the next PDN action")


def should_pay_host_ir_steer(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 2,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the next host-mesh PDN action from the host-region residual.

    Shot 1: winning catalog on the host-region mesh. Shot 2: unused pkg L on
    the unconstrained host extract. Not candidate IR-steer, not a mixed vector.
    """
    if n_steer >= steer_max:
        return False, "host IR-residual-steered budget spent (host-region family + unused catalog)"
    if budget_left < min_s:
        return False, "wall budget would not cover host IR-steered Solver A"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no host IR-residual-steered PDN action (need a host-region residual pair)"
    src = str(steer.get("host_source") or "")
    if src not in ("f4_host_region_extract", "f4_host_extract"):
        return False, "host IR-steer refuses a candidate/region extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that host IR-steered PDN point is already measured on this extract"
    return True, str(steer.get("reason") or "F4 host-region residual steers the next host PDN action")


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


def _have_named_cone(mem: DesignMemory, cone: str) -> bool:
    return any(
        c.status == "ok"
        and c.fidelity == "F1"
        and (c.knobs or {}).get("cone") == cone
        for c in mem.by_level("logic")
    )


def _ctrl_hops(mem: DesignMemory, attr: dict | None = None) -> bool:
    from .attribute import ctrl_on_path

    if ctrl_on_path(attr):
        return True
    for c in reversed(list(mem.all())):
        if c.status != "ok":
            continue
        if ctrl_on_path(c.attr):
            return True
        cells = list((c.artifacts or {}).get("path_cells") or [])
        if ctrl_on_path(None, cells=cells):
            return True
    return False


def should_pay_ctrl_cone(
    mem: DesignMemory,
    *,
    budget_left: float,
    attr: dict | None = None,
    n_ctrl: int = 0,
    ctrl_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one cone-local ABC on the FSM. Not leftover of dpath, not a chip restart."""
    if n_ctrl >= ctrl_max:
        return False, "ctrl-cone ABC shot already spent"
    if _have_named_cone(mem, "ctrl"):
        return False, "already have a ctrl-cone F1"
    if budget_left < min_s:
        return False, "wall budget would not cover ctrl-cone F1"
    if not _have_named_cone(mem, "dpath") and not (attr and (attr.get("modules") or [None])[0] == "ctrl"):
        return False, "ctrl cone waits for the dpath cone teacher (or explicit ctrl focus)"
    if not _ctrl_hops(mem, attr):
        return False, "no attributed ctrl hops — not a leftover placeholder shot"
    return True, "cone-local ABC on ctrl (FSM+RegRst) — not leftover of dpath, not a chip restart"


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


def should_pay_ir_cell(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_cell: int = 0,
    cell_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one drive-up on IR-hotspot ODB instances. Not STA-path cell size-up, not ABC."""
    if n_cell >= cell_max:
        return False, "IR-hotspot cell size shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-hotspot cell STA"
    if any((c.knobs or {}).get("source") == "cell_size_ir" and c.status == "ok" for c in mem.by_level("cell")):
        return False, "already have an IR-hotspot cell-local size child"
    from pathlib import Path

    from .active import ir_hotspot_cells, iscale_parent

    spec = ir_hotspot_cells(mem)
    if spec is None or int(spec.get("n") or 0) < 1:
        return False, "no IR hotspot instance join (need I-scale-win / host extract insts)"
    if not spec.get("modules"):
        return False, "IR hotspot join has no module — not inventing a cone"
    host = iscale_parent(mem)
    mapped = None
    if host:
        mapped = (host.artifacts or {}).get("mapped_hier_v") or (host.artifacts or {}).get("mapped_v")
    if not host or not mapped or not Path(mapped).is_file():
        return False, "attributed host has no mapped netlist for IR-cell upsize"
    sta_cells = set(_attributed_path_cells(mem))
    ir_cells = [str(x) for x in spec.get("cells") or []]
    if sta_cells and ir_cells and set(ir_cells) <= sta_cells:
        return False, "IR hotspot cells already covered by STA cell size-up"
    mods = ",".join(spec.get("modules") or [])
    region = spec.get("region") or "unjoined"
    return True, (
        f"upsize {len(ir_cells)} IR-hotspot cells on {mods} region {region} — "
        "ODB join, not STA path, not ABC, not a VCD remap"
    )


def should_pay_ir_cell_champ(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_cell: int = 0,
    cell_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one drive-up on the I-scale-champ ODB join. Not the first ctrl IR-cell."""
    if n_cell >= cell_max:
        return False, "I-scale-champ cell size shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover I-scale-champ cell STA"
    if not steer or steer.get("level") != "ir_cell_champ":
        return False, "no I-scale-champ hotspot residual (need combo-heavy join ≠ first IR-cell)"
    champ_eid = str(steer.get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "cell_size_ir_champ"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == champ_eid
        for c in mem.by_level("cell")
    ):
        return False, "already have an I-scale-champ cell-local size child on this extract"
    cells = [str(x) for x in steer.get("cells") or []]
    if len(cells) < 1:
        return False, "I-scale-champ join has no cells"
    if not steer.get("modules"):
        return False, "I-scale-champ join has no module — not inventing a cone"
    from pathlib import Path

    from .active import ir_cell_host

    host = ir_cell_host(mem)
    mapped = None
    if host:
        mapped = (host.artifacts or {}).get("mapped_hier_v") or (host.artifacts or {}).get("mapped_v")
    if not host or not mapped or not Path(mapped).is_file():
        return False, "IR-cell host missing — not flattening champ size-up onto unsized port-steer"
    first = {str(x) for x in (host.knobs or {}).get("cells") or []}
    if first and set(cells) <= first:
        return False, "I-scale-champ cells already covered by the first IR-cell size-up"
    mods = ",".join(steer.get("modules") or [])
    region = steer.get("region") or "unjoined"
    return True, str(
        steer.get("reason")
        or (
            f"upsize {len(cells)} I-scale-champ cells on {mods} region {region} — "
            "not the first ctrl IR-cell, not STA path, not ABC, not VCD"
        )
    )


def should_pay_ir_cell_champ_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay write_pg_spice on the IR-cell-champ netlist. Residual vs IR-cell extract."""
    if n_extract >= extract_max:
        return False, "IR-cell-champ PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell-champ write_pg_spice"
    from pathlib import Path

    from .active import ir_cell_champ_host, ir_cell_extract_cand
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = ir_cell_champ_host(mem)
    if host is None:
        return False, "no IR-cell-champ size-up to extract a PDN from"
    mapped = (host.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, "IR-cell-champ netlist missing for write_pg_spice"
    ice = ir_cell_extract_cand(mem)
    if ice is None:
        return False, "no IR-cell extract to residual the champ mesh against"
    if str((ice.knobs or {}).get("parent_id") or "") == host.id:
        return False, "IR-cell-champ is already the IR-cell-extract parent"
    host_eid = str((host.knobs or {}).get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "f4_ir_cell_champ_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == host_eid
        for c in mem.by_level("pdn")
    ):
        return False, "already have an IR-cell-champ write_pg_spice mesh on this extract"
    nch = (host.artifacts or {}).get("n_changed") or len((host.knobs or {}).get("cells") or [])
    mods = ",".join(
        dict.fromkeys(
            str(x).split("/")[0]
            for x in (host.knobs or {}).get("cells") or []
            if "/" in str(x)
        )
    ) or "unjoined"
    return True, (
        f"write_pg_spice on IR-cell-champ {mods} n={nch} — champ-sized netlist IR residual "
        "vs IR-cell extract, not host extract, not gold, not ABC"
    )


def should_pay_ir_cell_champ_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the IR-cell-champ extract. Not host IR-steer."""
    if n_steer >= steer_max:
        return False, "IR-cell-champ PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell-champ PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no IR-cell-champ residual-steered PDN action (need a 1× residual)"
    if str(steer.get("host_source") or "") != "f4_ir_cell_champ_extract":
        return False, "IR-cell-champ PDN restamp refuses a host/IR-cell/region extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the IR-cell-champ extract"
    return True, str(steer.get("reason") or "IR-cell-champ residual steers a PDN restamp on the dpath-sized mesh")


def should_pay_ir_cell_champ_cone(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_cell: int = 0,
    cell_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay leftover-cone drive-up on the IR-cell-champ extract join. Not champ ctrl."""
    if n_cell >= cell_max:
        return False, "IR-cell-champ-cone cell size shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell-champ-cone cell STA"
    if not steer or steer.get("level") != "ir_cell_champ_cone":
        return False, "no IR-cell-champ-cone hotspot residual (need leftover cells ≠ champ size-up)"
    champ_eid = str(steer.get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "cell_size_ir_champ_cone"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == champ_eid
        for c in mem.by_level("cell")
    ):
        return False, "already have an IR-cell-champ-cone cell-local size child on this extract"
    cells = [str(x) for x in steer.get("cells") or []]
    if len(cells) < 1:
        return False, "IR-cell-champ-cone join has no leftover cells"
    if not steer.get("modules"):
        return False, "IR-cell-champ-cone join has no module — not inventing a cone"
    from pathlib import Path

    from .active import ir_cell_champ_host, ir_cell_host

    host = ir_cell_champ_host(mem)
    mapped = None
    if host:
        mapped = (host.artifacts or {}).get("mapped_hier_v") or (host.artifacts or {}).get("mapped_v")
    if not host or not mapped or not Path(mapped).is_file():
        return False, "IR-cell-champ host missing — not flattening cone size-up onto first ctrl IR-cell"
    sized = {str(x) for x in (host.knobs or {}).get("cells") or []}
    if sized and set(cells) <= sized:
        return False, "IR-cell-champ-cone cells already covered by the champ size-up"
    first = ir_cell_host(mem)
    first_cells = {str(x) for x in (first.knobs or {}).get("cells") or []} if first else set()
    if first_cells and set(cells) <= first_cells:
        return False, "IR-cell-champ-cone cells already covered by the first IR-cell size-up"
    mods = ",".join(steer.get("modules") or [])
    region = steer.get("region") or "unjoined"
    return True, str(
        steer.get("reason")
        or (
            f"upsize {len(cells)} leftover {mods} cells on champ-extract region {region} — "
            "not the champ size-up set, not first ctrl IR-cell, not STA path, not ABC, not VCD"
        )
    )


def should_pay_ir_cell_champ_cone_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay write_pg_spice on the leftover-cone netlist. Residual vs champ extract."""
    if n_extract >= extract_max:
        return False, "IR-cell-champ-cone PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell-champ-cone write_pg_spice"
    from pathlib import Path

    from .active import ir_cell_champ_cone_host, ir_cell_champ_extract_cand
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = ir_cell_champ_cone_host(mem)
    if host is None:
        return False, "no IR-cell-champ-cone size-up to extract a PDN from"
    mapped = (host.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, "IR-cell-champ-cone netlist missing for write_pg_spice"
    ice = ir_cell_champ_extract_cand(mem)
    if ice is None:
        return False, "no IR-cell-champ extract to residual the cone mesh against"
    if str((ice.knobs or {}).get("parent_id") or "") == host.id:
        return False, "IR-cell-champ-cone is already the champ-extract parent"
    host_eid = str((host.knobs or {}).get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == host_eid
        for c in mem.by_level("pdn")
    ):
        return False, "already have an IR-cell-champ-cone write_pg_spice mesh on this extract"
    nch = (host.artifacts or {}).get("n_changed") or len((host.knobs or {}).get("cells") or [])
    mods = ",".join(
        dict.fromkeys(
            str(x).split("/")[0]
            for x in (host.knobs or {}).get("cells") or []
            if "/" in str(x)
        )
    ) or "unjoined"
    return True, (
        f"write_pg_spice on IR-cell-champ-cone {mods} n={nch} — leftover-cone netlist IR residual "
        "vs IR-cell-champ extract, not host extract, not gold, not ABC"
    )


def should_pay_ir_cell_champ_cone_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the leftover-cone extract. Not champ IR-steer."""
    if n_steer >= steer_max:
        return False, "IR-cell-champ-cone PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell-champ-cone PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no IR-cell-champ-cone residual-steered PDN action (need a 1× residual)"
    if str(steer.get("host_source") or "") != "f4_ir_cell_champ_cone_extract":
        return False, "IR-cell-champ-cone PDN restamp refuses a champ/host/IR-cell extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the IR-cell-champ-cone extract"
    return True, str(
        steer.get("reason")
        or "IR-cell-champ-cone residual steers a PDN restamp on the leftover-cone mesh"
    )


def should_pay_ir_cell_champ_cone_region(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay density-cap write_pg_spice on the leftover-cone 1× bin. Not IR-cell-region rXY."""
    if n_extract >= extract_max:
        return False, "IR-cell-champ-cone-region extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover leftover-cone-region write_pg_spice"
    if not steer or steer.get("level") != "ir_cell_champ_cone_region":
        return False, "no leftover-cone hotspot residual (need a seq-heavy bin ≠ champ extract)"
    src = str(steer.get("host_source") or "")
    if src not in ("f4_ir_cell_champ_cone_extract", "f4_ir_cell_champ_cone_region_extract"):
        return False, "leftover-cone region refuses a champ/host/IR-cell extract"
    from pathlib import Path

    from .active import ir_cell_champ_cone_host
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = ir_cell_champ_cone_host(mem)
    mapped = (host.artifacts or {}).get("mapped_v") if host else None
    if not host or not mapped or not Path(mapped).is_file():
        return False, "leftover-cone netlist missing for a region extract"
    cone_eid = str(steer.get("extract_id") or "")
    region = steer.get("region") or "xy"
    hid = host.id
    if any(
        (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract"
        and c.status == "ok"
        and (
            str((c.knobs or {}).get("parent_extract_id") or "") == cone_eid
            or (
                str((c.knobs or {}).get("region") or "") == str(region)
                and str((c.knobs or {}).get("parent_id") or c.parent_id or "") == str(hid)
            )
        )
        for c in mem.by_level("pdn")
    ):
        return False, "already have a leftover-cone-region write_pg_spice mesh on this extract"
    return True, str(
        steer.get("reason")
        or (
            f"leftover-cone 1× hotspot {region} steers a region density cap — "
            "not more combo size-up, not IR-cell-region, not gold"
        )
    )


def should_pay_ir_cell_champ_cone_region_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the leftover-cone-region extract. Not cone IR-steer."""
    if n_steer >= steer_max:
        return False, "IR-cell-champ-cone-region PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover leftover-cone-region PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no leftover-cone-region residual-steered PDN action (need |Δ| ≥ 1 mV)"
    if str(steer.get("host_source") or "") != "f4_ir_cell_champ_cone_region_extract":
        return False, "leftover-cone-region PDN restamp refuses a cone/champ/host extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the leftover-cone-region extract"
    return True, str(
        steer.get("reason")
        or "leftover-cone-region residual steers a PDN restamp on the capped leftover mesh"
    )


def leftover_cone_region_next(
    mem: DesignMemory,
    *,
    budget_left: float,
) -> dict | None:
    """Next leftover-cone-region extract or PDN. Closed-loop inspect, not one-pass."""
    from .active import (
        steer_from_ir_cell_champ_cone_hotspot,
        steer_from_ir_cell_champ_cone_region_hotspot,
        steer_from_ir_cell_champ_cone_region_residual,
    )

    steer = steer_from_ir_cell_champ_cone_region_hotspot(mem) or steer_from_ir_cell_champ_cone_hotspot(
        mem
    )
    eid = str((steer or {}).get("extract_id") or "")
    n_extract = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == eid
    )
    pay, why = should_pay_ir_cell_champ_cone_region(
        mem, budget_left=budget_left, steer=steer, n_extract=n_extract
    )
    if pay:
        return {"kind": "extract", "steer": steer, "why": why}
    steer_p = steer_from_ir_cell_champ_cone_region_residual(mem)
    eid_p = str((steer_p or {}).get("extract_id") or "")
    n_steer = sum(
        1
        for c in mem.all()
        if (c.attr or {}).get("via") == "active_f4_ir_cell_champ_cone_region_pdn"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == eid_p
    )
    pay_p, why_p = should_pay_ir_cell_champ_cone_region_pdn(
        mem, budget_left=budget_left, steer=steer_p, n_steer=n_steer
    )
    if pay_p:
        return {"kind": "pdn", "steer": steer_p, "why": why_p}
    return None


def should_pay_winning_ir_region(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay density-cap write_pg_spice on the winning-IR 1× bin. Not leftover-cone rXY."""
    if n_extract >= extract_max:
        return False, "winning-IR-region extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region write_pg_spice"
    if not steer or steer.get("level") != "winning_ir_region":
        return False, "no winning-IR hotspot residual (need a seq-heavy bin ≠ IR-cell-region)"
    src = str(steer.get("host_source") or "")
    if src not in (
        "f4_em_strap_extract",
        "f4_static_strap_extract",
        "f4_ir_cell_extract",
        "f4_ir_cell_champ_extract",
        "f4_winning_ir_region_extract",
        "f4_host_extract",
        "f4_host_region_extract",
    ):
        return False, "winning-IR region refuses leftover-cone / IR-cell-region flatten"
    from pathlib import Path

    from .active import ir_cell_host, ir_cell_region_extract_cand
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = ir_cell_host(mem)
    mapped = (host.artifacts or {}).get("mapped_v") if host else None
    if not host or not mapped or not Path(mapped).is_file():
        return False, "IR-cell netlist missing for a winning-IR region extract"
    eid = str(steer.get("extract_id") or "")
    region = steer.get("region") or "xy"
    ice_r = ir_cell_region_extract_cand(mem)
    ice_bin = (ice_r.knobs or {}).get("region") if ice_r else None
    if region and ice_bin and str(region) == str(ice_bin):
        return False, "winning-IR region refuses the IR-cell-region bin"
    hid = host.id
    if any(
        (c.knobs or {}).get("source") == "f4_winning_ir_region_extract"
        and c.status == "ok"
        and (
            str((c.knobs or {}).get("parent_extract_id") or "") == eid
            or (
                str((c.knobs or {}).get("region") or "") == str(region)
                and str((c.knobs or {}).get("parent_id") or c.parent_id or "") == str(hid)
            )
        )
        for c in mem.by_level("pdn")
    ):
        return False, "already have a winning-IR-region write_pg_spice mesh on this extract"
    return True, str(
        steer.get("reason")
        or (
            f"winning-IR 1× hotspot {region} steers a region density cap — "
            "not leftover-cone-region, not more combo size-up, not gold"
        )
    )


def should_pay_winning_ir_region_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the winning-IR-region extract."""
    if n_steer >= steer_max:
        return False, "winning-IR-region PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no winning-IR-region residual-steered PDN action (need |Δ| ≥ 1 mV)"
    if str(steer.get("host_source") or "") != "f4_winning_ir_region_extract":
        return False, "winning-IR-region PDN restamp refuses leftover-cone / host extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the winning-IR-region extract"
    return True, str(
        steer.get("reason")
        or "winning-IR-region residual steers a PDN restamp on the capped winning-IR mesh"
    )


def winning_ir_region_next(
    mem: DesignMemory,
    *,
    budget_left: float,
) -> dict | None:
    """Next winning-IR-region extract or PDN. Closed-loop inspect, not one-pass."""
    from .active import (
        steer_from_winning_ir_hotspot,
        steer_from_winning_ir_region_hotspot,
        steer_from_winning_ir_region_residual,
    )

    steer = steer_from_winning_ir_region_hotspot(mem) or steer_from_winning_ir_hotspot(mem)
    eid = str((steer or {}).get("extract_id") or "")
    n_extract = sum(
        1
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_winning_ir_region_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == eid
    )
    pay, why = should_pay_winning_ir_region(
        mem, budget_left=budget_left, steer=steer, n_extract=n_extract
    )
    if pay:
        return {"kind": "extract", "steer": steer, "why": why}
    steer_p = steer_from_winning_ir_region_residual(mem)
    eid_p = str((steer_p or {}).get("extract_id") or "")
    n_steer = sum(
        1
        for c in mem.all()
        if (c.attr or {}).get("via") == "active_f4_winning_ir_region_pdn"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == eid_p
    )
    pay_p, why_p = should_pay_winning_ir_region_pdn(
        mem, budget_left=budget_left, steer=steer_p, n_steer=n_steer
    )
    if pay_p:
        return {"kind": "pdn", "steer": steer_p, "why": why_p}
    return None


def should_pay_winning_ir_region_cell(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_cell: int = 0,
    cell_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay leftover combo drive-up on the winning-IR-region PDN join. Not leftover-cone."""
    if n_cell >= cell_max:
        return False, "winning-IR-region-cell size shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region-cell STA"
    if not steer or steer.get("level") != "winning_ir_region_cell":
        return False, "no winning-IR-region-cell residual (need leftover combo cells ≠ leftover-cone)"
    src = str(steer.get("host_source") or "")
    if src not in ("f4_winning_ir_region_extract", "active_f4_winning_ir_region_pdn"):
        return False, "winning-IR-region-cell refuses leftover-cone / champ flatten"
    eid = str(steer.get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "cell_size_ir_winning_region"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == eid
        for c in mem.by_level("cell")
    ):
        return False, "already have a winning-IR-region-cell size child on this extract"
    cells = [str(x) for x in steer.get("cells") or []]
    if len(cells) < 1:
        return False, "winning-IR-region-cell join has no leftover cells"
    if not steer.get("modules"):
        return False, "winning-IR-region-cell join has no module — not inventing a cone"
    from pathlib import Path

    from .active import ir_cell_champ_cone_host, ir_cell_champ_host, ir_cell_host

    host = ir_cell_host(mem)
    mapped = None
    if host:
        mapped = (host.artifacts or {}).get("mapped_hier_v") or (host.artifacts or {}).get("mapped_v")
    if not host or not mapped or not Path(mapped).is_file():
        return False, "IR-cell netlist missing — not flattening winning-IR-region-cell onto leftover-cone"
    sized = set()
    for h in (host, ir_cell_champ_host(mem), ir_cell_champ_cone_host(mem)):
        if h is None:
            continue
        sized.update(str(x) for x in (h.knobs or {}).get("cells") or [])
    if sized and set(cells) <= sized:
        return False, "winning-IR-region-cell cells already covered by IR-cell / champ / leftover-cone"
    mods = ",".join(steer.get("modules") or [])
    region = steer.get("region") or "unjoined"
    return True, str(
        steer.get("reason")
        or (
            f"upsize {len(cells)} leftover {mods} cells on winning-IR-region PDN region {region} — "
            "not leftover-cone, not champ ctrl, not first IR-cell, not STA path, not ABC, not VCD"
        )
    )


def should_pay_winning_ir_region_cell_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay write_pg_spice on the winning-IR-region leftover-combo netlist."""
    if n_extract >= extract_max:
        return False, "winning-IR-region-cell PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region-cell write_pg_spice"
    from pathlib import Path

    from .active import winning_ir_region_cell_host, winning_ir_region_extract_cand
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = winning_ir_region_cell_host(mem)
    if host is None:
        return False, "no winning-IR-region-cell size-up to extract a PDN from"
    mapped = (host.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, "winning-IR-region-cell netlist missing for write_pg_spice"
    reg = winning_ir_region_extract_cand(mem)
    if reg is None:
        return False, "no winning-IR-region extract to residual the leftover-combo mesh against"
    if str((reg.knobs or {}).get("parent_id") or "") == host.id:
        return False, "winning-IR-region-cell is already the region-extract parent"
    host_eid = str((host.knobs or {}).get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == host_eid
        for c in mem.by_level("pdn")
    ):
        return False, "already have a winning-IR-region-cell write_pg_spice mesh on this extract"
    nch = (host.artifacts or {}).get("n_changed") or len((host.knobs or {}).get("cells") or [])
    mods = ",".join(
        dict.fromkeys(
            str(x).split("/")[0]
            for x in (host.knobs or {}).get("cells") or []
            if "/" in str(x)
        )
    ) or "unjoined"
    return True, (
        f"write_pg_spice on winning-IR-region-cell {mods} n={nch} — leftover-combo IR residual "
        "vs winning-IR-region extract, not leftover-cone, not gold, not ABC"
    )


def should_pay_winning_ir_region_cell_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the winning-IR-region-cell extract."""
    if n_steer >= steer_max:
        return False, "winning-IR-region-cell PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region-cell PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no winning-IR-region-cell residual-steered PDN action (need a 1× residual)"
    if str(steer.get("host_source") or "") != "f4_winning_ir_region_cell_extract":
        return False, "winning-IR-region-cell PDN restamp refuses leftover-cone / region extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the winning-IR-region-cell extract"
    return True, str(
        steer.get("reason")
        or "winning-IR-region-cell residual steers a PDN restamp on the leftover-combo mesh"
    )


def should_pay_winning_ir_region_cell_leftover(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_cell: int = 0,
    cell_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay leftover drive-up on the leftover-combo PDN join. Not leftover-combo flatten."""
    if n_cell >= cell_max:
        return False, "winning-IR-region-cell leftover size shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region-cell leftover STA"
    if not steer or steer.get("level") != "winning_ir_region_cell_leftover":
        return False, "no winning-IR-region-cell leftover residual (need leftover combo cells ≠ leftover-combo)"
    src = str(steer.get("host_source") or "")
    if src not in ("f4_winning_ir_region_cell_extract", "active_f4_winning_ir_region_cell_pdn"):
        return False, "winning-IR-region-cell leftover refuses leftover-cone / region flatten"
    eid = str(steer.get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover"
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == eid
        for c in mem.by_level("cell")
    ):
        return False, "already have a winning-IR-region-cell leftover size child on this extract"
    cells = [str(x) for x in steer.get("cells") or []]
    if len(cells) < 1:
        return False, "winning-IR-region-cell leftover join has no leftover cells"
    if not steer.get("modules"):
        return False, "winning-IR-region-cell leftover join has no module — not inventing a cone"
    from pathlib import Path

    from .active import (
        ir_cell_champ_cone_host,
        ir_cell_champ_host,
        ir_cell_host,
        winning_ir_region_cell_host,
    )

    host = winning_ir_region_cell_host(mem)
    mapped = None
    if host:
        mapped = (host.artifacts or {}).get("mapped_hier_v") or (host.artifacts or {}).get("mapped_v")
    if not host or not mapped or not Path(mapped).is_file():
        return False, "leftover-combo netlist missing — not flattening leftover onto IR-cell host"
    sized = set()
    for h in (host, ir_cell_host(mem), ir_cell_champ_host(mem), ir_cell_champ_cone_host(mem)):
        if h is None:
            continue
        sized.update(str(x) for x in (h.knobs or {}).get("cells") or [])
    if sized and set(cells) <= sized:
        return False, "winning-IR-region-cell leftover cells already covered by leftover-combo / IR-cell / champ / leftover-cone"
    mods = ",".join(steer.get("modules") or [])
    region = steer.get("region") or "unjoined"
    return True, str(
        steer.get("reason")
        or (
            f"upsize {len(cells)} leftover {mods} cells on leftover-combo PDN region {region} — "
            "not leftover-combo flatten, not leftover-cone, not champ ctrl, not first IR-cell, not STA path, not ABC, not VCD"
        )
    )


def should_pay_winning_ir_region_cell_leftover_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay write_pg_spice on the leftover-combo leftover netlist."""
    if n_extract >= extract_max:
        return False, "winning-IR-region-cell leftover PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region-cell leftover write_pg_spice"
    from pathlib import Path

    from .active import winning_ir_region_cell_extract_cand, winning_ir_region_cell_leftover_host
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = winning_ir_region_cell_leftover_host(mem)
    if host is None:
        return False, "no winning-IR-region-cell leftover size-up to extract a PDN from"
    mapped = (host.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, "winning-IR-region-cell leftover netlist missing for write_pg_spice"
    ice = winning_ir_region_cell_extract_cand(mem)
    if ice is None:
        return False, "no leftover-combo extract to residual the leftover mesh against"
    if str((ice.knobs or {}).get("parent_id") or "") == host.id:
        return False, "winning-IR-region-cell leftover is already the cell-extract parent"
    host_eid = str((host.knobs or {}).get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover_extract"
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == host_eid
        for c in mem.by_level("pdn")
    ):
        return False, "already have a winning-IR-region-cell leftover write_pg_spice mesh on this extract"
    nch = (host.artifacts or {}).get("n_changed") or len((host.knobs or {}).get("cells") or [])
    mods = ",".join(
        dict.fromkeys(
            str(x).split("/")[0]
            for x in (host.knobs or {}).get("cells") or []
            if "/" in str(x)
        )
    ) or "unjoined"
    return True, (
        f"write_pg_spice on winning-IR-region-cell leftover {mods} n={nch} — leftover-combo leftover "
        "IR residual vs leftover-combo extract, not leftover-cone, not gold, not ABC"
    )


def should_pay_winning_ir_region_cell_leftover_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the leftover-combo leftover extract."""
    if n_steer >= steer_max:
        return False, "winning-IR-region-cell leftover PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR-region-cell leftover PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no winning-IR-region-cell leftover residual-steered PDN action (need a 1× residual)"
    if str(steer.get("host_source") or "") != "f4_winning_ir_region_cell_leftover_extract":
        return False, "winning-IR-region-cell leftover PDN restamp refuses leftover-combo / leftover-cone extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the winning-IR-region-cell leftover extract"
    return True, str(
        steer.get("reason")
        or "winning-IR-region-cell leftover residual steers a PDN restamp on the leftover mesh"
    )


def should_pay_ir_cell_extract(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay write_pg_spice on the IR-cell-sized netlist. Residual vs host extract."""
    if n_extract >= extract_max:
        return False, "IR-cell PDN extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell write_pg_spice"
    from pathlib import Path

    from .active import ir_cell_host
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = ir_cell_host(mem)
    if host is None:
        return False, "no IR-cell size-up to extract a PDN from"
    mapped = (host.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, "IR-cell netlist missing for write_pg_spice"
    host_ext = latest_host_extract_cand(mem)
    if host_ext is None:
        return False, "no host extract to residual the IR-cell mesh against"
    if str((host_ext.knobs or {}).get("parent_id") or "") == host.id:
        return False, "IR-cell is already the host-extract parent"
    if any(
        (c.knobs or {}).get("source") == "f4_ir_cell_extract" and c.status == "ok"
        for c in mem.by_level("pdn")
    ):
        return False, "already have an IR-cell write_pg_spice mesh"
    nch = (host.artifacts or {}).get("n_changed") or len((host.knobs or {}).get("cells") or [])
    mods = ",".join(
        dict.fromkeys(
            str(x).split("/")[0]
            for x in (host.knobs or {}).get("cells") or []
            if "/" in str(x)
        )
    ) or "unjoined"
    return True, (
        f"write_pg_spice on IR-cell {mods} n={nch} — sized netlist IR residual "
        "vs host extract, not gold, not ABC, not STA-only"
    )


def should_pay_ir_cell_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the IR-cell extract. Not host IR-steer."""
    if n_steer >= steer_max:
        return False, "IR-cell PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no IR-cell residual-steered PDN action (need a 1× residual)"
    if str(steer.get("host_source") or "") != "f4_ir_cell_extract":
        return False, "IR-cell PDN restamp refuses a host/candidate extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the IR-cell extract"
    return True, str(steer.get("reason") or "IR-cell residual steers a PDN restamp on the sized mesh")


def should_pay_ir_cell_region(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_extract: int = 0,
    extract_max: int = 1,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    """Pay density-cap write_pg_spice on the IR-cell 1× bin. Not host-region rXY."""
    if n_extract >= extract_max:
        return False, "IR-cell region extract already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell-region write_pg_spice"
    if not steer or steer.get("level") != "ir_cell_region":
        return False, "no IR-cell hotspot residual (need a seq-heavy bin ≠ host)"
    if str(steer.get("host_source") or "") != "f4_ir_cell_extract":
        return False, "IR-cell region refuses a host/candidate extract"
    from pathlib import Path

    from .active import ir_cell_host
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    host = ir_cell_host(mem)
    mapped = (host.artifacts or {}).get("mapped_v") if host else None
    if not host or not mapped or not Path(mapped).is_file():
        return False, "IR-cell netlist missing for a region extract"
    if any(
        (c.knobs or {}).get("source") == "f4_ir_cell_region_extract" and c.status == "ok"
        for c in mem.by_level("pdn")
    ):
        return False, "already have an IR-cell-region write_pg_spice mesh"
    return True, str(steer.get("reason") or "IR-cell 1× hotspot steers a region density cap")


def should_pay_ir_cell_region_pdn(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    """Pay the winning PDN family on the IR-cell-region extract. Not host IR-steer."""
    if n_steer >= steer_max:
        return False, "IR-cell-region PDN restamp already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover IR-cell-region PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no IR-cell-region residual-steered PDN action (need |Δ| ≥ 1 mV)"
    if str(steer.get("host_source") or "") != "f4_ir_cell_region_extract":
        return False, "IR-cell-region PDN restamp refuses a host/candidate/1× extract"
    spec = steer["spec"]
    from .pdn_space import measured_pdn_keys

    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that PDN point is already measured on the IR-cell-region extract"
    return True, str(steer.get("reason") or "IR-cell-region residual steers a PDN restamp")


def should_pay_net_buffer(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_net: int = 0,
    net_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one BUF insert on attributed worst-path hops. Not more ABC."""
    if n_net >= net_max:
        return False, "net-local buffer shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover net-local STA"
    if any((c.knobs or {}).get("source") == "net_buffer" and c.status == "ok" for c in mem.by_level("net")):
        return False, "already have a net-local buffer child"
    hops = _attributed_path_nets(mem)
    if len(hops) < 1:
        return False, "no attributed STA path hops to buffer"
    return True, f"insert BUF on {len(hops)} attributed worst-path hops — not ABC, not a chip restart"


def should_pay_net_port(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_net: int = 0,
    n_port: int = 0,
    port_max: int = 1,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    """Pay one parent-scoped BUF on ctrl↔dpath port nets. Not intra-module hops."""
    if n_port >= port_max:
        return False, "port-net buffer shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover port-net STA"
    if any(
        (c.knobs or {}).get("source") == "net_buffer_port" and c.status == "ok" for c in mem.by_level("net")
    ):
        return False, "already have a port-net buffer child"
    have_intra = n_net >= 1 or any(
        (c.knobs or {}).get("source") == "net_buffer" and c.status == "ok" for c in mem.by_level("net")
    )
    if not have_intra:
        return False, "port-net waits for the intra-module net shot"
    hops = _attributed_cross_module_nets(mem)
    if not hops:
        return False, "no attributed cross-module hops (ctrl↔dpath ports)"
    from .net_space import hop_is_block_port

    n_block = sum(1 for h in hops if hop_is_block_port(h))
    return True, (
        f"insert BUF on {n_block or len(hops)} port-net hops at the parent "
        "— not intra-module, not ABC, not a chip restart"
    )


def _attributed_cross_module_nets(mem: DesignMemory) -> list[str]:
    """Prefer ctrl↔dpath port hops over later flatten/submodule-only paths."""
    from .net_space import hop_is_block_port, hop_is_cross_module

    fallback: list[str] = []
    for c in reversed(list(mem.all())):
        if c.status != "ok":
            continue
        art = c.artifacts or {}
        hops = [h for h in (art.get("path_nets") or []) if isinstance(h, str)]
        if not hops:
            hops = [h for h in ((c.attr or {}).get("nets") or []) if isinstance(h, str)]
        block = [h for h in hops if hop_is_block_port(h)]
        if block:
            return block
        cross = [h for h in hops if hop_is_cross_module(h)]
        if cross and not fallback:
            fallback = cross
    return fallback


def _attributed_path_nets(mem: DesignMemory) -> list[str]:
    for c in reversed(list(mem.all())):
        if c.status != "ok":
            continue
        art = c.artifacts or {}
        hops = [h for h in (art.get("path_nets") or []) if isinstance(h, str) and "->" in h]
        if hops:
            return hops
        attr = c.attr or {}
        hops = [h for h in (attr.get("nets") or []) if isinstance(h, str) and "->" in h]
        if hops and attr.get("kind") == "sta_path":
            return hops
    return []


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


def _solver_on_extract(mem: DesignMemory, source: str, extract_id: str) -> bool:
    want = str(extract_id)
    return any(
        c.status == "ok"
        and (c.knobs or {}).get("source") == source
        and str((c.knobs or {}).get("extract_id") or "finish") == want
        for c in mem.by_level("pdn")
    )


def champ_mf_n(mem: DesignMemory, via: str) -> int:
    """Champion MF shots already paid on the *current* winning_ir extract."""
    from .active import winning_ir_pdn

    champ = winning_ir_pdn(mem)
    if champ is None:
        return 0
    eid = str((champ.knobs or {}).get("extract_id") or champ.id)
    return sum(
        1
        for c in mem.by_level("pdn")
        if c.status == "ok"
        and (c.attr or {}).get("via") == via
        and str((c.knobs or {}).get("extract_id") or "") == eid
    )


def champ_mf_target(
    mem: DesignMemory, *, variant: str = "flowlab"
) -> tuple[object | None, str, str]:
    """winning_ir_pdn extract for an MF solver residual. Not finish, not candidate."""
    from .active import winning_ir_pdn
    from .f4_oracle import available

    champ = winning_ir_pdn(mem)
    if champ is None:
        return None, "", "no 1× IR champion to restamp with an MF solver"
    eid = str((champ.knobs or {}).get("extract_id") or champ.id)
    if eid in ("finish", ""):
        return None, eid, "champion MF solver refuses the gold finish extract"
    cand = latest_ok_extract(mem)
    if cand and str(cand.get("extract_id") or "") == eid:
        return None, eid, "champion mesh is already the candidate extract — MF residual already measured there"
    if not extract_on_disk(mem, eid) and not available(variant):
        return None, eid, "champion extract is not on disk"
    return champ, eid, ""


def should_pay_f4_amg_champ(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_amg: int = 0,
    amg_max: int = 1,
    min_s: float = 6.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """SA-AMG on winning_ir_pdn with the same DirectLU knobs. Not candidate AMG, not gold."""
    if n_amg >= amg_max:
        return False, "champion AMG shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover champion AMG"
    champ, eid, why = champ_mf_target(mem, variant=variant)
    if champ is None:
        return False, why
    if _solver_on_extract(mem, "f4_solver_amg", eid):
        return False, "this champion extract already has an AMG child"
    src = (champ.knobs or {}).get("name") or (champ.attr or {}).get("via")
    return True, (
        f"SA-AMG on winning_ir_pdn {src} {float(champ.qor.dynamic_ir_mv):.3f} mV "
        f"extract {eid} — same DirectLU knobs, not candidate AMG, not gold"
    )


def should_pay_f4_ras_champ(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_ras: int = 0,
    ras_max: int = 1,
    min_s: float = 8.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """RAS on winning_ir_pdn after AMG on the same extract. Not candidate RAS, not gold."""
    if n_ras >= ras_max:
        return False, "champion RAS shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover champion RAS"
    champ, eid, why = champ_mf_target(mem, variant=variant)
    if champ is None:
        return False, why
    if not _solver_on_extract(mem, "f4_solver_amg", eid):
        return False, "champion AMG residual not yet measured on this extract"
    if _solver_on_extract(mem, "f4_solver_ras", eid):
        return False, "this champion extract already has a RAS child"
    src = (champ.knobs or {}).get("name") or (champ.attr or {}).get("via")
    return True, (
        f"RAS on winning_ir_pdn {src} {float(champ.qor.dynamic_ir_mv):.3f} mV "
        f"extract {eid} — domain-decomp after champion AMG, not candidate RAS, not gold"
    )


def should_pay_f4_krylov_champ(
    mem: DesignMemory,
    *,
    budget_left: float,
    n_krylov: int = 0,
    krylov_max: int = 1,
    min_s: float = 10.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """Krylov/MOR on winning_ir_pdn after RAS on the same extract. Not candidate Krylov, not gold."""
    if n_krylov >= krylov_max:
        return False, "champion Krylov shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover champion Krylov/MOR"
    champ, eid, why = champ_mf_target(mem, variant=variant)
    if champ is None:
        return False, why
    if not _solver_on_extract(mem, "f4_solver_ras", eid):
        return False, "champion RAS residual not yet measured on this extract"
    if _solver_on_extract(mem, "f4_solver_krylov", eid):
        return False, "this champion extract already has a Krylov/MOR child"
    src = (champ.knobs or {}).get("name") or (champ.attr or {}).get("via")
    return True, (
        f"Krylov/MOR on winning_ir_pdn {src} {float(champ.qor.dynamic_ir_mv):.3f} mV "
        f"extract {eid} — reduced-order after champion RAS, not candidate Krylov, not gold"
    )


def should_pay_static_ir_steer(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 8.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """Pay unused pkg_r on winning_static_pdn. Not decap, not pkg L, not Dynamic IR-steer."""
    if n_steer >= steer_max:
        return False, "static-IR pkg_r shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover static-IR pkg_r restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no static-IR residual-steered pkg_r action"
    spec = steer["spec"]
    from .pdn_space import PDN_CATALOG, measured_pdn_keys

    if str(spec.get("name") or "") in {s["name"] for s in PDN_CATALOG}:
        return False, "static-IR steer refuses a Dynamic IR / decap / pkg L catalog point"
    if abs(float(spec.get("pkg_r") or 0.05) - 0.05) < 1e-12:
        return False, "static-IR steer requires a pkg_r delta, not gold 50 mΩ"
    eid = str(steer["extract_id"])
    if eid in ("finish", ""):
        return False, "static-IR steer refuses the gold finish extract"
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that pkg_r point is already measured on the static-IR extract"
    from .f4_oracle import available

    if not extract_on_disk(mem, eid) and not available(variant):
        return False, "static-IR champion extract is not on disk"
    return True, str(steer.get("reason") or "static IR steers unused pkg_r — not decap, not gold")


def should_pay_static_mesh(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 12.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """Pay denser bumps on the static-IR champ ODB after a null pkg_r residual."""
    from pathlib import Path

    if n_steer >= steer_max:
        return False, "static-IR bump mesh shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover static-IR bump restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no static-IR residual-steered bump action"
    spec = steer["spec"]
    from .pdn_space import PDN_CATALOG, STATIC_PDN_CATALOG

    names = {s["name"] for s in PDN_CATALOG} | {s["name"] for s in STATIC_PDN_CATALOG}
    if str(spec.get("name") or "") in names:
        return False, "static-IR mesh refuses a pkg_r / decap / pkg L catalog point"
    if spec.get("bump_dx") is None:
        return False, "static-IR mesh requires a bump_dx delta, not a PDN restamp"
    eid = str(steer["extract_id"])
    if eid in ("finish", ""):
        return False, "static-IR mesh refuses the gold finish extract"
    odb = steer.get("odb")
    if not odb or not Path(odb).is_file():
        return False, "static-IR champion ODB is not on disk"
    return True, str(steer.get("reason") or "static IR steers unused bump pitch — not pkg_r, not gold")


def should_pay_static_straps(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 12.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """Pay denser metal4 straps after a null bump residual. Not bumps, not pkg_r."""
    from pathlib import Path

    if n_steer >= steer_max:
        return False, "static-IR strap mesh shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover static-IR strap restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no static-IR residual-steered strap action"
    spec = steer["spec"]
    from .pdn_space import EM_STRAP_CATALOG, PDN_CATALOG, STATIC_MESH_CATALOG, STATIC_PDN_CATALOG

    names = (
        {s["name"] for s in PDN_CATALOG}
        | {s["name"] for s in STATIC_PDN_CATALOG}
        | {s["name"] for s in STATIC_MESH_CATALOG}
        | {s["name"] for s in EM_STRAP_CATALOG}
    )
    if str(spec.get("name") or "") in names:
        return False, "static-IR straps refuse a bump / pkg_r / decap / pkg L catalog point"
    if spec.get("m4_pitch") is None:
        return False, "static-IR straps require an m4_pitch delta, not a bump restamp"
    eid = str(steer["extract_id"])
    if eid in ("finish", ""):
        return False, "static-IR straps refuse the gold finish extract"
    odb = steer.get("odb")
    if not odb or not Path(odb).is_file():
        return False, "static-IR champion ODB is not on disk"
    return True, str(steer.get("reason") or "static IR steers unused metal4 pitch — not bumps, not gold")


def should_pay_em_straps(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 1,
    min_s: float = 12.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """Pay wider metal4 after strap pitch is measured. Not pitch, not decap."""
    from pathlib import Path

    if n_steer >= steer_max:
        return False, "EM strap-width shot already spent"
    if budget_left < min_s:
        return False, "wall budget would not cover EM width restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no EM residual-steered width action"
    spec = steer["spec"]
    from .pdn_space import PDN_CATALOG, STATIC_MESH_CATALOG, STATIC_PDN_CATALOG, STATIC_STRAP_CATALOG

    names = (
        {s["name"] for s in PDN_CATALOG}
        | {s["name"] for s in STATIC_PDN_CATALOG}
        | {s["name"] for s in STATIC_MESH_CATALOG}
        | {s["name"] for s in STATIC_STRAP_CATALOG}
    )
    if str(spec.get("name") or "") in names:
        return False, "EM width refuses a pitch / bump / pkg_r / decap catalog point"
    if spec.get("m4_width") is None:
        return False, "EM width requires an m4_width delta, not a pitch restamp"
    eid = str(steer["extract_id"])
    if eid in ("finish", ""):
        return False, "EM width refuses the gold finish extract"
    odb = steer.get("odb")
    if not odb or not Path(odb).is_file():
        return False, "EM strap host ODB is not on disk"
    return True, str(steer.get("reason") or "EM steers unused metal4 width — not pitch, not gold")


def should_pay_winning_ir_catalog(
    mem: DesignMemory,
    *,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 2,
    min_s: float = 8.0,
    variant: str = "flowlab",
) -> tuple[bool, str]:
    """Pay unused Dynamic IR catalog on a strap/EM winning_ir extract.

    Shot 1: unused C (decap) with host pkg_r/L. Shot 2: unused pkg L with
    host pkg_r/C. Not pitch, not width, not static pkg_r, not gold.
    """
    if n_steer >= steer_max:
        return False, "winning-IR Dynamic IR catalog spent (decap + unused pkg L)"
    if budget_left < min_s:
        return False, "wall budget would not cover winning-IR catalog restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, "no winning-IR unused Dynamic IR catalog action"
    spec = steer["spec"]
    from .pdn_space import (
        EM_STRAP_CATALOG,
        PDN_CATALOG,
        STATIC_MESH_CATALOG,
        STATIC_PDN_CATALOG,
        STATIC_STRAP_CATALOG,
        measured_pdn_keys,
    )

    name = str(spec.get("name") or "")
    refuse = (
        {s["name"] for s in STATIC_PDN_CATALOG}
        | {s["name"] for s in STATIC_MESH_CATALOG}
        | {s["name"] for s in STATIC_STRAP_CATALOG}
        | {s["name"] for s in EM_STRAP_CATALOG}
    )
    if name in refuse:
        return False, "winning-IR catalog refuses a pitch / width / bump / pkg_r point"
    if name not in {s["name"] for s in PDN_CATALOG}:
        return False, "winning-IR catalog requires a Dynamic IR catalog point"
    if spec.get("m4_pitch") is not None or spec.get("m4_width") is not None or spec.get("bump_dx") is not None:
        return False, "winning-IR catalog refuses a geometry restamp"
    eid = str(steer["extract_id"])
    if eid in ("finish", ""):
        return False, "winning-IR catalog refuses the gold finish extract"
    from .active import extract_is_new_rgraph

    if not extract_is_new_rgraph(mem, eid):
        return False, "winning-IR catalog refuses a host/candidate mesh (not a new R-graph)"
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, "that Dynamic IR point is already measured on the winning-IR extract"
    return True, str(steer.get("reason") or "winning_ir unused Dynamic IR catalog — not pitch, not gold")


def latest_ok_extract(mem: DesignMemory) -> dict | None:
    """Most recent successful candidate write_pg_spice (spice+insts on disk)."""
    return _latest_extract(mem, source="f4_candidate_extract")


def latest_ok_host_extract(mem: DesignMemory) -> dict | None:
    """Most recent write_pg_spice of the attributed host netlist."""
    return _latest_extract(mem, source="f4_host_extract")


def latest_ok_host_region_extract(mem: DesignMemory) -> dict | None:
    """Most recent host-bin density-cap write_pg_spice. Not the unconstrained host mesh."""
    return _latest_extract(mem, source="f4_host_region_extract")


def latest_ok_region_extract(mem: DesignMemory) -> dict | None:
    """Most recent successful IR-bin write_pg_spice (spice+insts on disk)."""
    return _latest_extract(mem, source="f4_region_extract")


def _latest_extract(mem: DesignMemory, *, source: str) -> dict | None:
    from pathlib import Path

    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok" or (c.knobs or {}).get("source") != source:
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
                "odb": art.get("odb")
                if art.get("odb") and Path(str(art.get("odb"))).is_file()
                else (
                    str(Path(spice).parent / "candidate.odb")
                    if spice and (Path(spice).parent / "candidate.odb").is_file()
                    else None
                ),
            }
    return None


def extract_on_disk(mem: DesignMemory, extract_id: str) -> dict | None:
    """Resolve spice+insts for a named extract (candidate or region)."""
    want = str(extract_id)
    for src in (
        "f4_region_extract",
        "f4_candidate_extract",
        "f4_host_extract",
        "f4_host_region_extract",
        "f4_ir_cell_extract",
        "f4_ir_cell_region_extract",
        "f4_ir_cell_champ_extract",
        "f4_ir_cell_champ_cone_extract",
        "f4_ir_cell_champ_cone_region_extract",
        "f4_winning_ir_region_extract",
        "f4_winning_ir_region_cell_extract",
        "f4_winning_ir_region_cell_leftover_extract",
        "f4_static_mesh_extract",
        "f4_static_strap_extract",
        "f4_em_strap_extract",
    ):
        hit = _latest_extract(mem, source=src)
        if hit and str(hit["extract_id"]) == want:
            return hit
        # _latest_extract only returns the newest of that source; scan all.
    from pathlib import Path

    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok":
            continue
        if str((c.knobs or {}).get("extract_id") or c.id) != want:
            continue
        if (c.knobs or {}).get("source") not in (
            "f4_candidate_extract",
            "f4_region_extract",
            "f4_host_extract",
            "f4_host_region_extract",
            "f4_ir_cell_extract",
            "f4_ir_cell_region_extract",
            "f4_ir_cell_champ_extract",
            "f4_ir_cell_champ_cone_extract",
            "f4_ir_cell_champ_cone_region_extract",
            "f4_winning_ir_region_extract",
            "f4_winning_ir_region_cell_extract",
            "f4_winning_ir_region_cell_leftover_extract",
            "f4_static_mesh_extract",
            "f4_static_strap_extract",
            "f4_em_strap_extract",
        ):
            continue
        art = c.artifacts or {}
        spice, insts = art.get("spice"), art.get("insts")
        if spice and insts and Path(spice).is_file() and Path(insts).is_file():
            odb = art.get("odb")
            if not odb or not Path(str(odb)).is_file():
                guess = Path(spice).parent / "candidate.odb"
                odb = str(guess) if guess.is_file() else None
            return {
                "spice": spice,
                "insts": insts,
                "odb": odb,
                "extract_id": want,
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
    if level == "f5_local":
        return "F5"
    if level == "f5_port":
        return "F5"
    if level == "port_steer":
        return "F3"
    if level == "residual_steer":
        return "F5"
    if level == "f2_region":
        return "F2"
    if level == "f4_amg":
        return "F4"
    if level == "f4_ras":
        return "F4"
    if level in ("f4_krylov", "f4_mor", "f4_amg_champ", "f4_ras_champ", "f4_krylov_champ"):
        return "F4"
    if level in ("f4_activity", "f4_host_arrivals"):
        return "F3"
    if level in (
        "pdn",
        "f4_extract",
        "f4_scale",
        "f4_region_extract",
        "f4_host_extract",
        "f4_host_region",
        "f4_host_region_extract",
        "ir_steer",
        "host_ir_steer",
        "f4_scale_win",
        "f4_scale_champ",
        "ir_cell_extract",
        "f4_ir_cell_extract",
        "ir_cell_pdn",
        "ir_cell_region",
        "f4_ir_cell_region_extract",
        "ir_cell_region_pdn",
        "ir_cell_champ_extract",
        "f4_ir_cell_champ_extract",
        "ir_cell_champ_pdn",
        "ir_cell_champ_cone_extract",
        "f4_ir_cell_champ_cone_extract",
        "ir_cell_champ_cone_pdn",
        "ir_cell_champ_cone_region",
        "f4_ir_cell_champ_cone_region_extract",
        "ir_cell_champ_cone_region_pdn",
        "winning_ir_region",
        "f4_winning_ir_region_extract",
        "winning_ir_region_pdn",
        "winning_ir_region_cell_extract",
        "f4_winning_ir_region_cell_extract",
        "winning_ir_region_cell_pdn",
        "winning_ir_region_cell_leftover_extract",
        "f4_winning_ir_region_cell_leftover_extract",
        "winning_ir_region_cell_leftover_pdn",
        "static_ir_steer",
        "static_mesh",
        "static_straps",
        "em_straps",
        "winning_ir_pdn",
    ):
        return "F4"
    if level in ("synthesis", "f1_synth"):
        return "F1"
    if level in (
        "cell",
        "cell_size",
        "ir_cell",
        "ir_cell_champ",
        "ir_cell_champ_cone",
        "winning_ir_region_cell",
        "winning_ir_region_cell_leftover",
    ):
        return "F3"
    if level in ("net", "net_buffer", "net_port", "net_buffer_port"):
        return "F3"
    need = float(cost_hint.get("F1", 2.0))
    if budget_left < need:
        return "F0"
    return "F1"
