"""Attributed physical feedback: IR/timing → region → cells/nets → cone.

Does not invent an RTL rewrite. Stores transformation+context hooks so a
later cell-local or cone-local search can target named instances instead
of restarting chip DSE.

Hierarchy: chip → block → region → logic_cone → cell → net.
"""

from __future__ import annotations

import json
from pathlib import Path

HIERARCHY = ["chip", "block", "region", "logic_cone", "cell", "net"]


def _module_of(name: str | None) -> str | None:
    if not name:
        return None
    n = str(name).replace("\\", "")
    if n.startswith("dpath.") or n.startswith("dpath/"):
        return "dpath"
    if n.startswith("ctrl.") or n.startswith("ctrl/"):
        return "ctrl"
    if "dpath" in n:
        return "dpath"
    if "ctrl" in n:
        return "ctrl"
    for sep in ("/", "."):
        if sep in n:
            head = n.split(sep)[0]
            if head:
                return head
    return None


def _cones_of(name: str | None) -> list[str]:
    """Hierarchical STA: dpath/sub/_122_ → [dpath, dpath/sub]; aes/sa00/u0 → [aes, aes/sa00]."""
    if not name:
        return []
    n = str(name).replace("\\", "").split()[0]
    if "/" in n:
        parts = [p for p in n.split("/") if p]
    elif "." in n:
        parts = [p for p in n.split(".") if p]
    else:
        m = _module_of(n)
        return [m] if m else []
    if not parts:
        return []
    if parts[0] not in ("dpath", "ctrl"):
        m = _module_of(n)
        head = m or parts[0]
        out = [head]
        if len(parts) >= 2 and not parts[1].startswith("_"):
            out.append(f"{head}/{parts[1]}")
        return out
    out = [parts[0]]
    if len(parts) >= 2 and not parts[1].startswith("_"):
        out.append(f"{parts[0]}/{parts[1]}")
    return out


def _cell_of(name: str | None) -> str | None:
    if not name:
        return None
    n = str(name).replace("\\", "")
    return n.split()[0] if n else None


def _region(x_dbu: float | None, y_dbu: float | None, *, bins: int = 4, die_dbu: float = 80000.0) -> str | None:
    if x_dbu is None or y_dbu is None:
        return None
    nx = min(bins - 1, max(0, int(bins * float(x_dbu) / max(die_dbu, 1.0))))
    ny = min(bins - 1, max(0, int(bins * float(y_dbu) / max(die_dbu, 1.0))))
    return f"r{nx}{ny}"


def ir_report_from_solve(dyn: dict | None, *, insts: Path | str | None = None) -> dict:
    """F4 worker payload → attribution report. Inst map is the ODB-geom fallback."""
    dyn = dyn or {}
    em = dyn.get("em") if isinstance(dyn.get("em"), dict) else {}
    report: dict = {
        "hotspot": {
            "node": dyn.get("worst_node"),
            "droop_mv": dyn.get("worst_droop_mv"),
            "x_dbu": dyn.get("x_dbu"),
            "y_dbu": dyn.get("y_dbu"),
            "contributors": {
                "seq_frac": dyn.get("seq_frac"),
                "combo_frac": dyn.get("combo_frac"),
            },
        },
        "em": em,
    }
    am = dyn.get("activity_model")
    if isinstance(am, dict) and am:
        report["activity_model"] = am
    src = insts if insts is not None else dyn.get("insts")
    if src:
        report["insts"] = str(src)
    return report


