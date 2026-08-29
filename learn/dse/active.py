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
