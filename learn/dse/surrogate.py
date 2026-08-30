"""Cross-stage residual predictors. Never physical truth.

F0 for F1 area:
  n>=2  — SSK-GP posterior (mean ± std) on the ABC sequence
  else  — empirical mean of F1 area; uncertainty high if n<2

F1→F4 residual (RTLDistil-shaped):
  only when the same rtl_fp has both an F1 area and an F4 droop.
  With a single pair, uncertainty stays high — we do not invent IR from area.
"""

from __future__ import annotations

import math

from pathlib import Path

from .boils import gp_predict
from .gnn import embed_path, predict_hpwl as gnn_hpwl
from .memory import Candidate

_F2_FAST = {"f2_fast_netgraph", "f2_fast_barycenter"}


def predict_f1_area(logic: list[Candidate], ops: list[str] | None = None) -> dict:
    xs = [
        (list(c.knobs.get("abc_ops") or []), float(c.qor.area_um2))
        for c in logic
        if c.status == "ok" and c.qor.area_um2 is not None
    ]
    if not xs:
        return {
            "metric": "area_um2",
            "mean": None,
            "std": None,
            "n": 0,
            "uncertainty": "high",
            "via": "no F1 observations",
            "not": "physical IR / timing",
        }
    seqs, ys = zip(*xs)
    mean = sum(ys) / len(ys)
    if len(ys) == 1:
        return {
            "metric": "area_um2",
            "mean": mean,
            "std": None,
            "n": 1,
            "uncertainty": "high",
            "via": "empirical mean of F1 mapped area",
            "not": "Dynamic IR, WNS, or a neural voltage map",
        }
    var = sum((x - mean) ** 2 for x in ys) / (len(ys) - 1)
    emp_std = math.sqrt(var)
    unc = "medium" if len(ys) < 6 else "low"
    out = {
        "metric": "area_um2",
        "mean": mean,
        "std": emp_std,
        "n": len(ys),
        "uncertainty": unc,
        "via": "empirical mean of F1 mapped area",
        "not": "Dynamic IR, WNS, or a neural voltage map",
    }
    if ops is not None:
        (mu, std) = gp_predict(list(seqs), list(ys), [list(ops)])[0]
        out.update(
            {
                "mean": mu,
                "std": std,
                "via": "SSK-GP posterior on ABC sequence (BOiLS-class)",
                "ops": list(ops),
            }
        )
        if std > 0.35 * (abs(mu) + 1.0):
            out["uncertainty"] = "high"
    return out


def residual(actual: float | None, pred: dict) -> dict | None:
    if actual is None or pred.get("mean") is None:
        return None
    return {
        "actual": actual,
        "pred": pred["mean"],
        "residual": float(actual) - float(pred["mean"]),
        "uncertainty": pred.get("uncertainty"),
    }


def predict_f2_from_f1(all_cands: list[Candidate]) -> dict:
    """Residual teacher: F1 area → F2-fast HPWL. Honest uncertainty.

    Fit HPWL ≈ a + b·area when n≥3. Below that, report mean HPWL only.
    Ingested GRT HPWL is a *different* teacher (scale), never mixed into IR.
    """
    pairs = []
    for c in all_cands:
        if c.fidelity != "F2" or c.status != "ok":
            continue
        if (c.knobs or {}).get("source") not in _F2_FAST:
            continue
        hpwl = (c.artifacts or {}).get("hpwl")
        parent = next((p for p in all_cands if p.id == c.parent_id), None)
        area = parent.qor.area_um2 if parent else c.qor.area_um2
        if hpwl is None or area is None or float(hpwl) < 1.0:
            continue
        pairs.append((float(area), float(hpwl)))
    if not pairs:
        return {
            "metric": "hpwl",
            "n": 0,
            "uncertainty": "high",
            "via": "no F1→F2-fast pairs",
            "not": "GRT or Dynamic IR",
        }
    areas = [p[0] for p in pairs]
    hp = [p[1] for p in pairs]
    mean_h = sum(hp) / len(hp)
    if len(pairs) < 3:
        return {
            "metric": "hpwl",
            "mean": mean_h,
            "n": len(pairs),
            "uncertainty": "high",
            "via": "mean F2-fast HPWL (n<3, no slope)",
            "not": "GRT or Dynamic IR",
        }
    # least-squares hpwl = a + b*area
    n = len(pairs)
    mx = sum(areas) / n
    my = mean_h
    den = sum((x - mx) ** 2 for x in areas)
    b = 0.0 if den < 1e-12 else sum((x - mx) * (y - my) for x, y in pairs) / den
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in pairs]
    var = sum(r * r for r in resid) / (n - 2)
    return {
        "metric": "hpwl",
        "mean": mean_h,
        "slope_d_hpwl_d_area": b,
        "intercept": a,
        "residual_std": var ** 0.5,
        "n": n,
        "uncertainty": "medium" if n < 6 else "low",
        "via": "linear residual F1 area → F2-fast HPWL (RTLDistil-shaped)",
        "not": "Dynamic IR / a neural voltage map",
    }


