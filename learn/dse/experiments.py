"""Current-invocation experiment records.

An ``ExperimentLog`` is isolated by default. Callers that need to share a
comparison must pass one explicit path created for the same invocation; no
external registry is opened implicitly.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
LIVE_ROOT = REPO / "learn" / "sim" / "dse" / "live"
DEFAULT_PATH: Path | None = None
DEFAULT_LOG: Path | None = None
PLACE_WNS_GATE_NS = 0.0  # live funnel P2 (learn/dse/funnel.py)


def plan_sha() -> str:
    """Return the current schema fingerprint, never a campaign-plan hash."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


PLAN_SHA = plan_sha()

DESIGN_CATALOG: dict[str, dict[str, Any]] = {
    "gcd": {
        "top": "gcd",
        "clk_ns": 0.46,
        "orfs_config": "gcd-tutorial",
        "orfs_design": "gcd",
        "clk_port": "clk",
    },
    "spi": {
        "top": "spi",
        "clk_ns": 1.0,
        "orfs_config": "spi",
        "orfs_design": "spi",
        "clk_port": "clk",
    },
    "aes": {
        "top": "aes_cipher_top",
        "clk_ns": 0.82,
        "orfs_config": "aes",
        "orfs_design": "aes",
        "clk_port": "clk",
    },
    "ibex": {
        "top": "ibex_core",
        "clk_ns": 2.2,
        "orfs_config": "ibex-verilog",
        "orfs_design": "ibex",
        "clk_port": "clk_i",
        "note": "slang missing; Verilog chameleon/ibex overlay",
    },
    "dynamic_node": {
        "top": "dynamic_node_top_wrap",
        "clk_ns": 6.0,
        "orfs_config": "dynamic_node",
        "orfs_design": "dynamic_node",
        "clk_port": "clk",
        "note": "P0 keeps ORFS SWAP_ARITH_OPERATORS=1 for the current recipe",
    },
}


def validate_variant(variant: str) -> str:
    from .flow_role import validate_variant as _validate

    return _validate(variant)


@dataclass
class Experiment:
    id: str
    phase: str
    design: str
    clock_ns: float
    variant: str
    role: str
    status: str = "pending"
    netlist: str | None = None
    target: str = "finish"
    runtime_s: float = 0.0
    exit_code: int | None = None
    sha256_6_report: str | None = None
    finish_wns_ns: float | None = None
    finish_tns_ns: float | None = None
    place_wns_ns: float | None = None
    stdcell_um2: float | None = None
    stdcell_count: int | None = None
    power_w: float | None = None
    leakage_w: float | None = None
    internal_power_w: float | None = None
    switching_power_w: float | None = None
    util: float | None = None
    ir_drop_v: float | None = None
    ir_mean_v: float | None = None
    fmax_hz: float | None = None
    setup_violation_count: int | None = None
    grt_wl: float | None = None
    grt_violations: int | None = None
    cong_wl_per_um2: float | None = None
    core_um2: float | None = None
    repair_buffer: int | None = None
    die_um2: float | None = None
    errors: int | None = None
    proxy_wns_ns: float | None = None
    orfs_variant: str | None = None
    orfs_design: str | None = None
    place_promoted: bool | None = None
    notes: str = ""
    extra: dict = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Experiment":
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in d.items() if k in known}
        if kw.get("extra") is None:
            kw["extra"] = {}
        return cls(**kw)

    def finish_wns_ps(self) -> float | None:
        if self.finish_wns_ns is None:
            return None
        return float(self.finish_wns_ns) * 1000.0

    def place_wns_ps(self) -> float | None:
        if self.place_wns_ns is None:
            return None
        return float(self.place_wns_ns) * 1000.0


