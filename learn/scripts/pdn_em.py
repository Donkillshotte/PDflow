#!/usr/bin/env python3
"""EM + thermal reporting on the PDN graph.

J from branch I and a width inferred from R, length, and LEF RPERSQ.
PDN straps are usually wider than min WIDTH; when inferred w is below
min WIDTH (OpenROAD R is not a pure rectangle), w is clamped to min WIDTH
so J is not a 10^12 A/m² artifact. Thickness from LEF. Black TTF is
*relative* (∝ J^{-n}); no foundry A.

Thermal: metal-graph diffusion (G_th = k A/L on same-layer straps *and*
adjacent-layer vias from LEF HEIGHT/CUT). Straps also couple vertically
through ILD (k_ox A_foot / HEIGHT) into a lumped Si node (k_si A_die / t_wafer)
that stars to the C4 pads. That is the substrate path metal-only vias omit —
not 3D FEM, not CFD, not a foundry package. Pads still G_amb to ambient.
Lumped Rth·I²R is a comparison, not the restamp ΔT when the mesh solves.
Skin depth is reported; Nangate metal1 is thinner than δ at the GCD clock
so Rac/Rdc ≈ 1. Never ML.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque

from pdn_extract import layer_of, node_xy_dbu

MU0 = 4.0e-7 * math.pi
MU0_2PI = 2.0e-7  # H/m = μ0/(2π)
EPS0_F_M = 8.854187817e-12  # F/m
EPS_R_OX = 3.9  # SiO2; same family as K_OX, not a foundry low-k card
K_CU_W_M_K = 400.0  # bulk Cu; not a foundry BEOL stack
K_OX_W_M_K = 1.4  # SiO2; not a foundry low-k stack
K_SI_W_M_K = 148.0  # bulk Si ~300 K
T_SI_M = 300e-6  # wafer thickness; not extracted from GDS
C_VOL_CU_J_M3_K = 3.45e6  # 385 J/kg/K × 8960 kg/m³
C_VOL_SI_J_M3_K = 1.63e6  # 700 J/kg/K × 2330 kg/m³
SIGMA_CU_S_M = 5.8e7
RTH_PAD_K_PER_W = 50.0  # C4-class bump → ambient; not extracted PKG


def grover_partial_L(l_m: float, w_m: float, t_m: float) -> float:
    """Partial self-inductance of a rectangular bar (Grover). No mutual, no skin.

    L = (mu0/2pi) * l * [ln(2l/(w+t)) + 1/2 + 0.2235 (w+t)/l].
    The log argument is clamped to >= 1 so a stub shorter than (w+t) stays non-negative.
    This is not loop inductance and not a PEEC mutual matrix.
    """
    l = max(float(l_m), 1e-18)
    wt = max(float(w_m) + float(t_m), 1e-18)
    return MU0_2PI * l * (math.log(max(2.0 * l / wt, 1.0)) + 0.5 + 0.2235 * wt / l)


def skin_depth_m(f_hz: float, sigma: float = SIGMA_CU_S_M) -> float:
    """Classical skin depth δ = 1/√(π f μ σ). No anomalous skin, no roughness."""
    f = max(float(f_hz), 1e-30)
    return 1.0 / math.sqrt(math.pi * f * MU0 * max(float(sigma), 1.0))


def rac_over_rdc(t_m: float, f_hz: float, sigma: float = SIGMA_CU_S_M) -> float:
    """Wide-sheet Rac/Rdc ≈ t / min(t, δ). t ≪ δ → 1. Not Wheeler round-wire, not PEEC."""
    t = max(float(t_m), 1e-18)
    delta = skin_depth_m(f_hz, sigma)
    return t / min(t, delta)


def cox_lateral_f(t_m: float, length_m: float, gap_m: float) -> float:
    """Same-layer facing-sidewall C = ε0 εr t L_ov / d_gap. SiO2 εr, not LEF CPERSQDIST."""
    g = max(float(gap_m), 1e-18)
    return EPS0_F_M * EPS_R_OX * max(float(t_m), 0.0) * max(float(length_m), 0.0) / g


def cox_plate_f(area_m2: float, h_m: float) -> float:
    """Adjacent-layer plate C = ε0 εr A_ov / h_ILD. h is via ILD, not HEIGHT-to-substrate."""
    h = max(float(h_m), 1e-18)
    return EPS0_F_M * EPS_R_OX * max(float(area_m2), 0.0) / h


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


def _nearest_end(rec: dict, cx: float, cy: float) -> str | None:
    if rec.get("xa_m") is None or rec.get("ya_m") is None:
        return None
    da = (float(rec["xa_m"]) - cx) ** 2 + (float(rec["ya_m"]) - cy) ** 2
    db = (float(rec["xb_m"]) - cx) ** 2 + (float(rec["yb_m"]) - cy) ** 2
    return rec["a"] if da <= db else rec["b"]


def strap_aabb(rec: dict) -> tuple[float, float, float, float] | None:
    """Axis-aligned footprint (x0, y0, x1, y1) from strap axis + width. None if no XY."""
    ax = _strap_axis(rec)
    if ax is None or rec.get("w_m") is None or rec.get("xa_m") is None:
        return None
    ori, lo, hi, perp = ax
    if hi <= lo:
        return None
    hw = 0.5 * float(rec["w_m"])
    if ori == "H":
        return lo, perp - hw, hi, perp + hw
    return perp - hw, lo, perp + hw, hi


def _aabb_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]):
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    dx, dy = x1 - x0, y1 - y0
    if dx <= 0.0 or dy <= 0.0:
        return 0.0, None
    return dx * dy, (0.5 * (x0 + x1), 0.5 * (y0 + y1))


def _aabb_cells(box: tuple[float, float, float, float], cell: float):
    x0, y0, x1, y1 = box
    c = max(float(cell), 1e-12)
    ix0, ix1 = int(math.floor(x0 / c)), int(math.floor(x1 / c))
    iy0, iy1 = int(math.floor(y0 / c)), int(math.floor(y1 / c))
    for ix in range(ix0, ix1 + 1):
        for iy in range(iy0, iy1 + 1):
            yield ix, iy


def ild_gap_m(layer_a: str | None, layer_b: str | None, tech: dict | None) -> float | None:
    """ILD thickness between adjacent metals: HEIGHT_hi − HEIGHT_lo − t_lo. Else None."""
    na, nb = _metal_index(layer_a), _metal_index(layer_b)
    if na is None or nb is None or abs(na - nb) != 1:
        return None
    layers = (tech or {}).get("layers") or {}
    lo, hi = (layer_a, layer_b) if na < nb else (layer_b, layer_a)
    spec_lo, spec_hi = layers.get(lo) or {}, layers.get(hi) or {}
    h_lo, t_lo, h_hi = spec_lo.get("height_um"), spec_lo.get("thickness_um"), spec_hi.get("height_um")
    if h_lo is None or t_lo is None or h_hi is None:
        return None
    L_um = float(h_hi) - float(h_lo) - float(t_lo)
    if L_um <= 0.0:
        return None
    return L_um * 1e-6


def pair_rail_overlap_c(
    vdd_branches: list,
    vss_branches: list,
    tech: dict | None = None,
    *,
    cutoff_m: float = 2e-6,
    max_pairs: int = 100_000,
) -> dict:
    """VDD↔VSS overlapping-strap Cox. Spatial hash — not O(n²).

    Same-layer lateral: C = ε0 εr t L_ov / d_gap with d_gap = d_center − (w1+w2)/2.
    Skip d_gap ≤ 0 (footprints touch/overlap — would be a short). Cutoff 2 µm on the gap,
    same family as Grover mutual. Adjacent-layer plate: C = ε0 εr A_ov / h_ILD with the
    via ILD (HEIGHT_hi − HEIGHT_lo − t_lo). Not foundry PEX, not LEF CPERSQDIST, not
    instance-pin C_rr, not signal SPEF. Lumped onto endpoints nearest the overlap centroid.
    """
    cutoff = max(float(cutoff_m), 1e-12)
    tech = tech or {}
    pairs: list[dict] = []
    max_w = 0.0
    for rec in vdd_branches:
        max_w = max(max_w, float(rec.get("w_m") or 0.0))
    for rec in vss_branches:
        max_w = max(max_w, float(rec.get("w_m") or 0.0))
    bin_m = cutoff
    n_db = int(math.ceil((cutoff + max_w) / bin_m)) + 1
    buckets: dict[tuple, list[int]] = defaultdict(list)
    axes_s = []
    for j, rec in enumerate(vss_branches):
        ax = _strap_axis(rec)
        axes_s.append(ax)
        if ax is None:
            continue
        ori, _lo, _hi, perp = ax
        b = int(round(perp / bin_m))
        buckets[(rec.get("layer"), ori, b)].append(j)
    n_lat_raw = 0
    for rec_i in vdd_branches:
        ax_i = _strap_axis(rec_i)
        if ax_i is None:
            continue
        ori, lo_i, hi_i, perp_i = ax_i
        layer = rec_i.get("layer")
        w_i = float(rec_i["w_m"])
        t_i = float(rec_i["t_m"])
        b0 = int(round(perp_i / bin_m))
        neigh = []
        for db in range(-n_db, n_db + 1):
            neigh.extend(buckets.get((layer, ori, b0 + db), ()))
        for j in neigh:
            ax_j = axes_s[j]
            if ax_j is None:
                continue
            _, lo_j, hi_j, perp_j = ax_j
            ov = min(hi_i, hi_j) - max(lo_i, lo_j)
            if ov <= 0.0:
                continue
            d = abs(perp_i - perp_j)
            w_j = float(vss_branches[j]["w_m"])
            gap = d - 0.5 * (w_i + w_j)
            if gap <= 1e-12 or gap > cutoff:
                continue
            t = min(t_i, float(vss_branches[j]["t_m"]))
            c = cox_lateral_f(t, ov, gap)
            if c <= 0.0:
                continue
            mid = 0.5 * (max(lo_i, lo_j) + min(hi_i, hi_j))
            perp_m = 0.5 * (perp_i + perp_j)
            cx, cy = (mid, perp_m) if ori == "H" else (perp_m, mid)
            nd_i = _nearest_end(rec_i, cx, cy)
            nd_j = _nearest_end(vss_branches[j], cx, cy)
            if nd_i is None or nd_j is None:
                continue
            n_lat_raw += 1
            pairs.append(
                {
                    "kind": "lateral",
                    "vdd_node": nd_i,
                    "vss_node": nd_j,
                    "c_f": c,
                    "layer": layer,
                    "L_ov_m": ov,
                    "gap_m": gap,
                }
            )

    cell = cutoff
    vss_boxes = []
    plate_buckets: dict[tuple, list[int]] = defaultdict(list)
    for j, rec in enumerate(vss_branches):
        box = strap_aabb(rec)
        vss_boxes.append(box)
        if box is None:
            continue
        ly = rec.get("layer")
        for ix, iy in _aabb_cells(box, cell):
            plate_buckets[(ly, ix, iy)].append(j)
    n_plate_raw = 0
    seen_plate: set[tuple[int, int]] = set()
    for i, rec_i in enumerate(vdd_branches):
        box_i = strap_aabb(rec_i)
        if box_i is None:
            continue
        la = rec_i.get("layer")
        for ix, iy in _aabb_cells(box_i, cell):
            na = _metal_index(la)
            if na is None:
                continue
            for nb in (na - 1, na + 1):
                if nb < 1:
                    continue
                ly_s = f"metal{nb}"
                for dix in (-1, 0, 1):
                    for diy in (-1, 0, 1):
                        for j in plate_buckets.get((ly_s, ix + dix, iy + diy), ()):
                            pair_id = (i, j)
                            if pair_id in seen_plate:
                                continue
                            box_j = vss_boxes[j]
                            if box_j is None:
                                continue
                            area, cen = _aabb_overlap(box_i, box_j)
                            if area <= 0.0 or cen is None:
                                continue
                            h = ild_gap_m(la, ly_s, tech)
                            if h is None:
                                continue
                            seen_plate.add(pair_id)
                            c = cox_plate_f(area, h)
                            if c <= 0.0:
                                continue
                            nd_i = _nearest_end(rec_i, cen[0], cen[1])
                            nd_j = _nearest_end(vss_branches[j], cen[0], cen[1])
                            if nd_i is None or nd_j is None:
                                continue
                            n_plate_raw += 1
                            pairs.append(
                                {
                                    "kind": "plate",
                                    "vdd_node": nd_i,
                                    "vss_node": nd_j,
                                    "c_f": c,
                                    "layer_vdd": la,
                                    "layer_vss": ly_s,
                                    "area_m2": area,
                                    "h_ild_m": h,
                                }
                            )

    pairs.sort(key=lambda p: float(p["c_f"]), reverse=True)
    truncated = len(pairs) > max_pairs
    pairs = pairs[:max_pairs]
    n_lat = sum(1 for p in pairs if p["kind"] == "lateral")
    n_plate = sum(1 for p in pairs if p["kind"] == "plate")
    c_sum = float(sum(p["c_f"] for p in pairs)) if pairs else 0.0
    c_max = float(max((p["c_f"] for p in pairs), default=0.0))
    return {
        "status": "READY" if pairs else "GAP",
        "n_pairs": len(pairs),
        "n_lateral": n_lat,
        "n_plate": n_plate,
        "n_lateral_found": n_lat_raw,
        "n_plate_found": n_plate_raw,
        "n_vdd_straps": len(vdd_branches),
        "n_vss_straps": len(vss_branches),
        "c_sum_f": c_sum,
        "c_max_f": c_max,
        "cutoff_m": cutoff,
        "eps_r": EPS_R_OX,
        "truncated": truncated,
        "pairs": pairs,
        "via": (
            "overlapping-strap Cox: same-layer ε0εr t L_ov/d_gap (d_gap≤2 µm) + "
            "adjacent-layer ε0εr A_ov/h_ILD (via HEIGHT stack); SiO2 εr=3.9"
        ),
        "not": (
            "foundry PEX / LEF CPERSQDIST / instance-pin C_rr / signal SPEF / "
            "Nangate C_decap cells / GCD default TRAN"
        ),
        "note": (
            "Lumped onto strap endpoints nearest the overlap centroid — not distributed PEX. "
            "d_gap≤0 is skipped (would be a short). Non-adjacent metals are GAP (no stacked ILD)."
            if pairs
            else "no VDD/VSS strap overlap within cutoff / adjacent-layer AABB"
        ),
    }


def strap_branches(resistors, tech: dict | None) -> list:
    """Same-layer write_pg_spice straps with Grover L and XY. Shared by on-die L and Cox.

    Vias (layer change) are omitted — no length model, same as estimate_on_die_L.
    """
    branches = []
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
    return branches


def estimate_on_die_L(resistors, tech: dict | None) -> dict:
    """Grover L on same-layer write_pg_spice straps. Vias stay R (no length model)."""
    branches = strap_branches(resistors, tech)
    by_layer: dict[str, dict] = {}
    for rec in branches:
        Lh = float(rec["L_h"])
        slot = by_layer.setdefault(rec["layer"], {"n": 0, "L_sum_h": 0.0, "L_max_h": 0.0})
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
        "kind": "strap",
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


def _metal_index(layer: str | None) -> int | None:
    if not layer:
        return None
    s = str(layer).lower()
    if not s.startswith("metal"):
        return None
    try:
        return int(s[5:])
    except ValueError:
        return None


def via_geometry(a: str, b: str, r: float, tech: dict | None) -> dict | None:
    """Adjacent-layer via: A = n_cuts · w_cut², L from LEF HEIGHT.

    n_cuts = max(R_cut / R, 1). OpenROAD often lumps several cuts into one R.
    L = HEIGHT_upper − HEIGHT_lower − THICKNESS_lower (ILD, not metal).
    Non-adjacent hops stay GAP (write_pg_spice has intermediate nodes).
    Not a 3D FEM via, not a foundry BEOL k(T).
    """
    la, lb = layer_of(a), layer_of(b)
    na, nb = _metal_index(la), _metal_index(lb)
    if na is None or nb is None or abs(na - nb) != 1:
        return None
    tech = tech or {}
    layers = tech.get("layers") or {}
    cuts = tech.get("cuts") or {}
    lo, hi = (la, lb) if na < nb else (lb, la)
    spec_lo, spec_hi = layers.get(lo) or {}, layers.get(hi) or {}
    h_lo, t_lo, h_hi = spec_lo.get("height_um"), spec_lo.get("thickness_um"), spec_hi.get("height_um")
    if h_lo is None or t_lo is None or h_hi is None:
        return None
    L_um = float(h_hi) - float(h_lo) - float(t_lo)
    if L_um <= 0.0:
        return None
    cut_name = f"via{min(na, nb)}"
    cut = cuts.get(cut_name) or {}
    w_um = cut.get("width_um")
    if w_um is None:
        return None
    r_cut = cut.get("r_ohm")
    n_cuts = (float(r_cut) / max(float(r), 1e-18)) if r_cut else 1.0
    n_cuts = max(n_cuts, 1.0)
    w_m = float(w_um) * 1e-6
    L_m = L_um * 1e-6
    area = n_cuts * w_m * w_m
    return {
        "kind": "via",
        "layer": cut_name,
        "layer_lo": lo,
        "layer_hi": hi,
        "cut": cut_name,
        "L_m": L_m,
        "w_m": w_m,
        "t_m": L_m,
        "area_m2": area,
        "n_cuts": n_cuts,
        "r_cut_ohm": float(r_cut) if r_cut is not None else None,
        "w_clamped": False,
    }


def thermal_edge_geometry(a: str, b: str, r: float, tech: dict | None) -> dict | None:
    """Strap (same layer) or via (adjacent layer). Else None — do not invent G_th."""
    return branch_geometry(a, b, float(r), tech or {}) or via_geometry(a, b, float(r), tech)


def strap_ild_g(geo: dict | None, tech: dict | None) -> float:
    """Vertical ILD: G = k_ox · (w L) / HEIGHT. HEIGHT is substrate→metal bottom.

    Oxide-equivalent stack, not a layered FEM. Vias are Cu and do not get this G.
    Missing HEIGHT → 0 (do not invent t_ild).
    """
    if not geo or geo.get("kind") != "strap":
        return 0.0
    spec = ((tech or {}).get("layers") or {}).get(geo.get("layer")) or {}
    h_um = spec.get("height_um")
    if h_um is None or float(h_um) <= 0.0:
        return 0.0
    w = float(geo.get("w_m") or 0.0)
    L = float(geo.get("L_m") or 0.0)
    if w <= 0.0 or L <= 0.0:
        return 0.0
    return K_OX_W_M_K * w * L / (float(h_um) * 1e-6)


def _bbox_area_m2(idx: dict, used: set, dbu: float, w_floor: float) -> float:
    """Die footprint from node bbox. A 1-D line of nodes uses max(span, w_floor)."""
    xs, ys = [], []
    floor = max(float(w_floor), 1e-9)
    for name, i in idx.items():
        if int(i) not in used:
            continue
        xy = node_xy_dbu(name)
        if xy is None:
            continue
        xs.append(xy[0] / dbu * 1e-6)
        ys.append(xy[1] / dbu * 1e-6)
    if not xs:
        return floor * floor
    dx = max(max(xs) - min(xs), floor)
    dy = max(max(ys) - min(ys), floor)
    return dx * dy


def _thermal_pads_reach(G, pad_th: list[int], n: int) -> bool:
    """Every node with a thermal edge must reach a pad. No invented island ambient."""
    adj: list[list[int]] = [[] for _ in range(n)]
    Gcsr = G.tocsr()
    for i in range(n):
        for j, v in zip(Gcsr.indices[Gcsr.indptr[i] : Gcsr.indptr[i + 1]], Gcsr.data[Gcsr.indptr[i] : Gcsr.indptr[i + 1]]):
            if i != j and v != 0.0:
                adj[i].append(int(j))
    if not pad_th:
        return False
    seen: set[int] = set()
    q = deque(pad_th)
    for p in pad_th:
        seen.add(int(p))
    while q:
        i = q.popleft()
        for j in adj[i]:
            if j not in seen:
                seen.add(j)
                q.append(j)
    for i in range(n):
        if adj[i] and i not in seen:
            return False
    return True


def assemble_thermal_mesh(
    resistors,
    idx: dict,
    pad_idx,
    tech: dict | None,
    *,
    rth_pad: float = RTH_PAD_K_PER_W,
    t_si: float = T_SI_M,
) -> dict | None:
    """SPD thermal graph: straps + vias + ILD-to-Si + pad G_amb.

    G_th_ij = k_Cu · A / L on metal. Straps add G_ild = k_ox (w L)/HEIGHT to a
    lumped Si node; Si stars to pads with G_vert/n_pads, G_vert = k_si A_die / t_wafer.
    All heat still exits through pad G_amb (Si has no second ambient).
    Compact: electrical nodes with no thermal edge are dropped (no fake G_amb).
    Not 3D FEM, not a mold/heat-sink CFD, not foundry BEOL k(T).
    """
    if "/usr/lib/python3/dist-packages" not in __import__("sys").path:
        __import__("sys").path.insert(0, "/usr/lib/python3/dist-packages")
    import numpy as np
    from scipy import sparse

    if not idx or not pad_idx:
        return None
    edges = []
    tech = tech or {}
    n_strap = 0
    n_via = 0
    n_ild = 0
    g_ild_sum = 0.0
    w_floor = 1e-9
    dbu = float(tech.get("dbu_per_um") or 2000.0)
    for a, b, r in resistors:
        if a not in idx or b not in idx:
            continue
        geo = thermal_edge_geometry(a, b, float(r), tech)
        if not geo:
            continue
        gth = K_CU_W_M_K * geo["area_m2"] / max(geo["L_m"], 1e-18)
        cth = C_VOL_CU_J_M3_K * geo["area_m2"] * geo["L_m"]
        kind = geo.get("kind") or "strap"
        g_ild = strap_ild_g(geo, tech)
        edges.append((int(idx[a]), int(idx[b]), gth, cth, kind, g_ild))
        if kind == "via":
            n_via += 1
        else:
            n_strap += 1
            w_floor = max(w_floor, float(geo.get("w_m") or 0.0))
        if g_ild > 0.0:
            n_ild += 1
            g_ild_sum += g_ild
    if not edges:
        return None
    pads = sorted({int(i) for i in pad_idx})
    if not pads:
        return None
    used = set(pads)
    for ia, ib, *_rest in edges:
        used.add(ia)
        used.add(ib)
    th_of = {e: k for k, e in enumerate(sorted(used))}
    n_metal = len(th_of)
    a_die = _bbox_area_m2(idx, used, dbu, w_floor)
    t_wafer = max(float(t_si), 1e-9)
    g_vert = K_SI_W_M_K * a_die / t_wafer
    use_si = n_ild > 0 and g_vert > 0.0
    n = n_metal + (1 if use_si else 0)
    si_th = n_metal if use_si else None
    G = sparse.lil_matrix((n, n), dtype=np.float64)
    C = np.zeros(n, dtype=np.float64)
    gth_sum = 0.0
    for ia, ib, gth, cth, _kind, g_ild in edges:
        ta, tb = th_of[ia], th_of[ib]
        G[ta, ta] += gth
        G[tb, tb] += gth
        G[ta, tb] -= gth
        G[tb, ta] -= gth
        C[ta] += 0.5 * cth
        C[tb] += 0.5 * cth
        gth_sum += gth
        if use_si and g_ild > 0.0 and si_th is not None:
            half = 0.5 * g_ild
            for t in (ta, tb):
                G[t, t] += half
                G[si_th, si_th] += half
                G[t, si_th] -= half
                G[si_th, t] -= half
    g_amb = 1.0 / max(float(rth_pad), 1e-9)
    pad_th = [th_of[i] for i in pads if i in th_of]
    if not pad_th:
        return None
    for t in pad_th:
        G[t, t] += g_amb
    if use_si and si_th is not None:
        gsp = g_vert / float(len(pad_th))
        for t in pad_th:
            G[t, t] += gsp
            G[si_th, si_th] += gsp
            G[t, si_th] -= gsp
            G[si_th, t] -= gsp
        C[si_th] += C_VOL_SI_J_M3_K * a_die * t_wafer
    Gcsr = G.tocsr()
    if not _thermal_pads_reach(Gcsr, pad_th, n):
        return None
    C = np.maximum(C, 1e-18)
    elec_of = [-1] * n
    for elec, th_i in th_of.items():
        elec_of[th_i] = elec
    return {
        "G": Gcsr,
        "C": C,
        "n": n,
        "n_metal": n_metal,
        "n_edges": len(edges),
        "n_straps": n_strap,
        "n_vias": n_via,
        "n_ild": n_ild,
        "n_si": 1 if use_si else 0,
        "si_th": si_th,
        "n_pads": len(pad_th),
        "pads": pads,
        "pad_th": pad_th,
        "th_of": th_of,
        "elec_of": elec_of,
        "g_amb": g_amb,
        "rth_pad": float(rth_pad),
        "gth_sum": gth_sum,
        "g_ild_sum": g_ild_sum,
        "g_vert": g_vert if use_si else 0.0,
        "a_die_m2": a_die,
        "t_si_m": t_wafer if use_si else None,
        "k_cu": K_CU_W_M_K,
        "k_ox": K_OX_W_M_K,
        "k_si": K_SI_W_M_K,
        "c_vol": C_VOL_CU_J_M3_K,
        "via": (
            "metal-graph G_th=kA/L + via HEIGHT/CUT + ILD k_ox A/HEIGHT to lumped Si "
            f"(k_si A_die/t_wafer, t={t_wafer*1e6:.0f} µm); pad G_amb; not 3D FEM"
            if use_si
            else "metal-graph G_th=kA/L on straps + adjacent vias; pad G_amb; no HEIGHT → no ILD/Si"
        ),
    }


def thermal_power_vector(
    n: int,
    idx: dict,
    branches: list,
    currents: dict | None,
    vdd: float,
) -> "object":
    """Node heat: half of each strap I²R plus cell P≈I_avg·Vdd at sinks.

    Cell power is dissipated in the device, not in the grid R — not a double count.
    """
    import numpy as np

    P = np.zeros(int(n), dtype=np.float64)
    for rec in branches:
        a, b = rec.get("a"), rec.get("b")
        if a not in idx or b not in idx:
            continue
        p = 0.5 * float(rec.get("p_w") or 0.0)
        P[int(idx[a])] += p
        P[int(idx[b])] += p
    if currents and vdd:
        for name, iavg in currents.items():
            if name in idx:
                P[int(idx[name])] += abs(float(iavg)) * float(vdd)
    return P


def solve_thermal_steady(G, P) -> dict:
    """SPD G_th T = P. Direct LU (native if present). AMG when n is large."""
    import numpy as np
    from pdn_solvers import DirectLU, SAAMG, residual_rel

    P = np.ascontiguousarray(P, dtype=np.float64)
    n = int(G.shape[0])
    solver = SAAMG(G) if n >= 256 else DirectLU(G)
    T = np.asarray(solver.solve(P), dtype=np.float64)
    return {
        "T": T,
        "dT_absmax_k": float(np.max(T)) if T.size else 0.0,
        "dT_mean_k": float(np.mean(T)) if T.size else 0.0,
        "backend": getattr(solver, "backend", "python"),
        "solver": getattr(solver, "name", type(solver).__name__),
        "n_levels": getattr(solver, "n_levels", 1),
        "rel_res": residual_rel(G, T, P),
    }


def timestep_thermal_be(sys: dict, P, dt: float, t_end: float, *, T0=None, n_track: int = 0) -> dict:
    """Implicit Euler on C Ṫ + G T = P(t). P may be a vector or f(t)->vector.

    Thermal Δt is independent of the IR TRAN Δt. Not a sub-ps electrical step.
    Tracks max ΔT (optionally on [0, n_track) so a lumped Si node can be excluded
    from the restamp metric). Constant P uses native LU in libdpn when present.
    Callable P stays on the Python loop. DPN_NATIVE=0 forces SciPy.
    """
    import numpy as np
    from scipy import sparse
    from pdn_solvers import DirectLU, native_timestep_thermal, residual_rel

    G = sys["G"].tocsr()
    C = np.asarray(sys["C"], dtype=np.float64)
    n = int(G.shape[0])
    A = (G + sparse.diags(C / dt)).tocsc()
    lu = DirectLU(A)
    if not callable(P):
        Pv = np.asarray(P, dtype=np.float64)
        nat = native_timestep_thermal(lu, C, Pv, dt, t_end, T0, n_track)
        if nat is not None:
            return nat
    T = np.zeros(n, dtype=np.float64) if T0 is None else np.asarray(T0, dtype=np.float64).copy()
    steps = max(2, int(math.ceil(t_end / dt)))
    n0 = int(n_track) if (n_track and 0 < int(n_track) <= n) else n
    worst = float(np.max(T[:n0])) if T.size else 0.0
    t_worst = 0.0
    i_worst = int(np.argmax(T[:n0])) if T.size else 0
    T_worst = T.copy()
    res_max = 0.0
    wave_t, wave_tmax = [], []
    for s in range(steps):
        t = s * dt
        rhs_p = P(t) if callable(P) else P
        rhs = (C / dt) * T + np.asarray(rhs_p, dtype=np.float64)
        T = np.asarray(lu.solve(rhs), dtype=np.float64)
        res_max = max(res_max, residual_rel(A, T, rhs))
        tmax = float(np.max(T[:n0]))
        imax = int(np.argmax(T[:n0]))
        wave_t.append(t)
        wave_tmax.append(tmax)
        if tmax > worst:
            worst = tmax
            t_worst = t
            i_worst = imax
            T_worst = T.copy()
    return {
        "T": T,
        "T_worst": T_worst,
        "dT_absmax_k": worst,
        "worst_time_s": t_worst,
        "worst_node": i_worst,
        "steps": steps,
        "dt": dt,
        "rel_res_max": res_max,
        "wave_t": wave_t,
        "wave_tmax": wave_tmax,
        "backend": getattr(lu, "backend", "python"),
        "timestep_loop": "python_thermal",
        "via": "thermal BE C/Δt + G_th (same LU as electrical, max ΔT, different Δt)",
    }


def ngspice_thermal_1node_gold(g_amb: float, c_th: float, p_w: float, dt: float, t_end: float) -> dict:
    """ngspice analogue: voltage=ΔT, current=P, R=1/G_amb, C=C_th."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    if not shutil.which("ngspice"):
        return {"ok": False, "status": "GAP", "reason": "ngspice not in PATH"}
    tmp = Path(tempfile.mkdtemp(prefix="dpn-th-"))
    sp = tmp / "th.sp"
    dat = tmp / "th.dat"
    r = 1.0 / max(g_amb, 1e-18)
    sp.write_text(
        f"""* thermal analogue 1-node (V=ΔT, I=P)
Ramb t 0 {r:.16e}
Cth t 0 {c_th:.16e}
Ip 0 t DC {p_w:.16e}
.control
option method=gear maxord=1
set filetype=ascii
tran {dt:.8e} {t_end:.8e}
wrdata {dat} v(t)
.endc
.end
"""
    )
    proc = subprocess.run(
        ["ngspice", "-b", str(sp)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    vmax = None
    for p in sorted(tmp.glob("th.dat*")):
        text = p.read_text(errors="replace")
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    vmax = float(parts[-1]) if vmax is None else max(vmax, float(parts[-1]))
                except ValueError:
                    continue
    if vmax is None:
        return {"ok": False, "status": "GAP", "reason": "no wrdata", "raw": (proc.stdout or "")[-400:]}
    return {"ok": True, "ngspice_dT_k": vmax, "g_amb": g_amb, "c_th": c_th, "p_w": p_w}


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
    currents: dict | None = None,
    vdd: float = 0.0,
    f_hz: float | None = None,
) -> dict:
    """I, J, relative Black TTF, metal-graph ΔT (straps+vias), lumped ΔT comparison.

    Physics screening, not sign-off EM or package thermal.
    """
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
    n_j = 0
    j_absmax = 0.0
    dt_absmax = 0.0
    p_joule = 0.0
    for a, b, r in resistors:
        va, vb = vnode(a), vnode(b)
        if va is None or vb is None:
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
        geo = branch_geometry(a, b, r, tech)
        if geo:
            rec.update(geo)
            rec["j_a_m2"] = rec["i_abs"] / geo["area_m2"]
            rec["dT_lumped_k"] = rec["p_w"] * RTH_K_PER_W
            rec["dT_k"] = rec["dT_lumped_k"]
            rec["r_scale"] = 1.0 + ALPHA_R * rec["dT_k"]
            rec["ttf_rel"] = (J_REF_A_M2 / max(rec["j_a_m2"], 1.0)) ** BLACK_N
            n_j += 1
            j_absmax = max(j_absmax, rec["j_a_m2"])
            dt_absmax = max(dt_absmax, rec["dT_k"])
        branches.append(rec)
    branches.sort(key=lambda x: -x["i_abs"])
    by_j = [b for b in branches if "j_a_m2" in b]
    by_j.sort(key=lambda x: -x["j_a_m2"])
    hottest_i = branches[0] if branches else None
    hottest_j = by_j[0] if by_j else None

    mesh_meta = None
    pad_idx = [int(b) for b in (bump or [])]
    th = assemble_thermal_mesh(resistors, idx, pad_idx, tech)
    if th:
        n_elec = 1 + max(int(i) for i in idx.values())
        P_e = thermal_power_vector(n_elec, idx, branches, currents, vdd)
        P = np.zeros(th["n"], dtype=np.float64)
        for elec_i, th_i in th["th_of"].items():
            if 0 <= int(elec_i) < P_e.size:
                P[int(th_i)] += P_e[int(elec_i)]
        try:
            sol = solve_thermal_steady(th["G"], P)
            T = sol["T"]
            if (not np.isfinite(T).all()) or float(sol["rel_res"]) > 1e-4:
                raise RuntimeError(f"thermal residual {sol['rel_res']}")
        except Exception as exc:  # noqa: BLE001 — mesh is optional; IR TRAN must still report
            dt_mesh = None
            mesh_meta = {"status": "GAP", "reason": f"thermal G_th solve failed: {exc}"}
        else:
            th_of = th["th_of"]
            pad_temps = [float(T[t]) for t in th["pad_th"] if 0 <= t < T.size]
            si_th = th.get("si_th")
            metal_ts = [float(T[i]) for i in range(T.size) if si_th is None or i != int(si_th)]
            dT_metal = float(max(metal_ts)) if metal_ts else sol["dT_absmax_k"]
            dT_si = float(T[int(si_th)]) if si_th is not None and 0 <= int(si_th) < T.size else None
            mesh_meta = {
                "status": "READY",
                "n": th["n"],
                "n_metal": th.get("n_metal"),
                "n_edges": th["n_edges"],
                "n_straps": th["n_straps"],
                "n_vias": th["n_vias"],
                "n_ild": th.get("n_ild"),
                "n_si": th.get("n_si") or 0,
                "n_pads": th["n_pads"],
                "rth_pad": th["rth_pad"],
                "g_amb": th["g_amb"],
                "g_ild_sum": th.get("g_ild_sum"),
                "g_vert": th.get("g_vert"),
                "a_die_m2": th.get("a_die_m2"),
                "t_si_m": th.get("t_si_m"),
                "p_cell_w": float(max(float(P.sum()) - p_joule, 0.0)),
                "p_total_w": float(P.sum()),
                "dT_absmax_k": dT_metal,
                "dT_mean_k": float(sum(metal_ts) / len(metal_ts)) if metal_ts else sol["dT_mean_k"],
                "dT_pad_max_k": float(max(pad_temps)) if pad_temps else 0.0,
                "dT_si_k": dT_si,
                "backend": sol["backend"],
                "solver": sol["solver"],
                "rel_res": sol["rel_res"],
                "via": th["via"],
                "note": (
                    "Steady metal-graph ΔT; cell P=I_avg·Vdd at sinks + strap/via I²R. "
                    "Via G_th from LEF HEIGHT/CUT. ILD k_ox A/HEIGHT to lumped Si "
                    f"(t_wafer={float(th.get('t_si_m') or 0)*1e6:.0f} µm, not 3D FEM). "
                    "Pad Rth=50 K/W C4-class. All heat exits G_amb; Si has no second ambient."
                ),
            }
            for rec in branches:
                a, b = rec.get("a"), rec.get("b")
                if a not in idx or b not in idx:
                    continue
                ia, ib = int(idx[a]), int(idx[b])
                if ia in th_of and ib in th_of:
                    ta, tb = th_of[ia], th_of[ib]
                    if 0 <= ta < T.size and 0 <= tb < T.size:
                        rec["dT_mesh_k"] = 0.5 * (float(T[ta]) + float(T[tb]))
                        rec["dT_k"] = rec["dT_mesh_k"]
                        rec["r_scale"] = 1.0 + ALPHA_R * rec["dT_k"]
            dt_mesh = dT_metal
    else:
        dt_mesh = None
        mesh_meta = {
            "status": "GAP",
            "reason": "no strap/via G_th or no pad-reachable path to ambient",
        }

    scaled_resistors = []
    for rec in branches:
        a, b, r0 = rec["a"], rec["b"], rec["r_ohm"]
        scaled_resistors.append((a, b, r0 * float(rec.get("r_scale") or 1.0)))
    # resistors skipped (missing V) keep original R
    have = {(rec["a"], rec["b"]) for rec in branches}
    for a, b, r in resistors:
        if (a, b) not in have:
            scaled_resistors.append((a, b, r))

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

    dt_for_scale = dt_mesh if dt_mesh is not None else dt_absmax
    r_scale = 1.0 + ALPHA_R * dt_for_scale
    ttf_min = min((b["ttf_rel"] for b in by_j), default=None)
    n_scaled = sum(1 for rec in branches if abs(float(rec.get("r_scale") or 1.0) - 1.0) > 1e-15)
    f_use = float(f_hz) if f_hz and f_hz > 0 else None
    skin = None
    if hottest_j and hottest_j.get("t_m") and f_use:
        delta = skin_depth_m(f_use)
        ratio = rac_over_rdc(float(hottest_j["t_m"]), f_use)
        skin = {
            "status": "READY",
            "f_hz": f_use,
            "delta_m": delta,
            "t_m": float(hottest_j["t_m"]),
            "t_over_delta": float(hottest_j["t_m"]) / delta,
            "rac_rdc": ratio,
            "via": "wide-sheet t/min(t,δ); not Wheeler, not roughness, not PEEC",
            "note": (
                "Rac/Rdc≈1 — metal thinner than skin depth at this f"
                if ratio < 1.01
                else "Rac/Rdc>1 — AC correction is estimated, not stamped into G"
            ),
        }
    status = "READY" if n_j else "PARTIAL"
    mesh_ready = bool(mesh_meta and mesh_meta.get("status") == "READY")
    return {
        "status": status,
        "model": (
            "I=(Va-Vb)/R; w=max(RPERSQ·L/R, WIDTH_min); J=I/(w·t); "
            f"TTF_rel=(Jref/J)^{BLACK_N} at {T_EM_K:.0f} K; "
            + (
                "ΔT from metal-graph G_th=kA/L (straps+vias) + ILD/Si + pad G_amb (lumped Rth comparison)"
                if mesh_ready
                else f"ΔT=Rth·I²R with Rth={RTH_K_PER_W} K/W lumped (mesh GAP)"
            )
        ),
        "not": [
            "foundry Black A / TTF hours",
            "extracted strap width from LEF geometry (width from R, clamped to min WIDTH)",
            "3D thermal FEM / package CFD (lumped Si + ILD is not that)",
            "skin-effect stamp into G (reported, not restamped)",
        ],
        "n_branches": len(branches),
        "n_with_j": n_j,
        "i_absmax_a": float(hottest_i["i_abs"]) if hottest_i else 0.0,
        "j_absmax_a_m2": j_absmax,
        "dT_absmax_k": dt_absmax,
        "dT_lumped_absmax_k": dt_absmax,
        "dT_mesh_absmax_k": dt_mesh,
        "r_scale_hot": r_scale,
        "n_r_scaled": n_scaled,
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
        "thermal_mesh": mesh_meta,
        "skin": skin,
        "note": (
            "EM J from physics I(t) and LEF RPERSQ/thickness. "
            + (
                f"metal-graph max ΔT={dt_mesh:.4e} K "
                f"(lumped isolation max {dt_absmax:.4e} K)."
                if mesh_ready
                else "ΔT is lumped Rth·I²R (thermal mesh GAP)."
            )
            if n_j
            else "No same-layer R with coordinates — J remains GAP."
        ),
    }
