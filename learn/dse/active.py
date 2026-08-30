"""Active learning: residuals pick the next *level*, not a mixed knob vector.

F3→F5 residual + uncertainty:
  large |SPEF − ideal|  → interconnect-dominated → net host / net BUF
  small |SPEF − ideal|  → cell/logic delay       → cell host / cell size-up
  n<2 local pairs       → measure the other host  (reduce uncertainty)

F4 IR residual (mesh / PDN knob / region):
  large |catalog − gold-knob| → that PDN family on the region mesh
  small |catalog − gold-knob| → unused pkg L on the candidate extract
F4 host-region residual (this pair only, not the synth region residual):
  large |host-region − host| → winning PDN family on the host-region mesh
  after that / small residual → unused pkg L on the unconstrained host extract
F5-port residual (this pair only, not the mixed F5-local mean):
  large |SPEF − ideal| → intra-module BUF on SPEF hops (not another port BUF)
F4 I-scale host:
  port-steer > port-net > net > cell > F1 with a material power delta
  never flatten ABC + c_decap + util into one box
F4 I-scale-win hotspot → ODB inst join → cell_size_ir (ctrl combo, not STA dpath)
  then write_pg_spice on that sized netlist — residual vs host extract, not STA-only
IR-cell 1× hotspot bin ≠ host bin:
  seq-heavy → density-cap extract on the sized netlist (region, not more combo size-up)
F4 I-scale-champ hotspot (activity on winning_ir_pdn):
  combo-heavy + cells ≠ first IR-cell join → cell_size_ir_champ on the sized netlist
  then write_pg_spice on that netlist — residual vs the IR-cell extract, not host
leftover cells on the champ extract (minus champ size-up):
  combo-heavy → cell_size_ir_champ_cone + write_pg_spice residual vs champ extract
  leftover-cone 1× bin ≠ champ extract and seq-heavy → density-cap extract
  (not more combo size-up, not IR-cell-region rXY), then |Δ|≥1 mV PDN
winning-IR-region PDN leftover combo cells (minus IR-cell / champ / leftover-cone):
  combo-heavy → cell_size_ir_winning_region on the IR-cell netlist
  + write_pg_spice residual vs the winning-IR-region extract — not leftover-cone flatten
F4 static IR (DC ohmic, not Dynamic IR):
  winning_static_pdn is a separate 1× ranking — decap/pkg L do not move static
  unused pkg_r on that extract, not a flattened static+dynamic / decap vector
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


def _latest_f5_port(mem: DesignMemory):
    for c in reversed(list(mem.by_level("routing"))):
        k = c.knobs or {}
        if c.status == "ok" and k.get("source") == "f5_openroad_local" and k.get("host_level") == "port":
            return c
    return None


def _intra_spef_hops(hops: list[str]) -> list[str]:
    """SPEF hops that net_buffer can take. Skip portbuf and ctrl↔dpath."""
    from .net_space import hop_is_block_port, hop_is_cross_module

    out: list[str] = []
    for hop in hops:
        if "portbuf" in hop:
            continue
        if hop_is_block_port(hop) or hop_is_cross_module(hop):
            continue
        if "->" not in hop:
            continue
        a, b = hop.split("->", 1)
        if "/" not in a or "/" not in b:
            continue
        out.append(hop)
    return out


def steer_from_port_residual(mem: DesignMemory) -> dict | None:
    """Next local action from the F5-port pair only. Not the mixed F5-local mean."""
    child = _latest_f5_port(mem)
    if child is None:
        return None
    spef = (child.artifacts or {}).get("wns_ns")
    ideal = (child.artifacts or {}).get("ideal_wns_ns")
    if spef is None or ideal is None:
        return None
    r = float(spef) - float(ideal)
    hops = _intra_spef_hops(
        [str(h) for h in ((child.attr or {}).get("nets") or []) if "->" in str(h)]
    )
    if not hops:
        hops = _intra_spef_hops(_spef_path(mem, child)[1])
    host_id = child.parent_id
    if host_id is None:
        return None
    if r < WIRE_NS and hops:
        return {
            "level": "net",
            "host_id": host_id,
            "hops": hops,
            "reason": (
                f"F5-port residual {r:+.3f} ns (wire) — BUF on SPEF intra hops "
                f"({hops[0]}…), not another port BUF, not ABC"
            ),
            "residual_ns": r,
            "via": "active_f5_port_residual",
            "not": "a flattened black-box of port+net+ABC",
        }
    return None


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


def _winning_pdn_family(mem: DesignMemory) -> tuple[dict | None, float | None]:
    """Catalog point with the largest |ΔIR| on the candidate extract. Not a mixed vector."""
    from .pdn_space import PDN_CATALOG
    from .surrogate import residual_f4_knob

    knob = residual_f4_knob(list(mem.all()))
    pairs = list(knob.get("pairs") or [])
    if pairs:
        best = max(pairs, key=lambda p: abs(float(p["residual_mv"])))
        spec = next((s for s in PDN_CATALOG if s["name"] == best["catalog"]), None)
        if spec:
            return spec, float(best["residual_mv"])
    return (PDN_CATALOG[0] if PDN_CATALOG else None), knob.get("mean_residual_mv")


def steer_from_host_ir_residual(mem: DesignMemory) -> dict | None:
    """Next PDN action on the host mesh from the host-region residual. Not candidate IR-steer."""
    from .pdn_space import PDN_CATALOG, measured_pdn_keys
    from .surrogate import residual_f4_host_region

    host_r = residual_f4_host_region(list(mem.all()))
    if int(host_r.get("n") or 0) < 1:
        return None

    def _latest(src: str):
        for c in reversed(list(mem.by_level("pdn"))):
            if c.status == "ok" and (c.knobs or {}).get("source") == src:
                return c
        return None

    host = _latest("f4_host_extract")
    hreg = _latest("f4_host_region_extract")
    if host is None or hreg is None:
        return None

    spec_win, knob_r = _winning_pdn_family(mem)
    winning = str((spec_win or {}).get("name") or "")
    mesh_r = host_r.get("mean_residual_mv")
    large = mesh_r is not None and abs(float(mesh_r)) >= KNOB_MV

    if large and spec_win is not None:
        rid = str((hreg.knobs or {}).get("extract_id") or hreg.id)
        have = measured_pdn_keys(mem, extract_id=rid)
        key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
        if key not in have:
            return {
                "level": "pdn",
                "spec": spec_win,
                "extract_id": rid,
                "host_id": hreg.id,
                "host_source": "f4_host_region_extract",
                "reason": (
                    f"F4 host-region residual {float(mesh_r):+.3f} mV — "
                    f"restamp {winning} on the host-region mesh, not gold rXY, not ABC"
                ),
                "host_region_residual_mv": float(mesh_r),
                "knob_residual_mv": knob_r,
                "via": "active_f4_host_ir_residual",
                "not": "candidate IR-steer / a mixed ABC+PDN vector",
            }

    cid = str((host.knobs or {}).get("extract_id") or host.id)
    have = measured_pdn_keys(mem, extract_id=cid)
    unused = [
        s
        for s in PDN_CATALOG
        if (float(s["pkg_r"]), float(s["pkg_l"]), float(s["c_decap"])) not in have
    ]
    rid = str((hreg.knobs or {}).get("extract_id") or hreg.id)
    transferred = spec_win is not None and (
        float(spec_win["pkg_r"]),
        float(spec_win["pkg_l"]),
        float(spec_win["c_decap"]),
    ) in measured_pdn_keys(mem, extract_id=rid)
    small = mesh_r is not None and abs(float(mesh_r)) < KNOB_MV
    if unused and (small or transferred):
        spec = unused[0]
        if transferred and spec_win is not None:
            spec = next((s for s in unused if s["name"] != winning), spec)
        if transferred and not small:
            why = (
                f"F4 winning family {winning} already on the host-region mesh — "
                f"pay unused {spec['name']} on the unconstrained host extract "
                "(not candidate IR-steer, not ABC)"
            )
        elif small:
            why = (
                f"F4 host-region residual {float(mesh_r):+.3f} mV (small) — pay {spec['name']} "
                "on the unconstrained host extract, not more decap, not ABC"
            )
        else:
            why = (
                f"F4 host-region residual {mesh_r} mV — pay {spec['name']} "
                "on the unconstrained host extract, not ABC"
            )
        return {
            "level": "pdn",
            "spec": spec,
            "extract_id": cid,
            "host_id": host.id,
            "host_source": "f4_host_extract",
            "reason": why,
            "host_region_residual_mv": mesh_r,
            "knob_residual_mv": knob_r,
            "via": "active_f4_host_ir_residual",
            "not": "candidate IR-steer / a mixed ABC+PDN vector",
        }
    return None


def iscale_host(mem: DesignMemory):
    """Attributed netlist whose F3 power scales I(t).

    Port-steer > port-net > intra net > cell > F1 with a material power
    delta. Not the synth WNS-winner just because it has the best slack.
    """
    from .mo import timing_of

    base = None
    for c in mem.by_level("logic"):
        if c.status == "ok" and (c.knobs or {}).get("name") == "liberty_default":
            _w, p = timing_of(mem, c)
            if p is None and c.qor.power_w is not None:
                p = float(c.qor.power_w)
            if p:
                base = float(p)
                break
    if base is None or base <= 0:
        return None
    have = {
        (c.knobs or {}).get("parent_id")
        for c in mem.by_level("pdn")
        if (c.knobs or {}).get("source") == "f4_iscale" and c.status == "ok"
    }

    def _ok(c) -> bool:
        if c is None or c.status != "ok" or c.id in have:
            return False
        _w, p = timing_of(mem, c)
        if p is None:
            return False
        return abs(float(p) / base - 1.0) >= 0.03

    ranked: list[tuple[int, object]] = []
    for c in mem.all():
        src = (c.knobs or {}).get("source")
        via = (c.attr or {}).get("via")
        if via == "active_f5_port":
            ranked.append((0, c))
        elif src == "net_buffer_port":
            ranked.append((1, c))
        elif src == "net_buffer":
            ranked.append((2, c))
        elif src == "cell_size_up":
            ranked.append((3, c))
    ranked.sort(key=lambda t: t[0])
    for _, c in ranked:
        if _ok(c):
            return c
    f1s = [c for c in mem.all() if c.status == "ok" and c.fidelity == "F1"]
    f1s.sort(key=lambda c: 0 if c.level == "synthesis" else 1)
    for c in f1s:
        if _ok(c):
            return c
    return None


def iscale_parent(mem: DesignMemory):
    """Host already used for the first I-scale shot. Not a new iscale_host pick."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok" or (c.knobs or {}).get("source") != "f4_iscale":
            continue
        pid = (c.knobs or {}).get("parent_id")
        if pid:
            hit = mem.get(str(pid))
            if hit:
                return hit
    return iscale_host(mem)