def attribute_dynamic_ir(report: dict) -> dict:
    """Trace Dynamic IR hotspot toward a logic cone.

    Join order (do not flatten):
      1. OpenSTA worst-path start/end names.
      2. ODB inst_power_map geometric join at the hotspot (x_dbu, y_dbu)
         when STA has no module names (combo-heavy F4 shots often have none).
    """
    hs = report.get("hotspot") or {}
    path = ((report.get("activity_model") or {}).get("sta") or {}).get("worst_path") or {}
    em = report.get("em") or {}
    start = path.get("startpoint")
    end = path.get("endpoint")
    modules: list[str] = []
    cones: list[str] = []
    cells: list[str] = []
    join = "none"
    for n in (start, end):
        m = _module_of(n)
        if m and m not in modules:
            modules.append(m)
        for cone in _cones_of(n):
            if cone not in cones:
                cones.append(cone)
        c = _cell_of(n)
        if c and c not in cells:
            cells.append(c)
    if modules:
        join = "sta-path"
    if not modules:
        j = join_hotspot_insts(
            report.get("insts"),
            hs.get("x_dbu"),
            hs.get("y_dbu"),
        )
        if int(j.get("n") or 0) >= 1:
            modules = list(j.get("modules") or [])
            cones = list(j.get("cones") or [])
            cells = list(j.get("cells") or [])
            join = "odb-geom"
    timing = hs.get("timing") or {}
    contrib = hs.get("contributors") or {}
    region = _region(hs.get("x_dbu"), hs.get("y_dbu"))
    if modules:
        scope = "logic_cone"
    elif region:
        scope = "region"
    elif hs.get("node"):
        scope = "block"
    else:
        scope = "chip"
    status = "READY" if (hs.get("node") or modules) else "GAP"
    via_note = {
        "sta-path": "OpenSTA worst path → ",
        "odb-geom": "ODB inst join → ",
    }.get(join, "OpenSTA worst path → ")
    return {
        "status": status,
        "kind": "ir_hotspot",
        "node": hs.get("node"),
        "x_dbu": hs.get("x_dbu"),
        "y_dbu": hs.get("y_dbu"),
        "region": region,
        "droop_mv": hs.get("droop_mv"),
        "seq_frac": contrib.get("seq_frac"),
        "combo_frac": contrib.get("combo_frac"),
        "path_start": start,
        "path_end": end,
        "path_slack_ns": timing.get("path_slack_ns") or path.get("slack_ns"),
        "modules": modules,
        "cones": cones,
        "cells": cells,
        "nets": list(hs.get("nets") or []),
        "scope": scope,
        "join": join,
        "hierarchy": list(HIERARCHY),
        "em_j_a_m2": em.get("j_absmax_a_m2"),
        "dT_mesh_k": em.get("dT_mesh_absmax_k"),
        "note": (
            "IR hotspot + "
            + via_note
            + (f"cone {','.join(modules)}" if modules else "(no module join)")
            + (f" · region {region}" if region else "")
            + "; hierarchical focus, not a chip-wide restart"
        ),
    }


def join_hotspot_insts(
    insts_path: Path | str | None,
    x_dbu: float | None,
    y_dbu: float | None,
    *,
    k: int = 5,
    max_dbu: float = 8000.0,
    prefer_combo: bool = True,
) -> dict:
    """Nearest ODB instances to an IR hotspot. Same-extract geometry, not a VCD remap."""
    if not insts_path or x_dbu is None or y_dbu is None:
        return {
            "n": 0,
            "cells": [],
            "modules": [],
            "via": "no hotspot / inst map",
            "not": "an invented RTL→ITerm map",
        }
    p = Path(insts_path)
    if not p.is_file():
        return {
            "n": 0,
            "cells": [],
            "modules": [],
            "via": "inst_power_map missing",
            "not": "an invented RTL→ITerm map",
        }
    data = json.loads(p.read_text())
    hx, hy = float(x_dbu), float(y_dbu)

    def _rank(*, combo_only: bool) -> list[tuple[float, dict]]:
        out: list[tuple[float, dict]] = []
        for i in data.get("insts") or []:
            if i.get("filler"):
                continue
            if combo_only and i.get("seq"):
                continue
            dx = float(i.get("x") or 0.0) - hx
            dy = float(i.get("y") or 0.0) - hy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > max_dbu:
                continue
            out.append((dist, i))
        out.sort(key=lambda t: t[0])
        return out

    ranked = _rank(combo_only=prefer_combo)
    if not ranked and prefer_combo:
        ranked = _rank(combo_only=False)
    picked = [i for _, i in ranked[:k]]
    cells = [str(i.get("name") or "") for i in picked if i.get("name")]
    modules: list[str] = []
    cones: list[str] = []
    for n in cells:
        m = _module_of(n)
        if m and m not in modules:
            modules.append(m)
        for cone in _cones_of(n):
            if cone not in cones:
                cones.append(cone)
    die = data.get("die") if isinstance(data.get("die"), dict) else {}
    die_dbu = max(float(die.get("x1") or 0.0), float(die.get("y1") or 0.0)) or 80000.0
    n_seq = sum(1 for i in picked if i.get("seq"))
    n_combo = len(picked) - n_seq
    n_pick = max(len(picked), 1)
    return {
        "n": len(cells),
        "cells": cells,
        "modules": modules,
        "cones": cones,
        "n_seq": n_seq,
        "n_combo": n_combo,
        "combo_frac": n_combo / n_pick,
        "seq_frac": n_seq / n_pick,
        "nearest_dbu": ranked[0][0] if ranked else None,
        "region": _region(hx, hy, die_dbu=die_dbu),
        "insts": str(p),
        "via": "ODB inst_power_map geometric join — not a VCD remap",
        "not": "an invented RTL→ITerm map",
    }


