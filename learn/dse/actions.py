"""Generic refine actions — one steer/pay pair per stage, depth as a parameter.

These replace the per-layer `steer_from_winning_ir_region_cell*` /
`should_pay_winning_ir_region_cell*` families for the refine chain. The
semantics are identical (A/B-tested against the legacy pairs); the depth
suffix lives in `frame.py`, so depth N+1 costs zero new code.

Invariants preserved:
  - combo-heavy (≥ 0.5) PDN join steers the next size-up; seq-heavy never does
  - sized lineage (base ∪ depths ≤ N−1) is always subtracted
  - single shot per extract per stage; refusal strings match legacy intent
  - winning family first, then unused Dynamic IR catalog (C then L, inherit
    host pkg_r); pitch / width / bump / pkg_r never flatten in
  - gold finish mesh is never restamped
"""

from __future__ import annotations

from pathlib import Path

from .frame import (
    RefinementFrame,
    refine_cell_source,
    refine_chain,
    refine_extract_source,
    refine_pdn_via,
    sized_through,
    _suffix,
)
from .memory import DesignMemory

COMBO_MIN = 0.5


def _label(depth: int) -> str:
    return f"refine[{depth}]"


def _join_host(mem: DesignMemory, depth: int):
    """PDN restamp whose hotspot join steers the depth-N size-up.

    depth 0 joins on the winning-IR-region PDN; depth N ≥ 1 joins on the
    depth N−1 refine PDN.
    """
    if depth == 0:
        for c in reversed(list(mem.all())):
            if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_pdn":
                return c
        return None
    chain = refine_chain(mem)
    prev = next((f for f in chain if f.depth == depth - 1), None)
    return prev.pdn if prev else None


def _join_host_source(mem: DesignMemory, depth: int) -> str:
    return "f4_winning_ir_region_extract" if depth == 0 else refine_extract_source(depth - 1)


def _frame(mem: DesignMemory, depth: int) -> RefinementFrame | None:
    return next((f for f in refine_chain(mem) if f.depth == depth), None)


def _sizeup_host(mem: DesignMemory, depth: int):
    """Netlist the depth-N size-up edits: IR-cell host at depth 0, else depth N−1."""
    if depth == 0:
        from .active import ir_cell_host

        return ir_cell_host(mem)
    prev = _frame(mem, depth - 1)
    return prev.cell if prev else None


def steer_refine_sizeup(mem: DesignMemory, depth: int) -> dict | None:
    """Combo-heavy join on the depth N−1 restamp minus the sized lineage."""
    pdn = _join_host(mem, depth)
    if pdn is None:
        return None
    attr = pdn.attr or {}
    combo = float(attr.get("combo_frac") or 0.0)
    if combo < COMBO_MIN:
        return None
    sized = sized_through(mem, depth - 1)
    cells = [str(x) for x in (attr.get("cells") or []) if str(x) not in sized]
    if not cells:
        return None
    modules = list(dict.fromkeys(str(c).split("/")[0] for c in cells if "/" in str(c)))
    if not modules:
        return None
    eid = str((pdn.knobs or {}).get("extract_id") or pdn.id)
    mods = ",".join(modules)
    return {
        "level": f"winning_ir_region_cell{_suffix(depth)}",
        "depth": depth,
        "cells": cells,
        "modules": modules,
        "cones": attr.get("cones"),
        "region": attr.get("region"),
        "combo_frac": combo,
        "extract_id": eid,
        "host_id": pdn.id,
        "host_source": _join_host_source(mem, depth),
        "reason": (
            f"{_label(depth)} PDN hotspot {attr.get('region') or 'xy'} combo {combo:.2f} "
            f"joins unsized {mods} cells — sized lineage subtracted, not a flatten of the "
            "previous depth, not champ ctrl, not first IR-cell, not STA-path size-up, not ABC, not VCD"
        ),
        "via": f"active_f4_winning_ir_region_cell{_suffix(depth)}",
        "not": "previous-depth flatten / leftover-cone / a flattened cell+decap vector",
    }