class ExperimentLog:
    def __init__(self, path: Path | None = None):
        selected = path or os.environ.get("PD_FLOW_EXPERIMENT_LOG")
        self.path = Path(selected) if selected else LIVE_ROOT / f"experiments-{uuid.uuid4().hex}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rows: list[Experiment] = []
        if self.path.is_file():
            for line in self.path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                self._rows.append(Experiment.from_dict(json.loads(line)))

    def __len__(self) -> int:
        return len(self._rows)

    def all(self) -> list[Experiment]:
        return list(self._rows)

    def by_phase(self, phase: str) -> list[Experiment]:
        return [e for e in self._rows if e.phase == phase]

    def by_variant(self, variant: str) -> list[Experiment]:
        return [e for e in self._rows if e.variant == variant]

    def has(self, variant: str, phase: str | None = None) -> bool:
        return any(
            e.variant == variant and (phase is None or e.phase == phase) for e in self._rows
        )

    def append(self, exp: Experiment) -> Experiment:
        validate_variant(exp.variant)
        if not exp.id:
            exp.id = uuid.uuid4().hex[:12]
        if not exp.created_at:
            exp.created_at = time.time()
        if exp.place_promoted is None and exp.place_wns_ns is not None:
            exp.place_promoted = float(exp.place_wns_ns) >= PLACE_WNS_GATE_NS - 1e-12
        self._rows.append(exp)
        with self.path.open("a") as fh:
            fh.write(json.dumps(exp.to_dict(), sort_keys=True) + "\n")
        return exp

    def rewrite(self) -> None:
        """Rewrite the JSONL from memory. Used only for schema enrichment."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w") as fh:
            for exp in self._rows:
                fh.write(json.dumps(exp.to_dict(), sort_keys=True) + "\n")
        tmp.replace(self.path)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def fill_from_logs(exp: Experiment, root: Path | None = None) -> Experiment:
    """Stamp finish/place metrics from on-disk ORFS logs. Never launches make."""
    root = Path(root or REPO)
    design = exp.orfs_design or DESIGN_CATALOG.get(exp.design, {}).get("orfs_design") or exp.design
    variant = exp.orfs_variant or exp.variant
    logs = root / "tools/OpenROAD-flow-scripts/flow/logs" / "nangate45" / design / variant
    from dse.f6_finish import parse_6_report, parse_place_dp, parse_grt

    report = logs / "6_report.json"
    place = logs / "3_5_place_dp.json"
    if report.is_file():
        blob = parse_6_report(report)
        exp.sha256_6_report = blob.get("sha256")
        exp.finish_wns_ns = _f(blob.get("wns_setup_ns"))
        exp.finish_tns_ns = _f(blob.get("tns_setup_ns"))
        exp.stdcell_um2 = _f(blob.get("stdcell_um2"))
        n = blob.get("stdcell_count")
        exp.stdcell_count = int(n) if n is not None else None
        exp.power_w = _f(blob.get("power_w"))
        exp.leakage_w = _f(blob.get("leakage_w"))
        exp.internal_power_w = _f(blob.get("internal_power_w"))
        exp.switching_power_w = _f(blob.get("switching_power_w"))
        exp.util = _f(blob.get("util"))
        exp.ir_drop_v = _f(blob.get("psm_vdd_drop_v"))
        exp.ir_mean_v = _f(blob.get("psm_vdd_mean_drop_v"))
        exp.fmax_hz = _f(blob.get("fmax_hz"))
        svc = blob.get("setup_violation_count")
        exp.setup_violation_count = int(svc) if svc is not None else None
        exp.core_um2 = _f(blob.get("core_um2"))
        rb = blob.get("repair_buffer")
        exp.repair_buffer = int(rb) if rb is not None else None
        exp.die_um2 = _f(blob.get("die_um2"))
        err = blob.get("errors")
        exp.errors = int(err) if err is not None else None
        exp.extra = dict(exp.extra or {})
        exp.extra["finish_path"] = str(report)
    grt = logs / "5_1_grt.json"
    if grt.is_file():
        gblob = parse_grt(grt)
        exp.grt_wl = _f(gblob.get("grt_wl"))
        gv = gblob.get("grt_violations")
        exp.grt_violations = int(gv) if gv is not None else None
        exp.extra = dict(exp.extra or {})
        exp.extra["grt_path"] = str(grt)
    if exp.grt_wl is not None and exp.core_um2 not in (None, 0):
        exp.cong_wl_per_um2 = float(exp.grt_wl) / float(exp.core_um2)
    if place.is_file():
        pblob = parse_place_dp(place)
        exp.place_wns_ns = _f(pblob.get("place_wns_ns"))
        exp.extra = dict(exp.extra or {})
        exp.extra["place_path"] = str(place)
    if exp.place_wns_ns is not None:
        exp.place_promoted = float(exp.place_wns_ns) >= PLACE_WNS_GATE_NS - 1e-12
    if exp.finish_wns_ns is not None and exp.errors == 0:
        exp.status = "done"
    return exp


def _f(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


def enrich_power_from_logs(log: ExperimentLog, *, root: Path | None = None) -> int:
    """Fill power/IR/GRT/fmax on existing rows from on-disk logs. No make."""
    n = 0
    for exp in log.all():
        if exp.status != "done":
            continue
        before = (exp.power_w, exp.ir_drop_v, exp.ir_mean_v, exp.grt_wl, exp.cong_wl_per_um2)
        fill_from_logs(exp, root=root)
        after = (exp.power_w, exp.ir_drop_v, exp.ir_mean_v, exp.grt_wl, exp.cong_wl_per_um2)
        if after != before:
            n += 1
    if n:
        log.rewrite()
    return n
