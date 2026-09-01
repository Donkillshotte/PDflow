"""Feasibility-first dominance. Proxy QoR cannot declare a finish winner.

A candidate is feasible only after equiv PASS, zero flow errors, and
closed timing (WNS ≥ 0, TNS = 0) at finish evidence. Among infeasible
points, less-negative slack ranks higher but never dominates a feasible
point. IR may only compare under compatible geometry + same extract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .contracts import (
    ConstraintContract,
    GeometryContract,
    SemanticContract,
    contracts_from_candidate,
    evidence_of,
    ir_rank,
    timing_rank,
)
from .memory import Candidate
from .metrics import QoR, dominates


@dataclass
class Feasibility:
    feasible: bool
    equiv_ok: bool
    flow_ok: bool
    timing_closed: bool
    finish_ready: bool
    reason: str
    wns_ns: float | None = None
    tns_ns: float | None = None
    timing_source: str = "none"

    def to_dict(self) -> dict:
        return {
            "feasible": self.feasible,
            "equiv_ok": self.equiv_ok,
            "flow_ok": self.flow_ok,
            "timing_closed": self.timing_closed,
            "finish_ready": self.finish_ready,
            "reason": self.reason,
            "wns_ns": self.wns_ns,
            "tns_ns": self.tns_ns,
            "timing_source": self.timing_source,
        }


def _flow_errors(c: Candidate) -> int | None:
    art = c.artifacts or {}
    for key in ("flow_errors", "errors", "finish_errors"):
        if art.get(key) is not None:
            return int(art[key])
    qnote = (c.qor.note or "") if c.qor else ""
    if c.status != "ok":
        return 1
    if "error" in qnote.lower():
        return 1
    return 0 if c.status == "ok" else None


def _wns_ns(c: Candidate) -> tuple[float | None, str]:
    ev = evidence_of(c, "wns")
    if ev is not None and ev.value is not None:
        return float(ev.value), ev.source
    art = c.artifacts or {}
    if art.get("finish_wns_ns") is not None:
        return float(art["finish_wns_ns"]), "finish"
    if art.get("place_wns_ns") is not None:
        return float(art["place_wns_ns"]), "place"
    if art.get("wns_ns") is not None:
        src = str(art.get("wns_source") or "ideal")
        return float(art["wns_ns"]), src
    if c.qor and c.qor.wns_cost is not None:
        src = "finish" if c.fidelity == "F6" else str(c.qor.fidelity or "ideal")
        if src.startswith("F"):
            src = {"F3": "ideal", "F5": "route", "F6": "finish"}.get(src, "ideal")
        return -float(c.qor.wns_cost), src
    return None, "none"


def _tns_ns(c: Candidate) -> float | None:
    ev = evidence_of(c, "tns")
    if ev is not None and ev.value is not None:
        return float(ev.value)
    art = c.artifacts or {}
    if art.get("finish_tns_ns") is not None:
        return float(art["finish_tns_ns"])
    if art.get("tns_ns") is not None:
        return float(art["tns_ns"])
    if c.qor and c.qor.tns_cost is not None:
        return -float(c.qor.tns_cost)
    return None


def feasibility_of(c: Candidate, *, require_finish: bool = True) -> Feasibility:
    _cc, _gc, sem = contracts_from_candidate(c)
    equiv_ok = sem.ok or (c.attr or {}).get("equiv") == "PASS"
    errors = _flow_errors(c)
    flow_ok = errors == 0
    wns, src = _wns_ns(c)
    tns = _tns_ns(c)
    closed = wns is not None and wns >= -1e-6 and (tns is None or tns >= -1e-6)
    finish_src = timing_rank(src) >= timing_rank("finish")
    ready = bool(getattr(c, "finish_ready", False) or (c.attr or {}).get("finish_ready"))
    if require_finish:
        timing_ok = closed and finish_src
    else:
        timing_ok = closed
    reasons: list[str] = []
    if not equiv_ok:
        reasons.append("equiv_not_pass")
    if not flow_ok:
        reasons.append("flow_errors")
    if require_finish and not finish_src:
        reasons.append("no_finish_timing")
    if not closed:
        reasons.append("timing_open")
    feasible = bool(equiv_ok and flow_ok and timing_ok)
    return Feasibility(
        feasible=feasible,
        equiv_ok=bool(equiv_ok),
        flow_ok=bool(flow_ok),
        timing_closed=bool(closed),
        finish_ready=bool(ready or finish_src),
        reason="ok" if feasible else ",".join(reasons) or "unknown",
        wns_ns=wns,
        tns_ns=tns,
        timing_source=src,
    )


def ir_comparable(a: Candidate, b: Candidate) -> bool:
    _ca, ga, _sa = contracts_from_candidate(a)
    _cb, gb, _sb = contracts_from_candidate(b)
    if not ga.compatible(gb):
        return False
    ea, eb = evidence_of(a, "dynamic_ir_mv"), evidence_of(b, "dynamic_ir_mv")
    if ea is None or eb is None:
        # Fall back: same extract id in artifacts
        xa = (a.artifacts or {}).get("extract_id") or (a.knobs or {}).get("extract_id")
        xb = (b.artifacts or {}).get("extract_id") or (b.knobs or {}).get("extract_id")
        return bool(xa) and xa == xb
    if ir_rank(ea.source) == 0 or ir_rank(eb.source) == 0:
        return False
    if ea.source != eb.source:
        return False
    art_a = ea.artifact or (a.artifacts or {}).get("extract_id")
    art_b = eb.artifact or (b.artifacts or {}).get("extract_id")
    return bool(art_a) and art_a == art_b


def constraint_dominates(a: Candidate, b: Candidate, *, require_finish: bool = True) -> bool:
    """Lexicographic feasibility, then QoR. Proxy cannot beat finish."""
    fa, fb = feasibility_of(a, require_finish=require_finish), feasibility_of(b, require_finish=require_finish)
    _cca, ga, _ = contracts_from_candidate(a)
    _ccb, gb, _ = contracts_from_candidate(b)
    if not ga.compatible(gb) and (ga.kind == "fixed" or gb.kind == "fixed"):
        return False
    if fa.equiv_ok != fb.equiv_ok:
        return fa.equiv_ok and not fb.equiv_ok
    if fa.flow_ok != fb.flow_ok:
        return fa.flow_ok and not fb.flow_ok
    if fa.feasible != fb.feasible:
        return fa.feasible and not fb.feasible
    if not fa.feasible and not fb.feasible:
        # Less-negative finish/place slack ranks, never via ideal-only if the
        # other side has stronger timing evidence.
        if timing_rank(fa.timing_source) != timing_rank(fb.timing_source):
            if timing_rank(fa.timing_source) < timing_rank(fb.timing_source):
                return False
        wa, wb = fa.wns_ns, fb.wns_ns
        if wa is None or wb is None:
            return False
        if wa > wb + 1e-12:
            return True
        if wa < wb - 1e-12:
            return False
        return False
    qa, qb = a.qor or QoR(), b.qor or QoR()
    if not ir_comparable(a, b):
        da, db = qa.to_dict(), qb.to_dict()
        da["dynamic_ir_mv"] = None
        da["static_ir_mv"] = None
        db["dynamic_ir_mv"] = None
        db["static_ir_mv"] = None
        qa, qb = QoR.from_dict(da), QoR.from_dict(db)
    return dominates(qa, qb)


def feasible_pareto(cands: Iterable[Candidate], *, require_finish: bool = True) -> list[str]:
    rows = [c for c in cands if c is not None]
    keep: list[str] = []
    for a in rows:
        if any(constraint_dominates(b, a, require_finish=require_finish) for b in rows if b.id != a.id):
            continue
        keep.append(a.id)
    return keep
