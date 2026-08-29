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

from .boils import gp_predict
from .memory import Candidate


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
        if (c.knobs or {}).get("source") != "f2_fast_barycenter":
            continue
        hpwl = (c.artifacts or {}).get("hpwl")
        parent = next((p for p in all_cands if p.id == c.parent_id), None)
        area = parent.qor.area_um2 if parent else c.qor.area_um2
        if hpwl is None or area is None:
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
    f1 = {
        c.rtl_fp: c.qor.area_um2
        for c in all_cands
        if c.fidelity == "F1" and c.status == "ok" and c.rtl_fp and c.qor.area_um2 is not None
    }
    pairs = []
    for c in all_cands:
        if c.qor.dynamic_ir_mv is None or not c.rtl_fp:
            continue
        if c.rtl_fp in f1:
            pairs.append((f1[c.rtl_fp], float(c.qor.dynamic_ir_mv)))
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
        "via": "RTLDistil-shaped residual placeholder (need ≥4 pairs to fit)",
        "not": "Dynamic IR gold / a neural voltage map",
    }