def winning_host_pdn(mem: DesignMemory):
    """Lowest 1× droop among host extract / host-region / host-IR-steer. Not gold."""
    best = None
    best_mv = None
    for c in mem.by_level("pdn"):
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        src = (c.knobs or {}).get("source")
        via = (c.attr or {}).get("via")
        if src not in ("f4_host_extract", "f4_host_region_extract") and via != "active_f4_host_ir":
            continue
        if abs(float((c.knobs or {}).get("i_scale") or 1.0) - 1.0) > 1e-9:
            continue
        mv = float(c.qor.dynamic_ir_mv)
        if best_mv is None or mv < best_mv:
            best, best_mv = c, mv
    return best


def winning_ir_pdn(mem: DesignMemory):
    """Lowest 1× droop among host-win, IR-cell family, and a new strap R-graph.

    pkg_r / bump restamps stay off this ranking (same spice as the host).
    A pdngen -ripup strap extract is a new mesh — it may become the 1× champ.
    winning_host_pdn stays host-only. Not gold.
    """
    best = winning_host_pdn(mem)
    best_mv = float(best.qor.dynamic_ir_mv) if best and best.qor.dynamic_ir_mv is not None else None
    extra_src = (
        "f4_ir_cell_extract",
        "f4_ir_cell_region_extract",
        "f4_ir_cell_champ_extract",
        "f4_ir_cell_champ_cone_extract",
        "f4_ir_cell_champ_cone_region_extract",
        "f4_winning_ir_region_extract",
        "f4_winning_ir_region_cell_extract",
        "f4_winning_ir_region_cell_leftover_extract",
        "f4_winning_ir_region_cell_leftover2_extract",
        "f4_static_strap_extract",
        "f4_em_strap_extract",
    )
    extra_via = (
        "active_f4_ir_cell_pdn",
        "active_f4_ir_cell_region_pdn",
        "active_f4_ir_cell_champ_pdn",
        "active_f4_ir_cell_champ_cone_pdn",
        "active_f4_ir_cell_champ_cone_region_pdn",
        "active_f4_winning_ir_region_pdn",
        "active_f4_winning_ir_region_cell_pdn",
        "active_f4_winning_ir_region_cell_leftover_pdn",
        "active_f4_winning_ir_region_cell_leftover2_pdn",
        "active_f4_static_straps",
        "active_f4_em_straps",
        "active_f4_winning_ir_pdn",
    )
    for c in mem.by_level("pdn"):
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        src = (c.knobs or {}).get("source")
        via = (c.attr or {}).get("via")
        if src not in extra_src and via not in extra_via:
            continue
        if abs(float((c.knobs or {}).get("i_scale") or 1.0) - 1.0) > 1e-9:
            continue
        mv = float(c.qor.dynamic_ir_mv)
        if best_mv is None or mv < best_mv:
            best, best_mv = c, mv
    return best


def _ir_family_1x_member(c) -> bool:
    """Host-extract / host-IR / IR-cell family. Not gold, not candidate-only."""
    src = (c.knobs or {}).get("source")
    via = (c.attr or {}).get("via")
    if src in (
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
        "f4_winning_ir_region_cell_leftover2_extract",
    ):
        return True
    if via in (
        "active_f4_host_ir",
        "active_f4_ir_cell_pdn",
        "active_f4_ir_cell_region_pdn",
        "active_f4_ir_cell_champ_pdn",
        "active_f4_ir_cell_champ_cone_pdn",
        "active_f4_ir_cell_champ_cone_region_pdn",
        "active_f4_winning_ir_region_pdn",
        "active_f4_winning_ir_region_cell_pdn",
        "active_f4_winning_ir_region_cell_leftover_pdn",
        "active_f4_winning_ir_region_cell_leftover2_pdn",
        "active_f4_static_ir",
        "active_f4_static_mesh",
        "active_f4_static_straps",
        "active_f4_em_straps",
        "active_f4_winning_ir_pdn",
    ):
        return True
    if src == "f4_static_mesh_extract":
        return True
    if src == "f4_static_strap_extract":
        return True
    if src == "f4_em_strap_extract":
        return True
    if src == "f4_solver_a" and (c.knobs or {}).get("name") == "pkg_r_25m":
        return True
    return False


def winning_static_pdn(mem: DesignMemory):
    """Lowest 1× static_ir_mv on the IR/host family. Not gold, not winning_ir_pdn.

    Decap and pkg L do not move static IR (live champ stays 6.178 mV). Ties
    break toward the lower Dynamic IR point so pkg_r inherits champ L/C.
    """
    best = None
    best_mv = None
    best_dyn = None
    for c in mem.by_level("pdn"):
        if c.status != "ok" or c.qor.static_ir_mv is None:
            continue
        if not _ir_family_1x_member(c):
            continue
        if abs(float((c.knobs or {}).get("i_scale") or 1.0) - 1.0) > 1e-9:
            continue
        eid = str((c.knobs or {}).get("extract_id") or c.id)
        if eid in ("finish", ""):
            continue
        mv = float(c.qor.static_ir_mv)
        dyn = float(c.qor.dynamic_ir_mv) if c.qor.dynamic_ir_mv is not None else 1e9
        if best_mv is None or mv < best_mv - 1e-12:
            best, best_mv, best_dyn = c, mv, dyn
        elif abs(mv - best_mv) <= 1e-12 and dyn < (best_dyn if best_dyn is not None else 1e9):
            best, best_dyn = c, dyn
    return best


