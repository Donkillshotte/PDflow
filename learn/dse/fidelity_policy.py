"""Per-design place→finish residual policy. Not a finish substitute.

Q0 calibrated residuals live in eval_policy.json. The controller asks:
which evaluation can change the decision per unit cost? This module only
answers STOP vs EVALUATE from place-DP + a per-design residual.

Candidate.delta (vs parent/baseline) is the existing field; this module
does not introduce DesignState.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Q0 calibration (P* only). Overridden when a caller passes live stats.
DEFAULT_RESIDUAL: dict[str, tuple[float, float]] = {
    "gcd": (-0.05056025, 0.023567516623135037),
    "ibex": (-0.15308242500000002, 0.1260051596869946),
    "aes": (-0.01205103, 0.040),
    "spi": (0.0235295, 0.00931047498788322),
    "dynamic_node": (-0.24974, 0.040),
}

# Frozen §5: 5 ps slack tie. STOP if predicted finish is worse than
# baseline by more than 2σ and also worse than the 5 ps tie band.
WIN_WNS_EPS_NS = 0.005


@dataclass
class PolicyDecision:
    action: str  # STOP | EVALUATE
    reason: str
    pred_finish_ns: float | None
    pred_delta_vs_base_ns: float | None
    sigma_ns: float
    residual_ns: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "pred_finish_ns": self.pred_finish_ns,
            "pred_delta_vs_base_ns": self.pred_delta_vs_base_ns,
            "sigma_ns": self.sigma_ns,
            "residual_ns": self.residual_ns,
        }


def residual_of(design: str, table: dict[str, tuple[float, float]] | None = None) -> tuple[float, float]:
    tab = table or DEFAULT_RESIDUAL
    return tab.get(design) or (-0.050, 0.040)


def decide(
    *,
    design: str,
    place_wns_ns: float | None,
    baseline_finish_ns: float | None,
    residual_table: dict[str, tuple[float, float]] | None = None,
) -> PolicyDecision:
    """STOP if the candidate is confidently worse than the same-clock base."""
    mu, sd = residual_of(design, residual_table)
    sd = max(float(sd), 1e-4)
    if place_wns_ns is None or baseline_finish_ns is None:
        return PolicyDecision("EVALUATE", "missing_place_or_baseline", None, None, sd, mu)
    pred = float(place_wns_ns) + mu
    delta = pred - float(baseline_finish_ns)
    # Confidently worse: predicted slack below base by >2σ and outside the 5 ps tie.
    if delta < -2.0 * sd and delta < -WIN_WNS_EPS_NS:
        return PolicyDecision("STOP", "confidently_worse_than_base", pred, delta, sd, mu)
    return PolicyDecision("EVALUATE", "not_confidently_worse", pred, delta, sd, mu)