def predict_f4_from_f1(all_cands: list[Candidate]) -> dict:
    """Teacher/student residual: F4 droop vs F1 area, paired on rtl_fp.

    One pair cannot identify a slope. We record the pairing and keep
    uncertainty=high so F0 never stands in for Dynamic IR.
    """
    f1_nl = {
        c.netlist_fp: c.qor.area_um2
        for c in all_cands
        if c.fidelity == "F1" and c.status == "ok" and c.netlist_fp and c.qor.area_um2 is not None
    }
    f1_rtl = {
        c.rtl_fp: c.qor.area_um2
        for c in all_cands
        if c.fidelity == "F1" and c.status == "ok" and c.rtl_fp and c.qor.area_um2 is not None
    }
    by_id = {c.id: c for c in all_cands}
    pairs = []
    for c in all_cands:
        if c.qor.dynamic_ir_mv is None:
            continue
        area = None
        if c.netlist_fp and c.netlist_fp in f1_nl:
            area = f1_nl[c.netlist_fp]
        elif c.parent_id and c.parent_id in by_id and by_id[c.parent_id].qor.area_um2 is not None:
            area = by_id[c.parent_id].qor.area_um2
        elif c.rtl_fp and c.rtl_fp in f1_rtl:
            area = f1_rtl[c.rtl_fp]
        if area is not None:
            pairs.append((float(area), float(c.qor.dynamic_ir_mv)))
    if not pairs:
        return {
            "metric": "dynamic_ir_mv",
            "mean": None,
            "n": 0,
            "uncertainty": "high",
            "via": "no F1↔F4 pair on the same rtl_fp",
            "not": "a voltage map",
        }
    irs = [p[1] for p in pairs]
    return {
        "metric": "dynamic_ir_mv",
        "mean": sum(irs) / len(irs),
        "n": len(pairs),
        "pairs": len(pairs),
        "uncertainty": "high" if len(pairs) < 4 else "medium",
        "via": "RTLDistil-shaped residual (need ≥4 pairs to fit a slope)",
        "not": "Dynamic IR gold / a neural voltage map",
    }


def predict_f2_gnn(all_cands: list[Candidate], query_mapped=None) -> dict:
    """GNN readout on the candidate netlist → F2-fast HPWL. Not IR."""
    teachers = []
    for c in all_cands:
        if (c.knobs or {}).get("source") not in _F2_FAST or c.status != "ok":
            continue
        hpwl = (c.artifacts or {}).get("hpwl")
        mapped = (c.artifacts or {}).get("mapped_v") or ""
        parent = next((p for p in all_cands if p.id == c.parent_id), None)
        src = mapped or (parent.artifacts or {}).get("mapped_v") if parent else mapped
        if hpwl is None or float(hpwl) < 1.0 or not src or not Path(src).is_file():
            continue
        try:
            teachers.append((embed_path(src), float(hpwl)))
        except OSError:
            continue
    q = None
    if query_mapped and Path(query_mapped).is_file():
        q = embed_path(query_mapped)
    elif teachers:
        q = teachers[0][0]
    else:
        q = [0.0] * 8
    return gnn_hpwl(teachers, q)