def steer_from_static_ir_residual(mem: DesignMemory) -> dict | None:
    """Unused pkg_r on winning_static_pdn. Not decap, not pkg L, not Dynamic IR-steer."""
    from .pdn_space import next_static_pdn_spec

    host = winning_static_pdn(mem)
    if host is None or host.qor.static_ir_mv is None:
        return None
    eid = str((host.knobs or {}).get("extract_id") or host.id)
    if eid in ("finish", ""):
        return None
    spec = next_static_pdn_spec(mem, host)
    if spec is None:
        return None
    win_d = winning_ir_pdn(mem)
    dyn_eid = str((win_d.knobs or {}).get("extract_id") or win_d.id) if win_d else ""
    same = bool(dyn_eid) and dyn_eid == eid
    src = (host.knobs or {}).get("name") or (host.attr or {}).get("via") or host.id
    extra = (
        " — same extract as winning_ir_pdn, pkg_r not decap"
        if same
        else f" — static champ extract ≠ dynamic champ {dyn_eid or 'none'}"
    )
    return {
        "level": "pdn",
        "spec": spec,
        "extract_id": eid,
        "host_id": host.id,
        "host_source": (host.knobs or {}).get("source") or host.level,
        "static_ir_mv": float(host.qor.static_ir_mv),
        "dynamic_ir_mv": float(host.qor.dynamic_ir_mv) if host.qor.dynamic_ir_mv is not None else None,
        "same_extract_as_winning_ir": same,
        "reason": (
            f"static IR {float(host.qor.static_ir_mv):.3f} mV on {src} — "
            f"{spec['name']} pkg_r={spec['pkg_r']}{extra}, not Dynamic IR-steer, not gold"
        ),
        "via": "active_f4_static_ir",
        "not": "a flattened static+dynamic / decap / pkg L / gold vector",
    }


def _null_pkg_r_residual(mem: DesignMemory) -> dict | None:
    """Latest pkg_r shot whose on-die static residual is ~0. Not a Dynamic IR residual."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_static_ir":
            continue
        res = (c.attr or {}).get("residual_vs_static_champ_mv")
        if res is None:
            continue
        if abs(float(res)) < 0.05:
            return {
                "id": c.id,
                "residual_mv": float(res),
                "extract_id": str((c.knobs or {}).get("extract_id") or c.id),
            }
    return None


def _odb_for_extract(mem: DesignMemory, eid: str) -> str | None:
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1].parent
    want = str(eid)
    for c in reversed(list(mem.by_level("pdn"))):
        if str((c.knobs or {}).get("extract_id") or c.id) != want:
            continue
        art = c.artifacts or {}
        odb = art.get("odb")
        if odb and Path(odb).is_file():
            return str(odb)
        spice = art.get("spice")
        if spice:
            guess = Path(spice).parent / "candidate.odb"
            if guess.is_file():
                return str(guess)
    guess = repo / "learn" / "sim" / "dse" / "extracts" / want / "candidate.odb"
    if guess.is_file():
        return str(guess)
    return None


def steer_from_static_mesh_residual(mem: DesignMemory) -> dict | None:
    """Denser bumps on the static-IR champ ODB after a null pkg_r residual.

    Not decap, not pkg L, not a new GPL, not gold.
    """
    from .pdn_space import next_static_mesh_spec

    null = _null_pkg_r_residual(mem)
    if null is None:
        return None
    host = winning_static_pdn(mem)
    if host is None or host.qor.static_ir_mv is None:
        return None
    eid = str((host.knobs or {}).get("extract_id") or host.id)
    if eid in ("finish", ""):
        return None
    spec = next_static_mesh_spec(mem)
    if spec is None:
        return None
    odb = _odb_for_extract(mem, eid)
    src = (host.knobs or {}).get("name") or (host.attr or {}).get("via") or host.id
    return {
        "level": "pdn",
        "spec": spec,
        "extract_id": eid,
        "odb": odb,
        "host_id": host.id,
        "host_source": (host.knobs or {}).get("source") or host.level,
        "static_ir_mv": float(host.qor.static_ir_mv),
        "pkg_r_residual_mv": null["residual_mv"],
        "pkg_r_id": null["id"],
        "reason": (
            f"pkg_r residual {null['residual_mv']:+.3f} mV is null on-die — "
            f"{spec['name']} bump_dx={spec['bump_dx']} on {src} extract {eid}, "
            "same place, not Dynamic IR-steer, not gold"
        ),
        "via": "active_f4_static_mesh",
        "not": "a flattened pkg_r+bump / decap / GPL / gold vector",
    }


def _null_bump_residual(mem: DesignMemory) -> dict | None:
    """Latest bump-mesh shot whose on-die static residual is ~0. Not pkg_r."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok" or (c.attr or {}).get("via") != "active_f4_static_mesh":
            continue
        res = (c.attr or {}).get("residual_vs_static_champ_mv")
        if res is None:
            continue
        if abs(float(res)) < 0.05:
            return {
                "id": c.id,
                "residual_mv": float(res),
                "extract_id": str((c.knobs or {}).get("parent_extract_id") or (c.knobs or {}).get("extract_id") or c.id),
            }
    return None


def steer_from_static_strap_residual(mem: DesignMemory) -> dict | None:
    """Denser metal4 straps on the static-IR champ ODB after a null bump residual.

    Not bumps, not pkg_r, not decap, not a new GPL, not gold.
    """
    from .pdn_space import next_static_strap_spec

    null = _null_bump_residual(mem)
    if null is None:
        return None
    host = winning_static_pdn(mem)
    if host is None or host.qor.static_ir_mv is None:
        return None
    eid = str((host.knobs or {}).get("extract_id") or host.id)
    if eid in ("finish", ""):
        return None
    spec = next_static_strap_spec(mem)
    if spec is None:
        return None
    odb = _odb_for_extract(mem, eid)
    src = (host.knobs or {}).get("name") or (host.attr or {}).get("via") or host.id
    return {
        "level": "pdn",
        "spec": spec,
        "extract_id": eid,
        "odb": odb,
        "host_id": host.id,
        "host_source": (host.knobs or {}).get("source") or host.level,
        "static_ir_mv": float(host.qor.static_ir_mv),
        "bump_residual_mv": null["residual_mv"],
        "bump_id": null["id"],
        "reason": (
            f"bump residual {null['residual_mv']:+.3f} mV is null on-die — "
            f"{spec['name']} m4_pitch={spec['m4_pitch']} on {src} extract {eid}, "
            "same place, not bumps, not Dynamic IR-steer, not gold"
        ),
        "via": "active_f4_static_straps",
        "not": "a flattened bump+strap / pkg_r / decap / GPL / gold vector",
    }


