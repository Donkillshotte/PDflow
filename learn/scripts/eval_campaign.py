#!/usr/bin/env python3
"""Evaluate a pre-registered campaign against frozen H1–H6 criteria.

Reads `learn/sim/dse/campaign_experiments.jsonl` plus on-disk ORFS
`6_report.json` / place-DP when present. Does **not** retune
`learn/dse/experiment_campaign_plan.md` §5 after seeing data.

Usage:
    PYTHONPATH=learn python3 learn/scripts/eval_campaign.py
    PYTHONPATH=learn python3 learn/scripts/eval_campaign.py --jsonl PATH
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_LEARN = Path(__file__).resolve().parents[1]
if str(_LEARN) not in sys.path:
    sys.path.insert(0, str(_LEARN))

from dse.experiments import (  # noqa: E402
    Experiment,
    ExperimentLog,
    DEFAULT_LOG,
    PLAN_PATH,
    PLAN_SHA,
    PLACE_WNS_GATE_NS,
)

OUT_MD = _LEARN / "dse" / "eval_campaign.md"
OUT_JSON = _LEARN / "dse" / "eval_campaign.json"

# Frozen §5 (copied, not retuned).
WIN_WNS_EPS_PS = 5.0
WIN_AREA_FRAC = 0.10
H2_MIN_N = 15
H2_MIN_PREC = 0.80
H2_MIN_REC = 0.80
H3_AREA_WIN = 0.25
H5_OUTLIER_FRAC = 0.30


def _wns_finish_ps(exp: Experiment) -> float | None:
    return exp.finish_wns_ps()


def _area(exp: Experiment) -> float | None:
    if exp.stdcell_um2 is None:
        return None
    return float(exp.stdcell_um2)


def _closed(exp: Experiment) -> bool:
    w = _wns_finish_ps(exp)
    return w is not None and w >= 0.0


def winner_variant(a: Experiment, b: Experiment) -> str:
    """Frozen §5: better finish WNS, or WNS within 5 ps and ≥10% smaller, or first to close."""
    wa, wb = _wns_finish_ps(a), _wns_finish_ps(b)
    if wa is None or wb is None:
        return "incomplete"
    ca, cb = _closed(a), _closed(b)
    if ca and not cb:
        return a.variant
    if cb and not ca:
        return b.variant
    if abs(wa - wb) <= WIN_WNS_EPS_PS:
        aa, ab = _area(a), _area(b)
        if aa is not None and ab is not None:
            if aa <= ab * (1.0 - WIN_AREA_FRAC):
                return a.variant
            if ab <= aa * (1.0 - WIN_AREA_FRAC):
                return b.variant
        return "tie"
    return a.variant if wa > wb else b.variant


def _beats_base(challenger: Experiment, base: Experiment) -> bool:
    w = winner_variant(challenger, base)
    return w == challenger.variant


def _clk_key(exp: Experiment) -> str:
    return f"{float(exp.clock_ns):.3f}"


def _h1(exps: list[Experiment]) -> dict[str, Any]:
    """Proxies invert true ranking if, at a fixed clock, finish winner ≠ proxy winner."""
    by_slot: dict[tuple[str, str], list[Experiment]] = defaultdict(list)
    for e in exps:
        if e.role == "ainj":
            continue
        if e.status == "done" and e.finish_wns_ns is not None:
            by_slot[(e.design, _clk_key(e))].append(e)
    out: dict[str, Any] = {"slots": {}, "supported": False, "inverted": []}
    inverted_designs: set[str] = set()
    for (design, clk), rows in sorted(by_slot.items()):
        finish_rank = sorted(rows, key=lambda r: -float(r.finish_wns_ns or -1e9))
        with_proxy = [r for r in rows if r.proxy_wns_ns is not None]
        finish_best = finish_rank[0].variant if finish_rank else None
        proxy_best = None
        inverted = None
        if len(with_proxy) >= 1 and finish_best is not None:
            proxy_rank = sorted(with_proxy, key=lambda r: -float(r.proxy_wns_ns or -1e9))
            proxy_best = proxy_rank[0].variant
            inverted = finish_best != proxy_best
            out["supported"] = True
        else:
            proxy_rank = []
        key = f"{design}@{clk}"
        out["slots"][key] = {
            "n": len(rows),
            "finish_rank": [r.variant for r in finish_rank],
            "proxy_rank": [r.variant for r in proxy_rank] if with_proxy else None,
            "finish_best": finish_best,
            "proxy_best": proxy_best,
            "inverted": inverted,
            "finish_wns_ps": {r.variant: r.finish_wns_ps() for r in finish_rank},
        }
        if inverted:
            inverted_designs.add(design)
            out["inverted"].append(key)
    out["inverted_designs"] = sorted(inverted_designs)
    if out["inverted"]:
        out["verdict"] = "H1 supported on " + ", ".join(out["inverted"])
    elif out["supported"]:
        out["verdict"] = "H1 not observed (proxy winner matches finish winner)"
    else:
        out["verdict"] = "H1 incomplete"
    return out


def _h2(exps: list[Experiment]) -> dict[str, Any]:
    """§5 precision/recall of the live P2 gate (place WNS ≥ 0 ns).

    Compared per (design, clock): a product-win is a non-base that beats the
    base at that same clock under frozen §5. Promoted = place WNS ≥ 0.
    """
    labeled = [
        e
        for e in exps
        if e.status == "done"
        and e.place_wns_ns is not None
        and e.finish_wns_ns is not None
        and e.role != "ainj"
    ]
    n = len(labeled)
    by_slot: dict[tuple[str, str], list[Experiment]] = defaultdict(list)
    for e in labeled:
        by_slot[(e.design, _clk_key(e))].append(e)

    promoted = [
        e for e in labeled if e.place_wns_ns is not None and float(e.place_wns_ns) >= PLACE_WNS_GATE_NS - 1e-12
    ]
    tp_prec = 0
    prec_den = 0
    real_wins: list[Experiment] = []
    for rows in by_slot.values():
        base = next((r for r in rows if r.role == "base"), None)
        slot_promoted = [
            r for r in rows if r.place_wns_ns is not None and float(r.place_wns_ns) >= PLACE_WNS_GATE_NS - 1e-12
        ]
        promoted_bases = [b for b in ([base] if base else []) if b in slot_promoted]
        worst = None
        if promoted_bases and promoted_bases[0].finish_wns_ns is not None:
            worst = float(promoted_bases[0].finish_wns_ns)
        for e in slot_promoted:
            if worst is None:
                continue
            prec_den += 1
            if e.role == "base" or float(e.finish_wns_ns) > worst - 1e-15:
                tp_prec += 1
        if base is None:
            continue
        for e in rows:
            if e.role == "base":
                continue
            if _beats_base(e, base):
                real_wins.append(e)
    prec = (tp_prec / prec_den) if prec_den else None
    rec_hits = sum(
        1
        for e in real_wins
        if e.place_wns_ns is not None and float(e.place_wns_ns) >= PLACE_WNS_GATE_NS - 1e-12
    )
    rec = (rec_hits / len(real_wins)) if real_wins else None

    enough = n >= H2_MIN_N
    pass_bar = (
        enough
        and prec is not None
        and rec is not None
        and prec >= H2_MIN_PREC
        and rec >= H2_MIN_REC
    )
    if pass_bar:
        verdict = "H2 pass"
    elif not enough:
        verdict = f"H2 incomplete (n={n} < {H2_MIN_N})"
    elif rec is None:
        verdict = "H2 incomplete (no product-wins vs same-clock base; recall N/A)"
    else:
        verdict = "H2 fail (n enough, bar missed)"
    return {
        "n": n,
        "n_promoted": len(promoted),
        "n_real_wins": len(real_wins),
        "precision": prec,
        "recall": rec,
        "gate_place_wns_ns": PLACE_WNS_GATE_NS,
        "min_n": H2_MIN_N,
        "bar": {"precision": H2_MIN_PREC, "recall": H2_MIN_REC},
        "enough_n": enough,
        "pass": pass_bar,
        "verdict": verdict,
    }


def _h3(exps: list[Experiment]) -> dict[str, Any]:
    gcd = [e for e in exps if e.design == "gcd" and e.status == "done" and e.finish_wns_ns is not None]
    by_clk: dict[str, list[Experiment]] = defaultdict(list)
    for e in gcd:
        by_clk[f"{float(e.clock_ns):.3f}"].append(e)
    points = []
    for clk, rows in sorted(by_clk.items()):
        closed = [r for r in rows if _closed(r)]
        if not closed:
            points.append({"sdc_ns": clk, "closed": [], "winner": None, "small_wins_area": None})
            continue
        closed.sort(key=lambda r: (_area(r) is None, _area(r) or 1e9, -float(r.finish_wns_ns or 0)))
        winner = closed[0]
        small = [r for r in closed if r.role == "dse_small"]
        small_wins = False
        if small and _area(small[0]) is not None:
            baseish = [r for r in closed if r.role in ("base", "ainj")]
            if baseish and _area(baseish[0]) is not None:
                small_wins = _area(small[0]) <= _area(baseish[0]) * (1.0 - H3_AREA_WIN)
        points.append({
            "sdc_ns": clk,
            "closed": [r.variant for r in closed],
            "winner": winner.variant,
            "winner_role": winner.role,
            "winner_area": winner.stdcell_um2,
            "small_wins_area": small_wins,
            "b_closed_a_open": bool(small) and not any(r.role in ("base", "ainj") for r in closed),
        })
    any_close = any(p["closed"] for p in points)
    h3_hit = any(p.get("small_wins_area") or p.get("b_closed_a_open") for p in points)
    if not any_close:
        verdict = "H3 incomplete (nobody timing-closed yet)"
    elif h3_hit:
        verdict = "H3 supported (B closed first or ≥25% smaller when closed)"
    else:
        verdict = "H3 not supported (A closes first; B area win <25% bar)"
    return {
        "points": points,
        "any_timing_closed": any_close,
        "h3_hit": h3_hit if any_close else None,
        "verdict": verdict,
    }


def _h4(exps: list[Experiment]) -> dict[str, Any]:
    """DSE value vs size at the design's product clock (P0 base vs DSE/abc at that clock)."""
    p0 = [e for e in exps if e.status == "done" and e.finish_wns_ns is not None and e.phase in ("P0", "P2")]
    by_design: dict[str, dict[str, Experiment]] = defaultdict(dict)
    for e in p0:
        if e.role in ("base", "abc_speed", "dse_small", "dse_fast", "dse_other"):
            by_design[e.design][e.role] = e
    rows = []
    for design, roles in by_design.items():
        base = roles.get("base")
        dses = [roles[k] for k in ("dse_small", "dse_fast", "dse_other", "abc_speed") if k in roles]
        if base is None or not dses:
            continue
        best = max(dses, key=lambda r: float(r.finish_wns_ns or -1e9))
        rows.append({
            "design": design,
            "n_instances": base.stdcell_count,
            "clock_ns": base.clock_ns,
            "base_wns_ps": base.finish_wns_ps(),
            "best_dse_variant": best.variant,
            "best_dse_wns_ps": best.finish_wns_ps(),
            "delta_wns_ps": float(best.finish_wns_ps() or 0) - float(base.finish_wns_ps() or 0),
        })
    rows.sort(key=lambda r: (r["n_instances"] is None, r["n_instances"] or 0))
    growing = None
    if len(rows) >= 3:
        deltas = [r["delta_wns_ps"] for r in rows]
        growing = all(deltas[i] <= deltas[i + 1] + 1e-9 for i in range(len(deltas) - 1))
    return {
        "rows": rows,
        "monotonic_growing_delta": growing,
        "verdict": (
            "H4 incomplete (need ≥3 designs with P0 base+DSE finish)"
            if len(rows) < 3
            else (
                "H4 supported (delta grows with size)"
                if growing
                else "H4 not supported (delta not monotonic in size)"
            )
        ),
    }