def predict_gpl_from_f1(all_cands: list[Candidate]) -> dict:
    """F1 area → OpenROAD GPL HPWL (µm). Separate scale from F2-fast grid HPWL."""
    pairs = []
    for c in all_cands:
        if (c.knobs or {}).get("source") != "f2_openroad_gpl" or c.status != "ok":
            continue
        hp = (c.artifacts or {}).get("hpwl_um")
        parent = next((p for p in all_cands if p.id == c.parent_id), None)
        area = parent.qor.area_um2 if parent else c.qor.area_um2
        if hp is None or area is None:
            continue
        pairs.append((float(area), float(hp)))
    if not pairs:
        return {
            "metric": "hpwl_um",
            "n": 0,
            "uncertainty": "high",
            "via": "no F1→GPL pairs",
            "not": "F2-fast grid HPWL or Dynamic IR",
        }
    mean = sum(p[1] for p in pairs) / len(pairs)
    return {
        "metric": "hpwl_um",
        "mean": mean,
        "n": len(pairs),
        "uncertainty": "high" if len(pairs) < 4 else "medium",
        "via": "mean OpenROAD GPL HPWL (µm)",
        "not": "F2-fast grid units or Dynamic IR",
    }


def _f1_to_metric(all_cands: list[Candidate], *, source: str, field: str, metric: str) -> dict:
    pairs = []
    for c in all_cands:
        if (c.knobs or {}).get("source") != source or c.status != "ok":
            continue
        val = getattr(c.qor, field, None)
        if val is None:
            val = (c.artifacts or {}).get(field)
        parent = next((p for p in all_cands if p.id == c.parent_id), None)
        area = parent.qor.area_um2 if parent else c.qor.area_um2
        if val is None or area is None:
            continue
        pairs.append((float(area), float(val)))
    if not pairs:
        return {
            "metric": metric,
            "n": 0,
            "uncertainty": "high",
            "via": f"no F1→{source} pairs",
            "not": "Dynamic IR",
        }
    mean = sum(p[1] for p in pairs) / len(pairs)
    return {
        "metric": metric,
        "mean": mean,
        "n": len(pairs),
        "uncertainty": "high" if len(pairs) < 4 else "medium",
        "via": f"mean {metric} from {source}",
        "not": "Dynamic IR / a neural voltage map",
    }


def predict_f5_from_f1(all_cands: list[Candidate]) -> dict:
    """F1 area → OpenRCX SPEF wns_cost. Separate from ideal STA and from IR."""
    return _f1_to_metric(
        all_cands, source="f5_openroad_drt_rcx", field="wns_cost", metric="wns_spef"
    )


def predict_f5_cts_from_f1(all_cands: list[Candidate]) -> dict:
    """F1 area → CTS SPEF wns_cost. Not the ideal-clock F5-lite residual."""
    return _f1_to_metric(
        all_cands, source="f5_openroad_cts_rcx", field="wns_cost", metric="wns_spef_cts"
    )


def _ideal_wns_ns(parent: Candidate | None, all_cands: list[Candidate], child: Candidate | None = None) -> float | None:
    """Ideal-clock WNS for a parent, from artifacts / F3 child / wns_cost."""
    if child is not None:
        w = (child.artifacts or {}).get("ideal_wns_ns")
        if w is not None:
            return float(w)
    if parent is not None:
        w = (parent.artifacts or {}).get("wns_ns")
        if w is not None:
            return float(w)
        if parent.qor.wns_cost is not None:
            return -float(parent.qor.wns_cost)
        pid = parent.id
        for c in all_cands:
            if c.status != "ok" or (c.knobs or {}).get("source") != "f3_opensta_ideal":
                continue
            if (c.knobs or {}).get("parent_id") != pid:
                continue
            ww = (c.artifacts or {}).get("wns_ns")
            if ww is not None:
                return float(ww)
            if c.qor.wns_cost is not None:
                return -float(c.qor.wns_cost)
    return None