def strap_extract_host(mem: DesignMemory):
    """Newest ok metal4-pitch extract. EM width inherits this geometry."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_static_strap_extract":
            return c
    return None


def winning_em_pdn(mem: DesignMemory):
    """Lowest 1× em_j_a_m2 on the IR/host family. Not gold, not I-scale."""
    best = None
    best_j = None
    for c in mem.by_level("pdn"):
        if c.status != "ok" or c.qor.em_j_a_m2 is None:
            continue
        if not _ir_family_1x_member(c):
            continue
        if abs(float((c.knobs or {}).get("i_scale") or 1.0) - 1.0) > 1e-9:
            continue
        eid = str((c.knobs or {}).get("extract_id") or c.id)
        if eid in ("finish", ""):
            continue
        j = float(c.qor.em_j_a_m2)
        if best_j is None or j < best_j:
            best, best_j = c, j
    return best


def steer_from_em_width_residual(mem: DesignMemory) -> dict | None:
    """Wider metal4 on the strap-pitch mesh. Not pitch, not decap, not gold.

    Waits until the pitch catalog is consumed so the residual is width-only.
    """
    from .pdn_space import next_em_strap_spec, next_static_strap_spec

    if next_static_strap_spec(mem) is not None:
        return None
    host = strap_extract_host(mem)
    if host is None or (host.knobs or {}).get("m4_pitch") is None:
        return None
    spec = next_em_strap_spec(mem, host)
    if spec is None:
        return None
    parent_eid = str((host.knobs or {}).get("parent_extract_id") or (host.knobs or {}).get("extract_id") or host.id)
    if parent_eid in ("finish", ""):
        return None
    odb = _odb_for_extract(mem, parent_eid) or _odb_for_extract(mem, str((host.knobs or {}).get("extract_id") or host.id))
    em_win = winning_em_pdn(mem)
    return {
        "level": "pdn",
        "spec": spec,
        "extract_id": parent_eid,
        "odb": odb,
        "host_id": host.id,
        "host_source": (host.knobs or {}).get("source") or host.level,
        "em_j_a_m2": float(host.qor.em_j_a_m2) if host.qor.em_j_a_m2 is not None else None,
        "winning_em_id": em_win.id if em_win else None,
        "winning_em_j": float(em_win.qor.em_j_a_m2) if em_win and em_win.qor.em_j_a_m2 is not None else None,
        "strap_pitch": spec["m4_pitch"],
        "reason": (
            f"EM width on strap mesh {host.id} m4_pitch={spec['m4_pitch']} — "
            f"{spec['name']} m4_width={spec['m4_width']} (host width "
            f"{(host.knobs or {}).get('m4_width')}), not pitch, not Dynamic IR-steer, not gold"
        ),
        "via": "active_f4_em_straps",
        "not": "a flattened pitch+width / pkg_r / decap / GPL / gold vector",
    }


NEW_RGRAPH_SOURCES = ("f4_static_strap_extract", "f4_em_strap_extract")


def extract_is_new_rgraph(mem: DesignMemory, eid: str) -> bool:
    """True when extract_id is a pdngen -ripup strap or EM-width mesh. Not gold."""
    want = str(eid)
    if want in ("finish", ""):
        return False
    for c in mem.by_level("pdn"):
        if c.status != "ok":
            continue
        if str((c.knobs or {}).get("extract_id") or c.id) != want:
            continue
        if (c.knobs or {}).get("source") in NEW_RGRAPH_SOURCES:
            return True
    return False


def steer_from_winning_ir_catalog(mem: DesignMemory) -> dict | None:
    """Unused Dynamic IR catalog on a strap/EM winning_ir extract.

    Inherits host pkg_r (C then L). Not pitch, not width, not pkg_r, not
    host/candidate IR-steer, not gold.
    """
    from .pdn_space import PDN_CATALOG, next_winning_ir_pdn_spec

    champ = winning_ir_pdn(mem)
    if champ is None or champ.qor.dynamic_ir_mv is None:
        return None
    eid = str((champ.knobs or {}).get("extract_id") or champ.id)
    if eid in ("finish", ""):
        return None
    if not extract_is_new_rgraph(mem, eid):
        return None
    spec = next_winning_ir_pdn_spec(mem, champ)
    if spec is None:
        return None
    if spec["name"] not in {s["name"] for s in PDN_CATALOG}:
        return None
    src = (champ.knobs or {}).get("name") or (champ.attr or {}).get("via") or champ.id
    host_l = float((champ.knobs or {}).get("pkg_l") or 2e-10)
    axis = "inductance" if abs(float(spec["pkg_l"]) - host_l) > 1e-18 else "decap"
    return {
        "level": "pdn",
        "spec": spec,
        "extract_id": eid,
        "host_id": champ.id,
        "host_source": (champ.knobs or {}).get("source") or champ.level,
        "dynamic_ir_mv": float(champ.qor.dynamic_ir_mv),
        "axis": axis,
        "reason": (
            f"winning_ir {src} {float(champ.qor.dynamic_ir_mv):.3f} mV extract {eid} "
            f"is a new R-graph — unused {spec['name']} ({axis}, inherit pkg_r="
            f"{spec['pkg_r']}), not pitch, not width, not pkg_r catalog, not gold"
        ),
        "via": "active_f4_winning_ir_pdn",
        "not": "a flattened pitch+width+pkg_r+decap / host IR-steer / gold vector",
    }


def ir_hotspot_cells(mem: DesignMemory) -> dict | None:
    """I-scale-win (else winning host PDN) hotspot → nearest ODB instances."""
    from .attribute import join_hotspot_insts

    host = None
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_iscale_win":
            host = c
            break
    if host is None:
        host = winning_host_pdn(mem)
    if host is None:
        return None
    attr = host.attr or {}
    art = host.artifacts or {}
    j = join_hotspot_insts(
        art.get("insts"),
        attr.get("x_dbu") if attr.get("x_dbu") is not None else art.get("x_dbu"),
        attr.get("y_dbu") if attr.get("y_dbu") is not None else art.get("y_dbu"),
    )
    if int(j.get("n") or 0) < 1:
        return None
    j["parent"] = host
    j["region"] = attr.get("region") or j.get("region")
    j["combo_frac"] = attr.get("combo_frac")
    j["seq_frac"] = attr.get("seq_frac")
    return j


def ir_cell_host(mem: DesignMemory):
    """Newest IR-hotspot cell size-up. That netlist is the next F4 extract parent."""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir":
            return c
    return None


def ir_cell_champ_host(mem: DesignMemory):
    """Newest I-scale-champ dpath size-up. Next extract parent — not first ctrl IR-cell."""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_champ":
            return c
    return None


def ir_cell_extract_cand(mem: DesignMemory):
    """Newest IR-cell write_pg_spice. Residual vs host extract lives on this point."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_extract":
            return c
    return None


def steer_from_ir_cell_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the IR-cell mesh after the 1× residual. Not host IR-steer."""
    from .pdn_space import measured_pdn_keys

    ice = ir_cell_extract_cand(mem)
    if ice is None or ice.qor.dynamic_ir_mv is None:
        return None
    res = (ice.attr or {}).get("residual_mv")
    if res is None:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_ir_cell_extract",
        "reason": (
            f"IR-cell 1× residual {float(res):+.3f} mV ({sign} droop vs host) — "
            f"restamp {spec_win['name']} on the sized mesh, not host IR-steer, not ABC"
        ),
        "ir_cell_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_ir_cell_pdn",
        "not": "a flattened cell+PDN vector / gold",
    }


def steer_from_ir_cell_hotspot(mem: DesignMemory) -> dict | None:
    """IR-cell 1× hotspot chooses region vs more combo size-up. Not host-region rXY."""
    from .acquire import latest_host_extract_cand

    ice = ir_cell_extract_cand(mem)
    if ice is None:
        return None
    attr = ice.attr or {}
    region = attr.get("region")
    x_dbu, y_dbu = attr.get("x_dbu"), attr.get("y_dbu")
    if not region and x_dbu is None:
        return None
    host_ext = latest_host_extract_cand(mem)
    host_r = (host_ext.attr or {}).get("region") if host_ext else None
    if region and host_r and str(region) == str(host_r):
        return None
    combo = float(attr.get("combo_frac") or 0.0)
    if combo >= 0.5:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    return {
        "level": "ir_cell_region",
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_ir_cell_extract",
        "region": region,
        "x_dbu": x_dbu,
        "y_dbu": y_dbu,
        "combo_frac": combo,
        "host_region": host_r,
        "reason": (
            f"IR-cell 1× bin {region or 'xy'} combo {combo:.2f} ≠ host {host_r} — "
            "seq-heavy: density cap on the sized netlist, not more combo size-up, "
            "not gold rXY, not ABC"
        ),
        "via": "active_f4_ir_cell_region",
        "not": "host-region / a flattened cell+util vector",
    }


def ir_cell_region_extract_cand(mem: DesignMemory):
    """Newest IR-cell-region write_pg_spice. Residual vs the unconstrained IR-cell extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_region_extract":
            return c
    return None


