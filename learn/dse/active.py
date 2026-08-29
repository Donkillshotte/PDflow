"""Active learning: residuals pick the next *level*, not a mixed knob vector.

F3→F5 residual + uncertainty:
  large |SPEF − ideal|  → interconnect-dominated → net host / net BUF
  small |SPEF − ideal|  → cell/logic delay       → cell host / cell size-up
  n<2 local pairs       → measure the other host  (reduce uncertainty)

F4 IR residual (mesh / PDN knob / region):
  large |catalog − gold-knob| → that PDN family on the region mesh
  small |catalog − gold-knob| → unused pkg L on the candidate extract
  never flatten ABC + c_decap + util into one box
"""

from __future__ import annotations

from .acquire import local_hosts
from .memory import DesignMemory
from .surrogate import residual_f3_to_f5_lite, residual_f3_to_f5_local

# SPEF worse than ideal by ≥50 ps → treat as wire-dominated.
WIRE_NS = -0.05


def order_local_hosts(mem: DesignMemory) -> tuple[list, dict]:
    """F3→F5-lite residual reorders cell vs net hosts. Default stays net-first."""
    hosts = list(local_hosts(mem))
    lite = residual_f3_to_f5_lite(list(mem.all()))
    r = lite.get("mean_residual_ns")
    if r is None:
        return hosts, {
            "lite_residual_ns": None,
            "uncertainty": lite.get("uncertainty"),
            "reason": "no F5-lite residual yet — default net then cell",
            "via": "active_f3_to_f5_lite",
        }
    if float(r) >= WIRE_NS:
        hosts = sorted(hosts, key=lambda c: 0 if c.level == "cell" else 1)
        why = (
            f"F3→F5-lite residual {float(r):+.3f} ns (small) — cell host first; "
            "ideal STA is trustworthy, not a mixed knob vector"
        )
    else:
        hosts = sorted(hosts, key=lambda c: 0 if c.level == "net" else 1)
        why = (
            f"F3→F5-lite residual {float(r):+.3f} ns (wire) — net host first; "
            "interconnect dominates, not more ABC"
        )
    return hosts, {
        "lite_residual_ns": float(r),
        "uncertainty": lite.get("uncertainty"),
        "reason": why,
        "via": "active_f3_to_f5_lite",
        "n": lite.get("n"),
    }


def unmeasured_local_hosts(mem: DesignMemory) -> list:
    """Local hosts that do not yet have an F5-local SPEF child."""
    measured = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("routing")
        if (c.knobs or {}).get("source") == "f5_openroad_local" and c.status == "ok"
    }
    hosts, _ = order_local_hosts(mem)
    return [h for h in hosts if h.id not in measured]


