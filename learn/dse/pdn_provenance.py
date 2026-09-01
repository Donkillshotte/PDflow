"""PDN comparisons are valid only on the same extract + geometry.

The honest GCD win (DirectLU 6.075 → decap 4.156 mV) is the template:
same n_r, same finish mesh, labeled not-gold. Catalog leftover meshes
must not dominate a finish timing point.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import contracts_from_candidate, evidence_of, ir_rank
from .memory import Candidate


@dataclass
class PdnCompare:
    ok: bool
    reason: str
    delta_mv: float | None = None

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason, "delta_mv": self.delta_mv}


def extract_id_of(c: Candidate) -> str | None:
    art = c.artifacts or {}
    kn = c.knobs or {}
    ev = evidence_of(c, "dynamic_ir_mv")
    for v in (
        art.get("extract_id"),
        kn.get("extract_id"),
        art.get("n_r") and f"n_r:{art.get('n_r')}",
        ev.artifact if ev else None,
    ):
        if v:
            return str(v)
    return None


def same_extract_delta(host: Candidate, child: Candidate) -> PdnCompare:
    _ch, gh, _ = contracts_from_candidate(host)
    _cc, gc, _ = contracts_from_candidate(child)
    if gh.kind == "fixed" or gc.kind == "fixed":
        if not gh.compatible(gc):
            return PdnCompare(False, "geometry_mismatch")
    hid, cid = extract_id_of(host), extract_id_of(child)
    if not hid or not cid or hid != cid:
        return PdnCompare(False, "extract_mismatch")
    eh, ec = evidence_of(host, "dynamic_ir_mv"), evidence_of(child, "dynamic_ir_mv")
    hv = (eh.value if eh else None) or (host.qor.dynamic_ir_mv if host.qor else None)
    cv = (ec.value if ec else None) or (child.qor.dynamic_ir_mv if child.qor else None)
    if hv is None or cv is None:
        return PdnCompare(False, "missing_ir")
    src_h = eh.source if eh else "directlu"
    src_c = ec.source if ec else "directlu"
    if ir_rank(src_h) == 0 or ir_rank(src_c) == 0:
        return PdnCompare(False, "ir_source_none")
    if src_h != src_c:
        return PdnCompare(False, "ir_oracle_mismatch")
    return PdnCompare(True, "same_extract", delta_mv=float(cv) - float(hv))
