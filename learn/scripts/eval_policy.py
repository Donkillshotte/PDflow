#!/usr/bin/env python3
"""Evaluate next-iteration hypotheses I1–I5 on the campaign registry.

Reads `learn/sim/dse/campaign_experiments.jsonl`. Does **not** retune
`learn/dse/next_iteration_plan.md` after seeing data. Q0 is zero-cost:
I1/I3/I4 stay incomplete until Q1/Q2 cooks exist.

Usage:
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/eval_policy.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_LEARN = Path(__file__).resolve().parents[1]
if str(_LEARN) not in sys.path:
    sys.path.insert(0, str(_LEARN))

from dse.experiments import Experiment, ExperimentLog, DEFAULT_LOG  # noqa: E402
from dse.recipe_labels import label_for, synth_method_from_exploration  # noqa: E402
from dse.win_rule import verdict as product_verdict  # noqa: E402
from eval_campaign import WIN_AREA_FRAC, WIN_WNS_EPS_PS, _beats_base, winner_variant  # noqa: E402

NEXT_PLAN = _LEARN / "dse" / "next_iteration_plan.md"
OUT_MD = _LEARN / "dse" / "eval_policy.md"
OUT_JSON = _LEARN / "dse" / "eval_policy.json"
OUT_QOR = _LEARN / "dse" / "qor_compare.md"
OUT_SYNTH = _LEARN / "dse" / "synth_method.json"

SPEARMAN_BAR = 0.6
I5_MIN_N = 8
I2_COVERAGE = 0.80
I2_MIN_CALIB = 3
I1_GCD_RANGE_PS = 25.0
I1_IBEX_RANGE_PS = 50.0
I3_PREC = 0.80
PLACE_GATE_NS = 0.0


def next_plan_sha() -> str:
    if not NEXT_PLAN.is_file():
        return ""
    return hashlib.sha256(NEXT_PLAN.read_bytes()).hexdigest()


def _ranks(xs: list[float]) -> list[float]:
    n = len(xs)
    order = sorted(range(n), key=lambda i: xs[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 or dy == 0.0:
        return None
    return num / (dx * dy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return _pearson(_ranks(xs), _ranks(ys))


def _clk(e: Experiment) -> str:
    return f"{float(e.clock_ns):.3f}"


def _labeled(exps: list[Experiment]) -> list[Experiment]:
    out = []
    for e in exps:
        if e.status != "done" or e.finish_wns_ns is None:
            continue
        if e.role == "ainj":
            continue
        out.append(e)
    return out


def _bases(exps: list[Experiment]) -> dict[tuple[str, str], Experiment]:
    by: dict[tuple[str, str], Experiment] = {}
    for e in exps:
        if e.status != "done" or e.finish_wns_ns is None:
            continue
        if e.role != "base":
            continue
        if e.phase not in ("P0", "P1", "P5", "Q1"):
            continue
        key = (e.design, _clk(e))
        # Prefer P0 product-clock bases over later bookkeeping.
        if key not in by or e.phase == "P0":
            by[key] = e
    return by


def _mean_std(xs: list[float]) -> tuple[float | None, float | None]:
    if not xs:
        return None, None
    mu = sum(xs) / len(xs)
    if len(xs) < 2:
        return mu, 0.0
    var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
    return mu, math.sqrt(var)


def _i5(exps: list[Experiment]) -> dict[str, Any]:
    labeled = _labeled(exps)
    place_pairs = [
        (float(e.place_wns_ns), float(e.finish_wns_ns))
        for e in labeled
        if e.place_wns_ns is not None
    ]
    f1_pairs = [
        (float(e.proxy_wns_ns), float(e.finish_wns_ns))
        for e in labeled
        if e.proxy_wns_ns is not None
    ]
    place_r = spearman([a for a, _ in place_pairs], [b for _, b in place_pairs]) if place_pairs else None
    f1_r = spearman([a for a, _ in f1_pairs], [b for _, b in f1_pairs]) if f1_pairs else None
    n_place = len(place_pairs)
    n_f1 = len(f1_pairs)
    if n_place < I5_MIN_N or place_r is None:
        verdict = "I5 incomplete (need ≥8 place+finish pairs)"
        supported = None
    elif place_r < SPEARMAN_BAR:
        verdict = f"I5 not supported (place Spearman {place_r:.3f} < {SPEARMAN_BAR})"
        supported = False
    else:
        f1_note = "n/a" if f1_r is None else f"{f1_r:.3f}"
        verdict = (
            f"I5 supported (place Spearman {place_r:.3f} ≥ {SPEARMAN_BAR}; "
            f"F1 Spearman {f1_note})"
        )
        supported = True
    return {
        "n_place_pairs": n_place,
        "n_f1_pairs": n_f1,
        "place_spearman": place_r,
        "f1_spearman": f1_r,
        "bar": SPEARMAN_BAR,
        "min_n": I5_MIN_N,
        "supported": supported,
        "verdict": verdict,
    }


def _gate(exps: list[Experiment]) -> dict[str, Any]:
    bases = _bases(exps)
    labeled = _labeled(exps)
    n = 0
    n_promoted = 0
    n_wins = 0
    tp = fp = fn = tn = 0
    for e in labeled:
        if e.place_wns_ns is None:
            continue
        base = bases.get((e.design, _clk(e)))
        if base is None or e.variant == base.variant:
            continue
        n += 1
        promoted = float(e.place_wns_ns) >= PLACE_GATE_NS - 1e-12
        win = _beats_base(e, base)
        if promoted:
            n_promoted += 1
        if win:
            n_wins += 1
        if promoted and win:
            tp += 1
        elif promoted and not win:
            fp += 1
        elif (not promoted) and win:
            fn += 1
        else:
            tn += 1
    prec = (tp / (tp + fp)) if (tp + fp) else None
    rec = (tp / (tp + fn)) if (tp + fn) else None
    return {
        "n_challengers": n,
        "n_promoted": n_promoted,
        "n_real_wins": n_wins,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": prec,
        "recall": rec,
        "verdict": (
            f"gate FP={fp} FN={fn} precision="
            f"{'n/a' if prec is None else f'{prec:.3f}'} "
            f"({n_wins} product-wins among {n} challengers)"
        ),
    }


def _i2(exps: list[Experiment]) -> dict[str, Any]:
    labeled = [e for e in _labeled(exps) if e.place_wns_ns is not None]
    by_design: dict[str, list[Experiment]] = defaultdict(list)
    for e in labeled:
        by_design[e.design].append(e)
    calib: dict[str, dict[str, Any]] = {}
    for design, rows in sorted(by_design.items()):
        res = [float(e.finish_wns_ns) - float(e.place_wns_ns) for e in rows]
        mu, sd = _mean_std(res)
        calib[design] = {
            "n": len(rows),
            "mean_ns": mu,
            "std_ns": sd,
        }
    holdout = [e for e in labeled if e.phase.startswith("Q")]
    train = [e for e in labeled if not e.phase.startswith("Q")]
    coverage = None
    n_hold = 0
    n_in = 0
    per_point = []
    if holdout and train:
        train_by: dict[str, list[float]] = defaultdict(list)
        for e in train:
            train_by[e.design].append(float(e.finish_wns_ns) - float(e.place_wns_ns))
        for e in holdout:
            xs = train_by.get(e.design) or []
            if len(xs) < I2_MIN_CALIB:
                continue
            mu, sd = _mean_std(xs)
            if mu is None or sd is None:
                continue
            pred = float(e.place_wns_ns) + mu
            err = float(e.finish_wns_ns) - pred
            band = 2.0 * (sd if sd > 1e-12 else 1e-12)
            inside = abs(err) <= band
            n_hold += 1
            n_in += int(inside)
            per_point.append({
                "variant": e.variant,
                "design": e.design,
                "pred_ns": pred,
                "actual_ns": float(e.finish_wns_ns),
                "err_ns": err,
                "band_ns": band,
                "inside": inside,
            })
        coverage = (n_in / n_hold) if n_hold else None
    if coverage is None:
        verdict = "I2 incomplete (need Q* holdout after ≥3 calib finishes/design)"
        supported = None
    elif coverage >= I2_COVERAGE:
        verdict = f"I2 supported ({n_in}/{n_hold} holdout inside per-design ±2σ)"
        supported = True
    else:
        verdict = f"I2 not supported ({n_in}/{n_hold} holdout inside per-design ±2σ < {I2_COVERAGE:.0%})"
        supported = False
    return {
        "calibration": calib,
        "n_holdout": n_hold,
        "n_inside": n_in,
        "coverage": coverage,
        "bar": I2_COVERAGE,
        "holdout": per_point,
        "supported": supported,
        "verdict": verdict,
    }


def _i1(exps: list[Experiment]) -> dict[str, Any]:
    q1 = [e for e in _labeled(exps) if e.phase == "Q1"]
    bases = _bases(exps)
    wins = []
    ranges: dict[str, dict[str, Any]] = {}
    for design in ("gcd", "ibex"):
        rows = [e for e in q1 if e.design == design]
        base = bases.get((design, {"gcd": "0.460", "ibex": "2.200"}[design]))
        wns = []
        if base and base.finish_wns_ns is not None:
            wns.append(float(base.finish_wns_ns))
        for e in rows:
            wns.append(float(e.finish_wns_ns))
            if base and _beats_base(e, base):
                wins.append(e.variant)
        if len(wns) >= 2:
            span_ps = (max(wns) - min(wns)) * 1000.0
        else:
            span_ps = None
        ranges[design] = {"n_q1": len(rows), "range_ps": span_ps, "n_wns": len(wns)}
    if not q1:
        verdict = "I1 incomplete (no Q1 knob finishes yet)"
        supported = None
    else:
        gcd_r = ranges["gcd"]["range_ps"]
        ibex_r = ranges["ibex"]["range_ps"]
        gcd_sensitive = gcd_r is not None and gcd_r >= I1_GCD_RANGE_PS
        ibex_sensitive = ibex_r is not None and ibex_r >= I1_IBEX_RANGE_PS
        if wins or gcd_sensitive or ibex_sensitive:
            verdict = (
                "I1 supported"
                + (f" (wins {wins})" if wins else "")
                + (f" gcd_range={gcd_r:.1f}ps" if gcd_r is not None else "")
                + (f" ibex_range={ibex_r:.1f}ps" if ibex_r is not None else "")
            )
            supported = True
        elif gcd_r is not None and ibex_r is not None:
            verdict = (
                f"I1 not supported (no §5 win; gcd range {gcd_r:.1f}ps < {I1_GCD_RANGE_PS}, "
                f"ibex range {ibex_r:.1f}ps < {I1_IBEX_RANGE_PS})"
            )
            supported = False
        else:
            verdict = "I1 incomplete (Q1 not finished on both designs)"
            supported = None
    return {
        "wins": wins,
        "ranges": ranges,
        "gcd_bar_ps": I1_GCD_RANGE_PS,
        "ibex_bar_ps": I1_IBEX_RANGE_PS,
        "supported": supported,
        "verdict": verdict,
    }


def _i3(exps: list[Experiment]) -> dict[str, Any]:
    from dse.fidelity_policy import decide as policy_decide

    train = [
        e
        for e in _labeled(exps)
        if (not str(e.phase).startswith("Q")) and e.place_wns_ns is not None
    ]
    by_d: dict[str, list[float]] = defaultdict(list)
    for e in train:
        by_d[e.design].append(float(e.finish_wns_ns) - float(e.place_wns_ns))
    table: dict[str, tuple[float, float]] = {}
    for design, xs in by_d.items():
        mu, sd = _mean_std(xs)
        if mu is not None:
            table[design] = (mu, sd if sd else 0.04)

    bases = _bases(exps)
    rows = []
    n_lose = 0
    seen: set[str] = set()

    def _consider(e: Experiment, via: str) -> None:
        nonlocal n_lose
        if e.variant in seen or e.role == "base" or e.place_wns_ns is None:
            return
        base = bases.get((e.design, _clk(e)))
        if base is None or e.variant == base.variant:
            return
        dec = policy_decide(
            design=e.design,
            place_wns_ns=float(e.place_wns_ns),
            baseline_finish_ns=float(base.finish_wns_ns) if base.finish_wns_ns is not None else None,
            residual_table=table or None,
        )
        if dec.action != "STOP" and via != "control_negative":
            return
        if dec.action != "STOP" and via == "control_negative":
            return
        lose = not _beats_base(e, base)
        seen.add(e.variant)
        n_lose += int(lose)
        rows.append({"variant": e.variant, "loses": lose, "via": via, "policy": dec.action})

    for e in exps:
        if e.phase == "Q2" and "control_negative" in (e.notes or "") and e.status == "done" and e.finish_wns_ns is not None:
            _consider(e, "control_negative")
    for e in _labeled(exps):
        if e.role in ("dse_small", "dse_fast", "dse_other") or e.phase in ("Q1", "Q2"):
            _consider(e, "replay")

    n = len(rows)
    prec = (n_lose / n) if n else None
    if prec is None:
        verdict = "I3 incomplete (no verified STOP decisions)"
        supported = None
    elif prec >= I3_PREC:
        verdict = f"I3 supported (STOP precision {prec:.0%} on {n} verified rejects)"
        supported = True
    else:
        verdict = f"I3 not supported (STOP precision {prec:.0%} < {I3_PREC:.0%} on {n})"
        supported = False
    return {
        "n_verified": n,
        "n_lose": n_lose,
        "precision": prec,
        "bar": I3_PREC,
        "rows": rows,
        "supported": supported,
        "verdict": verdict,
    }


def _i4(exps: list[Experiment]) -> dict[str, Any]:
    # Historical camp_gcd_clk090_b is explicitly not a retroactive win.
    bases = _bases(exps)
    candidates = [
        e
        for e in _labeled(exps)
        if e.phase in ("Q1", "Q2", "Q4") and e.role != "base"
    ]
    hits = []
    for e in candidates:
        base = bases.get((e.design, _clk(e)))
        if base is None or base.finish_wns_ns is None or e.finish_wns_ns is None:
            continue
        if float(base.finish_wns_ns) < 0 or float(e.finish_wns_ns) < 0:
            continue
        ba, ca = base.stdcell_um2, e.stdcell_um2
        if ba is None or ca is None:
            continue
        frac = (float(ba) - float(ca)) / float(ba)
        if frac >= WIN_AREA_FRAC:
            hits.append({"variant": e.variant, "area_frac": frac})
    if not candidates:
        verdict = "I4 incomplete (no Q1/Q2/Q4 area-regime candidates)"
        supported = None
    elif hits:
        verdict = f"I4 supported ({[h['variant'] for h in hits]})"
        supported = True
    else:
        verdict = "I4 not supported (no closed candidate ≥10% smaller than a closed base)"
        supported = False
    return {
        "n_candidates": len(candidates),
        "hits": hits,
        "area_frac": WIN_AREA_FRAC,
        "supported": supported,
        "verdict": verdict,
    }


def _pct(child: float | None, base: float | None) -> float | None:
    if child is None or base is None or abs(float(base)) < 1e-18:
        return None
    return (float(child) - float(base)) / float(base) * 100.0


def _abs_metrics(e: Experiment) -> dict[str, Any]:
    lab = label_for(e)
    return {
        "variant": e.variant,
        "title": lab.title,
        "does": lab.does,
        "payoff": lab.payoff,
        "wns_ps": None if e.finish_wns_ns is None else float(e.finish_wns_ns) * 1000.0,
        "tns_ns": e.finish_tns_ns,
        "area_um2": e.stdcell_um2,
        "cells": e.stdcell_count,
        "power_mw": None if e.power_w is None else float(e.power_w) * 1000.0,
        "leak_uw": None if e.leakage_w is None else float(e.leakage_w) * 1e6,
        "internal_mw": None if e.internal_power_w is None else float(e.internal_power_w) * 1000.0,
        "switching_mw": None if e.switching_power_w is None else float(e.switching_power_w) * 1000.0,
        "ir_mv": None if e.ir_drop_v is None else float(e.ir_drop_v) * 1000.0,
        "ir_mean_mv": None if e.ir_mean_v is None else float(e.ir_mean_v) * 1000.0,
        "density_pct": None if e.util is None else float(e.util) * 100.0,
        "util": e.util,
        "grt_wl": e.grt_wl,
        "cong_wl_per_um2": e.cong_wl_per_um2,
        "grt_violations": e.grt_violations,
        "fmax_mhz": None if e.fmax_hz is None else float(e.fmax_hz) / 1e6,
        "setup_viol": e.setup_violation_count,
        "die_um2": e.die_um2,
        "repair_buffer": e.repair_buffer,
    }


def _qor_vs_base(exps: list[Experiment]) -> dict[str, Any]:
    """Multi-axis vs same-clock ORFS base. Includes absolute reference values."""
    bases = _bases(exps)
    refs = []
    for (design, clk), b in sorted(bases.items()):
        refs.append({"design": design, "clock_ns": float(clk), **_abs_metrics(b)})
    rows = []
    for e in _labeled(exps):
        base = bases.get((e.design, _clk(e)))
        if base is None or e.variant == base.variant:
            continue
        if e.power_w is None and e.stdcell_um2 is None:
            continue
        win = product_verdict(e, base)
        bm, cm = _abs_metrics(base), _abs_metrics(e)
        rows.append({
            "variant": e.variant,
            "design": e.design,
            "clock_ns": e.clock_ns,
            "phase": e.phase,
            "base_variant": base.variant,
            "section5": win,
            "base": bm,
            "cand": cm,
            "d_wns_ps": None if bm["wns_ps"] is None or cm["wns_ps"] is None else cm["wns_ps"] - bm["wns_ps"],
            "d_area_pct": _pct(e.stdcell_um2, base.stdcell_um2),
            "d_power_pct": _pct(e.power_w, base.power_w),
            "d_leak_pct": _pct(e.leakage_w, base.leakage_w),
            "d_ir_pct": _pct(e.ir_drop_v, base.ir_drop_v),
            "d_ir_mean_pct": _pct(e.ir_mean_v, base.ir_mean_v),
            "d_wl_pct": _pct(e.grt_wl, base.grt_wl),
            "d_cong_pct": _pct(e.cong_wl_per_um2, base.cong_wl_per_um2),
            "d_density_pct": _pct(e.util, base.util),
        })
    n_ir = sum(1 for r in rows if r["base"]["ir_mv"] is not None)
    n_wl = sum(1 for r in rows if r["base"]["grt_wl"] is not None)
    wins = [r for r in rows if r["section5"] == "win"]
    return {
        "n_compared": len(rows),
        "n_references": len(refs),
        "n_with_ir": n_ir,
        "n_with_grt_wl": n_wl,
        "n_section5_wins": len(wins),
        "references": refs,
        "rows": rows,
        "verdict": (
            f"QoR vs base: {len(refs)} reference slots, {len(rows)} challengers, "
            f"{n_ir} with IR, {n_wl} with GRT WL, {len(wins)} product wins"
        ),
    }


def evaluate(log: ExperimentLog) -> dict[str, Any]:
    exps = log.all()
    return {
        "plan": str(NEXT_PLAN),
        "plan_sha": next_plan_sha(),
        "n_experiments": len(exps),
        "n_done": sum(1 for e in exps if e.status == "done"),
        "win_criteria_frozen": {
            "wns_eps_ps": WIN_WNS_EPS_PS,
            "area_frac": WIN_AREA_FRAC,
        },
        "I1_physical_knobs": _i1(exps),
        "I2_per_design_residual": _i2(exps),
        "I3_stop_precision": _i3(exps),
        "I4_area_regime": _i4(exps),
        "I5_proxy_correlation": _i5(exps),
        "gate_diagnostics": _gate(exps),
        "QoR_vs_base": _qor_vs_base(exps),
        "synth_method": synth_method_from_exploration(),
    }


def _n(v: Any, nd: int = 2) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def _ni(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return str(v)


def _metric_cells(m: dict[str, Any]) -> list[str]:
    return [
        _n(m.get("wns_ps"), 1),
        _n(m.get("tns_ns"), 3),
        _n(m.get("area_um2"), 1),
        _n(m.get("power_mw"), 3),
        _n(m.get("leak_uw"), 2),
        _n(m.get("ir_mv"), 2),
        _n(m.get("ir_mean_mv"), 2),
        _n(m.get("density_pct"), 1),
        _n(m.get("cong_wl_per_um2"), 2),
        _ni(m.get("grt_wl")),
        _n(m.get("fmax_mhz"), 1),
        _ni(m.get("setup_viol")),
    ]


def _flow_name(m: dict[str, Any]) -> str:
    title = m.get("title") or m.get("variant") or ""
    variant = m.get("variant") or ""
    if title and variant and title != variant:
        return f"{title} (`{variant}`)"
    return f"`{variant}`" if variant else title


def render_qor_tables(block: dict[str, Any]) -> list[str]:
    """Human tables: reference-flow absolutes sit next to every challenger."""
    refs = list(block.get("references") or [])
    rows = list(block.get("rows") or [])
    lines = [
        "I nomi in tabella dicono **cosa fa** la ricetta e (nella § Ricette) "
        "qual è il vantaggio o lo svantaggio. L'id `camp_*` resta solo il path ORFS.",
        "",
        "IR worst = drop VDD massimo. **IR mean** = drop medio sul die "
        "(VDD_nom − V_avg; la chiave ORFS `drop__average` su VDD è in realtà una tensione). "
        "**Density** = utilizzazione stdcell sul core. **Congestion** = GRT WL / area core "
        "(i JSON non hanno overflow fraction; `congestion_*_s` sono runtime).",
        "",
        "Vittoria prodotto: timing ±5 ps e (area o potenza o IR −10%), senza peggiorare nessuno del 10%. Oppure timing +5 ps senza peggiorare area/potenza/IR. Vedi `product.md`.",
        "",
        "### Ricette (cosa fanno, che vantaggio hanno)",
        "",
        "| Ricetta | Cosa fa | Vantaggio / esito |",
        "|---|---|---|",
    ]
    seen: set[str] = set()
    for src in list(refs) + [r.get("cand") or r for r in rows]:
        key = src.get("variant")
        if not key or key in seen:
            continue
        seen.add(key)
        lines.append(
            f"| {_flow_name(src)} | {src.get('does') or '—'} | {src.get('payoff') or '—'} |"
        )
    lines.extend([
        "",
        "### Reference flow (absolute, one row per design@clock)",
        "",
        "| Design | Clock ns | Ricetta | WNS ps | TNS ns | Area µm² | "
        "Power mW | Leak µW | IR worst | IR mean | Density % | Cong. WL/core | GRT WL | fmax MHz | setup viol |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for r in refs:
        lines.append(
            f"| {r['design']} | {_n(r.get('clock_ns'), 3)} | {_flow_name(r)} | "
            + " | ".join(_metric_cells(r))
            + " |"
        )
    lines.extend([
        "",
        "### All flows (reference + challengers, absolute values)",
        "",
        "| Design | Clock ns | Ricetta | Role | Prodotto | WNS ps | TNS ns | Area µm² | "
        "Power mW | Leak µW | IR worst | IR mean | Density % | Cong. | GRT WL | fmax | setup |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    by_slot: dict[tuple[str, float], list[dict]] = {}
    for r in rows:
        by_slot.setdefault((r["design"], float(r["clock_ns"])), []).append(r)
    for ref in refs:
        key = (ref["design"], float(ref["clock_ns"]))
        lines.append(
            f"| {ref['design']} | {_n(ref.get('clock_ns'), 3)} | {_flow_name(ref)} | "
            f"reference | — | " + " | ".join(_metric_cells(ref)) + " |"
        )
        slot = by_slot.get(key) or []
        slot = sorted(slot, key=lambda x: (0 if x["section5"] == "win" else 1, x["variant"]))
        for r in slot:
            lines.append(
                f"| {r['design']} | {_n(r.get('clock_ns'), 3)} | {_flow_name(r.get('cand') or r)} | "
                f"challenger | {r['section5']} | " + " | ".join(_metric_cells(r["cand"])) + " |"
            )
    lines.extend([
        "",
        "### Challengers vs the reference in the same slot (Δ)",
        "",
        "ΔWNS = cand − reference (ps; + better). Percent columns = "
        "100·(cand−reference)/reference (− better for area/power/leak/IR/WL).",
        "",
        "| Design | Clock | Ricetta | Prodotto | ΔWNS | Δarea % | Δpower % | Δleak % | "
        "ΔIR worst % | ΔIR mean % | ΔWL % | Δcong % | Δdens % |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for r in rows:
        b, c = r.get("base") or {}, r.get("cand") or {}
        lines.append(
            f"| {r['design']} | {_n(r.get('clock_ns'), 3)} | {_flow_name(c or r)} | {r['section5']} | "
            f"{_n(r.get('d_wns_ps'))} | {_n(r.get('d_area_pct'))} | {_n(r.get('d_power_pct'))} | "
            f"{_n(r.get('d_leak_pct'))} | {_n(r.get('d_ir_pct'))} | {_n(r.get('d_ir_mean_pct'))} | "
            f"{_n(r.get('d_wl_pct'))} | {_n(r.get('d_cong_pct'))} | {_n(r.get('d_density_pct'))} |"
        )
    lines.extend([
        "",
        "### Side-by-side sheets (reference column + each challenger)",
        "",
    ])
    metric_spec = [
        ("WNS (ps)", "wns_ps", 1, False),
        ("TNS (ns)", "tns_ns", 3, False),
        ("stdcell area (µm²)", "area_um2", 1, False),
        ("total power (mW)", "power_mw", 3, False),
        ("leakage (µW)", "leak_uw", 2, False),
        ("IR worst VDD (mV)", "ir_mv", 2, False),
        ("IR mean VDD (mV)", "ir_mean_mv", 2, False),
        ("cell density (%)", "density_pct", 1, False),
        ("congestion WL/core", "cong_wl_per_um2", 2, False),
        ("GRT wirelength", "grt_wl", 0, True),
        ("fmax (MHz)", "fmax_mhz", 1, False),
        ("setup violations", "setup_viol", 0, True),
    ]
    for ref in refs:
        key = (ref["design"], float(ref["clock_ns"]))
        slot = sorted(by_slot.get(key) or [], key=lambda x: (0 if x["section5"] == "win" else 1, x["variant"]))
        if not slot:
            continue
        chunks: list[list[dict]] = []
        for i in range(0, len(slot), 4):
            chunks.append(slot[i : i + 4])
        for ci, chunk in enumerate(chunks):
            variants = [ref.get("title") or ref["variant"]] + [
                (r.get("cand") or {}).get("title") or r["variant"] for r in chunk
            ]
            title = (
                f"#### {ref['design']} @ {_n(ref.get('clock_ns'), 3)} ns — "
                f"reference: {ref.get('title') or ref['variant']}"
            )
            if len(chunks) > 1:
                title += f" ({ci + 1}/{len(chunks)})"
            lines.append(title)
            lines.append("")
            lines.append("| Metric | " + " | ".join(f"`{v}`" for v in variants) + " |")
            lines.append("|" + "|".join("---" for _ in range(len(variants) + 1)) + "|")
            for label, mk, nd, as_int in metric_spec:
                cells = []
                for src in [ref] + [r["cand"] for r in chunk]:
                    val = src.get(mk)
                    cells.append(_ni(val) if as_int else _n(val, nd))
                lines.append("| " + label + " | " + " | ".join(cells) + " |")
            lines.append("")
    return lines


def render_qor_md(payload: dict[str, Any]) -> str:
    block = payload.get("QoR_vs_base") or {}
    lines = [
        "# QoR compare — reference flow vs challengers",
        "",
        f"Plan sha: `{payload.get('plan_sha')}`",
        f"Experiments: {payload.get('n_experiments')} ({payload.get('n_done')} done)",
        f"**Verdict:** {block.get('verdict')}",
        "",
    ]
    lines.extend(render_qor_tables(block))
    return "\n".join(lines).rstrip() + "\n"


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Next-iteration eval vs frozen I1–I5",
        "",
        f"Plan sha: `{payload['plan_sha']}`",
        f"Experiments: {payload['n_experiments']} ({payload['n_done']} done)",
        "",
        "I1–I5 bars stay frozen (historical). Product win is `dse.win_rule` (slack + area/power/IR).",
        "Readable reference+challenger sheets: `learn/dse/qor_compare.md`.",
        "",
    ]
    for key in (
        "I1_physical_knobs",
        "I2_per_design_residual",
        "I3_stop_precision",
        "I4_area_regime",
        "I5_proxy_correlation",
        "gate_diagnostics",
        "QoR_vs_base",
        "synth_method",
    ):
        block = payload[key]
        lines.append(f"## {key}")
        lines.append("")
        if key == "synth_method":
            lines.append(f"**Metodo di sintesi (nuovi challenger):** ABC `{block.get('abc')}` — {block.get('why')}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(block, indent=2))
            lines.append("```")
            lines.append("")
            continue
        lines.append(f"**Verdict:** {block.get('verdict')}")
        lines.append("")
        if key == "QoR_vs_base":
            lines.extend(render_qor_tables(block))
            lines.append("")
            continue
        lines.append("```json")
        dumped = json.dumps(block, indent=2, default=str)
        lines.append(dumped if len(dumped) < 4000 else dumped[:4000] + "\n…")
        lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jsonl", type=Path, default=DEFAULT_LOG)
    p.add_argument("--out-md", type=Path, default=OUT_MD)
    p.add_argument("--out-json", type=Path, default=OUT_JSON)
    p.add_argument("--out-qor", type=Path, default=OUT_QOR)
    p.add_argument("--out-synth", type=Path, default=OUT_SYNTH)
    args = p.parse_args(argv)
    payload = evaluate(ExperimentLog(args.jsonl))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    args.out_md.write_text(render_md(payload))
    args.out_qor.write_text(render_qor_md(payload))
    args.out_synth.write_text(json.dumps(payload["synth_method"], indent=2) + "\n")
    summary = {
        "n_experiments": payload["n_experiments"],
        "n_done": payload["n_done"],
        "plan_sha": payload["plan_sha"],
    }
    for k in (
        "I1_physical_knobs",
        "I2_per_design_residual",
        "I3_stop_precision",
        "I4_area_regime",
        "I5_proxy_correlation",
        "gate_diagnostics",
        "QoR_vs_base",
    ):
        summary[k] = payload[k].get("verdict")
    summary["synth_method"] = payload["synth_method"].get("abc")
    print(json.dumps(summary, indent=2))
    print(f"wrote {args.out_md} {args.out_json} {args.out_qor} {args.out_synth}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