def _h5(exps: list[Experiment]) -> dict[str, Any]:
    labeled = [
        e
        for e in exps
        if e.status == "done"
        and e.place_wns_ns is not None
        and e.finish_wns_ns is not None
        and e.role != "ainj"
    ]
    residuals = []
    by_design: dict[str, list[float]] = defaultdict(list)
    for e in labeled:
        r = float(e.finish_wns_ns) - float(e.place_wns_ns)
        residuals.append({"variant": e.variant, "design": e.design, "residual_ns": r})
        by_design[e.design].append(r)
    gcd_vals = by_design.get("gcd") or []
    gcd_mean = sum(gcd_vals) / len(gcd_vals) if gcd_vals else None
    gcd_std = None
    if len(gcd_vals) >= 2:
        mu = gcd_mean or 0.0
        gcd_std = (sum((x - mu) ** 2 for x in gcd_vals) / (len(gcd_vals) - 1)) ** 0.5
    others = {d: sum(v) / len(v) for d, v in by_design.items() if d != "gcd"}
    outlier_frac = None
    if gcd_mean is not None and gcd_std is not None and gcd_std > 0:
        n_out = sum(1 for r in residuals if abs(r["residual_ns"] - gcd_mean) > 2.0 * gcd_std)
        outlier_frac = n_out / len(residuals) if residuals else None
    transfer_ok = None
    if outlier_frac is not None and others:
        transfer_ok = outlier_frac <= H5_OUTLIER_FRAC
    if gcd_mean is None or not others:
        verdict = "H5 incomplete (need gcd + ≥1 other design with place+finish)"
    elif transfer_ok:
        verdict = "H5 supported (≤30% residuals outside gcd ±2σ)"
    else:
        verdict = "H5 not supported (>30% residuals outside gcd ±2σ)"
    return {
        "n": len(residuals),
        "residuals": residuals,
        "gcd_mean_residual_ns": gcd_mean,
        "gcd_std_residual_ns": gcd_std,
        "other_means_ns": others,
        "outlier_frac": outlier_frac,
        "transfer_ok": transfer_ok,
        "verdict": verdict,
    }


