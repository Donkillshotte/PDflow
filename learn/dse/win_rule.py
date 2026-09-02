"""Product win rule: slack plus area, power, leakage, and IR.

Historical P0–P7 §5 stays in eval_campaign.py. This module is the product
rule going forward (power, leakage, and IR can win or lose).
"""
from __future__ import annotations

from typing import Any

SLACK_PS = 5.0
METRIC_FRAC = 0.10  # 10%


def _imp(new: float | None, old: float | None) -> float | None:
    """Percent improvement as a reduction. +10 means 10% better (smaller)."""
    if new is None or old is None:
        return None
    old_f = float(old)
    if abs(old_f) < 1e-18:
        return None
    return (old_f - float(new)) / abs(old_f) * 100.0


def _good(imp: float | None) -> bool:
    return imp is not None and imp >= METRIC_FRAC * 100.0


def _bad(imp: float | None) -> bool:
    return imp is not None and imp <= -METRIC_FRAC * 100.0


def _axes(cand: Any, base: Any) -> tuple[float | None, float | None, float | None, float | None]:
    return (
        _imp(getattr(cand, "stdcell_um2", None), getattr(base, "stdcell_um2", None)),
        _imp(getattr(cand, "power_w", None), getattr(base, "power_w", None)),
        _imp(getattr(cand, "leakage_w", None), getattr(base, "leakage_w", None)),
        _imp(getattr(cand, "ir_drop_v", None), getattr(base, "ir_drop_v", None)),
    )


def verdict(cand: Any, base: Any) -> str:
    """Return win / tie / lose / incomplete."""
    cw = getattr(cand, "finish_wns_ns", None)
    bw = getattr(base, "finish_wns_ns", None)
    if cw is None or bw is None:
        return "incomplete"
    dw_ps = (float(cw) - float(bw)) * 1000.0
    c_closed = float(cw) >= 0.0
    b_closed = float(bw) >= 0.0
    area, power, leak, ir = _axes(cand, base)
    worse = _bad(area) or _bad(power) or _bad(leak) or _bad(ir)
    better = _good(area) or _good(power) or _good(leak) or _good(ir)
    slack_ok = dw_ps >= -SLACK_PS
    slack_win = dw_ps > SLACK_PS
    if c_closed and not b_closed and not worse:
        return "win"
    if b_closed and not c_closed:
        return "lose"
    if worse:
        return "lose"
    if slack_win or (slack_ok and better):
        return "win"
    if slack_ok:
        return "tie"
    return "lose"


def beats(cand: Any, base: Any) -> bool:
    return verdict(cand, base) == "win"