def steer_from_ir_cell_region_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the IR-cell-region mesh after a large spatial residual."""
    from .pdn_space import measured_pdn_keys

    reg = ir_cell_region_extract_cand(mem)
    if reg is None or reg.qor.dynamic_ir_mv is None:
        return None
    res = (reg.attr or {}).get("residual_mv")
    if res is None or abs(float(res)) < KNOB_MV:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((reg.knobs or {}).get("extract_id") or reg.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": reg.id,
        "host_source": "f4_ir_cell_region_extract",
        "region": (reg.knobs or {}).get("region") or (reg.attr or {}).get("region"),
        "reason": (
            f"IR-cell-region residual {float(res):+.3f} mV ({sign} droop vs 1× extract) — "
            f"restamp {spec_win['name']} on the {(reg.knobs or {}).get('region') or 'region'}-capped mesh, "
            "not host IR-steer, not ABC"
        ),
        "ir_cell_region_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_ir_cell_region_pdn",
        "not": "a flattened cell+PDN vector / gold / host-region",
    }


def iscale_champ_cand(mem: DesignMemory):
    """Newest I(t)×P shot on winning_ir_pdn. Not I-scale-win."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_iscale_champ":
            return c
    return None


def ir_champ_hotspot_cells(mem: DesignMemory) -> dict | None:
    """I-scale-champ xy → nearest ODB instances on the champion extract."""
    from .acquire import extract_on_disk
    from .attribute import join_hotspot_insts

    host = iscale_champ_cand(mem)
    if host is None:
        return None
    attr = host.attr or {}
    art = host.artifacts or {}
    eid = str((host.knobs or {}).get("extract_id") or host.id)
    hit = extract_on_disk(mem, eid)
    insts = (hit or {}).get("insts") or art.get("insts")
    j = join_hotspot_insts(
        insts,
        attr.get("x_dbu") if attr.get("x_dbu") is not None else art.get("x_dbu"),
        attr.get("y_dbu") if attr.get("y_dbu") is not None else art.get("y_dbu"),
    )
    if int(j.get("n") or 0) < 1:
        return None
    j["parent"] = host
    j["region"] = attr.get("region") or j.get("region")
    j["combo_frac"] = attr.get("combo_frac")
    j["seq_frac"] = attr.get("seq_frac")
    j["extract_id"] = eid
    return j


def steer_from_iscale_champ_hotspot(mem: DesignMemory) -> dict | None:
    """Combo-heavy I-scale-champ join that is not the first ctrl IR-cell set."""
    ice = ir_cell_host(mem)
    spec = ir_champ_hotspot_cells(mem)
    if spec is None or ice is None:
        return None
    combo = float(spec.get("combo_frac") or 0.0)
    if combo < 0.5:
        return None
    first = {str(x) for x in (ice.knobs or {}).get("cells") or []}
    cells = [str(x) for x in spec.get("cells") or []]
    if not cells or (first and set(cells) <= first):
        return None
    if not spec.get("modules"):
        return None
    mods = ",".join(spec.get("modules") or [])
    return {
        "level": "ir_cell_champ",
        "cells": cells,
        "modules": spec.get("modules"),
        "cones": spec.get("cones"),
        "region": spec.get("region"),
        "combo_frac": combo,
        "extract_id": spec.get("extract_id"),
        "reason": (
            f"I-scale-champ hotspot {spec.get('region')} combo {combo:.2f} joins "
            f"{mods} — not the first ctrl IR-cell, not STA-path size-up, not ABC, not VCD"
        ),
        "via": "active_f4_ir_cell_champ",
        "not": "a flattened cell+I-scale vector / host-win join",
    }


def ir_cell_champ_extract_cand(mem: DesignMemory):
    """Newest IR-cell-champ write_pg_spice. Residual vs the first IR-cell extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_champ_extract":
            return c
    return None


def steer_from_ir_cell_champ_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the IR-cell-champ mesh after the 1× residual."""
    from .pdn_space import measured_pdn_keys

    ice = ir_cell_champ_extract_cand(mem)
    if ice is None or ice.qor.dynamic_ir_mv is None:
        return None
    res = (ice.attr or {}).get("residual_mv")
    if res is None:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_ir_cell_champ_extract",
        "reason": (
            f"IR-cell-champ 1× residual {float(res):+.3f} mV ({sign} droop vs IR-cell extract) — "
            f"restamp {spec_win['name']} on the dpath-sized mesh, not host IR-steer, not ABC"
        ),
        "ir_cell_champ_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_ir_cell_champ_pdn",
        "not": "a flattened cell+PDN vector / gold / first IR-cell extract",
    }


def ir_cell_champ_extract_hotspot(mem: DesignMemory) -> dict | None:
    """1× IR-cell-champ extract xy → cells (attr join, else ODB insts)."""
    from .acquire import extract_on_disk
    from .attribute import join_hotspot_insts

    ice = ir_cell_champ_extract_cand(mem)
    if ice is None:
        return None
    attr = ice.attr or {}
    art = ice.artifacts or {}
    cells = [str(x) for x in (attr.get("cells") or []) if x]
    modules = list(attr.get("modules") or [])
    cones = list(attr.get("cones") or [])
    if not cells:
        eid = str((ice.knobs or {}).get("extract_id") or ice.id)
        hit = extract_on_disk(mem, eid)
        insts = (hit or {}).get("insts") or art.get("insts")
        j = join_hotspot_insts(
            insts,
            attr.get("x_dbu") if attr.get("x_dbu") is not None else art.get("x_dbu"),
            attr.get("y_dbu") if attr.get("y_dbu") is not None else art.get("y_dbu"),
        )
        if int(j.get("n") or 0) < 1:
            return None
        cells = [str(x) for x in (j.get("cells") or []) if x]
        modules = list(j.get("modules") or [])
        cones = list(j.get("cones") or [])
    if not cells:
        return None
    return {
        "parent": ice,
        "cells": cells,
        "modules": modules,
        "cones": cones,
        "region": attr.get("region"),
        "combo_frac": attr.get("combo_frac"),
        "seq_frac": attr.get("seq_frac"),
        "extract_id": str((ice.knobs or {}).get("extract_id") or ice.id),
        "x_dbu": attr.get("x_dbu"),
        "y_dbu": attr.get("y_dbu"),
        "join": attr.get("join"),
    }


def steer_from_ir_cell_champ_extract_hotspot(mem: DesignMemory) -> dict | None:
    """Combo-heavy champ-extract join whose cells are not the champ size-up set."""
    host = ir_cell_champ_host(mem)
    spec = ir_cell_champ_extract_hotspot(mem)
    if spec is None or host is None:
        return None
    combo = float(spec.get("combo_frac") or 0.0)
    if combo < 0.5:
        return None
    sized = {str(x) for x in (host.knobs or {}).get("cells") or []}
    cells = [str(x) for x in spec.get("cells") or [] if str(x) not in sized]
    if not cells:
        return None
    modules = list(
        dict.fromkeys(str(c).split("/")[0] for c in cells if "/" in str(c))
    )
    if not modules:
        return None
    mods = ",".join(modules)
    return {
        "level": "ir_cell_champ_cone",
        "cells": cells,
        "modules": modules,
        "cones": spec.get("cones"),
        "region": spec.get("region"),
        "combo_frac": combo,
        "extract_id": spec.get("extract_id"),
        "reason": (
            f"IR-cell-champ extract hotspot {spec.get('region')} combo {combo:.2f} "
            f"joins leftover {mods} — not the champ size-up set, not first ctrl IR-cell, "
            "not STA-path size-up, not ABC, not VCD"
        ),
        "via": "active_f4_ir_cell_champ_cone",
        "not": "a flattened cell+champ vector / I-scale-champ join",
    }


def ir_cell_champ_cone_host(mem: DesignMemory):
    """Newest leftover-cone size-up on an IR-cell-champ extract. Not champ ctrl."""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_champ_cone":
            return c
    return None


def ir_cell_champ_cone_extract_cand(mem: DesignMemory):
    """Newest cone write_pg_spice. Residual vs the IR-cell-champ extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_extract":
            return c
    return None


def steer_from_ir_cell_champ_cone_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the champ-cone mesh after the 1× residual."""
    from .pdn_space import measured_pdn_keys

    ice = ir_cell_champ_cone_extract_cand(mem)
    if ice is None or ice.qor.dynamic_ir_mv is None:
        return None
    res = (ice.attr or {}).get("residual_mv")
    if res is None:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_ir_cell_champ_cone_extract",
        "reason": (
            f"IR-cell-champ-cone 1× residual {float(res):+.3f} mV ({sign} droop vs champ extract) — "
            f"restamp {spec_win['name']} on the leftover-cone mesh, not champ IR-steer, not ABC"
        ),
        "ir_cell_champ_cone_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_ir_cell_champ_cone_pdn",
        "not": "a flattened cell+PDN vector / gold / champ extract",
    }