def _residual_pack(pairs: list[dict], *, via: str, empty_via: str) -> dict:
    if not pairs:
        return {
            "metric": "wns_spef_minus_ideal",
            "n": 0,
            "uncertainty": "high",
            "via": empty_via,
            "not": "Dynamic IR or a reused SPEF as physical truth",
        }
    rs = [p["residual_ns"] for p in pairs]
    mean_r = sum(rs) / len(rs)
    var = sum((x - mean_r) ** 2 for x in rs) / max(len(rs) - 1, 1)
    return {
        "metric": "wns_spef_minus_ideal",
        "mean_residual_ns": mean_r,
        "residual_std_ns": var ** 0.5,
        "n": len(pairs),
        "pairs": pairs,
        "uncertainty": "high" if len(pairs) < 2 else ("medium" if len(pairs) < 4 else "low"),
        "via": via,
        "not": "Dynamic IR or a reused SPEF as physical truth",
    }


def residual_f3_to_f5_lite(all_cands: list[Candidate]) -> dict:
    """Ideal STA WNS → F5-lite OpenRCX SPEF WNS on the F1 netlist.

    Available before F5-local. Steers which local host to measure first.
    """
    by_id = {c.id: c for c in all_cands}
    pairs: list[dict] = []
    for c in all_cands:
        if (c.knobs or {}).get("source") != "f5_openroad_drt_rcx" or c.status != "ok":
            continue
        spef_w = (c.artifacts or {}).get("wns_ns")
        parent = by_id.get(c.parent_id)
        ideal_w = _ideal_wns_ns(parent, all_cands, c)
        if spef_w is None or ideal_w is None:
            continue
        pairs.append(
            {
                "ideal_ns": float(ideal_w),
                "spef_ns": float(spef_w),
                "residual_ns": float(spef_w) - float(ideal_w),
                "host_level": "chip",
            }
        )
    return _residual_pack(
        pairs,
        via="F3 ideal → F5-lite OpenRCX residual on the F1 netlist",
        empty_via="no F3-ideal→F5-lite pairs",
    )


def residual_f3_to_f5_local(all_cands: list[Candidate]) -> dict:
    """Ideal STA WNS → OpenRCX SPEF WNS on the same cell/net netlist.

    This is the cross-stage residual for local transforms. It is not
    Dynamic IR and not a reuse of the F1 F5-lite SPEF.
    """
    by_id = {c.id: c for c in all_cands}
    pairs: list[dict] = []
    for c in all_cands:
        if (c.knobs or {}).get("source") != "f5_openroad_local" or c.status != "ok":
            continue
        spef_w = (c.artifacts or {}).get("wns_ns")
        parent = by_id.get(c.parent_id)
        ideal_w = _ideal_wns_ns(parent, all_cands, c)
        if spef_w is None or ideal_w is None:
            continue
        pairs.append(
            {
                "ideal_ns": float(ideal_w),
                "spef_ns": float(spef_w),
                "residual_ns": float(spef_w) - float(ideal_w),
                "host_level": (c.knobs or {}).get("host_level"),
            }
        )
    return _residual_pack(
        pairs,
        via="F3 ideal → F5 OpenRCX residual on the local cell/net netlist",
        empty_via="no F3-ideal→F5-local pairs",
    )


def predict_wns_from_f1(all_cands: list[Candidate]) -> dict:
    """F1 area → ideal-STA wns_cost. Separate from placed/GRT WNS and from IR."""
    return _f1_to_metric(
        all_cands, source="f3_opensta_ideal", field="wns_cost", metric="wns_cost"
    )


def predict_power_from_f1(all_cands: list[Candidate]) -> dict:
    return _f1_to_metric(
        all_cands, source="f3_opensta_ideal", field="power_w", metric="power_w"
    )


