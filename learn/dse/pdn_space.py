"""PDN search space — separate from ABC sequences and placer util.

c_decap / pkg L stay on the pdn level. A re-solve names the extract
(`finish` vs a candidate write_pg_spice id). All comparisons are scoped to
the live extract selected by the caller.
"""

from __future__ import annotations

from .memory import DesignMemory

# Catalog points are explicit experiment inputs. They are not recorded results.
PDN_CATALOG: list[dict] = [
    {"name": "decap_200f", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15},
    {"name": "pkg_l_100p", "pkg_r": 0.05, "pkg_l": 1e-10, "c_decap": 50e-15},
]

# Static IR is DC ohmic drop. Decap / pkg L do not move it in this model.
# pkg_r is its own catalog — not flattened into PDN_CATALOG / next_pdn_spec.
STATIC_PDN_CATALOG: list[dict] = [
    {"name": "pkg_r_25m", "pkg_r": 0.025, "pkg_l": 2e-10, "c_decap": 50e-15},
]

# On-die static IR. Denser bumps use the current ODB and are not GPL changes.
STATIC_MESH_CATALOG: list[dict] = [
    {"name": "bumps_80", "bump_dx": 80.0, "bump_dy": 80.0, "bump_size": 40.0, "bump_interval": 3},
]

# On-die static IR with denser metal4 straps and the current legalized ODB.
STATIC_STRAP_CATALOG: list[dict] = [
    {
        "name": "m4_pitch_8",
        "m4_pitch": 8.0,
        "m4_width": 0.48,
        "m7_pitch": 30.0,
        "m7_width": 1.40,
    },
]

# EM J = I/(w t). Width is its own catalog and inherits the host pitch.
EM_STRAP_CATALOG: list[dict] = [
    {"name": "m4_width_96", "m4_width": 0.96},
]

def _extract_id(knobs: dict) -> str:
    return str(knobs.get("extract_id") or "finish")


def measured_pdn_keys(
    mem: DesignMemory, *, extract_id: str = "finish"
) -> set[tuple[float, float, float]]:
    keys: set[tuple[float, float, float]] = set()
    for c in mem.by_level("pdn"):
        k = c.knobs or {}
        if k.get("source") not in ("f4_solver_a", "ingest_pdn"):
            continue
        if _extract_id(k) != extract_id:
            continue
        if k.get("pkg_l") is None or k.get("c_decap") is None:
            continue
        keys.add((float(k.get("pkg_r") or 0.05), float(k["pkg_l"]), float(k["c_decap"])))
    return keys


def next_pdn_spec(mem: DesignMemory, *, extract_id: str = "finish") -> dict | None:
    have = measured_pdn_keys(mem, extract_id=extract_id)
    for spec in PDN_CATALOG:
        key = (float(spec["pkg_r"]), float(spec["pkg_l"]), float(spec["c_decap"]))
        if key not in have:
            return spec
    return None


def next_static_pdn_spec(mem: DesignMemory, host) -> dict | None:
    """pkg_r delta on the static-IR champion. Inherits host L/C so residual is pkg_r-only."""
    if host is None:
        return None
    k = host.knobs or {}
    eid = str(k.get("extract_id") or getattr(host, "id", "finish"))
    have = measured_pdn_keys(mem, extract_id=eid)
    if k.get("pkg_l") is None or k.get("c_decap") is None:
        return None
    pkg_l = float(k["pkg_l"])
    c_decap = float(k["c_decap"])
    for spec in STATIC_PDN_CATALOG:
        out = {
            "name": spec["name"],
            "pkg_r": float(spec["pkg_r"]),
            "pkg_l": pkg_l,
            "c_decap": c_decap,
        }
        key = (out["pkg_r"], out["pkg_l"], out["c_decap"])
        if key not in have:
            return out
    return None


def measured_static_mesh_keys(mem: DesignMemory) -> set[tuple[float, float]]:
    keys: set[tuple[float, float]] = set()
    for c in mem.by_level("pdn"):
        k = c.knobs or {}
        if c.status != "ok" or k.get("source") != "f4_static_mesh_extract":
            continue
        if k.get("bump_dx") is None or k.get("bump_dy") is None:
            continue
        keys.add((float(k["bump_dx"]), float(k["bump_dy"])))
    return keys