def steer_from_ir_cell_champ_cone_hotspot(mem: DesignMemory) -> dict | None:
    """Seq-heavy leftover-cone 1× bin ≠ champ-extract bin. Not more combo size-up."""
    ice = ir_cell_champ_cone_extract_cand(mem)
    if ice is None:
        return None
    attr = ice.attr or {}
    region = attr.get("region")
    x_dbu, y_dbu = attr.get("x_dbu"), attr.get("y_dbu")
    if not region and x_dbu is None:
        return None
    champ = ir_cell_champ_extract_cand(mem)
    champ_r = (champ.attr or {}).get("region") if champ else None
    if region and champ_r and str(region) == str(champ_r):
        return None
    combo = float(attr.get("combo_frac") or 0.0)
    if combo >= 0.5:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    return {
        "level": "ir_cell_champ_cone_region",
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_ir_cell_champ_cone_extract",
        "region": region,
        "x_dbu": x_dbu,
        "y_dbu": y_dbu,
        "combo_frac": combo,
        "champ_region": champ_r,
        "reason": (
            f"IR-cell-champ-cone 1× bin {region or 'xy'} combo {combo:.2f} ≠ champ {champ_r} — "
            "seq-heavy: density cap on the leftover-cone netlist, not more combo size-up, "
            "not IR-cell-region rXY, not gold rXY, not ABC"
        ),
        "via": "active_f4_ir_cell_champ_cone_region",
        "not": "IR-cell-region / host-region / a flattened cell+util vector",
    }


def ir_cell_champ_cone_region_extract_cand(mem: DesignMemory):
    """Newest leftover-cone-region write_pg_spice. Residual vs unconstrained cone extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract":
            return c
    return None


def steer_from_ir_cell_champ_cone_region_hotspot(mem: DesignMemory) -> dict | None:
    """Seq-heavy leftover-cone-region hotspot ≠ the bin we just capped. Not more combo size-up."""
    reg = ir_cell_champ_cone_region_extract_cand(mem)
    if reg is None:
        return None
    attr = reg.attr or {}
    kn = reg.knobs or {}
    region = attr.get("region")
    cap = kn.get("region")
    x_dbu, y_dbu = attr.get("x_dbu"), attr.get("y_dbu")
    if not region and x_dbu is None:
        return None
    if region and cap and str(region) == str(cap):
        return None
    champ = ir_cell_champ_extract_cand(mem)
    champ_r = (champ.attr or {}).get("region") if champ else None
    if region and champ_r and str(region) == str(champ_r):
        return None
    combo = float(attr.get("combo_frac") or 0.0)
    if combo >= 0.5:
        return None
    host = ir_cell_champ_cone_host(mem)
    hid = host.id if host else None
    if region and hid and any(
        c.status == "ok"
        and (c.knobs or {}).get("source") == "f4_ir_cell_champ_cone_region_extract"
        and str((c.knobs or {}).get("region") or "") == str(region)
        and str((c.knobs or {}).get("parent_id") or c.parent_id or "") == str(hid)
        for c in mem.by_level("pdn")
    ):
        return None
    eid = str(kn.get("extract_id") or reg.id)
    return {
        "level": "ir_cell_champ_cone_region",
        "extract_id": eid,
        "host_id": reg.id,
        "host_source": "f4_ir_cell_champ_cone_region_extract",
        "region": region,
        "x_dbu": x_dbu,
        "y_dbu": y_dbu,
        "combo_frac": combo,
        "cap_region": cap,
        "champ_region": champ_r,
        "reason": (
            f"IR-cell-champ-cone-region 1× hotspot {region or 'xy'} combo {combo:.2f} ≠ cap {cap} — "
            "seq-heavy: density cap on the leftover-cone netlist, not more combo size-up, "
            "not IR-cell-region rXY, not gold rXY, not ABC"
        ),
        "via": "active_f4_ir_cell_champ_cone_region",
        "not": "IR-cell-region / a flattened leftover-cone-region vector / more combo size-up",
    }


def steer_from_ir_cell_champ_cone_region_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the leftover-cone-region mesh after a large spatial residual."""
    from .pdn_space import measured_pdn_keys

    reg = ir_cell_champ_cone_region_extract_cand(mem)
    if reg is None or reg.qor.dynamic_ir_mv is None:
        return None
    res = (reg.attr or {}).get("residual_mv")
    if res is None or abs(float(res)) < KNOB_MV:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((reg.knobs or {}).get("extract_id") or reg.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": reg.id,
        "host_source": "f4_ir_cell_champ_cone_region_extract",
        "region": (reg.knobs or {}).get("region") or (reg.attr or {}).get("region"),
        "reason": (
            f"IR-cell-champ-cone-region residual {float(res):+.3f} mV ({sign} droop vs cone extract) — "
            f"restamp {spec_win['name']} on the {(reg.knobs or {}).get('region') or 'region'}-capped leftover mesh, "
            "not champ IR-steer, not IR-cell-region PDN, not ABC"
        ),
        "ir_cell_champ_cone_region_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_ir_cell_champ_cone_region_pdn",
        "not": "a flattened cell+PDN vector / gold / IR-cell-region / champ extract",
    }


WINNING_IR_EXTRACT_SRC = (
    "f4_em_strap_extract",
    "f4_static_strap_extract",
    "f4_ir_cell_region_extract",
    "f4_ir_cell_extract",
    "f4_ir_cell_champ_extract",
    "f4_winning_ir_region_extract",
    "f4_winning_ir_region_cell_extract",
    "f4_winning_ir_region_cell_leftover_extract",
    "f4_winning_ir_region_cell_leftover2_extract",
    "f4_host_extract",
    "f4_host_region_extract",
)


def winning_ir_extract_cand(mem: DesignMemory):
    """1× R-graph under winning_ir_pdn. Not the catalog restamp, not leftover-cone."""
    champ = winning_ir_pdn(mem)
    if champ is None:
        return None
    eid = str((champ.knobs or {}).get("extract_id") or champ.id)
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status != "ok":
            continue
        if str((c.knobs or {}).get("extract_id") or c.id) != eid:
            continue
        if (c.knobs or {}).get("source") in WINNING_IR_EXTRACT_SRC:
            return c
    return None


def steer_from_winning_ir_hotspot(mem: DesignMemory) -> dict | None:
    """Seq-heavy winning-IR 1× bin ≠ leftover-cone / IR-cell-region caps."""
    ext = winning_ir_extract_cand(mem)
    if ext is None:
        return None
    attr = ext.attr or {}
    region = attr.get("region")
    x_dbu, y_dbu = attr.get("x_dbu"), attr.get("y_dbu")
    if not region and x_dbu is None:
        return None
    combo = float(attr.get("combo_frac") or 0.0)
    if combo >= 0.5:
        return None
    ice_r = ir_cell_region_extract_cand(mem)
    ice_bin = (ice_r.knobs or {}).get("region") if ice_r else None
    if region and ice_bin and str(region) == str(ice_bin):
        return None
    capped = {
        str((c.knobs or {}).get("region") or "")
        for c in mem.by_level("pdn")
        if c.status == "ok"
        and (c.knobs or {}).get("source")
        in ("f4_winning_ir_region_extract", "f4_ir_cell_region_extract")
        and (c.knobs or {}).get("region")
    }
    if region and str(region) in capped:
        return None
    eid = str((ext.knobs or {}).get("extract_id") or ext.id)
    return {
        "level": "winning_ir_region",
        "extract_id": eid,
        "host_id": ext.id,
        "host_source": (ext.knobs or {}).get("source") or "f4_em_strap_extract",
        "region": region,
        "x_dbu": x_dbu,
        "y_dbu": y_dbu,
        "combo_frac": combo,
        "ir_cell_region": ice_bin,
        "reason": (
            f"winning-IR 1× bin {region or 'xy'} combo {combo:.2f} ≠ leftover-cone / "
            f"IR-cell-region {ice_bin} — seq-heavy: density cap on the IR-cell netlist, "
            "not leftover-cone rXY, not more combo size-up, not gold rXY, not ABC"
        ),
        "via": "active_f4_winning_ir_region",
        "not": "leftover-cone-region / IR-cell-region / a flattened cell+util vector",
    }