def residual_f4_mesh(all_cands: list[Candidate]) -> dict:
    """Finish-gold droop vs candidate-extract DirectLU. Not a solver residual."""
    gold = cand = None
    cand_id = None
    for c in all_cands:
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        src = (c.knobs or {}).get("source")
        if src == "ingest_pdn":
            gold = float(c.qor.dynamic_ir_mv)
        elif src == "f4_candidate_extract":
            cand = float(c.qor.dynamic_ir_mv)
            cand_id = (c.knobs or {}).get("extract_id") or c.id
    if gold is None or cand is None:
        return {
            "metric": "dynamic_ir_mv",
            "n": 0,
            "uncertainty": "high",
            "via": "no finish-gold ↔ candidate-extract pair",
            "not": "a solver residual or Dynamic IR gold restamp",
        }
    return {
        "metric": "dynamic_ir_mv",
        "mean_residual_mv": cand - gold,
        "gold_mv": gold,
        "candidate_mv": cand,
        "extract_id": cand_id,
        "n": 1,
        "uncertainty": "medium",
        "via": "F4 candidate mesh vs finish gold — different R-graph, not a solver residual",
        "not": "Dynamic IR gold / a mixed ABC+PDN vector",
    }


def residual_f4_knob(all_cands: list[Candidate]) -> dict:
    """PDN catalog DirectLU vs gold-knob DirectLU on the same candidate extract."""
    base: dict[str, float] = {}
    catalogs: list[dict] = []
    for c in all_cands:
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        k = c.knobs or {}
        src = k.get("source")
        if src == "f4_candidate_extract":
            base[str(k.get("extract_id") or c.id)] = float(c.qor.dynamic_ir_mv)
        elif src == "f4_solver_a" and k.get("name") in ("decap_200f", "pkg_l_100p"):
            catalogs.append(
                {
                    "extract_id": str(k.get("extract_id") or ""),
                    "name": k.get("name"),
                    "mv": float(c.qor.dynamic_ir_mv),
                }
            )
    pairs = []
    for cat in catalogs:
        eid = cat["extract_id"]
        if eid not in base:
            continue
        pairs.append(
            {
                "extract_id": eid,
                "catalog": cat["name"],
                "base_mv": base[eid],
                "catalog_mv": cat["mv"],
                "residual_mv": cat["mv"] - base[eid],
            }
        )
    if not pairs:
        return {
            "metric": "dynamic_ir_mv",
            "n": 0,
            "uncertainty": "high",
            "via": "no PDN catalog ↔ gold-knob pair on the same extract",
            "not": "Dynamic IR gold / a mixed ABC+PDN vector",
        }
    rs = [p["residual_mv"] for p in pairs]
    mean_r = sum(rs) / len(rs)
    return {
        "metric": "dynamic_ir_mv",
        "mean_residual_mv": mean_r,
        "n": len(pairs),
        "pairs": pairs,
        "catalog": pairs[0]["catalog"],
        "extract_id": pairs[0]["extract_id"],
        "uncertainty": "medium" if len(pairs) < 2 else "low",
        "via": "F4 PDN catalog vs gold knobs on the named candidate extract",
        "not": "Dynamic IR gold / more ABC",
    }


def residual_f4_region(all_cands: list[Candidate]) -> dict:
    """IR-bin density-cap extract vs unconstrained candidate, gold knobs."""
    cand = region = None
    region_id = None
    for c in all_cands:
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        src = (c.knobs or {}).get("source")
        if src == "f4_candidate_extract":
            cand = float(c.qor.dynamic_ir_mv)
        elif src == "f4_region_extract":
            region = float(c.qor.dynamic_ir_mv)
            region_id = (c.knobs or {}).get("extract_id") or c.id
    if cand is None or region is None:
        return {
            "metric": "dynamic_ir_mv",
            "n": 0,
            "uncertainty": "high",
            "via": "no region-extract ↔ candidate-extract pair",
            "not": "Dynamic IR gold",
        }
    return {
        "metric": "dynamic_ir_mv",
        "mean_residual_mv": region - cand,
        "candidate_mv": cand,
        "region_mv": region,
        "extract_id": region_id,
        "n": 1,
        "uncertainty": "medium",
        "via": "F4 region mesh vs unconstrained candidate — density cap, not gold",
        "not": "a solver residual or a mixed ABC+PDN vector",
    }


