"""Finish-grade contracts: scenario, geometry, semantics, per-axis evidence.

Proxy fidelities (F0–F5) are not ordered against each other as a single
ladder. Timing from ideal STA is not the same evidence as finish WNS.
Missing evidence is None — never 0, never “good enough”.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

TIMING_EVIDENCE = ("none", "ideal", "floorplan", "place", "route", "finish")
AREA_EVIDENCE = ("none", "mapped", "placed", "finish")
POWER_EVIDENCE = ("none", "estimated", "placed", "finish")
IR_EVIDENCE = ("none", "psm", "directlu")

_TIMING_RANK = {k: i for i, k in enumerate(TIMING_EVIDENCE)}
_AREA_RANK = {k: i for i, k in enumerate(AREA_EVIDENCE)}
_POWER_RANK = {k: i for i, k in enumerate(POWER_EVIDENCE)}
_IR_RANK = {k: i for i, k in enumerate(IR_EVIDENCE)}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path | str | None) -> str | None:
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return _sha256_bytes(p.read_bytes())


def hash_text(*parts: str) -> str:
    blob = "\n".join(parts).encode("utf-8")
    return _sha256_bytes(blob)


@dataclass
class ConstraintContract:
    """Clock / SDC identity. Two finishes are incomparable if this differs."""

    clk_period_ns: float
    sdc_sha256: str | None = None
    profile: str = "balanced"  # performance | balanced | low_power

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "ConstraintContract":
        d = d or {}
        return cls(
            clk_period_ns=float(d.get("clk_period_ns") or 0.46),
            sdc_sha256=d.get("sdc_sha256"),
            profile=str(d.get("profile") or "balanced"),
        )

    def compatible(self, other: "ConstraintContract") -> bool:
        if abs(self.clk_period_ns - other.clk_period_ns) > 1e-12:
            return False
        if self.sdc_sha256 and other.sdc_sha256 and self.sdc_sha256 != other.sdc_sha256:
            return False
        return True


@dataclass
class GeometryContract:
    """Physical scene identity. IR/timing across dies must not mix."""

    kind: str  # fixed | product
    die_um2: float | None = None
    core_um2: float | None = None
    rows: int | None = None
    core_utilization_knob: float | None = None
    scene_hash: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "GeometryContract":
        d = d or {}
        return cls(
            kind=str(d.get("kind") or "product"),
            die_um2=_f(d.get("die_um2")),
            core_um2=_f(d.get("core_um2")),
            rows=_i(d.get("rows")),
            core_utilization_knob=_f(d.get("core_utilization_knob")),
            scene_hash=d.get("scene_hash"),
        )

    def compatible(self, other: "GeometryContract") -> bool:
        if self.kind != other.kind:
            return False
        if self.kind == "fixed":
            if self.scene_hash and other.scene_hash:
                return self.scene_hash == other.scene_hash
            return _close(self.die_um2, other.die_um2) and _close(self.core_um2, other.core_um2)
        return True


@dataclass
class SemanticContract:
    """What “equivalent” means for this candidate."""

    kind: str = "same_latency"  # same_latency | transactional
    status: str = "unknown"  # pass | fail | unsupported | unknown
    vs: str | None = None
    latency_cycles: int | None = None
    log: str | None = None
    engine: str = "yosys_equiv"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "SemanticContract":
        d = d or {}
        return cls(
            kind=str(d.get("kind") or "same_latency"),
            status=str(d.get("status") or "unknown"),
            vs=d.get("vs"),
            latency_cycles=_i(d.get("latency_cycles")),
            log=d.get("log"),
            engine=str(d.get("engine") or "yosys_equiv"),
        )

    @property
    def ok(self) -> bool:
        return self.status == "pass"


@dataclass
class AxisEvidence:
    axis: str
    value: float | None
    source: str  # TIMING/AREA/POWER/IR token
    artifact: str | None = None
    uncertainty: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "AxisEvidence":
        d = d or {}
        return cls(
            axis=str(d.get("axis") or ""),
            value=_f(d.get("value")),
            source=str(d.get("source") or "none"),
            artifact=d.get("artifact"),
            uncertainty=_f(d.get("uncertainty")),
        )


def timing_rank(source: str) -> int:
    return int(_TIMING_RANK.get(str(source or "none"), 0))


def area_rank(source: str) -> int:
    return int(_AREA_RANK.get(str(source or "none"), 0))


def power_rank(source: str) -> int:
    return int(_POWER_RANK.get(str(source or "none"), 0))


def ir_rank(source: str) -> int:
    return int(_IR_RANK.get(str(source or "none"), 0))


def evidence_of(c: Any, axis: str) -> AxisEvidence | None:
    """Read per-axis evidence from Candidate.evidence / attr / qor fallback."""
    blob = getattr(c, "evidence", None) or {}
    if isinstance(blob, dict) and axis in blob:
        raw = blob[axis]
        if isinstance(raw, dict):
            return AxisEvidence.from_dict({"axis": axis, **raw})
    attr = getattr(c, "attr", None) or {}
    ev = attr.get("evidence") if isinstance(attr, dict) else None
    if isinstance(ev, dict) and axis in ev and isinstance(ev[axis], dict):
        return AxisEvidence.from_dict({"axis": axis, **ev[axis]})
    return None


def stamp_evidence(c: Any, axis: str, value: float | None, source: str, artifact: str | None = None) -> None:
    ev = dict(getattr(c, "evidence", None) or {})
    ev[axis] = AxisEvidence(axis=axis, value=value, source=source, artifact=artifact).to_dict()
    c.evidence = ev


def geometry_scene_hash(*, die_um2: float | None, core_um2: float | None, rows: int | None, knob: float | None) -> str:
    return hash_text(
        f"die={die_um2}",
        f"core={core_um2}",
        f"rows={rows}",
        f"knob={knob}",
    )


def _f(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


def _i(v: Any) -> int | None:
    if v is None:
        return None
    return int(v)


def _close(a: float | None, b: float | None, rel: float = 1e-4) -> bool:
    if a is None or b is None:
        return a is b
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= rel * scale


def contracts_from_candidate(c: Any) -> tuple[ConstraintContract, GeometryContract, SemanticContract]:
    kn = getattr(c, "knobs", None) or {}
    attr = getattr(c, "attr", None) or {}
    cc = ConstraintContract.from_dict(getattr(c, "constraint_contract", None) or attr.get("constraint_contract") or kn.get("constraint_contract"))
    gc = GeometryContract.from_dict(getattr(c, "geometry_contract", None) or attr.get("geometry_contract") or kn.get("geometry_contract"))
    sc = SemanticContract.from_dict(getattr(c, "semantic_contract", None) or attr.get("semantic_contract") or kn.get("semantic_contract"))
    return cc, gc, sc
