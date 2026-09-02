"""TPE score and constraints from the product win rule. No Optuna import."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .floorplan import moves_floorplan
from .win_rule import METRIC_FRAC, SLACK_PS, _axes, verdict


@dataclass
class TuneOutcome:
    score: float
    constraints: list[float]
    verdict: str
    dw_ps: float | None = None
    notes: str = ""
    axes: dict[str, float | None] = field(default_factory=dict)

    @property
    def feasible(self) -> bool:
        return all(c <= 0.0 for c in self.constraints)


def _axis_c(imp: float | None) -> float:
    if imp is None:
        return 0.0
    return -(METRIC_FRAC * 100.0) - float(imp)


def evaluate(cand: Any, base: Any) -> TuneOutcome:
    """Minimize score. Constraints: each ≤ 0 is feasible. STOP does not invent IR."""
    status = str(getattr(cand, "status", "") or "")
    cw = getattr(cand, "finish_wns_ns", None)
    bw = getattr(base, "finish_wns_ns", None)

    if status == "stopped_by_policy" or (cw is None and status != "done"):
        extra = getattr(cand, "extra", None) or {}
        policy = extra.get("policy") or {}
        pred = policy.get("pred_finish_ns")
        c_slack = 1.0
        dw = None
        if pred is not None and bw is not None:
            dw = (float(pred) - float(bw)) * 1000.0
            c_slack = -SLACK_PS - dw
        return TuneOutcome(
            score=1.0,
            constraints=[c_slack, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            verdict="incomplete",
            dw_ps=dw,
            notes="place stop or missing finish; IR not scored",
        )

    if bw is None or cw is None:
        return TuneOutcome(
            score=1.0,
            constraints=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            verdict="incomplete",
            notes="missing WNS",
        )

    v = verdict(cand, base)
    dw_ps = (float(cw) - float(bw)) * 1000.0
    area, power, leak, ir = _axes(cand, base)
    c_slack = -SLACK_PS - dw_ps
    c_die = 1.0 if moves_floorplan(cand, base) else 0.0
    c_done = 0.0 if status in ("done", "") else 1.0
    constraints = [
        c_slack,
        _axis_c(area),
        _axis_c(power),
        _axis_c(leak),
        _axis_c(ir),
        c_die,
        c_done,
    ]
    better_vals = [x for x in (area, power, leak, ir) if x is not None]
    better = max([0.0, *better_vals]) if better_vals else 0.0
    if v == "win":
        score = -1.0 - 0.01 * better - 0.001 * max(0.0, dw_ps)
    elif v == "tie":
        score = 0.0
    else:
        score = 1.0
    return TuneOutcome(
        score=score,
        constraints=constraints,
        verdict=v,
        dw_ps=dw_ps,
        axes={"area": area, "power": power, "leak": leak, "ir": ir},
    )
