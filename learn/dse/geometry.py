"""Locked scene for A. CORE_UTILIZATION alone does not freeze the die."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .contracts import GeometryContract, geometry_scene_hash, hash_file


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def geometry_a_path() -> Path:
    return Path(__file__).with_name("geometry_a.json")


def load_geometry_a() -> dict[str, Any]:
    return json.loads(geometry_a_path().read_text())


def parse_def_geometry(path: Path | str) -> dict[str, Any]:
    text = Path(path).read_text(errors="replace")
    um = 2000
    m_u = re.search(r"UNITS DISTANCE MICRONS\s+(\d+)", text)
    if m_u:
        um = int(m_u.group(1))
    m_d = re.search(
        r"DIEAREA\s*\(\s*([-\d]+)\s+([-\d]+)\s*\)\s*\(\s*([-\d]+)\s+([-\d]+)\s*\)",
        text,
    )
    if not m_d:
        raise ValueError(f"no DIEAREA in {path}")
    dllx, dlly, durx, dury = (int(m_d.group(i)) for i in range(1, 5))
    rows = re.findall(
        r"^ROW\s+\S+\s+\S+\s+(-?\d+)\s+(-?\d+)\s+\S+\s+DO\s+(\d+)\s+BY\s+\d+\s+STEP\s+(-?\d+)",
        text,
        re.M,
    )
    core = None
    n_rows = len(rows)
    if rows:
        x0 = int(rows[0][0])
        y0 = int(rows[0][1])
        n_sites = int(rows[0][2])
        x_step = int(rows[0][3])
        y_last = int(rows[-1][1])
        pitch = int(rows[1][1]) - y0 if len(rows) > 1 else x_step
        core = (x0, y0, x0 + n_sites * x_step, y_last + pitch)
    die_um = [v / um for v in (dllx, dlly, durx, dury)]
    core_um = [v / um for v in core] if core else None
    die_um2 = abs((die_um[2] - die_um[0]) * (die_um[3] - die_um[1]))
    core_um2 = (
        abs((core_um[2] - core_um[0]) * (core_um[3] - core_um[1])) if core_um else None
    )
    return {
        "units_distance_microns": um,
        "die_dbu": [dllx, dlly, durx, dury],
        "core_dbu": list(core) if core else None,
        "die_area": " ".join(f"{v:g}" for v in die_um),
        "core_area": " ".join(f"{v:g}" for v in core_um) if core_um else None,
        "die_um2": die_um2,
        "core_um2": core_um2,
        "rows": n_rows,
        "path": str(path),
        "sha256": hash_file(path),
    }


def locked_contract_a() -> GeometryContract:
    blob = load_geometry_a()
    return GeometryContract(
        kind="fixed",
        die_um2=float(blob["die_um2"]),
        core_um2=float(blob["core_um2"]),
        rows=int(blob["rows"]),
        core_utilization_knob=None,
        scene_hash=geometry_scene_hash(
            die_um2=float(blob["die_um2"]),
            core_um2=float(blob["core_um2"]),
            rows=int(blob["rows"]),
            knob=None,
        ),
    )


def orfs_lock_env() -> dict[str, str]:
    """Env for make: DIE_AREA/CORE_AREA set, CORE_UTILIZATION empty (mutex)."""
    blob = load_geometry_a()
    return {
        "DIE_AREA": str(blob["die_area"]),
        "CORE_AREA": str(blob["core_area"]),
        "CORE_UTILIZATION": "",
    }
