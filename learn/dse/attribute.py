"""Attributed physical feedback: IR/timing → region → cells/nets → cone.

Does not invent an RTL rewrite. Stores transformation+context hooks so a
later cell-local or cone-local search can target named instances instead
of restarting chip DSE.

Hierarchy: chip → block → region → logic_cone → cell.
"""

from __future__ import annotations

import json
from pathlib import Path


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
    return None


def _cones_of(name: str | None) -> list[str]:
    """Hierarchical STA: dpath/sub/_122_ → [dpath, dpath/sub]."""
    if not name:
        return []
    n = str(name).replace("\\", "").split()[0]
    if "/" in n:
        parts = [p for p in n.split("/") if p]
    elif n.startswith("dpath.") or n.startswith("ctrl."):
        parts = [p for p in n.split(".") if p]
    else:
        m = _module_of(n)
        return [m] if m else []
    if not parts or parts[0] not in ("dpath", "ctrl"):
        m = _module_of(n)
        return [m] if m else []
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


def attribute_dynamic_ir(report: dict) -> dict:
    """Trace Dynamic IR hotspot toward a logic cone. GAP if names do not join."""
    hs = report.get("hotspot") or {}
    path = ((report.get("activity_model") or {}).get("sta") or {}).get("worst_path") or {}
    em = report.get("em") or {}
    start = path.get("startpoint")
    end = path.get("endpoint")
    modules: list[str] = []
    cones: list[str] = []
    cells: list[str] = []
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
        "hierarchy": ["chip", "block", "region", "logic_cone", "cell"],
        "em_j_a_m2": em.get("j_absmax_a_m2"),
        "dT_mesh_k": em.get("dT_mesh_absmax_k"),
        "note": (
            "IR hotspot + OpenSTA worst path → "
            + (f"cone {','.join(modules)}" if modules else "(no module join)")
            + (f" · region {region}" if region else "")
            + "; hierarchical focus, not a chip-wide restart"
        ),
    }


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
        "hierarchy": ["chip", "block", "region", "logic_cone", "cell"],
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
        "hierarchy": ["chip", "block", "region", "logic_cone", "cell"],
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
