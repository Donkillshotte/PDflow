#!/usr/bin/env python3
"""EM + lumped thermal reporting on the PDN graph.

J from branch I and a width inferred from R, length, and LEF RPERSQ.
PDN straps are usually wider than min WIDTH; when inferred w is below
min WIDTH (OpenROAD R is not a pure rectangle), w is clamped to min WIDTH
so J is not a 10^12 A/m² artifact. Thickness from LEF. Black TTF is
*relative* (∝ J^{-n}); no foundry A. Thermal is lumped P→ΔT→R(T), not a
3D solver, and not a sub-ns TRAN (thermal RC is much slower).
Never ML.
"""

from __future__ import annotations

import math

from pdn_extract import layer_of, node_xy_dbu

# Cu-class. Documented, not a foundry card.
ALPHA_R = 0.0039  # 1/K
EA_EV = 0.9
K_EV = 8.617333262145e-5
BLACK_N = 2.0
T_EM_K = 85.0 + 273.15
RTH_K_PER_W = 500.0  # lumped segment thermal resistance — not extracted
J_REF_A_M2 = 1.0e10  # reference for relative TTF only


def _len_m(a: str, b: str, dbu_per_um: float) -> float | None:
    pa, pb = node_xy_dbu(a), node_xy_dbu(b)
    if pa is None or pb is None:
        return None
    dx = (pa[0] - pb[0]) / dbu_per_um
    dy = (pa[1] - pb[1]) / dbu_per_um
    l_um = math.hypot(dx, dy)
    if l_um < 1e-6:
        return None
    return l_um * 1e-6


def branch_geometry(a: str, b: str, r: float, tech: dict) -> dict | None:
    """Same-layer metal: w = RPERSQ · L / R. Via (layer change) has no length model here."""
    la, lb = layer_of(a), layer_of(b)
    if la is None or lb is None or la != lb:
        return None
    layers = (tech or {}).get("layers") or {}
    spec = layers.get(la) or {}
    rpsq = spec.get("rpersq")
    t_um = spec.get("thickness_um")
    if rpsq is None or t_um is None:
        return None
    dbu = float((tech or {}).get("dbu_per_um") or 2000.0)
    L = _len_m(a, b, dbu)
    if L is None:
        return None
    w_inf_m = (float(rpsq) * L) / max(r, 1e-18)
    t_m = float(t_um) * 1e-6
    w_min_m = float(spec.get("width_um") or 0.0) * 1e-6
    # OpenROAD R is not a pure rectangle (vias lumped into the edge).
    # A legal wire cannot be thinner than min WIDTH — clamp so J is not a
    # 10^12 A/m² artifact from w≪WIDTH.
    w_m = max(w_inf_m, w_min_m) if w_min_m > 0.0 else w_inf_m
    if w_m <= 0.0 or t_m <= 0.0:
        return None
    return {
        "layer": la,
        "L_m": L,
        "w_m": w_m,
        "w_inferred_m": w_inf_m,
        "t_m": t_m,
        "area_m2": w_m * t_m,
        "rpersq": float(rpsq),
        "w_min_m": w_min_m,
        "w_over_min": (w_m / w_min_m) if w_min_m > 0 else None,
        "w_clamped": bool(w_min_m > 0.0 and w_inf_m < w_min_m),
    }