def persist_hotspot_join(cand) -> bool:
    """Fill empty IR cells from ODB-geom. Does not invent an RTL→ITerm map."""
    attr = dict(cand.attr or {})
    if attr.get("cells"):
        return False
    art = cand.artifacts or {}
    j = join_hotspot_insts(
        art.get("insts") or attr.get("insts"),
        attr.get("x_dbu") if attr.get("x_dbu") is not None else art.get("x_dbu"),
        attr.get("y_dbu") if attr.get("y_dbu") is not None else art.get("y_dbu"),
    )
    if int(j.get("n") or 0) < 1:
        return False
    attr["cells"] = list(j.get("cells") or [])
    attr["modules"] = list(j.get("modules") or [])
    attr["cones"] = list(j.get("cones") or [])
    attr["join"] = "odb-geom"
    if j.get("combo_frac") is not None and attr.get("combo_frac") is None:
        attr["combo_frac"] = j.get("combo_frac")
        attr["seq_frac"] = j.get("seq_frac")
    if j.get("region") and not attr.get("region"):
        attr["region"] = j.get("region")
    attr["scope"] = "logic_cone" if attr.get("modules") else attr.get("scope") or "region"
    cand.attr = attr
    return True


def inspect_f4(cand, *, design_id: str | None = None) -> dict:
    """Attribute a paid F4 candidate: node → xy → ODB join → block/cone.

    Flattened Yosys names keep ``DesignSpec.top`` as the block. A design
    without ``dpath``/``ctrl`` cones never inherits those GCD names.
    """
    from .designs import resolve

    spec = resolve(design_id or getattr(cand, "design_id", None) or "gcd")
    art = dict(cand.artifacts or {})
    attr = dict(cand.attr or {})
    node = attr.get("node") or art.get("worst_node") or art.get("static_node")
    x = attr.get("x_dbu") if attr.get("x_dbu") is not None else art.get("x_dbu")
    y = attr.get("y_dbu") if attr.get("y_dbu") is not None else art.get("y_dbu")
    if (x is None or y is None) and node:
        try:
            from pdn_activity import node_xy
        except ImportError:
            import sys

            scripts = Path(__file__).resolve().parents[1] / "scripts"
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            from pdn_activity import node_xy  # type: ignore

        xy = node_xy(str(node))
        if xy:
            x, y = xy
    if x is not None:
        attr["x_dbu"] = float(x)
    if y is not None:
        attr["y_dbu"] = float(y)
    if node:
        attr["node"] = node
    cand.attr = attr
    persist_hotspot_join(cand)
    attr = dict(cand.attr or {})
    modules = [str(m) for m in (attr.get("modules") or []) if m]
    cones = [str(c) for c in (attr.get("cones") or []) if c]
    if not spec.has_cone("dpath"):
        modules = [m for m in modules if m not in ("dpath", "ctrl")]
        cones = [
            c
            for c in cones
            if not str(c).startswith("dpath") and not str(c).startswith("ctrl")
        ]
    if not modules:
        modules = [spec.top]
    if not cones:
        cones = [spec.top]
    attr["modules"] = modules
    attr["cones"] = cones
    attr["scope"] = "logic_cone" if modules else (attr.get("scope") or "region")
    attr["via"] = attr.get("via") or "inspect_f4"
    attr["kind"] = "ir_hotspot"
    attr["status"] = "READY" if (attr.get("cells") or node) else "GAP"
    attr["design_id"] = spec.id
    attr["not"] = [
        "gcd dpath/ctrl leftover",
        "invented RTL→ITerm map",
        "gold 45.298 restamp",
        "flattened cell+PDN vector",
    ]
    attr["note"] = (
        f"F4 inspect {spec.id} node={node} region={attr.get('region')} "
        f"join={attr.get('join')} cells={len(attr.get('cells') or [])} "
        f"block={','.join(modules)} — hierarchy from ODB/names, not a chip restart"
    )
    cand.attr = attr
    return attr