def winning_ir_region_extract_cand(mem: DesignMemory):
    """Newest winning-IR-region write_pg_spice. Residual vs the winning-IR extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_extract":
            return c
    return None


def steer_from_winning_ir_region_hotspot(mem: DesignMemory) -> dict | None:
    """Seq-heavy winning-IR-region hotspot ≠ the bin we just capped. Not IR-cell-region rXY."""
    reg = winning_ir_region_extract_cand(mem)
    if reg is None:
        return None
    attr = reg.attr or {}
    kn = reg.knobs or {}
    region = attr.get("region")
    cap = kn.get("region")
    x_dbu, y_dbu = attr.get("x_dbu"), attr.get("y_dbu")
    if not region and x_dbu is None:
        return None
    if region and cap and str(region) == str(cap):
        return None
    ice_r = ir_cell_region_extract_cand(mem)
    ice_bin = (ice_r.knobs or {}).get("region") if ice_r else None
    if region and ice_bin and str(region) == str(ice_bin):
        return None
    combo = float(attr.get("combo_frac") or 0.0)
    if combo >= 0.5:
        return None
    capped = {
        str((c.knobs or {}).get("region") or "")
        for c in mem.by_level("pdn")
        if c.status == "ok"
        and (c.knobs or {}).get("source")
        in ("f4_winning_ir_region_extract", "f4_ir_cell_region_extract")
        and (c.knobs or {}).get("region")
    }
    if region and str(region) in capped:
        return None
    eid = str(kn.get("extract_id") or reg.id)
    return {
        "level": "winning_ir_region",
        "extract_id": eid,
        "host_id": reg.id,
        "host_source": "f4_winning_ir_region_extract",
        "region": region,
        "x_dbu": x_dbu,
        "y_dbu": y_dbu,
        "combo_frac": combo,
        "cap_region": cap,
        "ir_cell_region": ice_bin,
        "reason": (
            f"winning-IR-region 1× hotspot {region or 'xy'} combo {combo:.2f} ≠ cap {cap} — "
            "seq-heavy: density cap on the IR-cell netlist, not leftover-cone rXY, "
            "not more combo size-up, not IR-cell-region "
            f"{ice_bin}, not gold rXY, not ABC"
        ),
        "via": "active_f4_winning_ir_region",
        "not": "leftover-cone-region / IR-cell-region / a flattened winning-IR-region vector / more combo size-up",
    }


def steer_from_winning_ir_region_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the winning-IR-region mesh after |Δ| ≥ 1 mV."""
    from .pdn_space import measured_pdn_keys

    reg = winning_ir_region_extract_cand(mem)
    if reg is None or reg.qor.dynamic_ir_mv is None:
        return None
    res = (reg.attr or {}).get("residual_mv")
    if res is None or abs(float(res)) < KNOB_MV:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((reg.knobs or {}).get("extract_id") or reg.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": reg.id,
        "host_source": "f4_winning_ir_region_extract",
        "region": (reg.knobs or {}).get("region") or (reg.attr or {}).get("region"),
        "reason": (
            f"winning-IR-region residual {float(res):+.3f} mV ({sign} droop vs winning-IR extract) — "
            f"restamp {spec_win['name']} on the {(reg.knobs or {}).get('region') or 'region'}-capped "
            "winning-IR mesh, not leftover-cone-region PDN, not ABC"
        ),
        "winning_ir_region_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_winning_ir_region_pdn",
        "not": "a flattened cell+PDN vector / gold / leftover-cone-region / champ extract",
    }


def winning_ir_region_pdn_cand(mem: DesignMemory):
    """Newest winning-IR-region PDN restamp. Combo join lives here after |Δ| decap."""
    for c in reversed(list(mem.all())):
        if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_pdn":
            return c
    return None


def winning_ir_region_cell_host(mem: DesignMemory):
    """Newest leftover combo size-up on a winning-IR-region PDN join. Not leftover-cone."""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region":
            return c
    return None


def winning_ir_region_cell_extract_cand(mem: DesignMemory):
    """Newest winning-IR-region-cell write_pg_spice. Residual vs the region extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_extract":
            return c
    return None


def steer_from_winning_ir_region_pdn_hotspot(mem: DesignMemory) -> dict | None:
    """Combo-heavy winning-IR-region PDN leftover cells ≠ IR-cell / champ / leftover-cone."""
    pdn = winning_ir_region_pdn_cand(mem)
    if pdn is None:
        return None
    attr = pdn.attr or {}
    combo = float(attr.get("combo_frac") or 0.0)
    if combo < 0.5:
        return None
    ice = ir_cell_host(mem)
    icc = ir_cell_champ_host(mem)
    iccc = ir_cell_champ_cone_host(mem)
    sized = set()
    for host in (ice, icc, iccc):
        if host is None:
            continue
        sized.update(str(x) for x in (host.knobs or {}).get("cells") or [])
    cells = [str(x) for x in (attr.get("cells") or []) if str(x) not in sized]
    if not cells:
        return None
    modules = list(dict.fromkeys(str(c).split("/")[0] for c in cells if "/" in str(c)))
    if not modules:
        return None
    eid = str((pdn.knobs or {}).get("extract_id") or pdn.id)
    mods = ",".join(modules)
    return {
        "level": "winning_ir_region_cell",
        "cells": cells,
        "modules": modules,
        "cones": attr.get("cones"),
        "region": attr.get("region"),
        "combo_frac": combo,
        "extract_id": eid,
        "host_id": pdn.id,
        "host_source": "f4_winning_ir_region_extract",
        "reason": (
            f"winning-IR-region PDN hotspot {attr.get('region') or 'xy'} combo {combo:.2f} "
            f"joins leftover {mods} — not leftover-cone size-up, not champ ctrl, "
            "not first IR-cell, not STA-path size-up, not ABC, not VCD"
        ),
        "via": "active_f4_winning_ir_region_cell",
        "not": "leftover-cone / IR-cell-champ / a flattened cell+decap vector",
    }


def steer_from_winning_ir_region_cell_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the winning-IR-region-cell mesh after the 1× residual."""
    from .pdn_space import measured_pdn_keys

    ice = winning_ir_region_cell_extract_cand(mem)
    if ice is None or ice.qor.dynamic_ir_mv is None:
        return None
    res = (ice.attr or {}).get("residual_mv")
    if res is None:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_winning_ir_region_cell_extract",
        "region": (ice.knobs or {}).get("region") or (ice.attr or {}).get("region"),
        "reason": (
            f"winning-IR-region-cell 1× residual {float(res):+.3f} mV ({sign} droop vs "
            f"winning-IR-region extract) — restamp {spec_win['name']} on the leftover-combo "
            "IR-cell mesh, not leftover-cone PDN, not champ IR-steer, not ABC"
        ),
        "winning_ir_region_cell_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_winning_ir_region_cell_pdn",
        "not": "a flattened cell+PDN vector / gold / leftover-cone / champ extract",
    }


def winning_ir_region_cell_pdn_cand(mem: DesignMemory):
    """Newest leftover-combo PDN restamp. Combo join lives here after |Δ| decap."""
    for c in reversed(list(mem.all())):
        if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_pdn":
            return c
    return None


def winning_ir_region_cell_leftover_host(mem: DesignMemory):
    """Newest leftover size-up on a leftover-combo PDN join. Not IR-cell flatten."""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover":
            return c
    return None


