"""Attributed physical feedback: IR/timing → region → cells → RTL module.

Does not invent an RTL rewrite. Stores transformation+context hooks so a
later cone-local search can target dpath vs ctrl instead of restarting chip DSE.

Hierarchy: chip → block → region → logic_cone.
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
    cells: list[str] = []
    for n in (start, end):
        m = _module_of(n)
        if m and m not in modules:
            modules.append(m)
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
        "cells": cells,
        "scope": scope,
        "hierarchy": ["chip", "block", "region", "logic_cone"],
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
        "cells": list(attr.get("cells") or []),
        "region": region,
        "restart_chip": False,
        "focus": modules[0] if modules else (region or "chip"),
        "hierarchy": ["chip", "block", "region", "logic_cone"],
    }


def attribute_from_path(path: Path) -> dict:
    if not path.is_file():
        return {"status": "GAP", "reason": f"missing {path}"}
    return attribute_dynamic_ir(json.loads(path.read_text()))