def should_pay_refine_sizeup(
    mem: DesignMemory,
    *,
    depth: int,
    budget_left: float,
    steer: dict | None,
    min_s: float = 3.0,
) -> tuple[bool, str]:
    if budget_left < min_s:
        return False, f"wall budget would not cover {_label(depth)} STA"
    if not steer or steer.get("level") != f"winning_ir_region_cell{_suffix(depth)}":
        return False, f"no {_label(depth)} residual (need unsized join cells)"
    if str(steer.get("host_source") or "") != _join_host_source(mem, depth):
        return False, f"{_label(depth)} refuses a foreign join host (cone / champ / region flatten)"
    eid = str(steer.get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == refine_cell_source(depth)
        and c.status == "ok"
        and str((c.knobs or {}).get("extract_id") or "") == eid
        for c in mem.by_level("cell")
    ):
        return False, f"already have a {_label(depth)} size child on this extract"
    cells = [str(x) for x in steer.get("cells") or []]
    if not cells:
        return False, f"{_label(depth)} join has no unsized cells"
    if not steer.get("modules"):
        return False, f"{_label(depth)} join has no module — not inventing a cone"
    host = _sizeup_host(mem, depth)
    mapped = None
    if host:
        mapped = (host.artifacts or {}).get("mapped_hier_v") or (host.artifacts or {}).get("mapped_v")
    if not host or not mapped or not Path(mapped).is_file():
        return False, f"depth {depth - 1} netlist missing — not flattening {_label(depth)} onto an older host"
    sized = sized_through(mem, depth - 1)
    if sized and set(cells) <= sized:
        return False, f"{_label(depth)} cells already covered by the sized lineage"
    return True, str(steer.get("reason") or f"upsize {len(cells)} {_label(depth)} cells on the join")


def should_pay_refine_extract(
    mem: DesignMemory,
    *,
    depth: int,
    budget_left: float,
    min_s: float = 12.0,
) -> tuple[bool, str]:
    if budget_left < min_s:
        return False, f"wall budget would not cover {_label(depth)} write_pg_spice"
    from .openroad_f2 import extract_available

    if not extract_available():
        return False, "openroad/PDN tcl missing — not launching finish"
    frame = _frame(mem, depth)
    if frame is None or frame.cell is None:
        return False, f"no {_label(depth)} size-up to extract a PDN from"
    mapped = (frame.cell.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return False, f"{_label(depth)} netlist missing for write_pg_spice"
    prev = _frame(mem, depth - 1) if depth > 0 else None
    prev_extract = prev.extract if prev else None
    if depth == 0:
        for c in reversed(list(mem.by_level("pdn"))):
            if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_extract":
                prev_extract = c
                break
    if prev_extract is None:
        return False, f"no depth {depth - 1} extract to residual the {_label(depth)} mesh against"
    host_eid = str((frame.cell.knobs or {}).get("extract_id") or "")
    if any(
        (c.knobs or {}).get("source") == refine_extract_source(depth)
        and c.status == "ok"
        and str((c.knobs or {}).get("parent_extract_id") or "") == host_eid
        for c in mem.by_level("pdn")
    ):
        return False, f"already have a {_label(depth)} write_pg_spice mesh on this extract"
    nch = (frame.cell.artifacts or {}).get("n_changed") or len(frame.cells)
    return True, (
        f"write_pg_spice on {_label(depth)} n={nch} — IR residual vs the depth {depth - 1} extract, not gold, not ABC"
    )


def steer_refine_pdn(mem: DesignMemory, depth: int) -> dict | None:
    """Winning PDN family on the depth-N mesh after the 1× residual."""
    from .active import _winning_pdn_family
    from .pdn_space import measured_pdn_keys

    frame = _frame(mem, depth)
    if frame is None or frame.extract is None or frame.extract.qor.dynamic_ir_mv is None:
        return None
    res = (frame.extract.attr or {}).get("residual_mv")
    if res is None:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = frame.extract_id
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "depth": depth,
        "spec": spec_win,
        "extract_id": eid,
        "host_id": frame.extract.id,
        "host_source": refine_extract_source(depth),
        "region": (frame.extract.knobs or {}).get("region") or (frame.extract.attr or {}).get("region"),
        "reason": (
            f"{_label(depth)} 1× residual {float(res):+.3f} mV ({sign} droop vs depth {depth - 1} extract) — "
            f"restamp {spec_win['name']} on the {_label(depth)} mesh, not a previous-depth PDN, not champ IR-steer, not ABC"
        ),
        "residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": refine_pdn_via(depth),
        "not": "a flattened cell+PDN vector / gold / previous depths",
    }