def next_static_mesh_spec(mem: DesignMemory) -> dict | None:
    have = measured_static_mesh_keys(mem)
    for spec in STATIC_MESH_CATALOG:
        key = (float(spec["bump_dx"]), float(spec["bump_dy"]))
        if key not in have:
            return dict(spec)
    return None


def measured_static_strap_keys(mem: DesignMemory) -> set[float]:
    keys: set[float] = set()
    for c in mem.by_level("pdn"):
        k = c.knobs or {}
        if c.status != "ok" or k.get("source") != "f4_static_strap_extract":
            continue
        if k.get("m4_pitch") is None:
            continue
        keys.add(float(k["m4_pitch"]))
    return keys


def next_static_strap_spec(mem: DesignMemory) -> dict | None:
    have = measured_static_strap_keys(mem)
    for spec in STATIC_STRAP_CATALOG:
        if float(spec["m4_pitch"]) not in have:
            return dict(spec)
    return None


def host_m4_geometry(host) -> dict:
    k = (host.knobs if host is not None else {}) or {}
    return {
        "m4_pitch": float(k.get("m4_pitch") or 8.0),
        "m4_width": float(k.get("m4_width") or 0.48),
        "m7_pitch": float(k.get("m7_pitch") or 30.0),
        "m7_width": float(k.get("m7_width") or 1.40),
    }


def measured_em_strap_keys(mem: DesignMemory) -> set[tuple[float, float]]:
    keys: set[tuple[float, float]] = set()
    for c in mem.by_level("pdn"):
        k = c.knobs or {}
        if c.status != "ok" or k.get("source") != "f4_em_strap_extract":
            continue
        if k.get("m4_pitch") is None or k.get("m4_width") is None:
            continue
        keys.add((float(k["m4_pitch"]), float(k["m4_width"])))
    return keys


def next_winning_ir_pdn_spec(mem: DesignMemory, host) -> dict | None:
    """Unused Dynamic IR catalog on a new strap/EM R-graph.

    Inherits host pkg_r so the residual is C then L — not a flattened
    pkg_r+decap vector, not pitch, not width. Host (R,L,C) is already the 1×
    extract solve.
    """
    if host is None:
        return None
    k = host.knobs or {}
    eid = str(k.get("extract_id") or getattr(host, "id", "finish"))
    have = set(measured_pdn_keys(mem, extract_id=eid))
    if any(k.get(key) is None for key in ("pkg_r", "pkg_l", "c_decap")):
        return None
    host_r = float(k["pkg_r"])
    host_l = float(k["pkg_l"])
    host_c = float(k["c_decap"])
    have.add((host_r, host_l, host_c))
    for spec in PDN_CATALOG:
        if abs(float(spec["pkg_l"]) - host_l) > 1e-18:
            continue
        out = {
            "name": spec["name"],
            "pkg_r": host_r,
            "pkg_l": host_l,
            "c_decap": float(spec["c_decap"]),
        }
        key = (out["pkg_r"], out["pkg_l"], out["c_decap"])
        if key not in have:
            return out
    for spec in PDN_CATALOG:
        if abs(float(spec["c_decap"]) - host_c) > 1e-18:
            continue
        out = {
            "name": spec["name"],
            "pkg_r": host_r,
            "pkg_l": float(spec["pkg_l"]),
            "c_decap": host_c,
        }
        key = (out["pkg_r"], out["pkg_l"], out["c_decap"])
        if key not in have:
            return out
    return None


def next_em_strap_spec(mem: DesignMemory, host) -> dict | None:
    """Wider metal4 on the strap-pitch host. Residual is width-only."""
    geom = host_m4_geometry(host)
    have = measured_em_strap_keys(mem)
    for spec in EM_STRAP_CATALOG:
        out = {
            "name": spec["name"],
            "m4_pitch": geom["m4_pitch"],
            "m4_width": float(spec["m4_width"]),
            "m7_pitch": geom["m7_pitch"],
            "m7_width": geom["m7_width"],
        }
        key = (out["m4_pitch"], out["m4_width"])
        if key not in have and abs(out["m4_width"] - geom["m4_width"]) > 1e-9:
            return out
    return None