def _h6(exps: list[Experiment]) -> dict[str, Any]:
    pairs = []
    by_slot: dict[tuple[str, str], dict[str, Experiment]] = defaultdict(dict)
    for e in exps:
        if e.status != "done" or e.role not in ("base", "ainj"):
            continue
        by_slot[(e.design, _clk_key(e))][e.role] = e
    all_match = True
    any_pair = False
    for (design, clk), roles in sorted(by_slot.items()):
        if "base" not in roles or "ainj" not in roles:
            continue
        any_pair = True
        b, a = roles["base"], roles["ainj"]
        sha_ok = bool(b.sha256_6_report and a.sha256_6_report and b.sha256_6_report == a.sha256_6_report)
        wns_ok = (
            b.finish_wns_ns is not None
            and a.finish_wns_ns is not None
            and abs(float(b.finish_wns_ns) - float(a.finish_wns_ns)) < 1e-5
        )
        match = bool(sha_ok and wns_ok)
        if not match:
            all_match = False
        pairs.append({
            "design": design,
            "clock_ns": clk,
            "base_variant": b.variant,
            "ainj_variant": a.variant,
            "report_sha_match": sha_ok,
            "wns_match": wns_ok,
            "match": match,
            "base_report_sha": b.sha256_6_report,
            "ainj_report_sha": a.sha256_6_report,
        })
    if not any_pair:
        verdict = "H6 incomplete (need base+ainj pair)"
        all_match_v = None
    elif all_match:
        verdict = "H6 supported (A-injected bit-identical on all pairs)"
        all_match_v = True
    else:
        verdict = "H6 FAIL — freeze campaign, do not interpret DSE"
        all_match_v = False
    return {"pairs": pairs, "all_match": all_match_v, "verdict": verdict}


