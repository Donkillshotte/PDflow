"""Persistent experiment / design graph. JSONL + sidecar index. Resumable."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .metrics import QoR, qor_delta


@dataclass
class Candidate:
    """One experiment node. Not a DesignState parallel type.

    Roles (do not flatten into one bag):
    * ``knobs`` — action taken at ``level``
    * ``artifacts`` — raw observation (tool JSON, SolveResult, paths)
    * ``attr`` — interpretation / attribution (hotspot, module, residual)
    * ``pred`` — surrogate prediction + uncertainty
    * ``qor`` — comparable metrics at ``fidelity``
    * ``delta`` — ``qor_delta`` vs parent; missing axes omitted
    """

    id: str
    design_id: str
    parent_id: str | None
    level: str  # architecture | logic | synthesis | physical | pdn
    knobs: dict
    knobs_fp: str
    rtl_fp: str | None
    netlist_fp: str | None
    fidelity: str
    qor: QoR
    cost_s: float
    pred: dict = field(default_factory=dict)
    attr: dict = field(default_factory=dict)
    egraph: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    delta: dict = field(default_factory=dict)
    status: str = "ok"
    failure: str | None = None
    created_at: float = 0.0
    note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["qor"] = self.qor.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        q = QoR.from_dict(d.get("qor") if isinstance(d.get("qor"), dict) else {})
        return cls(
            id=str(d["id"]),
            design_id=str(d.get("design_id") or "gcd"),
            parent_id=d.get("parent_id"),
            level=str(d.get("level") or "logic"),
            knobs=dict(d.get("knobs") or {}),
            knobs_fp=str(d.get("knobs_fp") or ""),
            rtl_fp=d.get("rtl_fp"),
            netlist_fp=d.get("netlist_fp"),
            fidelity=str(d.get("fidelity") or "F0"),
            qor=q,
            cost_s=float(d.get("cost_s") or 0.0),
            pred=dict(d.get("pred") or {}),
            attr=dict(d.get("attr") or {}),
            egraph=dict(d.get("egraph") or {}),
            artifacts=dict(d.get("artifacts") or {}),
            delta=dict(d.get("delta") or {}),
            status=str(d.get("status") or "ok"),
            failure=d.get("failure"),
            created_at=float(d.get("created_at") or 0.0),
            note=str(d.get("note") or ""),
        )


class DesignMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rows: dict[str, Candidate] = {}
        if self.path.is_file():
            for line in self.path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                c = Candidate.from_dict(json.loads(line))
                self._rows[c.id] = c

    def __len__(self) -> int:
        return len(self._rows)

    def all(self) -> list[Candidate]:
        return list(self._rows.values())

    def get(self, cid: str) -> Candidate | None:
        return self._rows.get(cid)

    def by_level(self, level: str) -> list[Candidate]:
        return [c for c in self._rows.values() if c.level == level]

    def seen_knobs(self, level: str) -> set[str]:
        return {c.knobs_fp for c in self.by_level(level)}

    def add(self, c: Candidate) -> Candidate:
        if not c.id:
            c.id = uuid.uuid4().hex[:12]
        if not c.created_at:
            c.created_at = time.time()
        if c.parent_id and not c.delta:
            parent = self._rows.get(c.parent_id)
            if parent is not None:
                c.delta = qor_delta(c.qor, parent.qor)
        self._rows[c.id] = c
        self._rewrite()
        return c

    def touch(self, c: Candidate) -> Candidate:
        self._rows[c.id] = c
        self._rewrite()
        return c

    def _rewrite(self) -> None:
        tmp = self.path.with_suffix(".jsonl.tmp")
        with tmp.open("w") as f:
            for row in self._rows.values():
                f.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
        tmp.replace(self.path)
        self._write_index()

    def _write_index(self) -> None:
        idx = {
            "n": len(self._rows),
            "path": str(self.path),
            "levels": sorted({c.level for c in self._rows.values()}),
            "ids": list(self._rows),
        }
        self.path.with_suffix(".index.json").write_text(json.dumps(idx, indent=2) + "\n")

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:12]
