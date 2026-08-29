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
from collections import defaultdict

from pdn_extract import layer_of, node_xy_dbu

MU0_2PI = 2.0e-7  # H/m = μ0/(2π)


def grover_partial_L(l_m: float, w_m: float, t_m: float) -> float:
    """Partial self-inductance of a rectangular bar (Grover). No mutual, no skin.

    L = (mu0/2pi) * l * [ln(2l/(w+t)) + 1/2 + 0.2235 (w+t)/l].
    The log argument is clamped to >= 1 so a stub shorter than (w+t) stays non-negative.
    This is not loop inductance and not a PEEC mutual matrix.
    """
    l = max(float(l_m), 1e-18)
    wt = max(float(w_m) + float(t_m), 1e-18)
    return MU0_2PI * l * (math.log(max(2.0 * l / wt, 1.0)) + 0.5 + 0.2235 * wt / l)


def grover_partial_M(length_m: float, dist_m: float) -> float:
    """Partial mutual inductance of two parallel filaments (Grover / Neumann).

    M = (μ0/2π) * l * [ln(2l/d) - 1 + d/l] for overlapping length l and
    perpendicular distance d. No skin, not a full PEEC kernel.
    Negative results (d ≳ l) are clamped to 0.
    """
    l = max(float(length_m), 1e-18)
    d = max(float(dist_m), 1e-18)
    return max(MU0_2PI * l * (math.log(2.0 * l / d) - 1.0 + d / l), 0.0)


def _strap_axis(rec: dict) -> tuple[str, float, float, float] | None:
    xa, ya, xb, yb = rec.get("xa_m"), rec.get("ya_m"), rec.get("xb_m"), rec.get("yb_m")
    if xa is None or ya is None or xb is None or yb is None:
        return None
    dx, dy = abs(xb - xa), abs(yb - ya)
    if dx >= dy:
        return "H", min(xa, xb), max(xa, xb), 0.5 * (ya + yb)
    return "V", min(ya, yb), max(ya, yb), 0.5 * (xa + xb)


def pair_parallel_straps(
    branches: list,
    *,
    cutoff_m: float = 2e-6,
    max_pairs: int = 100_000,
    k_max: float = 0.99,
) -> list:
    """Same-layer, same-orientation, overlapping projection, d ≤ cutoff.

    Spatial hash — not O(n²) on every strap pair. k = M/√(L_i L_j) is clamped
    to [0, k_max] so E stays safely positive-definite. Not full PEEC.
    """
    buckets: dict[tuple, list[int]] = defaultdict(list)
    axes = []
    cutoff = max(float(cutoff_m), 1e-12)
    bin_m = cutoff
    for i, rec in enumerate(branches):
        ax = _strap_axis(rec)
        axes.append(ax)
        if ax is None:
            continue
        ori, _lo, _hi, perp = ax
        b = int(round(perp / bin_m))
        buckets[(rec.get("layer"), ori, b)].append(i)
    cands: list[tuple[float, int, int, float]] = []
    seen: set[tuple[int, int]] = set()
    for key, members in list(buckets.items()):
        layer, ori, b0 = key
        neigh = []
        for db in (-1, 0, 1):
            neigh.extend(buckets.get((layer, ori, b0 + db), ()))
        for i in members:
            ax_i = axes[i]
            if ax_i is None:
                continue
            _, lo_i, hi_i, perp_i = ax_i
            Li = max(float(branches[i]["L_h"]), 1e-30)
            for j in neigh:
                if j <= i:
                    continue
                pair = (i, j)
                if pair in seen:
                    continue
                ax_j = axes[j]
                if ax_j is None:
                    continue
                _, lo_j, hi_j, perp_j = ax_j
                ov = min(hi_i, hi_j) - max(lo_i, lo_j)
                if ov <= 0.0:
                    continue
                d = abs(perp_i - perp_j)
                if d < 1e-9 or d > cutoff:
                    continue
                seen.add(pair)
                M = grover_partial_M(ov, d)
                Lj = max(float(branches[j]["L_h"]), 1e-30)
                den = math.sqrt(Li * Lj)
                k = M / den if den > 0 else 0.0
                if k > k_max:
                    k = k_max
                    M = k * den
                if M <= 0.0:
                    continue
                cands.append((M, i, j, k))
    cands.sort(key=lambda t: t[0], reverse=True)
    truncated = len(cands) > max_pairs
    cands = cands[:max_pairs]
    return [
        {
            "i": i,
            "j": j,
            "M_h": M,
            "k": k,
            "layer": branches[i].get("layer"),
            "truncated": truncated,
        }
        for M, i, j, k in cands
    ]


def estimate_on_die_L(resistors, tech: dict | None) -> dict:
    """Grover L on same-layer write_pg_spice straps. Vias stay R (no length model)."""
    branches = []
    by_layer: dict[str, dict] = {}
    tech = tech or {}
    dbu = float(tech.get("dbu_per_um") or 2000.0)
    for a, b, r in resistors:
        g = branch_geometry(a, b, float(r), tech)
        if not g:
            continue
        Lh = grover_partial_L(g["L_m"], g["w_m"], g["t_m"])
        pa, pb = node_xy_dbu(a), node_xy_dbu(b)
        rec = {
            "a": a,
            "b": b,
            "r_ohm": float(r),
            "L_h": Lh,
            "layer": g["layer"],
            "L_m": g["L_m"],
            "w_m": g["w_m"],
            "t_m": g["t_m"],
        }
        if pa is not None and pb is not None:
            rec["xa_m"] = pa[0] / dbu * 1e-6
            rec["ya_m"] = pa[1] / dbu * 1e-6
            rec["xb_m"] = pb[0] / dbu * 1e-6
            rec["yb_m"] = pb[1] / dbu * 1e-6
        branches.append(rec)
        slot = by_layer.setdefault(g["layer"], {"n": 0, "L_sum_h": 0.0, "L_max_h": 0.0})
        slot["n"] += 1
        slot["L_sum_h"] += Lh
        slot["L_max_h"] = max(slot["L_max_h"], Lh)
    mutual = pair_parallel_straps(branches) if branches else []
    Lvals = [b["L_h"] for b in branches]
    Lvals_sorted = sorted(Lvals)
    p50 = Lvals_sorted[len(Lvals_sorted) // 2] if Lvals_sorted else 0.0
    Mvals = [m["M_h"] for m in mutual]
    return {
        "status": "READY" if branches else "GAP",
        "n_stamped": len(branches),
        "n_r": len(resistors),
        "L_sum_h": float(sum(Lvals)) if Lvals else 0.0,
        "L_max_h": float(max(Lvals)) if Lvals else 0.0,
        "L_p50_h": float(p50),
        "n_mutual": len(mutual),
        "M_max_h": float(max(Mvals)) if Mvals else 0.0,
        "k_max": float(max((m["k"] for m in mutual), default=0.0)),
        "cutoff_m": 2e-6,
        "by_layer": by_layer,
        "branches": branches,
        "mutual": mutual,
        "via": "Grover partial self-L + cutoff partial mutual on same-layer write_pg_spice straps",
        "note": (
            "Σ partial self is not loop L (mesh paths are parallel). Partial mutual is "
            "same-layer parallel filaments with overlapping projection and d≤2 µm "
            "(spatial hash, k clamped to 0.99). No skin, no full PEEC. Vias stay resistive. "
            "Descriptor stamp is unsymmetric — not AMG. Default TRAN stays N3 RC+pkg companion "
            "unless --on-die-l."
            if branches
            else "no same-layer strap with LEF geometry — on-die L stays GAP"
        ),
    }


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