def evaluate(log: ExperimentLog) -> dict[str, Any]:
    exps = log.all()
    return {
        "plan": str(PLAN_PATH),
        "plan_sha": PLAN_SHA,
        "n_experiments": len(exps),
        "n_done": sum(1 for e in exps if e.status == "done"),
        "win_criteria_frozen": {
            "wns_eps_ps": WIN_WNS_EPS_PS,
            "area_frac": WIN_AREA_FRAC,
            "place_gate_ns": PLACE_WNS_GATE_NS,
        },
        "H1_proxy_inversion": _h1(exps),
        "H2_place_dp_gate": _h2(exps),
        "H3_small_when_clock_relaxes": _h3(exps),
        "H4_dse_value_vs_size": _h4(exps),
        "H5_place_finish_residual": _h5(exps),
        "H6_oven_deterministic": _h6(exps),
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Campaign eval vs frozen H1–H6",
        "",
        f"Plan sha: `{payload['plan_sha']}`",
        f"Experiments: {payload['n_experiments']} ({payload['n_done']} done)",
        "",
        "Win criteria are **frozen**. This script does not retune them.",
        "",
    ]
    for key in (
        "H1_proxy_inversion",
        "H2_place_dp_gate",
        "H3_small_when_clock_relaxes",
        "H4_dse_value_vs_size",
        "H5_place_finish_residual",
        "H6_oven_deterministic",
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
    log = ExperimentLog(args.jsonl)
    payload = evaluate(log)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    args.out_md.write_text(render_md(payload))
    summary = {
        "n_experiments": payload["n_experiments"],
        "n_done": payload["n_done"],
        "plan_sha": payload["plan_sha"],
    }
    for k in (
        "H1_proxy_inversion",
        "H2_place_dp_gate",
        "H3_small_when_clock_relaxes",
        "H4_dse_value_vs_size",
        "H5_place_finish_residual",
        "H6_oven_deterministic",
    ):
        summary[k] = payload[k].get("verdict")
    print(json.dumps(summary, indent=2))
    print(f"wrote {args.out_md} {args.out_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
