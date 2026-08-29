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
        ideal_w = None
        if parent is not None:
            ideal_w = (parent.artifacts or {}).get("wns_ns")
        if ideal_w is None:
            ideal_w = (c.artifacts or {}).get("ideal_wns_ns")
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
    if not pairs:
        return {
            "metric": "wns_spef_minus_ideal",
            "n": 0,
            "uncertainty": "high",
            "via": "no F3-ideal→F5-local pairs",
            "not": "Dynamic IR or the F1 F5-lite SPEF",
        }
    mean_r = sum(p["residual_ns"] for p in pairs) / len(pairs)
    return {
        "metric": "wns_spef_minus_ideal",
        "mean_residual_ns": mean_r,
        "n": len(pairs),
        "pairs": pairs,
        "uncertainty": "high" if len(pairs) < 3 else "medium",
        "via": "F3 ideal → F5 OpenRCX residual on the local cell/net netlist",
        "not": "Dynamic IR or a reused F1 SPEF",
    }


def predict_wns_from_f1(all_cands: list[Candidate]) -> dict:
    """F1 area → ideal-STA wns_cost. Separate from placed/GRT WNS and from IR."""
    return _f1_to_metric(
        all_cands, source="f3_opensta_ideal", field="wns_cost", metric="wns_cost"
    )


def predict_power_from_f1(all_cands: list[Candidate]) -> dict:
    return _f1_to_metric(
        all_cands, source="f3_opensta_ideal", field="power_w", metric="power_w"
    )
