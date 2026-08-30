"""PDN search space — separate from ABC sequences and placer util.

c_decap / pkg L stay on the pdn level. A re-solve names the extract
(`finish` vs a candidate write_pg_spice id). It is not gold and not a new P&R.
"""

from __future__ import annotations

from .memory import DesignMemory

# Baseline (ingest gold) is pkg_l=2e-10, c_decap=50e-15, pkg_r=0.05.
# Catalog points are *deltas* from that teacher.
PDN_CATALOG: list[dict] = [
    {"name": "decap_200f", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 200e-15},
    {"name": "pkg_l_100p", "pkg_r": 0.05, "pkg_l": 1e-10, "c_decap": 50e-15},
]

# Static IR is DC ohmic drop. Decap / pkg L do not move it (live champ
# stays 6.178 mV across gold knobs and decap_200f). pkg_r is its own
# catalog — not flattened into PDN_CATALOG / next_pdn_spec.
STATIC_PDN_CATALOG: list[dict] = [
    {"name": "pkg_r_25m", "pkg_r": 0.025, "pkg_l": 2e-10, "c_decap": 50e-15},
]

# On-die static IR. Live pkg_r_25m on b7cc was Δ=+0.000 because solve_static
# fixes ideal bump V sources. Denser bumps restamp the same ODB — not GPL,
# not flattened into PDN_CATALOG / STATIC_PDN_CATALOG.
STATIC_MESH_CATALOG: list[dict] = [
    {"name": "bumps_80", "bump_dx": 80.0, "bump_dy": 80.0, "bump_size": 40.0, "bump_interval": 3},
]

# On-die static IR after a null bump residual (GCD die ~40 µm: bump_dx 80
# still n_v=5). Denser metal4 straps, same legalized ODB — pdngen -ripup,
# not a new GPL, not flattened into PDN / STATIC_PDN / STATIC_MESH.
# Pitch 28 is a no-op on this core (same n_r as 56); 8.0 adds M4 straps.
STATIC_STRAP_CATALOG: list[dict] = [
    {
        "name": "m4_pitch_8",
        "m4_pitch": 8.0,
        "m4_width": 0.48,
        "m7_pitch": 30.0,
        "m7_width": 1.40,
    },
]

# EM J = I/(w t). Pitch already moved IR; width is its own catalog — inherit
# host m4_pitch so the residual is width-only. Not flattened into STATIC_STRAP.
EM_STRAP_CATALOG: list[dict] = [
    {"name": "m4_width_96", "m4_width": 0.96},
]

GOLD_KNOBS = {"pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 50e-15}


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
    pkg_l = float(k.get("pkg_l") or GOLD_KNOBS["pkg_l"])
    c_decap = float(k.get("c_decap") or GOLD_KNOBS["c_decap"])
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
