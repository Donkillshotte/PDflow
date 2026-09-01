"""Event-driven next-action picker. Not a fixed stage tour.

Each call returns at most one action: generate / equiv / map / place /
finish / pdn / reject. Heavy actions carry an explicit cost so a wall
budget can skip them. GNN/bandit are not consulted.
"""

from __future__ import annotations

from dataclasses import dataclass

from .feasibility import feasibility_of
from .funnel import gate_f6, gate_p2_place, gate_r1_semantic, promote_or_reject
from .memory import Candidate, DesignMemory
from .place_finish_model import predict_finish_wns


@dataclass
class Action:
    kind: str
    candidate_id: str | None
    reason: str
    cost_s: float
    expected_gain: float = 0.0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "candidate_id": self.candidate_id,
            "reason": self.reason,
            "cost_s": self.cost_s,
            "expected_gain": self.expected_gain,
        }


COST = {
    "equiv": 5.0,
    "map": 8.0,
    "place": 20.0,
    "finish": 60.0,
    "pdn": 30.0,
    "generate": 2.0,
    "reject": 0.0,
    "stop": 0.0,
}


def _by_id(mem: DesignMemory, cid: str | None) -> Candidate | None:
    return mem.get(cid) if cid else None


def next_action(
    mem: DesignMemory,
    *,
    budget_s: float,
    finish_shots_left: int = 1,
    profile: str = "balanced",
) -> Action:
    """Pick the single most valuable remaining action under ``budget_s``."""
    ok = [c for c in mem.all() if c.status == "ok" and not getattr(c, "rejection_reason", None)]
    if not ok:
        return Action("generate", None, "empty_memory", COST["generate"])

    # 1. Unproven semantics
    for c in ok:
        r1 = gate_r1_semantic(c)
        if not r1.ok and r1.reason == "equiv_unknown" and budget_s >= COST["equiv"]:
            return Action("equiv", c.id, "r1_unknown", COST["equiv"], expected_gain=1.0)

    # 2. Reject proven-fail, unsupported, or place-impossible
    for c in ok:
        r1 = gate_r1_semantic(c)
        if not r1.ok and r1.reason != "equiv_unknown":
            return Action("reject", c.id, r1.reason, COST["reject"])
        p2 = gate_p2_place(c)
        if (c.artifacts or {}).get("place_wns_ns") is not None and not p2.ok:
            if not getattr(c, "rejection_reason", None):
                promote_or_reject(c)
                return Action("reject", c.id, p2.reason, COST["reject"])

    # 3. Place screen for mapped-but-unplaced
    for c in ok:
        r1 = gate_r1_semantic(c)
        if not r1.ok:
            continue
        art = c.artifacts or {}
        if art.get("place_wns_ns") is None and c.qor and c.qor.area_um2 is not None:
            if budget_s >= COST["place"] and c.level in ("architecture", "logic", "synthesis", "physical"):
                return Action("place", c.id, "need_place_gate", COST["place"], expected_gain=0.8)

    # 4. Finish only place-ready + shots left. Per-design residual may STOP
    # a candidate that is confidently worse than the best finish already in memory.
    from .fidelity_policy import decide as policy_decide

    baselines = [
        float(c.artifacts["finish_wns_ns"])
        for c in mem.all()
        if (c.artifacts or {}).get("finish_wns_ns") is not None
    ]
    base_w = max(baselines) if baselines else None

    if finish_shots_left > 0 and budget_s >= COST["finish"]:
        ranked: list[tuple[float, Candidate]] = []
        for c in ok:
            g = gate_f6(c)
            if not g.ok:
                continue
            if c.fidelity == "F6" or (c.artifacts or {}).get("finish_wns_ns") is not None:
                continue
            place = (c.artifacts or {}).get("place_wns_ns")
            dec = policy_decide(
                design=str(c.design_id),
                place_wns_ns=None if place is None else float(place),
                baseline_finish_ns=base_w,
            )
            if dec.action == "STOP":
                return Action("reject", c.id, f"policy_stop_{dec.reason}", COST["reject"])
            pred = predict_finish_wns(c)
            ranked.append((pred.p_close + 0.01 * pred.information, c))
        ranked.sort(key=lambda t: -t[0])
        if ranked:
            c = ranked[0][1]
            return Action("finish", c.id, "f6_place_ready", COST["finish"], expected_gain=ranked[0][0])

    # 5. Same-extract PDN on a finish winner (once)
    for c in ok:
        fs = feasibility_of(c, require_finish=True)
        if fs.feasible and budget_s >= COST["pdn"]:
            has_ir = (c.qor and c.qor.dynamic_ir_mv is not None) or bool((c.evidence or {}).get("dynamic_ir_mv"))
            if (c.artifacts or {}).get("pdn_done") or (c.artifacts or {}).get("pdn_skipped"):
                continue
            if not has_ir and c.fidelity == "F6":
                return Action("pdn", c.id, "same_extract_pdn", COST["pdn"], expected_gain=0.4)

    return Action("stop", None, "no_valuable_action", COST["stop"])


def apply_rejection(mem: DesignMemory, action: Action) -> Candidate | None:
    if action.kind != "reject" or not action.candidate_id:
        return None
    c = mem.get(action.candidate_id)
    if c is None:
        return None
    c.rejection_reason = action.reason
    c.finish_ready = False
    c.status = "rejected"
    mem.touch(c)
    return c
