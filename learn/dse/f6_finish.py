"""F6: parse ORFS ``6_report.json`` and stamp finish QoR onto a Candidate.

Never overwrites FLOW_VARIANT=flowlab. The heavy ``make finish`` is the
existing ``scripts/run_dse_handoff_finish.sh`` wrapper; this module is the
contract + ingest + optional launch.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .contracts import (
    AxisEvidence,
    ConstraintContract,
    GeometryContract,
    geometry_scene_hash,
    hash_file,
    stamp_evidence,
)
from .fingerprint import knobs_fp
from .memory import Candidate, DesignMemory
from .metrics import QoR, tns_cost_from_tns_ns, wns_cost_from_slack_ns

LOCKED_VARIANTS = frozenset({"flowlab", "learn"})

BASELINE_6_REPORT_SHA = "5cba9a7a882a0420cfd6f3b121dc078244f86e79893963d3726ab53fb26bd543"
BASELINE_6_ODB_SHA = "f691539f60f2f66f025108163819b827df43670a660f24362368d0ce56e62594"

_FINISH_KEYS = {
    "wns_setup_ns": "finish__timing__setup__ws",
    "tns_setup_ns": "finish__timing__setup__tns",
    "stdcell_um2": "finish__design__instance__area__stdcell",
    "stdcell_count": "finish__design__instance__count__stdcell",
    "repair_buffer": "finish__design__instance__count__class:timing_repair_buffer",
    "clock_buffer": "finish__design__instance__count__class:clock_buffer",
    "power_w": "finish__power__total",
    "leakage_w": "finish__power__leakage__total",
    "internal_power_w": "finish__power__internal__total",
    "switching_power_w": "finish__power__switching__total",
    "util": "finish__design__instance__utilization",
    "psm_vdd_drop_v": "finish__design_powergrid__drop__worst__net:VDD__corner:default",
    "psm_vdd_avg": "finish__design_powergrid__drop__average__net:VDD__corner:default",
    "psm_vdd_worst_voltage": "finish__design_powergrid__voltage__worst__net:VDD__corner:default",
    "psm_vss_avg_drop_v": "finish__design_powergrid__drop__average__net:VSS__corner:default",
    "fmax_hz": "finish__timing__fmax",
    "die_um2": "finish__design__die__area",
    "core_um2": "finish__design__core__area",
    "setup_violation_count": "finish__timing__drv__setup_violation_count",
    "errors": "finish__flow__errors__count",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def orfs_logs(variant: str, *, design: str = "gcd", platform: str = "nangate45") -> Path:
    return repo_root() / "tools/OpenROAD-flow-scripts/flow/logs" / platform / design / variant


def parse_6_report(path: Path | str) -> dict[str, Any]:
    """Last-key-wins JSON (ORFS duplicates instance count keys)."""
    raw = Path(path).read_text()
    d = json.loads(raw)
    out: dict[str, Any] = {}
    for name, key in _FINISH_KEYS.items():
        if key in d:
            out[name] = d[key]
    out["path"] = str(path)
    out["sha256"] = hash_file(path)
    # ORFS names VDD drop__average but the value is average voltage (~1.1 V).
    # Mean IR = VDD_nom − V_avg, with VDD_nom = V_worst + drop_worst.
    avg = out.get("psm_vdd_avg")
    worst_v = out.get("psm_vdd_worst_voltage")
    worst_d = out.get("psm_vdd_drop_v")
    if avg is not None and worst_v is not None and worst_d is not None:
        nom = float(worst_v) + float(worst_d)
        if float(avg) > 0.5:
            out["psm_vdd_mean_drop_v"] = nom - float(avg)
        else:
            out["psm_vdd_mean_drop_v"] = float(avg)
    return out


def parse_place_dp(path: Path | str) -> dict[str, Any]:
    d = json.loads(Path(path).read_text())
    return {
        "place_wns_ns": d.get("detailedplace__timing__setup__ws"),
        "place_tns_ns": d.get("detailedplace__timing__setup__tns"),
        "place_stdcell_um2": d.get("detailedplace__design__instance__area__stdcell"),
        "place_stdcell_count": d.get("detailedplace__design__instance__count__stdcell"),
        "path": str(path),
    }


def parse_grt(path: Path | str) -> dict[str, Any]:
    """Last-key-wins GRT JSON. Wirelength is the routing-size proxy (no overflow key)."""
    d = json.loads(Path(path).read_text())
    return {
        "grt_wl": d.get("globalroute__global_route__wirelength"),
        "grt_wl_est": d.get("globalroute__route__wirelength__estimated"),
        "grt_violations": d.get("globalroute__design__violations"),
        "path": str(path),
    }


def parse_floorplan(path: Path | str) -> dict[str, Any]:
    d = json.loads(Path(path).read_text())
    die = d.get("floorplan__design__die__area")
    core = d.get("floorplan__design__core__area")
    rows = d.get("floorplan__design__rows")
    return {
        "die_um2": die,
        "core_um2": core,
        "rows": rows,
        "fp_wns_ns": d.get("floorplan__timing__setup__ws"),
        "fp_stdcell_um2": d.get("floorplan__design__instance__area__stdcell"),
        "path": str(path),
    }


def qor_from_finish(blob: dict[str, Any]) -> QoR:
    wns = blob.get("wns_setup_ns")
    tns = blob.get("tns_setup_ns")
    n_cells = blob.get("stdcell_count")
    return QoR(
        area_um2=_f(blob.get("stdcell_um2")),
        n_cells=float(n_cells) if n_cells is not None else None,
        wns_cost=wns_cost_from_slack_ns(_f(wns)),
        tns_cost=tns_cost_from_tns_ns(_f(tns)),
        power_w=_f(blob.get("power_w")),
        leakage_w=_f(blob.get("leakage_w")),
        internal_power_w=_f(blob.get("internal_power_w")),
        switching_power_w=_f(blob.get("switching_power_w")),
        core_util=_f(blob.get("util")),
        fidelity="F6",
        note="ORFS make finish 6_report — not F5-lite",
    )


def refuse_locked_variant(variant: str) -> None:
    if variant in LOCKED_VARIANTS:
        raise ValueError(f"REFUSED: FLOW_VARIANT={variant} is locked (baseline/course)")
    if "aes" in str(variant).lower():
        raise ValueError("REFUSED: F6 handoff is GCD-only")


def assert_baseline_frozen() -> dict[str, str]:
    """Refuse to continue if someone restamped flowlab finish artifacts."""
    logs = orfs_logs("flowlab") / "6_report.json"
    odb = repo_root() / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
    got_rep = hash_file(logs)
    got_odb = hash_file(odb)
    if got_rep != BASELINE_6_REPORT_SHA:
        raise RuntimeError(f"flowlab 6_report sha drifted: {got_rep}")
    if got_odb != BASELINE_6_ODB_SHA:
        raise RuntimeError(f"flowlab 6_final.odb sha drifted: {got_odb}")
    return {"sha256_6_report": got_rep or "", "sha256_6_final_odb": got_odb or ""}


def ingest_finish(
    mem: DesignMemory,
    *,
    variant: str,
    parent: Candidate | None,
    design_id: str = "gcd",
    logs: Path | None = None,
    geometry_kind: str = "product",
    clk_period_ns: float = 0.46,
    core_utilization_knob: float = 35.0,
) -> Candidate:
    logs = logs or orfs_logs(variant)
    finish_path = logs / "6_report.json"
    if not finish_path.is_file():
        raise FileNotFoundError(finish_path)
    blob = parse_6_report(finish_path)
    place_path = logs / "3_5_place_dp.json"
    fp_path = logs / "2_1_floorplan.json"
    place = parse_place_dp(place_path) if place_path.is_file() else {}
    fp = parse_floorplan(fp_path) if fp_path.is_file() else {}
    q = qor_from_finish(blob)
    geom = GeometryContract(
        kind=geometry_kind,
        die_um2=_f(blob.get("die_um2") or fp.get("die_um2")),
        core_um2=_f(blob.get("core_um2") or fp.get("core_um2")),
        rows=_i(fp.get("rows")),
        core_utilization_knob=core_utilization_knob,
        scene_hash=geometry_scene_hash(
            die_um2=_f(blob.get("die_um2") or fp.get("die_um2")),
            core_um2=_f(blob.get("core_um2") or fp.get("core_um2")),
            rows=_i(fp.get("rows")),
            knob=core_utilization_knob if geometry_kind == "fixed" else None,
        ),
    )
    knobs = {
        "source": "f6_orfs_finish",
        "variant": variant,
        "geometry": geometry_kind,
    }
    art = {
        "finish": blob,
        "place": place,
        "floorplan": fp,
        "finish_wns_ns": blob.get("wns_setup_ns"),
        "finish_tns_ns": blob.get("tns_setup_ns"),
        "place_wns_ns": place.get("place_wns_ns"),
        "repair_buffer": blob.get("repair_buffer"),
        "clock_buffer": blob.get("clock_buffer"),
        "flow_errors": blob.get("errors") or 0,
        "6_report": str(finish_path),
        "sha256_6_report": blob.get("sha256"),
    }
    cand = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id if parent else None,
        level="signoff",
        knobs=knobs,
        knobs_fp=knobs_fp("signoff", knobs),
        rtl_fp=parent.rtl_fp if parent else None,
        netlist_fp=parent.netlist_fp if parent else None,
        fidelity="F6",
        qor=q,
        cost_s=0.0,
        artifacts=art,
        attr={"finish_ready": True, "via": "f6_ingest"},
        note=f"F6 ingest {variant} WNS={blob.get('wns_setup_ns')}",
        finish_ready=True,
        constraint_contract=ConstraintContract(clk_period_ns=clk_period_ns).to_dict(),
        geometry_contract=geom.to_dict(),
        semantic_contract=dict(parent.semantic_contract) if parent and parent.semantic_contract else {"status": "unknown"},
        schema_version=2,
    )
    stamp_evidence(cand, "wns", _f(blob.get("wns_setup_ns")), "finish", str(finish_path))
    stamp_evidence(cand, "tns", _f(blob.get("tns_setup_ns")), "finish", str(finish_path))
    stamp_evidence(cand, "area_um2", _f(blob.get("stdcell_um2")), "finish", str(finish_path))
    stamp_evidence(cand, "power_w", _f(blob.get("power_w")), "finish", str(finish_path))
    if place.get("place_wns_ns") is not None:
        stamp_evidence(cand, "place_wns", _f(place.get("place_wns_ns")), "place", str(place_path))
    mem.add(cand)
    return cand


def run_f6_handoff(
    netlist: Path | str,
    *,
    variant: str,
    target: str = "finish",
    core_utilization: float = 35.0,
    timeout_s: float = 900.0,
    die_area: str | None = None,
    core_area: str | None = None,
) -> subprocess.CompletedProcess:
    refuse_locked_variant(variant)
    script = repo_root() / "scripts/run_dse_handoff_finish.sh"
    env = os.environ.copy()
    env["FLOW_VARIANT"] = variant
    env["SYNTH_NETLIST_FILES"] = str(Path(netlist).resolve())
    if die_area and core_area:
        env["DIE_AREA"] = die_area
        env["CORE_AREA"] = core_area
        env["CORE_UTILIZATION"] = ""
    else:
        env["CORE_UTILIZATION"] = str(core_utilization)
        env.pop("DIE_AREA", None)
        env.pop("CORE_AREA", None)
    return subprocess.run(
        [str(script), target],
        env=env,
        cwd=str(repo_root()),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def evaluate_f6(
    mem: DesignMemory,
    parent: Candidate,
    *,
    variant: str,
    netlist: Path | str | None = None,
    launch: bool = False,
    geometry_kind: str = "product",
    design_id: str = "gcd",
) -> Candidate:
    """Ingest an existing finish, or launch handoff then ingest.

    Reading ``flowlab`` logs is allowed (baseline A). Launching into
    ``flowlab`` / ``learn`` is refused.
    """
    t0 = time.time()
    if launch:
        refuse_locked_variant(variant)
        nl = netlist or (parent.artifacts or {}).get("mapped_v") or parent.netlist_fp
        if not nl:
            raise FileNotFoundError("F6 launch needs a mapped netlist")
        proc = run_f6_handoff(nl, variant=variant)
        if proc.returncode != 0:
            fail = Candidate(
                id=DesignMemory.new_id(),
                design_id=design_id,
                parent_id=parent.id,
                level="signoff",
                knobs={"source": "f6_orfs_finish", "variant": variant},
                knobs_fp=knobs_fp("signoff", {"source": "f6_orfs_finish", "variant": variant}),
                rtl_fp=parent.rtl_fp,
                netlist_fp=str(nl),
                fidelity="F6",
                qor=QoR(fidelity="F6"),
                cost_s=time.time() - t0,
                status="fail",
                failure=f"handoff exit {proc.returncode}",
                artifacts={"stderr": (proc.stderr or "")[-2000:], "flow_errors": 1},
                finish_ready=False,
            )
            mem.add(fail)
            return fail
    cand = ingest_finish(
        mem,
        variant=variant,
        parent=parent,
        design_id=design_id,
        geometry_kind=geometry_kind,
    )
    cand.cost_s = time.time() - t0
    mem.touch(cand)
    return cand


def _f(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


def _i(v: Any) -> int | None:
    if v is None:
        return None
    return int(v)
