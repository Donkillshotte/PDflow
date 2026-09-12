"""Per-design place→finish policy using measurements from this invocation.

The controller may pass residual statistics collected during the active run.
Without those statistics the safe action is EVALUATE; no persisted calibration
is loaded and no prior campaign is treated as a target.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# A small tie band is a decision policy, not a measured design value.
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
    if table and design in table:
        mean, deviation = table[design]
        return float(mean), max(float(deviation), 1e-4)
    return 0.0, 0.0


def decide(
    *,
    design: str,
    place_wns_ns: float | None,
    reference_finish_ns: float | None,
    residual_table: dict[str, tuple[float, float]] | None = None,
) -> PolicyDecision:
    """STOP if the candidate is confidently worse than the same-clock base."""
    if residual_table is None or design not in residual_table:
        return PolicyDecision("EVALUATE", "no_same_invocation_residual", None, None, 0.0, 0.0)
    mu, sd = residual_of(design, residual_table)
    sd = max(float(sd), 1e-4)
    if place_wns_ns is None or reference_finish_ns is None:
        return PolicyDecision("EVALUATE", "missing_place_or_reference", None, None, sd, mu)
    pred = float(place_wns_ns) + mu
    delta = pred - float(reference_finish_ns)
    # Confidently worse: predicted slack below base by >2σ and outside the 5 ps tie.
    if delta < -2.0 * sd and delta < -WIN_WNS_EPS_NS:
        return PolicyDecision("STOP", "confidently_worse_than_base", pred, delta, sd, mu)
    return PolicyDecision("EVALUATE", "not_confidently_worse", pred, delta, sd, mu)
