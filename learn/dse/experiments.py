"""Append-only campaign experiment registry.

Criteria in experiment_campaign_plan.md §5 are frozen. This module records
runs; it does not reinterpret wins. Locked FLOW_VARIANT names (flowlab /
learn / base) cannot be appended as writable variants — historical GCD A
is registered as camp_gcd_base with orfs_variant=flowlab.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO / "learn" / "sim" / "dse" / "campaign_experiments.jsonl"
DEFAULT_LOG = DEFAULT_PATH
PLAN_PATH = Path(__file__).resolve().parent / "experiment_campaign_plan.md"
LOCKED_VARIANTS = frozenset({"flowlab", "learn", "base"})
PLACE_WNS_GATE_NS = 0.0  # live funnel P2 (learn/dse/funnel.py)


def plan_sha() -> str:
    if not PLAN_PATH.is_file():
        return ""
    return hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()


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
        "note": "P0 keeps ORFS SWAP_ARITH_OPERATORS=1 (official recipe)",
    },
}


def refuse_locked_variant(variant: str) -> None:
    if variant in LOCKED_VARIANTS:
        raise ValueError(f"REFUSED: FLOW_VARIANT={variant} is locked")
    if "krylov" in str(variant).lower():
        raise ValueError("REFUSED: Krylov is not a campaign finish variant")


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
        self.path = Path(path or DEFAULT_PATH)
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
        refuse_locked_variant(exp.variant)
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
    from dse.f6_finish import parse_6_report, parse_place_dp

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
        rb = blob.get("repair_buffer")
        exp.repair_buffer = int(rb) if rb is not None else None
        exp.die_um2 = _f(blob.get("die_um2"))
        err = blob.get("errors")
        exp.errors = int(err) if err is not None else None
        exp.extra = dict(exp.extra or {})
        exp.extra["finish_path"] = str(report)
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
    """Fill power/leakage on existing rows from on-disk 6_report. No make."""
    n = 0
    for exp in log.all():
        if exp.status != "done":
            continue
        before = exp.power_w
        fill_from_logs(exp, root=root)
        if exp.power_w is not None and before != exp.power_w:
            n += 1
        elif exp.power_w is not None and before is None:
            n += 1
    return n


def seed_gcd_bakeoff(log: ExperimentLog | None = None, *, root: Path | None = None) -> list[str]:
    """Register already-finished GCD A/Ainj/B/C/Bfix. Does not relaunch flowlab."""
    log = log or ExperimentLog()
    root = Path(root or REPO)
    added: list[str] = []
    rows = (
        dict(
            id="gcdp0base000",
            phase="P0",
            design="gcd",
            clock_ns=0.46,
            variant="camp_gcd_base",
            role="base",
            orfs_variant="flowlab",
            orfs_design="gcd",
            notes="Historical ORFS baseline A. Artifacts stay in flowlab/. Not relaunched.",
            extra={"tag": "A", "core_utilization": 35},
        ),
        dict(
            id="gcdp0ainj000",
            phase="P0",
            design="gcd",
            clock_ns=0.46,
            variant="camp_gcd_ainj",
            role="ainj",
            orfs_variant="flowlab_dse_ainj",
            orfs_design="gcd",
            netlist=str(root / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"),
            notes="A-injected: A's 1_2_yosys.v recooked. Bit-identical to A.",
            extra={"tag": "Ainj"},
        ),
        dict(
            id="gcdp0small00",
            phase="P0",
            design="gcd",
            clock_ns=0.46,
            variant="camp_gcd_dse_small",
            role="dse_small",
            orfs_variant="flowlab_dse_small",
            orfs_design="gcd",
            netlist=str(root / "learn/sim/dse/netlists/54142494d890.v"),
            proxy_wns_ns=-0.5215,
            notes="DSE sub_twos_complement. Already finished in bake-off.",
            extra={"tag": "B", "dse_id": "54142494d890"},
        ),
        dict(
            id="gcdp0fast000",
            phase="P0",
            design="gcd",
            clock_ns=0.46,
            variant="camp_gcd_dse_fast",
            role="dse_fast",
            orfs_variant="flowlab_dse_fast",
            orfs_design="gcd",
            netlist=str(root / "learn/sim/dse/netlists/52e0ecacb19b.v"),
            proxy_wns_ns=-0.1142,
            notes="DSE orfs_abc_speed. Already finished in bake-off.",
            extra={"tag": "C", "dse_id": "52e0ecacb19b"},
        ),
        dict(
            id="gcdp0fixedb0",
            phase="P0",
            design="gcd",
            clock_ns=0.46,
            variant="camp_gcd_dse_fixedb",
            role="dse_other",
            orfs_variant="flowlab_dse_fixedb",
            orfs_design="gcd",
            netlist=str(root / "learn/sim/dse/netlists/54142494d890.v"),
            proxy_wns_ns=-0.5215,
            notes="Same B netlist on A's die. Control, not a product challenger.",
            extra={"tag": "Bfix", "dse_id": "54142494d890", "geometry": "locked_A"},
        ),
    )
    for kw in rows:
        if log.has(kw["variant"], kw["phase"]):
            continue
        exp = Experiment(**kw)
        fill_from_logs(exp, root=root)
        if exp.finish_wns_ns is None:
            exp.status = "missing_logs"
            exp.notes = (exp.notes + " ").strip() + "6_report not on disk at seed time."
        else:
            exp.status = "done"
        log.append(exp)
        added.append(exp.variant)
    return added