def em_thermal_snapshot(
    resistors,
    idx: dict,
    order,
    V,
    *,
    bump,
    bump_v,
    i_L,
    pkg_r: float,
    pkg_l: float,
    tech: dict | None = None,
) -> dict:
    """I, J, relative Black TTF, lumped ΔT. Physics screening, not sign-off EM."""
    import numpy as np

    def vnode(name: str) -> float | None:
        if name == "0":
            return 0.0
        i = idx.get(name)
        if i is None or i < 0 or i >= len(V):
            return None
        return float(V[i])

    tech = tech or {}
    branches = []
    scaled_resistors = []
    n_j = 0
    j_absmax = 0.0
    dt_absmax = 0.0
    p_joule = 0.0
    for a, b, r in resistors:
        va, vb = vnode(a), vnode(b)
        if va is None or vb is None:
            scaled_resistors.append((a, b, r))
            continue
        i_br = (va - vb) / max(r, 1e-18)
        rec = {
            "a": a,
            "b": b,
            "r_ohm": r,
            "i_a": i_br,
            "i_abs": abs(i_br),
            "p_w": i_br * i_br * r,
        }
        p_joule += rec["p_w"]
        r_use = r
        geo = branch_geometry(a, b, r, tech)
        if geo:
            rec.update(geo)
            rec["j_a_m2"] = rec["i_abs"] / geo["area_m2"]
            rec["dT_k"] = rec["p_w"] * RTH_K_PER_W
            rec["r_scale"] = 1.0 + ALPHA_R * rec["dT_k"]
            rec["ttf_rel"] = (J_REF_A_M2 / max(rec["j_a_m2"], 1.0)) ** BLACK_N
            n_j += 1
            j_absmax = max(j_absmax, rec["j_a_m2"])
            dt_absmax = max(dt_absmax, rec["dT_k"])
            r_use = r * rec["r_scale"]
        scaled_resistors.append((a, b, r_use))
        branches.append(rec)
    branches.sort(key=lambda x: -x["i_abs"])
    by_j = [b for b in branches if "j_a_m2" in b]
    by_j.sort(key=lambda x: -x["j_a_m2"])
    hottest_i = branches[0] if branches else None
    hottest_j = by_j[0] if by_j else None

    pkg = []
    i_L_list = np.asarray(i_L, dtype=np.float64).tolist() if i_L is not None else []
    for k, bi in enumerate(bump or []):
        node = order[int(bi)] if order is not None and 0 <= int(bi) < len(order) else str(bi)
        pkg.append(
            {
                "node": node,
                "v_src": float(bump_v[k]) if bump_v is not None and k < len(bump_v) else None,
                "i_L_a": float(i_L_list[k]) if k < len(i_L_list) else None,
            }
        )
    pkg.sort(key=lambda p: -abs(p["i_L_a"] or 0.0))

    r_scale = 1.0 + ALPHA_R * dt_absmax
    ttf_min = min((b["ttf_rel"] for b in by_j), default=None)
    status = "READY" if n_j else "PARTIAL"
    return {
        "status": status,
        "model": (
            "I=(Va-Vb)/R; w=max(RPERSQ·L/R, WIDTH_min); J=I/(w·t); "
            f"TTF_rel=(Jref/J)^{BLACK_N} at {T_EM_K:.0f} K; "
            f"ΔT=Rth·I²R with Rth={RTH_K_PER_W} K/W lumped"
        ),
        "not": [
            "foundry Black A / TTF hours",
            "extracted strap width from LEF geometry (width from R, clamped to min WIDTH)",
            "3D thermal / sub-ns thermal TRAN",
        ],
        "n_branches": len(branches),
        "n_with_j": n_j,
        "i_absmax_a": float(hottest_i["i_abs"]) if hottest_i else 0.0,
        "j_absmax_a_m2": j_absmax,
        "dT_absmax_k": dt_absmax,
        "r_scale_hot": r_scale,
        "n_r_scaled": sum(
            1
            for (_, _, r0), (_, _, r1) in zip(resistors, scaled_resistors)
            if abs(r1 - r0) > 1e-18 * max(abs(r0), 1.0)
        ),
        "_scaled_resistors": scaled_resistors,
        "p_joule_w": p_joule,
        "ttf_rel_min": ttf_min,
        "black_n": BLACK_N,
        "ea_ev": EA_EV,
        "t_em_k": T_EM_K,
        "j_ref_a_m2": J_REF_A_M2,
        "hottest": hottest_i,
        "hottest_j": hottest_j,
        "top": branches[:8],
        "top_j": by_j[:8],
        "package_i_L": pkg[:8],
        "pkg_r": pkg_r,
        "pkg_l": pkg_l,
        "tech_path": tech.get("path"),
        "note": (
            "EM J from physics I(t) and LEF RPERSQ/thickness. "
            "ΔT is lumped and tiny on this sub-ns window — thermal RC is not the IR TRAN."
            if n_j
            else "No same-layer R with coordinates — J remains GAP."
        ),
    }