def _latest_f5_local(mem: DesignMemory):
    for c in reversed(list(mem.by_level("routing"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f5_openroad_local":
            return c
    return None


def _spef_path(mem: DesignMemory, child) -> tuple[list[str], list[str]]:
    art = child.artifacts or {}
    cells = [str(x) for x in (art.get("path_cells") or (child.attr or {}).get("cells") or [])]
    hops = [str(x) for x in (art.get("path_nets") or (child.attr or {}).get("nets") or []) if "->" in str(x)]
    sta = art.get("sta") if isinstance(art.get("sta"), dict) else {}
    if not cells:
        cells = [str(x) for x in (sta.get("path_cells") or [])]
    if not hops:
        hops = [str(x) for x in (sta.get("path_nets") or []) if "->" in str(x)]
    return cells, hops


def steer_from_residual(mem: DesignMemory) -> dict | None:
    """Next local action from F3→F5 residual + uncertainty. None if nothing to pay."""
    loc = residual_f3_to_f5_local(list(mem.all()))
    lite = residual_f3_to_f5_lite(list(mem.all()))
    if int(loc.get("n") or 0) < 1:
        return None
    left = unmeasured_local_hosts(mem)
    if left:
        h = left[0]
        return {
            "level": "f5_local",
            "host_id": h.id,
            "host_level": h.level,
            "reason": (
                f"n={loc.get('n')} F3→F5-local pair(s), uncertainty={loc.get('uncertainty')} "
                f"— measure the {h.level} host to cut residual uncertainty, not another ABC"
            ),
            "residual_ns": loc.get("mean_residual_ns"),
            "lite_residual_ns": lite.get("mean_residual_ns"),
            "uncertainty": loc.get("uncertainty"),
            "via": "active_f3_to_f5_residual",
            "not": "a flattened black-box of cell+net+ABC",
        }
    r = loc.get("mean_residual_ns")
    if r is None:
        return None
    child = _latest_f5_local(mem)
    if child is None:
        return None
    cells, hops = _spef_path(mem, child)
    host_id = child.parent_id
    if float(r) < WIRE_NS and hops:
        return {
            "level": "net",
            "host_id": host_id,
            "hops": hops,
            "reason": (
                f"F3→F5-local residual {float(r):+.3f} ns (wire) — BUF on SPEF hops, "
                "not more cell size-up, not a chip restart"
            ),
            "residual_ns": float(r),
            "lite_residual_ns": lite.get("mean_residual_ns"),
            "uncertainty": loc.get("uncertainty"),
            "via": "active_f3_to_f5_residual",
            "not": "a flattened black-box of cell+net+ABC",
        }
    if float(r) >= WIRE_NS and cells:
        return {
            "level": "cell",
            "host_id": host_id,
            "cells": cells,
            "reason": (
                f"F3→F5-local residual {float(r):+.3f} ns (small) — size SPEF-path cells; "
                "ideal STA is trustworthy, not more ABC"
            ),
            "residual_ns": float(r),
            "lite_residual_ns": lite.get("mean_residual_ns"),
            "uncertainty": loc.get("uncertainty"),
            "via": "active_f3_to_f5_residual",
            "not": "a flattened black-box of cell+net+ABC",
        }
    return None


# |catalog − gold-knob| ≥ 1 mV on the same extract → that PDN family works.
KNOB_MV = 1.0


def steer_from_ir_residual(mem: DesignMemory) -> dict | None:
    """Next PDN/region action from F4 mesh/knob/region residuals. Not ABC."""
    from .pdn_space import PDN_CATALOG, measured_pdn_keys
    from .surrogate import residual_f4_knob, residual_f4_mesh, residual_f4_region

    mesh = residual_f4_mesh(list(mem.all()))
    knob = residual_f4_knob(list(mem.all()))
    region = residual_f4_region(list(mem.all()))
    if int(mesh.get("n") or 0) < 1 and int(knob.get("n") or 0) < 1:
        return None

    def _latest(src: str):
        for c in reversed(list(mem.by_level("pdn"))):
            if c.status == "ok" and (c.knobs or {}).get("source") == src:
                return c
        return None

    cand = _latest("f4_candidate_extract")
    reg = _latest("f4_region_extract")
    knob_r = knob.get("mean_residual_mv")
    winning = str(knob.get("catalog") or "")
    spec_win = next((s for s in PDN_CATALOG if s["name"] == winning), None)

    # Large knob residual (decap moved IR) → transfer that family to the region mesh.
    if (
        knob_r is not None
        and abs(float(knob_r)) >= KNOB_MV
        and spec_win is not None
        and reg is not None
    ):
        rid = str((reg.knobs or {}).get("extract_id") or reg.id)
        have = measured_pdn_keys(mem, extract_id=rid)
        key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
        if key not in have:
            return {
                "level": "pdn",
                "spec": spec_win,
                "extract_id": rid,
                "host_id": reg.id,
                "host_source": "f4_region_extract",
                "reason": (
                    f"F4 knob residual {float(knob_r):+.3f} mV ({winning} on candidate) "
                    "— restamp that PDN family on the region mesh, not pkg L, not ABC"
                ),
                "mesh_residual_mv": mesh.get("mean_residual_mv"),
                "knob_residual_mv": float(knob_r),
                "region_residual_mv": region.get("mean_residual_mv"),
                "via": "active_f4_ir_residual",
                "not": "a flattened black-box of ABC+PDN knobs",
            }

    # After the winning family is on the region (or residual is small / missing)
    # → unused catalog on the candidate. Inductance ≠ more decap.
    if cand is not None:
        cid = str((cand.knobs or {}).get("extract_id") or cand.id)
        have = measured_pdn_keys(mem, extract_id=cid)
        unused = [
            s
            for s in PDN_CATALOG
            if (float(s["pkg_r"]), float(s["pkg_l"]), float(s["c_decap"])) not in have
        ]
        small = knob_r is not None and abs(float(knob_r)) < KNOB_MV
        transferred = (
            spec_win is not None
            and reg is not None
            and (
                float(spec_win["pkg_r"]),
                float(spec_win["pkg_l"]),
                float(spec_win["c_decap"]),
            )
            in measured_pdn_keys(mem, extract_id=str((reg.knobs or {}).get("extract_id") or reg.id))
        )
        if unused and (small or knob_r is None or transferred):
            spec = unused[0]
            if transferred and not small:
                why = (
                    f"F4 winning family {winning} already on the region mesh "
                    f"— pay unused {spec['name']} on the candidate extract "
                    "(inductance, not more decap, not ABC)"
                )
            elif small:
                why = (
                    f"F4 knob residual {float(knob_r):+.3f} mV (small) — pay {spec['name']} "
                    "on the candidate extract, not more decap, not ABC"
                )
            else:
                why = (
                    f"F4 mesh residual {mesh.get('mean_residual_mv')} mV vs gold — "
                    f"pay {spec['name']} on the candidate extract, not ABC"
                )
            return {
                "level": "pdn",
                "spec": spec,
                "extract_id": cid,
                "host_id": cand.id,
                "host_source": "f4_candidate_extract",
                "reason": why,
                "mesh_residual_mv": mesh.get("mean_residual_mv"),
                "knob_residual_mv": knob_r,
                "region_residual_mv": region.get("mean_residual_mv"),
                "via": "active_f4_ir_residual",
                "not": "a flattened black-box of ABC+PDN knobs",
            }
    return None