def residual_f4_host_region(all_cands: list[Candidate]) -> dict:
    """Host density-cap extract vs unconstrained host extract. Not gold rXY."""
    host = host_r = None
    host_bin = region_bin = None
    region_id = None
    for c in all_cands:
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        src = (c.knobs or {}).get("source")
        if src == "f4_host_extract":
            host = float(c.qor.dynamic_ir_mv)
            host_bin = (c.attr or {}).get("region")
        elif src == "f4_host_region_extract":
            host_r = float(c.qor.dynamic_ir_mv)
            region_bin = (c.knobs or {}).get("region") or (c.attr or {}).get("region")
            region_id = (c.knobs or {}).get("extract_id") or c.id
    if host is None or host_r is None:
        return {
            "metric": "dynamic_ir_mv",
            "n": 0,
            "uncertainty": "high",
            "via": "no host-region-extract ↔ host-extract pair",
            "not": "Dynamic IR gold / synth region extract",
        }
    return {
        "metric": "dynamic_ir_mv",
        "mean_residual_mv": host_r - host,
        "host_mv": host,
        "host_region_mv": host_r,
        "host_bin": host_bin,
        "region_bin": region_bin,
        "extract_id": region_id,
        "n": 1,
        "uncertainty": "medium",
        "via": "F4 host-region mesh vs unconstrained host — density cap, not gold rXY",
        "not": "a solver residual or a mixed ABC+PDN vector",
    }


def residual_f4_static(all_cands: list[Candidate]) -> dict:
    """Static IR champion vs Dynamic IR champion vs gold. Not a Dynamic IR copy."""
    from .active import winning_ir_pdn, winning_static_pdn

    by_level: dict[str, list[Candidate]] = {}
    for c in all_cands:
        by_level.setdefault(c.level, []).append(c)

    class _View:
        def by_level(self, level):
            return by_level.get(level, [])

        def all(self):
            return all_cands

    view = _View()
    gold = None
    for c in all_cands:
        if c.status == "ok" and (c.knobs or {}).get("source") == "ingest_pdn" and c.qor.static_ir_mv is not None:
            gold = float(c.qor.static_ir_mv)
            break
    # winning_* expect DesignMemory; call the ranking loops here instead.
    win_s = winning_static_pdn(view)  # type: ignore[arg-type]
    win_d = winning_ir_pdn(view)  # type: ignore[arg-type]
    if win_s is None or win_s.qor.static_ir_mv is None:
        return {
            "metric": "static_ir_mv",
            "n": 0,
            "uncertainty": "high",
            "via": "no 1× static-IR champion on the host/IR-cell family",
            "not": "Dynamic IR gold / a decap restamp",
        }
    s_mv = float(win_s.qor.static_ir_mv)
    d_static = float(win_d.qor.static_ir_mv) if win_d and win_d.qor.static_ir_mv is not None else None
    s_eid = str((win_s.knobs or {}).get("extract_id") or win_s.id)
    d_eid = str((win_d.knobs or {}).get("extract_id") or win_d.id) if win_d else None
    out = {
        "metric": "static_ir_mv",
        "winning_static_mv": s_mv,
        "winning_static_id": win_s.id,
        "winning_static_extract": s_eid,
        "winning_dynamic_id": win_d.id if win_d else None,
        "winning_dynamic_extract": d_eid,
        "winning_dynamic_static_mv": d_static,
        "same_extract": bool(d_eid) and d_eid == s_eid,
        "n": 1,
        "uncertainty": "medium",
        "via": "F4 static IR 1× ranking vs Dynamic IR champion — pkg_r axis, not decap",
        "not": "Dynamic IR gold / a mixed ABC+PDN vector",
    }
    if gold is not None:
        out["gold_static_mv"] = gold
        out["static_vs_gold_mv"] = s_mv - gold
    if d_static is not None:
        out["static_vs_dynamic_champ_mv"] = s_mv - d_static
    return out
