"""Checkpoint-aware analysis eligibility for the PDflow workbench.

This module is intentionally policy-only. It does not launch tools. The local
agent uses it to explain which checks are meaningful for a selected stage,
which artifacts and native dependencies are available, and what evidence
quality the result can have before a user submits a job.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import ArtifactCatalog

STAGES = (
    "rtl",
    "synth",
    "floorplan",
    "pdn",
    "place",
    "cts",
    "route",
    "finish",
    "package",
)

_PHYSICAL_ARTIFACTS = {
    "synth": ("1_synth.odb",),
    "floorplan": ("2_floorplan.odb", "2_1_floorplan.odb", "2_4_floorplan_pdn.odb"),
    "pdn": ("2_4_floorplan_pdn.odb",),
    "place": ("3_place.odb", "3_5_place_dp.odb"),
    "cts": ("4_cts.odb",),
    "route": ("5_2_route.odb", "5_route.odb"),
    "finish": ("6_final.odb",),
}

_REPORT_FILES = {
    "gridcheck": "gridcheck_{variant}.json",
    "sta": "sta_checkpoint_{variant}_{stage}.json",
    "static_ir": "pdn_chip_ir_{variant}.json",
    "dynamic_ir": "dynamic_ir_{variant}_direct.json",
    "power_grid_em": "vyges_em_ir_{variant}.json",
    "drc": "drc_signoff_{variant}.json",
    "lvs": "lvs_signoff_{variant}.json",
    "system_pdn": "system_pdn_{variant}.json",
}

_LAB_REPORT_FILES = {
    "gridcheck": ("gridcheck_{variant}_{stage}.json",),
    "sta": ("sta_checkpoint_{variant}_{stage}.json", "lab_asap7.json"),
    "static_ir": ("lab_asap7_chip_pdn_{variant}.json", "lab_asap7_chip_pdn.json"),
    "dynamic_ir": ("lab_asap7_chip_pdn_{variant}.json", "lab_asap7_chip_pdn.json"),
    "power_grid_em": ("lab_asap7_chip_pdn_{variant}.json", "lab_asap7_chip_pdn.json"),
    "drc": ("lab_asap7_drc.json",),
    "lvs": ("lab_asap7_lvs.json",),
    "system_pdn": ("lab_asap7_system_pdn_{variant}.json", "lab_asap7_system_pdn.json"),
}

_REPORT_STATUSES = {"PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN"}
_EXECUTION_STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "CANCELLED", "FAILED", "NOT_RUN"}
_COST_ESTIMATES = {"light": 30, "medium": 120, "heavy": 600}

_KNOB_SCHEMA: dict[str, dict[str, Any]] = {
    "net": {
        "type": "enum",
        "options": ["BOTH", "VDD", "VSS"],
        "default": "BOTH",
        "unit": "rail",
    },
    "require_terminals": {"type": "boolean", "default": False},
    "corner": {"type": "enum", "options": ["BC", "TC", "WC"], "default": "TC"},
    "mode": {"type": "enum", "options": ["setup", "hold"], "default": "setup"},
    "sdc": {"type": "string", "default": "selected checkpoint SDC"},
    "rc_source": {"type": "enum", "options": ["ideal", "estimated", "spef", "routed"], "default": "estimated"},
    "path_group": {"type": "string", "default": "all"},
    "max_paths": {"type": "integer", "min": 1, "max": 1000, "default": 100},
    "voltage_domain": {"type": "string", "default": "core"},
    "activity_source": {"type": "enum", "options": ["vcd", "saif", "vectorless", "synthetic"], "default": "vectorless"},
    "peak_factor": {"type": "number", "min": 1, "max": 32, "default": 8},
    "ir_limit_pct": {
        "type": "number",
        "min": 0.01,
        "max": 100,
        "default": 5,
        "unit": "%",
        "step": 0.01,
    },
    "c_decap": {
        "type": "number",
        "min": 0,
        "max": 1e-6,
        "default": 5e-14,
        "unit": "F",
        "step": "any",
    },
    "switch_t_ns": {
        "type": "number",
        "min": 0,
        "max": 10000,
        "default": 1,
        "unit": "ns",
        "step": 0.001,
    },
    "switch_dur_ns": {
        "type": "number",
        "min": 0.001,
        "max": 1000,
        "default": 0.08,
        "unit": "ns",
        "step": 0.001,
    },
    "package_resistance": {
        "type": "number",
        "min": 0,
        "max": 1000,
        "default": 0.05,
        "unit": "Ω",
        "step": 0.001,
    },
    "package_inductance": {
        "type": "number",
        "min": 0,
        "max": 1,
        "default": 2e-10,
        "unit": "H",
        "step": "any",
    },
    "period_ns": {
        "type": "number",
        "min": 0.001,
        "max": 100000,
        "default": 0.46,
        "unit": "ns",
        "step": 0.001,
    },
    "duration_ns": {
        "type": "number",
        "min": 0.001,
        "max": 100000,
        "default": 0.08,
        "unit": "ns",
        "step": 0.001,
    },
    "timestep_ps": {
        "type": "number",
        "min": 0.001,
        "max": 100000,
        "default": 10,
        "unit": "ps",
        "step": 0.001,
    },
    "package_rlc": {"type": "string", "default": "declared package model"},
    "solver": {"type": "enum", "options": ["direct", "amg", "krylov", "ras"], "default": "direct"},
    "waveform_model": {"type": "enum", "options": ["measured", "pwl", "synthetic_triangle"], "default": "pwl"},
    "timestep": {"type": "number", "unit": "ps", "min": 0.1, "default": 10},
    "duration": {"type": "number", "unit": "ns", "min": 0.001, "default": 0.08},
    "convergence": {"type": "number", "min": 1e-12, "default": 1e-9},
    "current_mode": {"type": "enum", "options": ["average", "rms", "peak"], "default": "peak"},
    "temperature": {"type": "number", "unit": "C", "default": 25},
    "lifetime": {"type": "number", "unit": "years", "min": 0, "default": 10},
    "rule_deck": {"type": "string", "default": "not configured"},
    "layer_filter": {"type": "string", "default": "all"},
    "deck": {"type": "string", "default": "selected physical deck"},
    "scope": {"type": "enum", "options": ["checkpoint", "full"], "default": "checkpoint"},
    "runset": {"type": "string", "default": "selected LVS runset"},
    "top_cell": {"type": "string", "default": "gcd"},
    "netlist": {"type": "string", "default": "current extracted netlist"},
    "vrm": {"type": "string", "default": "declared VRM model"},
    "board_rlc": {"type": "string", "default": "declared board model"},
    "die_load": {"type": "string", "default": "current chip-load evidence"},
}

# Only these controls are sent to an adapter as runtime overrides. Other
# knobs remain visible as policy metadata but are intentionally rendered as
# derived/read-only until their native adapter contract exists.
_SUPPORTED_ANALYSIS_KNOBS: dict[str, set[str]] = {
    "gridcheck": {"net", "require_terminals"},
    "sta": {"mode", "max_paths"},
    "static_ir": {
        "package_resistance",
        "package_inductance",
        "c_decap",
        "peak_factor",
    },
    "dynamic_ir": {
        "package_resistance",
        "package_inductance",
        "c_decap",
        "peak_factor",
        "mode",
        "period_ns",
        "duration_ns",
        "timestep_ps",
    },
    "power_grid_em": {
        "peak_factor",
        "ir_limit_pct",
        "c_decap",
        "switch_t_ns",
        "switch_dur_ns",
        "package_resistance",
    },
}

# Some adapters intentionally use the same human-facing key for different
# domains. Keep the base schema compact, but publish the adapter's real option
# set to the UI so a default selected in one check can never be sent to a
# different adapter (for example STA ``setup`` versus Dynamic IR ``clock``).
_CHECK_KNOB_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "dynamic_ir": {
        "mode": {
            "type": "enum",
            "options": ["clock", "spatial", "simultaneous"],
            "default": "clock",
        },
    },
}

_INVALIDATIONS: dict[str, list[str]] = {
    "gridcheck": ["gridcheck"],
    "sta": ["sta", "timing", "signoff_all"],
    "static_ir": ["static_ir", "dynamic_ir", "power_grid_em", "signoff_all"],
    "dynamic_ir": ["dynamic_ir", "power_grid_em", "signoff_all"],
    "power_grid_em": ["power_grid_em", "signoff_all"],
    "signal_em": ["signal_em", "signoff_all"],
    "drc": ["drc", "lvs", "signoff_all"],
    "lvs": ["lvs", "signoff_all"],
    "system_pdn": ["system_pdn"],
}


CHECK_DESCRIPTORS: tuple[dict[str, Any], ...] = (
    {
        "check_id": "gridcheck",
        "display_name": "PDN grid connectivity",
        "scope": "flow",
        "eligible_stages": ["floorplan", "pdn", "place", "cts", "route", "finish"],
        "required_artifacts": ["odb"],
        "required_tools": ["openroad"],
        "action": "gridcheck",
        "default_trigger": "on-stage-success",
        "cost_class": "light",
        "quality_by_stage": {
            "floorplan": "CHECKPOINT_EVIDENCE",
            "pdn": "CHECKPOINT_EVIDENCE",
            "place": "CHECKPOINT_EVIDENCE",
            "cts": "CHECKPOINT_EVIDENCE",
            "route": "CHECKPOINT_EVIDENCE",
            "finish": "PRODUCT_INPUT",
        },
        "knobs": ["net", "require_terminals"],
        "description": "Read-only VDD/VSS connectivity check on the selected ODB.",
    },
    {
        "check_id": "sta",
        "display_name": "Static timing analysis",
        "scope": "flow",
        "eligible_stages": ["synth", "floorplan", "place", "cts", "route", "finish"],
        "required_artifacts": ["odb"],
        "required_tools": ["opensta"],
        "action": "sta_checkpoint",
        "default_trigger": "on-stage-success",
        "cost_class": "medium",
        "quality_by_stage": {
            "synth": "PROXY",
            "floorplan": "PROXY",
            "place": "PARTIAL",
            "cts": "PARTIAL",
            "route": "PARTIAL",
            "finish": "PRODUCT_INPUT",
        },
        "knobs": ["corner", "mode", "sdc", "rc_source", "path_group", "max_paths"],
        "description": "Stage-aware WNS/TNS, setup/hold, clocks and path evidence.",
    },
    {
        "check_id": "static_ir",
        "display_name": "Static IR drop",
        "scope": "flow",
        "eligible_stages": ["place", "cts", "route", "finish"],
        "required_artifacts": ["odb"],
        "required_tools": ["openroad"],
        "action": "chip_pdn_ir",
        "default_trigger": "manual",
        "cost_class": "heavy",
        "quality_by_stage": {
            "place": "PROXY",
            "cts": "PARTIAL",
            "route": "PARTIAL",
            "finish": "PRODUCT_INPUT",
        },
        "knobs": [
            "package_resistance",
            "package_inductance",
            "c_decap",
            "peak_factor",
        ],
        "description": "Spatial static drop with a stage-specific current and source model.",
    },
    {
        "check_id": "dynamic_ir",
        "display_name": "Dynamic IR drop I(t)",
        "scope": "flow",
        "eligible_stages": ["place", "cts", "route", "finish"],
        "required_artifacts": ["odb"],
        "required_tools": ["openroad", "opensta"],
        "action": "dynamic_ir",
        "default_trigger": "manual",
        "cost_class": "heavy",
        "quality_by_stage": {
            "place": "PROXY",
            "cts": "PARTIAL",
            "route": "PARTIAL",
            "finish": "PARTIAL",
        },
        "knobs": [
            "mode",
            "period_ns",
            "duration_ns",
            "timestep_ps",
            "package_resistance",
            "package_inductance",
            "c_decap",
            "peak_factor",
        ],
        "description": "Time-domain voltage droop with activity, waveform and solver provenance.",
    },
    {
        "check_id": "power_grid_em",
        "display_name": "Power-grid EM",
        "scope": "flow",
        "eligible_stages": ["route", "finish"],
        "required_artifacts": ["odb"],
        "required_tools": ["openroad", "vyges_em_ir"],
        "action": "power_grid_em",
        "default_trigger": "manual",
        "cost_class": "heavy",
        "quality_by_stage": {
            "route": "PROXY",
            "finish": "PROXY",
        },
        "knobs": [
            "peak_factor",
            "ir_limit_pct",
            "c_decap",
            "switch_t_ns",
            "switch_dur_ns",
            "package_resistance",
        ],
        "warnings": [
            "No qualified foundry current-density limit is configured; no EM PASS is possible.",
            "The open vyges-em-ir adapter reports IR evidence and EM coverage, but it is not a foundry signoff engine.",
        ],
        "description": "Power-grid current density and relative lifetime analysis.",
    },
    {
        "check_id": "signal_em",
        "display_name": "Signal EM",
        "scope": "flow",
        "eligible_stages": ["route", "finish"],
        "required_artifacts": ["odb"],
        "required_tools": [],
        "required_capabilities": ["signal_current_model", "signal_em_engine", "signal_em_limits"],
        "action": None,
        "default_trigger": "manual",
        "cost_class": "heavy",
        "quality_by_stage": {"route": "GAP", "finish": "GAP"},
        "knobs": ["current_mode", "temperature", "rule_deck", "layer_filter"],
        "description": "Dedicated signal/clock EM; route DRC and power EM are not substitutes.",
    },
    {
        "check_id": "drc",
        "display_name": "Physical DRC",
        "scope": "flow",
        "eligible_stages": ["floorplan", "place", "route", "finish"],
        "required_artifacts": ["odb"],
        "required_tools": ["openroad", "klayout"],
        "action": None,
        "default_trigger": "on-stage-success",
        "cost_class": "medium",
        "quality_by_stage": {
            "floorplan": "CHECKPOINT_EVIDENCE",
            "place": "CHECKPOINT_EVIDENCE",
            "route": "PARTIAL",
            "finish": "PRODUCT_INPUT",
        },
        "knobs": ["deck", "scope"],
        "description": "Stage-local geometry checks and final GDS DRC when the deck is available.",
    },
    {
        "check_id": "lvs",
        "display_name": "Layout versus schematic",
        "scope": "flow",
        "eligible_stages": ["finish"],
        "required_artifacts": ["gds", "verilog"],
        "required_tools": ["klayout"],
        "action": "klayout_lvs",
        "default_trigger": "manual",
        "cost_class": "heavy",
        "quality_by_stage": {"finish": "PRODUCT_INPUT"},
        "knobs": ["runset", "top_cell", "netlist"],
        "description": "Final GDS/netlist equivalence; requires a current extracted comparison.",
    },
    {
        "check_id": "system_pdn",
        "display_name": "Package System PDN",
        "scope": "package",
        "eligible_stages": ["package"],
        "required_artifacts": [],
        "required_tool_any": [["ngspice", "xyce"]],
        "action": "system_pdn",
        "default_trigger": "manual",
        "cost_class": "heavy",
        "quality_by_stage": {"package": "PACKAGE_EVIDENCE"},
        "knobs": ["vrm", "board_rlc", "package_rlc", "die_load", "timestep", "duration"],
        "description": "VRM-to-board-to-package-to-die simulation, separate from chip PDN signoff.",
    },
)


def _descriptor(check_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in CHECK_DESCRIPTORS if item["check_id"] == check_id),
        None,
    )


def _tool_map(tools: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("tool_id")): item
        for item in (tools or [])
        if isinstance(item, dict) and item.get("tool_id")
    }


def _candidate_artifacts(
    catalog: ArtifactCatalog,
    variant: str,
    run_id: str | None,
) -> list[Any]:
    if run_id:
        return catalog.list(limit=2000, run_id=run_id)
    return catalog.list(limit=2000, variant=variant)


def _find_artifact(
    artifacts: list[Any],
    names: tuple[str, ...],
    *,
    required_authority: str | None = None,
) -> Any | None:
    candidates = [
        item
        for item in artifacts
        if Path(item.relative_path).name in names
        and (required_authority is None or item.authority == required_authority)
    ]
    candidates.sort(
        key=lambda item: (
            0 if item.authority == "candidate" else 1,
            names.index(Path(item.relative_path).name),
            -int(item.mtime_ns),
        )
    )
    return candidates[0] if candidates else None


def _report_candidates(
    repo_root: Path,
    check_id: str,
    variant: str,
    stage: str,
    run_id: str | None = None,
    candidate_scope: bool | None = None,
) -> list[Path]:
    reports = repo_root / "learn" / "sim" / "reports"
    roots = [reports]
    if candidate_scope is None:
        candidate_scope = bool(run_id)
    if run_id and variant == "flowlab" and candidate_scope:
        # Candidate analysis reports are isolated beside the candidate ORFS
        # workspace. Prefer them over repository-level legacy evidence so a
        # run can never accidentally display a report from another run.
        roots = [
            repo_root
            / ".pdflow"
            / "runs"
            / run_id
            / "candidate"
            / "orfs"
            / "reports"
            / "nangate45"
            / "gcd"
            / "flowlab",
        ]
    elif run_id and variant == "flowlab":
        # A non-candidate analysis run may keep its generated report beside
        # the run while still reading the protected finish checkpoint. Prefer
        # that scoped report, then fall back to the live repository report.
        roots = [repo_root / ".pdflow" / "runs" / run_id / "reports", reports]
    if check_id == "power_grid_em" and not variant.startswith("lab_asap7_"):
        filename = (
            f"vyges_em_ir_{variant}.json"
            if stage == "finish"
            else f"vyges_em_ir_{variant}_{stage}.json"
        )
        return [root / filename for root in roots]
    if check_id == "static_ir" and not variant.startswith("lab_asap7_"):
        filename = (
            f"pdn_chip_ir_{variant}.json"
            if stage == "finish"
            else f"pdn_chip_ir_{variant}_{stage}.json"
        )
        return [root / filename for root in roots]
    if check_id == "dynamic_ir" and not variant.startswith("lab_asap7_"):
        filename = (
            f"dynamic_ir_{variant}_direct.json"
            if stage == "finish"
            else f"dynamic_ir_{variant}_{stage}_direct.json"
        )
        return [root / filename for root in roots]
    if variant.startswith("lab_asap7_"):
        return [
            reports / filename.format(variant=variant, stage=stage)
            for filename in _LAB_REPORT_FILES.get(check_id, ())
        ]
    filename = _REPORT_FILES.get(check_id)
    if check_id == "gridcheck":
        filename = "gridcheck_{variant}_{stage}.json"
    candidates = [
        root / filename.format(variant=variant, stage=stage)
        for root in roots
    ] if filename else []
    if check_id == "sta":
        candidates.extend(
            root / f"sta_checkpoint_{variant}_{stage}_hold.json" for root in roots
        )
    if check_id == "sta" and stage == "finish":
        candidates.extend(root / f"sta_signoff_{variant}.json" for root in roots)
    return candidates


def _load_requirement_profile(repo_root: Path, variant: str) -> dict[str, Any]:
    profile = "asap7/gcd" if variant.startswith("lab_asap7_") else "nangate45/gcd"
    try:
        raw = json.loads(
            (repo_root / "config" / "pdflow" / "requirements.json").read_text(
                encoding="utf-8"
            )
        )
        selected = raw.get("profiles", {}).get(profile, {})
        return selected if isinstance(selected, dict) else {}
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}


def _semantic_report_status(
    repo_root: Path,
    check_id: str,
    value: dict[str, Any],
    variant: str,
) -> str:
    """Normalize legacy reports without trusting a bare ``ok`` field.

    Older reports in the repository predate versioned requirements and mark
    parseable measurements as ``ok`` even when timing is open. The workbench
    must show the semantic result of the current policy while retaining those
    reports as evidence. Lab reports are never Product PASS, even when their
    native cook exits successfully.
    """

    raw = str(value.get("status") or "").upper()
    if raw in _REPORT_STATUSES:
        status = raw
    else:
        evaluation = value.get("evaluation")
        evaluation_status = (
            str(evaluation.get("status") or "").upper()
            if isinstance(evaluation, dict)
            else ""
        )
        if evaluation_status in _REPORT_STATUSES:
            status = evaluation_status
        elif check_id == "sta":
            timing = value.get("timing")
            if not isinstance(timing, dict):
                qor = value.get("qor")
                qor = qor if isinstance(qor, dict) else {}
                timing = {
                    "wns_ns": (
                        float(qor["wns_ps"]) / 1000.0
                        if qor.get("wns_ps") is not None
                        else None
                    ),
                    "tns": qor.get("tns_ps"),
                    "setup_violations": qor.get("setup_violations"),
                }
            required = ("wns_ns", "tns", "setup_violations")
            if all(key in timing and timing.get(key) is not None for key in required):
                try:
                    policy = _load_requirement_profile(repo_root, variant)
                    timing_policy = policy.get("timing") if isinstance(policy, dict) else {}
                    wns_min = float(timing_policy.get("wns_ns_min", 0.0))
                    tns_min = float(timing_policy.get("tns_min", 0.0))
                    setup_max = float(timing_policy.get("setup_violations_max", 0.0))
                    status = (
                        "PASS"
                        if float(timing["wns_ns"]) >= wns_min
                        and float(timing["tns"]) >= tns_min
                        and float(timing["setup_violations"]) <= setup_max
                        else "FAIL"
                    )
                except (TypeError, ValueError):
                    status = "GAP"
            else:
                status = "GAP"
        elif check_id == "drc":
            geometry = value.get("geometry")
            geometry = geometry if isinstance(geometry, dict) else {}
            values = [
                geometry.get("route_drc_violations", geometry.get("route_drc_lines")),
                geometry.get("gds_drc_violations"),
            ]
            if any(item is None for item in values):
                status = "GAP"
            else:
                try:
                    status = "PASS" if all(float(item) <= 0 for item in values) else "FAIL"
                except (TypeError, ValueError):
                    status = "GAP"
        elif check_id == "lvs":
            equivalence = value.get("equivalence")
            lvs_pass = equivalence.get("lvs_pass") if isinstance(equivalence, dict) else None
            status = "PASS" if isinstance(lvs_pass, bool) and lvs_pass else "FAIL" if isinstance(lvs_pass, bool) else "GAP"
        elif check_id in {"static_ir", "dynamic_ir", "power_grid_em", "system_pdn"}:
            # Measurements are useful, but no declared limits means they
            # cannot close Product signoff. Dynamic IR is also explicitly
            # partial in the current model (activity/model limits).
            status = "GAP"
        else:
            status = "PASS" if value.get("ok") is True else "FAIL" if value.get("ok") is False else "NOT_RUN"

    if variant.startswith("lab_asap7_") and status == "PASS":
        return "PROXY"
    if raw == "RAN" and value.get("ok") is True:
        return "PROXY"
    if value.get("product_win") is False and status == "PASS":
        return "PROXY"
    return status


def _report_metrics(check_id: str, value: dict[str, Any]) -> dict[str, Any]:
    """Expose stable, display-ready values without copying an entire report."""

    if check_id == "sta":
        timing = value.get("timing")
        if not isinstance(timing, dict):
            qor = value.get("qor") if isinstance(value.get("qor"), dict) else {}
            timing = {
                "wns_ns": (
                    float(qor["wns_ps"]) / 1000.0
                    if qor.get("wns_ps") is not None
                    else None
                ),
                "tns": qor.get("tns_ps"),
                "setup_violations": qor.get("setup_violations"),
                "period_min_ns": (
                    float(qor["period_min_ps"]) / 1000.0
                    if qor.get("period_min_ps") is not None
                    else None
                ),
            }
        return {
            key: timing.get(key)
            for key in ("wns_ns", "tns", "setup_violations", "period_min_ns", "worst_endpoint")
            if timing.get(key) is not None
        }
    if check_id == "drc":
        geometry = value.get("geometry") if isinstance(value.get("geometry"), dict) else {}
        return {
            key: geometry.get(key)
            for key in ("route_drc_violations", "route_drc_lines", "gds_drc_violations")
            if geometry.get(key) is not None
        }
    if check_id == "lvs":
        equivalence = value.get("equivalence") if isinstance(value.get("equivalence"), dict) else {}
        return {
            key: equivalence.get(key)
            for key in ("lvs_pass", "lvs_errors", "make_rc")
            if equivalence.get(key) is not None
        }
    if check_id == "static_ir":
        static = value.get("static") if isinstance(value.get("static"), dict) else {}
        transient = value.get("transient") if isinstance(value.get("transient"), dict) else {}
        return {
            "static_ir_v": static.get("worst_ir"),
            "transient_droop_v": transient.get("worst_droop"),
            "static_ir_mv": value.get("mesh_static_mv"),
            "transient_droop_mv": value.get("mesh_transient_droop_mv"),
        }
    if check_id in {"dynamic_ir", "power_grid_em"}:
        dynamic = value.get("dynamic") if isinstance(value.get("dynamic"), dict) else {}
        if check_id == "power_grid_em" and not dynamic:
            vyges = value.get("vyges") if isinstance(value.get("vyges"), dict) else {}
            dynamic = vyges.get("dynamic") if isinstance(vyges.get("dynamic"), dict) else {}
            worst_ir = vyges.get("worst_ir") if isinstance(vyges.get("worst_ir"), dict) else {}
        else:
            worst_ir = {}
        metrics = {
            "worst_droop_v": dynamic.get("worst_droop") or dynamic.get("drop"),
            "worst_droop_mv": value.get("mesh_transient_droop_mv"),
            "peak_current_a": dynamic.get("peak_current"),
        }
        if check_id == "power_grid_em":
            metrics.update(
                {
                    "static_ir_v": worst_ir.get("drop") or value.get("static_ir_v"),
                    "static_ir_pct": worst_ir.get("drop_pct") or value.get("static_ir_pct"),
                    "dynamic_droop_pct": dynamic.get("drop_pct"),
                    "em_checked": (value.get("requirements") or {}).get("power_grid_em", {}).get("em_checked")
                    if isinstance(value.get("requirements"), dict)
                    and isinstance((value.get("requirements") or {}).get("power_grid_em"), dict)
                    else value.get("em_checked"),
                }
            )
        return {key: item for key, item in metrics.items() if item is not None}
    if check_id == "system_pdn":
        transient = value.get("transient") if isinstance(value.get("transient"), dict) else {}
        impedance = value.get("impedance") if isinstance(value.get("impedance"), dict) else {}
        return {
            "droop_mv": transient.get("droop_mv"),
            "z_max_mohm": impedance.get("z_max_mohm"),
            "engine": value.get("engine"),
        }
    if check_id == "gridcheck":
        nets = value.get("nets") if isinstance(value.get("nets"), dict) else {}
        return {
            "vdd_connected": (nets.get("VDD") or {}).get("connected")
            if isinstance(nets.get("VDD"), dict)
            else None,
            "vss_connected": (nets.get("VSS") or {}).get("connected")
            if isinstance(nets.get("VSS"), dict)
            else None,
        }
    return {}


def _report_mentions_artifact(value: dict[str, Any], artifact: Any) -> bool:
    """Check explicit provenance, never infer a match from report mtime."""

    needles = {
        str(getattr(artifact, "relative_path", "")),
        Path(str(getattr(artifact, "relative_path", ""))).name,
        str(getattr(artifact, "content_hash", "") or ""),
    }
    needles.discard("")

    def walk(item: Any) -> bool:
        if isinstance(item, dict):
            return any(walk(key) or walk(child) for key, child in item.items())
        if isinstance(item, list):
            return any(walk(child) for child in item)
        return isinstance(item, str) and any(needle in item for needle in needles)

    # Only provenance-bearing fields may establish comparability. Searching
    # the entire report would let a log message or a copied path masquerade as
    # a verified input reference.
    for key in ("input_artifacts", "input_artifact_refs", "checkpoint_artifact", "artifact"):
        if key in value and walk(value[key]):
            return True
    return False


def _report_status(
    repo_root: Path,
    check_id: str,
    variant: str,
    stage: str,
    artifact: Any | None,
    run_id: str | None = None,
    candidate_scope: bool | None = None,
) -> tuple[str, bool, str | None, dict[str, Any], str | None]:
    candidates = _report_candidates(
        repo_root,
        check_id,
        variant,
        stage,
        run_id,
        candidate_scope,
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return "NOT_RUN", False, None, {}, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "GAP", True, "report exists but is unreadable", {}, str(path.relative_to(repo_root))
    if not isinstance(value, dict):
        return "GAP", True, "report is not a JSON object", {}, str(path.relative_to(repo_root))
    if variant.startswith("lab_asap7_"):
        report_variant = value.get("variant")
        if report_variant and str(report_variant) != variant:
            return "NOT_RUN", True, "report belongs to a different ASAP7 profile", {}, str(path.relative_to(repo_root))
    if artifact is not None:
        try:
            if path.stat().st_mtime_ns < int(artifact.mtime_ns):
                return "NOT_RUN", True, "report is older than the selected checkpoint", value, str(path.relative_to(repo_root))
        except OSError:
            return "NOT_RUN", True, "report timestamp is unavailable", value, str(path.relative_to(repo_root))
        if not _report_mentions_artifact(value, artifact):
            return (
                "GAP",
                True,
                "report lacks a verified input hash/path for the selected checkpoint",
                value,
                str(path.relative_to(repo_root)),
            )
    status = _semantic_report_status(repo_root, check_id, value, variant)
    reason = str(value.get("reason") or value.get("summary") or "") or None
    return status, False, reason, value, str(path.relative_to(repo_root))


def _status_dimensions(
    value: dict[str, Any],
    *,
    status: str,
    stale: bool,
    report_file: str | None,
    quality: str | None,
) -> dict[str, str]:
    """Keep execution, evidence, requirement and signoff semantics separate."""

    execution = str(value.get("execution_status") or "").upper()
    if execution not in _EXECUTION_STATUSES:
        if not report_file:
            execution = "NOT_RUN"
        elif value.get("termination_cause") in {"cancelled", "timeout", "memory", "resource_isolation", "crash"}:
            execution = "CANCELLED" if value.get("termination_cause") == "cancelled" else "FAILED"
        else:
            execution = "COMPLETED"

    evidence = str(value.get("evidence_status") or "").upper()
    if evidence not in _REPORT_STATUSES:
        evidence = "GAP" if stale or status == "GAP" else "PASS" if report_file else "NOT_RUN"

    requirement = str(value.get("requirement_status") or "").upper()
    if requirement not in _REPORT_STATUSES:
        if status in {"PASS", "FAIL", "WARN"}:
            requirement = status
        elif status in {"PROXY", "PARTIAL", "GAP", "NOT_RUN"}:
            requirement = status
        else:
            requirement = "NOT_RUN"

    signoff = str(value.get("signoff_status") or "").upper()
    if signoff not in _REPORT_STATUSES:
        signoff = (
            "PASS"
            if status == "PASS" and not stale and quality == "PRODUCT_INPUT"
            else "NOT_RUN"
            if not report_file
            else "NOT_RUN"
            if status == "PASS" and quality != "PRODUCT_INPUT"
            else status
        )
    return {
        "execution_status": execution,
        "evidence_status": evidence,
        "requirement_status": requirement,
        "signoff_status": signoff,
    }


def evaluate_check(
    repo_root: Path,
    catalog: ArtifactCatalog,
    *,
    check_id: str,
    stage: str,
    variant: str,
    run_id: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    candidate_scope: bool | None = None,
    artifacts: list[Any] | None = None,
) -> dict[str, Any]:
    descriptor = _descriptor(check_id)
    if descriptor is None:
        raise ValueError(f"unknown analysis check: {check_id}")
    if stage not in STAGES:
        raise ValueError(f"unknown checkpoint stage: {stage}")

    available_tools = _tool_map(tools)
    if candidate_scope is None:
        candidate_scope = bool(run_id)
    artifact_run_id = run_id if candidate_scope else None
    # ``check_policy`` supplies one snapshot for the complete policy. Keep the
    # fallback for direct callers and older integrations, but never rescan the
    # repository once a policy evaluation has already established its scope.
    scoped_artifacts = (
        artifacts
        if artifacts is not None
        else _candidate_artifacts(catalog, variant, artifact_run_id)
    )
    names = _PHYSICAL_ARTIFACTS.get(stage, ())
    artifact = _find_artifact(
        scoped_artifacts,
        names,
        required_authority="candidate" if candidate_scope else "finish",
    )
    missing: list[str] = []
    incompatible: list[str] = []
    warnings = list(descriptor.get("warnings") or [])
    stage_allowed = stage in descriptor["eligible_stages"]
    if not stage_allowed:
        missing.append(f"check is not defined for the {stage} checkpoint")

    if descriptor.get("required_artifacts") and artifact is None:
        missing.append("required physical checkpoint artifact is missing")

    missing_tools = [
        tool_id
        for tool_id in descriptor.get("required_tools", [])
        if available_tools.get(tool_id, {}).get("availability") != "READY"
    ]
    missing_any: list[list[str]] = []
    for group in descriptor.get("required_tool_any", []):
        if not any(available_tools.get(tool_id, {}).get("availability") == "READY" for tool_id in group):
            missing_any.append(list(group))
    for group in missing_any:
        missing.append("one of the native tools is required: " + " or ".join(group))

    missing_capabilities = list(descriptor.get("required_capabilities") or [])
    if missing_capabilities:
        missing.extend(
            "capability is not installed or configured: " + capability
            for capability in missing_capabilities
        )

    if missing_tools:
        missing.extend("native tool is unavailable: " + tool_id for tool_id in missing_tools)

    eligible = not missing
    quality = (
        descriptor.get("quality_by_stage", {}).get(stage)
        if eligible
        else "GAP"
    )
    if variant.startswith("lab_asap7_") and quality in {
        "PRODUCT_INPUT",
        "PACKAGE_EVIDENCE",
        "CHECKPOINT_EVIDENCE",
    }:
        # ASAP7 results are intentionally isolated from Product signoff. They
        # can be excellent experimental evidence, but they are not a Product
        # oracle until a matching certified policy says otherwise.
        quality = "PROXY"
    status, stale, report_reason, report_value, report_file = _report_status(
        repo_root,
        check_id,
        variant,
        stage,
        artifact,
        run_id,
        candidate_scope,
    )
    if not eligible:
        status = "GAP"
    elif stale:
        warnings.append(report_reason or "existing evidence is stale")
    elif report_reason:
        warnings.append(report_reason)

    if check_id == "power_grid_em":
        warnings.extend(
            [
                "No qualified foundry current-density limit is configured; the result remains PROXY.",
                "Relative TTF or inferred geometry is not a foundry EM signoff.",
            ]
        )
    if check_id == "dynamic_ir":
        warnings.extend(
            [
                "Evidence class is stage-dependent; final dynamic IR remains PARTIAL when activity/model limits are incomplete.",
            ]
        )

    # ASAP7 is a laboratory surface with its own native adapters. Never offer
    # a Nangate45/Product action (for example gridcheck, STA or KLayout LVS)
    # merely because the same check id exists in the generic policy.
    action = descriptor.get("action")
    if check_id == "drc" and stage == "finish" and not variant.startswith("lab_asap7_"):
        # Final DRC has a real native bundle; earlier checkpoints expose the
        # stage report as evidence-only until a checkpoint-specific deck
        # adapter is available.
        action = "drc_signoff"
    if variant.startswith("lab_asap7_"):
        if check_id in {"gridcheck", "sta"}:
            action = check_id if check_id == "gridcheck" else "sta_checkpoint"
        elif check_id == "system_pdn":
            action = "lab_asap7_pkg"
        elif check_id in {"static_ir", "dynamic_ir"} and stage == "finish":
            action = "lab_asap7_chip_pdn"
        else:
            action = None

    dimensions = _status_dimensions(
        report_value,
        status=status,
        stale=stale,
        report_file=report_file,
        quality=quality,
    )
    execution_class = (
        "UNAVAILABLE"
        if not eligible
        else "NATIVE_JOB"
        if action
        else "EVIDENCE_ONLY"
    )
    estimated_duration = _COST_ESTIMATES.get(str(descriptor.get("cost_class")), 120)

    return {
        "schema_version": 1,
        "check_id": check_id,
        "display_name": descriptor["display_name"],
        "description": descriptor["description"],
        "scope": descriptor["scope"],
        "stage": stage,
        "variant": variant,
        "run_id": run_id,
        "eligible": eligible,
        "status": status,
        "stale": stale,
        "evidence_class": quality,
        "execution_class": execution_class,
        "expected_evidence_class": quality,
        **dimensions,
        "action": action,
        "default_trigger": descriptor.get("default_trigger"),
        "cost_class": descriptor.get("cost_class"),
        "required_tools": list(descriptor.get("required_tools") or []),
        "missing_tools": missing_tools,
        "required_artifacts": list(descriptor.get("required_artifacts") or []),
        "artifact": artifact.to_dict() if artifact is not None else None,
        "missing": missing,
        "incompatible": incompatible,
        "missing_inputs": list(missing),
        "stale_inputs": [report_file] if stale and report_file else [],
        "blocking_reasons": [*missing, *incompatible],
        "warnings": warnings,
        "knobs": list(descriptor.get("knobs") or []),
        "knob_schema": {
            knob: {
                **dict(
                    _CHECK_KNOB_OVERRIDES.get(check_id, {}).get(
                        knob, _KNOB_SCHEMA.get(knob, {"type": "string"})
                    )
                ),
                "supported": knob
                in _SUPPORTED_ANALYSIS_KNOBS.get(check_id, set()),
            }
            for knob in descriptor.get("knobs") or []
        },
        "required_capabilities": list(descriptor.get("required_capabilities") or []),
        "estimated_duration_seconds": estimated_duration,
        "resource_limit": {
            "queue": "heavy" if descriptor.get("cost_class") == "heavy" else "standard",
            "timeout_seconds": 600,
        },
        "downstream_invalidations": list(_INVALIDATIONS.get(check_id, [])),
        "report_reason": report_reason,
        "report_file": report_file,
        "metrics": _report_metrics(check_id, report_value),
    }


def check_policy(
    repo_root: Path,
    catalog: ArtifactCatalog,
    *,
    stage: str,
    variant: str,
    run_id: str | None = None,
    check_id: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    candidate_scope: bool | None = None,
    artifacts: list[Any] | None = None,
) -> dict[str, Any]:
    descriptors = (
        [check_id]
        if check_id
        else [str(item["check_id"]) for item in CHECK_DESCRIPTORS]
    )
    if artifacts is None:
        artifacts = _candidate_artifacts(
            catalog,
            variant,
            run_id if candidate_scope else None,
        )
    checks = [
        evaluate_check(
            repo_root,
            catalog,
            check_id=item,
            stage=stage,
            variant=variant,
            run_id=run_id,
            tools=tools,
            candidate_scope=candidate_scope,
            artifacts=artifacts,
        )
        for item in descriptors
    ]
    return {
        "schema_version": 1,
        "stage": stage,
        "variant": variant,
        "run_id": run_id,
        "checks": checks,
        "stage_order": list(STAGES),
        "principle": "eligibility is derived from checkpoint artifacts and native dependencies; selecting a tab never launches a job",
    }