def should_pay_refine_pdn(
    mem: DesignMemory,
    *,
    depth: int,
    budget_left: float,
    steer: dict | None,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    if budget_left < min_s:
        return False, f"wall budget would not cover {_label(depth)} PDN restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, f"no {_label(depth)} residual-steered PDN action (need a 1× residual)"
    if str(steer.get("host_source") or "") != refine_extract_source(depth):
        return False, f"{_label(depth)} PDN restamp refuses a foreign extract"
    from .pdn_space import measured_pdn_keys

    spec = steer["spec"]
    have = measured_pdn_keys(mem, extract_id=str(steer["extract_id"]))
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, f"that PDN point is already measured on the {_label(depth)} extract"
    return True, str(steer.get("reason") or f"{_label(depth)} residual steers a PDN restamp on its mesh")


def steer_refine_catalog(mem: DesignMemory, depth: int) -> dict | None:
    """Unused Dynamic IR catalog on the depth-N mesh after the winning family."""
    from .pdn_space import PDN_CATALOG, next_winning_ir_pdn_spec

    frame = _frame(mem, depth)
    if frame is None or frame.extract is None or frame.pdn is None:
        return None
    if frame.pdn.qor.dynamic_ir_mv is None:
        return None
    eid = frame.extract_id
    if eid in ("finish", ""):
        return None
    spec = next_winning_ir_pdn_spec(mem, frame.pdn)
    if spec is None:
        return None
    if spec["name"] not in {s["name"] for s in PDN_CATALOG}:
        return None
    host_l = float((frame.pdn.knobs or {}).get("pkg_l") or 2e-10)
    axis = "inductance" if abs(float(spec["pkg_l"]) - host_l) > 1e-18 else "decap"
    src = (frame.pdn.knobs or {}).get("name") or frame.pdn.id
    return {
        "level": "pdn",
        "depth": depth,
        "spec": spec,
        "extract_id": eid,
        "host_id": frame.pdn.id,
        "host_source": refine_extract_source(depth),
        "dynamic_ir_mv": float(frame.pdn.qor.dynamic_ir_mv),
        "axis": axis,
        "reason": (
            f"{_label(depth)} {src} {float(frame.pdn.qor.dynamic_ir_mv):.3f} mV extract {eid} — "
            f"unused {spec['name']} ({axis}, inherit pkg_r={spec['pkg_r']}), not winning_ir "
            "catalog, not a deeper combo size-up, not pitch, not gold"
        ),
        "via": f"active_f4_winning_ir_region_cell{_suffix(depth)}_catalog",
        "not": "winning_ir catalog / deeper flatten / pitch / gold",
    }


def should_pay_refine_catalog(
    mem: DesignMemory,
    *,
    depth: int,
    budget_left: float,
    steer: dict | None,
    n_steer: int = 0,
    steer_max: int = 2,
    min_s: float = 8.0,
) -> tuple[bool, str]:
    if n_steer >= steer_max:
        return False, f"{_label(depth)} Dynamic IR catalog spent (decap + unused pkg L)"
    if budget_left < min_s:
        return False, f"wall budget would not cover {_label(depth)} catalog restamp"
    if not steer or not steer.get("spec") or not steer.get("extract_id"):
        return False, f"no {_label(depth)} unused Dynamic IR catalog action"
    if str(steer.get("host_source") or "") != refine_extract_source(depth):
        return False, f"{_label(depth)} catalog refuses a foreign extract (not winning_ir catalog)"
    from .pdn_space import (
        EM_STRAP_CATALOG,
        PDN_CATALOG,
        STATIC_MESH_CATALOG,
        STATIC_PDN_CATALOG,
        STATIC_STRAP_CATALOG,
        measured_pdn_keys,
    )

    spec = steer["spec"]
    name = str(spec.get("name") or "")
    refuse = (
        {s["name"] for s in STATIC_PDN_CATALOG}
        | {s["name"] for s in STATIC_MESH_CATALOG}
        | {s["name"] for s in STATIC_STRAP_CATALOG}
        | {s["name"] for s in EM_STRAP_CATALOG}
    )
    if name in refuse:
        return False, f"{_label(depth)} catalog refuses a pitch / width / bump / pkg_r point"
    if name not in {s["name"] for s in PDN_CATALOG}:
        return False, f"{_label(depth)} catalog requires a Dynamic IR catalog point"
    if spec.get("m4_pitch") is not None or spec.get("m4_width") is not None or spec.get("bump_dx") is not None:
        return False, f"{_label(depth)} catalog refuses a geometry restamp"
    eid = str(steer["extract_id"])
    if eid in ("finish", ""):
        return False, f"{_label(depth)} catalog refuses the gold finish extract"
    frame = _frame(mem, depth)
    if frame is None or frame.extract is None or frame.extract_id != eid:
        return False, f"{_label(depth)} catalog stays on its own extract"
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
    if key in have:
        return False, f"that Dynamic IR point is already measured on the {_label(depth)} extract"
    return True, str(steer.get("reason") or f"{_label(depth)} unused Dynamic IR catalog — not pitch, not gold")
