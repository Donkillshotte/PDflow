"""Promotion funnel: R1 semantics → M1 mapped → P1 floorplan → P2 place → F6.

Place-DP is the main gate before finish. Ideal STA never promotes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import SemanticContract, contracts_from_candidate, evidence_of, timing_rank
from .feasibility import _flow_errors, _wns_ns, feasibility_of
from .memory import Candidate

# Place WNS below this (ns) is not auto-promoted to F6 on a performance profile.
PLACE_WNS_GATE_NS = 0.0


@dataclass
class GateResult:
    stage: str
    ok: bool
    reason: str

    def to_dict(self) -> dict:
        return {"stage": self.stage, "ok": self.ok, "reason": self.reason}


def gate_r1_semantic(c: Candidate) -> GateResult:
    _cc, _gc, sem = contracts_from_candidate(c)
    if not isinstance(sem, SemanticContract):
        sem = SemanticContract.from_dict(sem if isinstance(sem, dict) else {})
    if sem.status == "pass" or (c.attr or {}).get("equiv") == "PASS":
        return GateResult("R1", True, "equiv_pass")
    if sem.status == "fail":
        return GateResult("R1", False, "equiv_fail")
    if sem.status == "unsupported":
        return GateResult("R1", False, "equiv_unsupported")
    return GateResult("R1", False, "equiv_unknown")


def gate_m1_mapped(c: Candidate) -> GateResult:
    r1 = gate_r1_semantic(c)
    if not r1.ok:
        return GateResult("M1", False, r1.reason)
    q = c.qor
    if q is None or q.area_um2 is None:
        return GateResult("M1", False, "no_mapped_area")
    if c.status != "ok":
        return GateResult("M1", False, "mapped_fail")
    return GateResult("M1", True, "mapped_ok")


def gate_p2_place(c: Candidate, *, wns_min_ns: float = PLACE_WNS_GATE_NS) -> GateResult:
    m1 = gate_m1_mapped(c)
    if not m1.ok:
        return GateResult("P2", False, m1.reason)
    wns, src = _wns_ns(c)
    art = c.artifacts or {}
    if art.get("place_wns_ns") is not None:
        wns, src = float(art["place_wns_ns"]), "place"
    ev = evidence_of(c, "place_wns") or evidence_of(c, "wns")
    if ev is not None and ev.source in ("place", "floorplan", "route", "finish") and ev.value is not None:
        if ev.axis == "place_wns" or ev.source == "place":
            wns, src = float(ev.value), "place"
    if timing_rank(src) < timing_rank("place"):
        return GateResult("P2", False, f"timing_source_{src}_below_place")
    if wns is None:
        return GateResult("P2", False, "no_place_wns")
    if wns < wns_min_ns - 1e-12:
        return GateResult("P2", False, f"place_wns_{wns:.4f}_below_{wns_min_ns}")
    return GateResult("P2", True, "place_ready")


def gate_f6(c: Candidate) -> GateResult:
    p2 = gate_p2_place(c)
    if not p2.ok:
        return GateResult("F6", False, p2.reason)
    if _flow_errors(c) not in (0, None):
        return GateResult("F6", False, "flow_errors")
    return GateResult("F6", True, "promote_finish")


def apply_gate(c: Candidate, gate: GateResult) -> Candidate:
    hist = list(getattr(c, "promotion_history", None) or [])
    hist.append(gate.to_dict())
    c.promotion_history = hist
    if not gate.ok:
        c.rejection_reason = gate.reason
        c.finish_ready = False
    elif gate.stage == "F6":
        c.finish_ready = True
        c.rejection_reason = None
    return c


def promote_or_reject(c: Candidate, *, wns_min_ns: float = PLACE_WNS_GATE_NS) -> GateResult:
    """Run R1→P2→F6 eligibility. Does not launch tools."""
    r1 = gate_r1_semantic(c)
    if not r1.ok:
        apply_gate(c, r1)
        return r1
    m1 = gate_m1_mapped(c)
    if not m1.ok:
        apply_gate(c, m1)
        return m1
    p2 = gate_p2_place(c, wns_min_ns=wns_min_ns)
    if not p2.ok:
        apply_gate(c, p2)
        return p2
    f6 = gate_f6(c)
    apply_gate(c, f6)
    return f6