def local_scope(attr: dict) -> dict:
    """chip → block → region → cone. Do not flatten back into a global restart."""
    modules = list(attr.get("modules") or [])
    region = attr.get("region")
    scope = attr.get("scope") or ("logic_cone" if modules else "chip")
    return {
        "scope": scope,
        "modules": modules,
        "cones": list(attr.get("cones") or []),
        "cells": list(attr.get("cells") or []),
        "nets": list(attr.get("nets") or []),
        "region": region,
        "restart_chip": False,
        "focus": modules[0] if modules else (region or "chip"),
        "hierarchy": list(HIERARCHY),
    }


def attribute_sta(sta: dict, *, inherit: dict | None = None) -> dict:
    """STA worst path → cone. Flattened netlists often lose dpath/ctrl names."""
    inherit = inherit or {}
    start = sta.get("path_start")
    end = sta.get("path_end")
    modules: list[str] = []
    cones: list[str] = []
    cells: list[str] = []
    for n in list(sta.get("path_cells") or []) + [start, end]:
        m = _module_of(n)
        if m and m not in modules:
            modules.append(m)
        for cone in _cones_of(n):
            if cone not in cones:
                cones.append(cone)
        c = _cell_of(n)
        if c and c not in cells:
            cells.append(c)
    if not modules:
        modules = list(inherit.get("modules") or [])
        cones = list(inherit.get("cones") or cones)
    scope = "logic_cone" if modules else (inherit.get("scope") or "chip")
    return {
        "status": "READY" if (start or modules) else "GAP",
        "kind": "sta_path",
        "path_start": start,
        "path_end": end,
        "path_slack_ns": sta.get("wns_ns"),
        "modules": modules,
        "cones": cones,
        "cells": cells,
        "nets": list(sta.get("path_nets") or inherit.get("nets") or []),
        "scope": "cell" if cells else scope,
        "hierarchy": list(HIERARCHY),
        "restart_chip": False,
        "inherited_from": inherit.get("transform") or inherit.get("inherited_from"),
        "note": (
            "OpenSTA worst path → "
            + (f"cone {','.join(modules)}" if modules else "flattened pins (cone inherited)")
            + "; not Dynamic IR"
        ),
    }


def attribute_from_path(path: Path) -> dict:
    if not path.is_file():
        return {"status": "GAP", "reason": f"missing {path}"}
    return attribute_dynamic_ir(json.loads(path.read_text()))


def ctrl_on_path(attr: dict | None = None, *, cells: list | None = None) -> bool:
    """True when STA/IR names the FSM — not inferred from leftover-of-dpath."""
    if attr:
        if "ctrl" in (attr.get("modules") or []):
            return True
        cells = list(attr.get("cells") or []) + list(cells or [])
    for n in cells or []:
        s = str(n)
        if s.startswith("ctrl/") or s.startswith("ctrl.") or "/ctrl/" in s:
            return True
    return False
