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
from eval_campaign import WIN_AREA_FRAC, WIN_WNS_EPS_PS, _beats_base  # noqa: E402

NEXT_PLAN = _LEARN / "dse" / "next_iteration_plan.md"
OUT_MD = _LEARN / "dse" / "eval_policy.md"
OUT_JSON = _LEARN / "dse" / "eval_policy.json"

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
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Next-iteration eval vs frozen I1–I5",
        "",
        f"Plan sha: `{payload['plan_sha']}`",
        f"Experiments: {payload['n_experiments']} ({payload['n_done']} done)",
        "",
        "Win criteria and I1–I5 bars are **frozen**. This script does not retune them.",
        "",
    ]
    for key in (
        "I1_physical_knobs",
        "I2_per_design_residual",
        "I3_stop_precision",
        "I4_area_regime",
        "I5_proxy_correlation",
        "gate_diagnostics",
    ):
        block = payload[key]
        lines.append(f"## {key}")
        lines.append("")
        lines.append(f"**Verdict:** {block.get('verdict')}")
        lines.append("")
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
    args = p.parse_args(argv)
    payload = evaluate(ExperimentLog(args.jsonl))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    args.out_md.write_text(render_md(payload))
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
    ):
        summary[k] = payload[k].get("verdict")
    print(json.dumps(summary, indent=2))
    print(f"wrote {args.out_md} {args.out_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