def winning_ir_region_cell_leftover_extract_cand(mem: DesignMemory):
    """Newest leftover-combo leftover write_pg_spice. Residual vs the cell extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover_extract":
            return c
    return None


def steer_from_winning_ir_region_cell_pdn_hotspot(mem: DesignMemory) -> dict | None:
    """Combo-heavy leftover-combo PDN leftover cells ≠ IR-cell / champ / leftover-cone / leftover-combo."""
    pdn = winning_ir_region_cell_pdn_cand(mem)
    if pdn is None:
        return None
    attr = pdn.attr or {}
    combo = float(attr.get("combo_frac") or 0.0)
    if combo < 0.5:
        return None
    ice = ir_cell_host(mem)
    icc = ir_cell_champ_host(mem)
    iccc = ir_cell_champ_cone_host(mem)
    wrc = winning_ir_region_cell_host(mem)
    sized = set()
    for host in (ice, icc, iccc, wrc):
        if host is None:
            continue
        sized.update(str(x) for x in (host.knobs or {}).get("cells") or [])
    cells = [str(x) for x in (attr.get("cells") or []) if str(x) not in sized]
    if not cells:
        return None
    modules = list(dict.fromkeys(str(c).split("/")[0] for c in cells if "/" in str(c)))
    if not modules:
        return None
    eid = str((pdn.knobs or {}).get("extract_id") or pdn.id)
    mods = ",".join(modules)
    return {
        "level": "winning_ir_region_cell_leftover",
        "cells": cells,
        "modules": modules,
        "cones": attr.get("cones"),
        "region": attr.get("region"),
        "combo_frac": combo,
        "extract_id": eid,
        "host_id": pdn.id,
        "host_source": "f4_winning_ir_region_cell_extract",
        "reason": (
            f"winning-IR-region-cell PDN hotspot {attr.get('region') or 'xy'} combo {combo:.2f} "
            f"joins leftover {mods} — not leftover-combo flatten, not leftover-cone, "
            "not champ ctrl, not first IR-cell, not STA-path size-up, not ABC, not VCD"
        ),
        "via": "active_f4_winning_ir_region_cell_leftover",
        "not": "leftover-combo flatten / leftover-cone / a flattened cell+decap vector",
    }


def steer_from_winning_ir_region_cell_leftover_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the leftover-combo leftover mesh after the 1× residual."""
    from .pdn_space import measured_pdn_keys

    ice = winning_ir_region_cell_leftover_extract_cand(mem)
    if ice is None or ice.qor.dynamic_ir_mv is None:
        return None
    res = (ice.attr or {}).get("residual_mv")
    if res is None:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_winning_ir_region_cell_leftover_extract",
        "region": (ice.knobs or {}).get("region") or (ice.attr or {}).get("region"),
        "reason": (
            f"winning-IR-region-cell leftover 1× residual {float(res):+.3f} mV ({sign} droop vs "
            f"leftover-combo extract) — restamp {spec_win['name']} on the leftover-combo leftover "
            "mesh, not leftover-combo PDN, not leftover-cone PDN, not champ IR-steer, not ABC"
        ),
        "winning_ir_region_cell_leftover_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_winning_ir_region_cell_leftover_pdn",
        "not": "a flattened cell+PDN vector / gold / leftover-combo / leftover-cone",
    }


def winning_ir_region_cell_leftover_pdn_cand(mem: DesignMemory):
    """Newest leftover leftover PDN restamp. Combo join lives here after |Δ| decap."""
    for c in reversed(list(mem.all())):
        if c.status == "ok" and (c.attr or {}).get("via") == "active_f4_winning_ir_region_cell_leftover_pdn":
            return c
    return None


def winning_ir_region_cell_leftover2_host(mem: DesignMemory):
    """Newest leftover leftover leftover size-up. Not leftover leftover flatten."""
    for c in reversed(list(mem.by_level("cell"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "cell_size_ir_winning_region_leftover2":
            return c
    return None


def winning_ir_region_cell_leftover2_extract_cand(mem: DesignMemory):
    """Newest leftover leftover leftover write_pg_spice. Residual vs leftover leftover extract."""
    for c in reversed(list(mem.by_level("pdn"))):
        if c.status == "ok" and (c.knobs or {}).get("source") == "f4_winning_ir_region_cell_leftover2_extract":
            return c
    return None


def steer_from_winning_ir_region_cell_leftover_pdn_hotspot(mem: DesignMemory) -> dict | None:
    """Combo-heavy leftover leftover PDN leftover cells ≠ leftover leftover / leftover-combo / IR-cell / champ / leftover-cone."""
    pdn = winning_ir_region_cell_leftover_pdn_cand(mem)
    if pdn is None:
        return None
    attr = pdn.attr or {}
    combo = float(attr.get("combo_frac") or 0.0)
    if combo < 0.5:
        return None
    ice = ir_cell_host(mem)
    icc = ir_cell_champ_host(mem)
    iccc = ir_cell_champ_cone_host(mem)
    wrc = winning_ir_region_cell_host(mem)
    wrl = winning_ir_region_cell_leftover_host(mem)
    sized = set()
    for host in (ice, icc, iccc, wrc, wrl):
        if host is None:
            continue
        sized.update(str(x) for x in (host.knobs or {}).get("cells") or [])
    cells = [str(x) for x in (attr.get("cells") or []) if str(x) not in sized]
    if not cells:
        return None
    modules = list(dict.fromkeys(str(c).split("/")[0] for c in cells if "/" in str(c)))
    if not modules:
        return None
    eid = str((pdn.knobs or {}).get("extract_id") or pdn.id)
    mods = ",".join(modules)
    return {
        "level": "winning_ir_region_cell_leftover2",
        "cells": cells,
        "modules": modules,
        "cones": attr.get("cones"),
        "region": attr.get("region"),
        "combo_frac": combo,
        "extract_id": eid,
        "host_id": pdn.id,
        "host_source": "f4_winning_ir_region_cell_leftover_extract",
        "reason": (
            f"winning-IR-region leftover leftover PDN hotspot {attr.get('region') or 'xy'} combo {combo:.2f} "
            f"joins leftover leftover leftover {mods} — not leftover leftover flatten, not leftover-combo, "
            "not leftover-cone, not champ ctrl, not first IR-cell, not STA-path size-up, not ABC, not VCD"
        ),
        "via": "active_f4_winning_ir_region_cell_leftover2",
        "not": "leftover leftover flatten / leftover-combo / leftover-cone / a flattened cell+decap vector",
    }


def steer_from_winning_ir_region_cell_leftover2_residual(mem: DesignMemory) -> dict | None:
    """Winning PDN family on the leftover leftover leftover mesh after the 1× residual."""
    from .pdn_space import measured_pdn_keys

    ice = winning_ir_region_cell_leftover2_extract_cand(mem)
    if ice is None or ice.qor.dynamic_ir_mv is None:
        return None
    res = (ice.attr or {}).get("residual_mv")
    if res is None:
        return None
    spec_win, knob_r = _winning_pdn_family(mem)
    if spec_win is None:
        return None
    eid = str((ice.knobs or {}).get("extract_id") or ice.id)
    have = measured_pdn_keys(mem, extract_id=eid)
    key = (float(spec_win["pkg_r"]), float(spec_win["pkg_l"]), float(spec_win["c_decap"]))
    if key in have:
        return None
    sign = "raised" if float(res) > 0 else "lowered"
    return {
        "level": "pdn",
        "spec": spec_win,
        "extract_id": eid,
        "host_id": ice.id,
        "host_source": "f4_winning_ir_region_cell_leftover2_extract",
        "region": (ice.knobs or {}).get("region") or (ice.attr or {}).get("region"),
        "reason": (
            f"winning-IR-region leftover leftover leftover 1× residual {float(res):+.3f} mV ({sign} droop vs "
            f"leftover leftover extract) — restamp {spec_win['name']} on the leftover leftover leftover "
            "mesh, not leftover leftover PDN, not leftover-combo PDN, not leftover-cone PDN, not champ IR-steer, not ABC"
        ),
        "winning_ir_region_cell_leftover2_residual_mv": float(res),
        "knob_residual_mv": knob_r,
        "via": "active_f4_winning_ir_region_cell_leftover2_pdn",
        "not": "a flattened cell+PDN vector / gold / leftover leftover / leftover-combo / leftover-cone",
    }
