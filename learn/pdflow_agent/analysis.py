"""Live-only package and path evidence helpers.

This module reads existing reports, never promotes a stale report to current
evidence, and keeps package/lab results outside the Product signoff verdict.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .artifacts import ArtifactCatalog
from .contracts import hash_text, utc_now


LAB_VARIANT_RE = re.compile(r"^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$")
COURSE_VARIANTS = frozenset({"flowlab", "learn", "eco_scratch"})

LAB_REPORT_NAMES = {
    "pkg_bump": "lab_asap7_pkg_bump.json",
    "pkg_rdl": "lab_asap7_pkg_rdl.json",
    "pkg_signoff": "lab_asap7_pkg.json",
    "system_pdn": "lab_asap7_system_pdn.json",
    "thermal_signoff": "lab_asap7_thermal.json",
    "sta_signoff": "lab_asap7.json",
    "pdn_chip_ir": "lab_asap7_chip_pdn.json",
}


def _is_lab_variant(variant: str) -> bool:
    return bool(LAB_VARIANT_RE.fullmatch(variant))


def _validate_variant(variant: str) -> str:
    value = str(variant).strip()
    if value in COURSE_VARIANTS or _is_lab_variant(value):
        return value
    raise ValueError("invalid or unsafe results variant")


def _report_rel(name: str, variant: str) -> str:
    filename = LAB_REPORT_NAMES.get(name) if _is_lab_variant(variant) else None
    return "learn/sim/reports/" + (filename or f"{name}_{variant}.json")


def active_variant(repo_root: Path) -> str:
    requested = os.environ.get("FLOW_VARIANT")
    if requested in {"flowlab", "learn"}:
        return requested
    flowlab = (
        repo_root
        / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
    )
    learn = (
        repo_root
        / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.odb"
    )
    return "flowlab" if flowlab.is_file() else "learn" if learn.is_file() else "flowlab"


def _finish_mtime(repo_root: Path, variant: str) -> float | None:
    tree = "asap7" if _is_lab_variant(variant) else "nangate45"
    root = repo_root / "tools/OpenROAD-flow-scripts/flow/results" / tree / "gcd" / variant
    values = []
    for name in ("6_final.odb", "6_final.v", "6_final.spef", "6_final.gds"):
        path = root / name
        try:
            values.append(path.stat().st_mtime)
        except OSError:
            pass
    return max(values) if values else None


def _report_path(repo_root: Path, name: str, variant: str) -> Path:
    if _is_lab_variant(variant):
        mapped = LAB_REPORT_NAMES.get(name)
        if mapped:
            return repo_root / "learn" / "sim" / "reports" / mapped
    return repo_root / "learn" / "sim" / "reports" / (name + "_" + variant + ".json")


def _load_live(
    repo_root: Path,
    name: str,
    variant: str,
) -> tuple[dict[str, Any] | None, str | None]:
    path = _report_path(repo_root, name, variant)
    if not path.is_file():
        return None, None
    finish_mtime = _finish_mtime(repo_root, variant)
    try:
        if finish_mtime is not None and path.stat().st_mtime < finish_mtime:
            return None, "report is older than the active finish artifacts"
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return None, "report is not a JSON object"
        report_variant = value.get("variant")
        if _is_lab_variant(variant) and report_variant:
            if str(report_variant) != variant:
                return None, "report variant does not match the selected ASAP7 variant"
        return value, None
    except (OSError, json.JSONDecodeError):
        return None, "report is unreadable"


def _status(report: dict[str, Any] | None, stale_reason: str | None) -> str:
    if stale_reason:
        return "GAP"
    if not report:
        return "NOT_RUN"
    raw = str(report.get("status") or "").upper()
    if raw in {"PASS", "FAIL", "WARN", "PARTIAL", "PROXY", "GAP", "NOT_RUN"}:
        return raw
    if report.get("ok") is True:
        return "PASS"
    if report.get("ok") is False:
        return "FAIL"
    return "NOT_RUN"


def package_evidence(
    repo_root: Path,
    catalog: ArtifactCatalog,
    variant: str | None = None,
) -> dict[str, Any]:
    variant = _validate_variant(variant or active_variant(repo_root))
    reports: dict[str, dict[str, Any] | None] = {}
    reasons: dict[str, str | None] = {}
    for name in (
        "pkg_bump",
        "pkg_rdl",
        "pkg_signoff",
        "pkg_manifest",
        "system_pdn",
        "thermal_signoff",
    ):
        reports[name], reasons[name] = _load_live(repo_root, name, variant)

    statuses = {name: _status(reports[name], reasons[name]) for name in reports}
    system = reports["system_pdn"] or {}
    pkg = reports["pkg_signoff"] or {}
    rdl = reports["pkg_rdl"] or {}
    bump = reports["pkg_bump"] or {}
    manifest = reports["pkg_manifest"]
    if not manifest and isinstance(pkg.get("manifest"), dict):
        # Keep compatibility with a lab package report generated before the
        # manifest received its own live-report path.
        nested = pkg["manifest"]
        if str(nested.get("variant") or "") == variant:
            manifest = nested

    manifest_status = _status(manifest, reasons["pkg_manifest"]) if manifest else "NOT_RUN"
    manifest_evidence_ok = bool(manifest and manifest.get("evidence_ok") is True)
    if statuses["system_pdn"] in {"GAP", "NOT_RUN"}:
        overall = "GAP"
    elif manifest_status in {"GAP", "NOT_RUN"} and manifest:
        overall = "GAP"
    elif manifest_status == "FAIL":
        overall = "FAIL"
    elif manifest_status == "PROXY":
        overall = "PROXY"
    elif statuses["pkg_signoff"] == "FAIL":
        overall = "FAIL"
    elif statuses["pkg_signoff"] == "PROXY":
        overall = "PROXY"
    elif pkg.get("ok") is True and statuses["pkg_rdl"] == "PASS":
        overall = "PROXY"
    else:
        overall = "PARTIAL"

    finish = [
        ref.to_dict()
        for ref in catalog.list(limit=2000)
        if ref.authority == "finish" and ref.variant == variant
        and (
            ("/results/asap7/gcd/" if _is_lab_variant(variant) else "/results/nangate45/gcd/")
            in f"/{ref.relative_path}"
        )
    ]
    computed_input_hash = hashlib.sha256(
        "\n".join(
            str(item.get("content_hash") or "")
            for item in sorted(finish, key=lambda item: item["relative_path"])
        ).encode("utf-8")
    ).hexdigest()
    input_hash = (
        ((manifest.get("provenance") or {}).get("input_fingerprint"))
        if isinstance(manifest, dict)
        else None
    ) or computed_input_hash
    rdl_evidence_ok = bool(rdl.get("evidence_ok") is True)
    if not rdl_evidence_ok and isinstance(manifest, dict):
        manifest_rdl = manifest.get("rdl") if isinstance(manifest.get("rdl"), dict) else {}
        missing_nets = manifest_rdl.get("missing_nets")
        rdl_evidence_ok = bool(
            manifest_rdl.get("ready") is True
            and isinstance(missing_nets, list)
            and not missing_nets
        )
    return {
        "schema_version": 1,
        "scope": "package",
        "variant": variant,
        "status": overall,
        "ok": False,
        "evidence_ok": manifest_evidence_ok,
        "comparison_scope": "same-live-invocation",
        "oracle": "current-finish-snapshot",
        "input_artifacts": finish,
        "input_fingerprint": input_hash,
        "manifest": manifest if isinstance(manifest, dict) else None,
        "steps": {
            "pkg_bump": {
                "status": statuses["pkg_bump"],
                "ok": statuses["pkg_bump"] == "PASS",
                "summary": bump.get("summary"),
                "report": _report_rel("pkg_bump", variant),
            },
            "pkg_rdl": {
                "status": statuses["pkg_rdl"],
                "ok": rdl_evidence_ok,
                "evidence_ok": rdl_evidence_ok,
                "summary": rdl.get("summary"),
                "report": _report_rel("pkg_rdl", variant),
                "educational": True,
                "dummy_bump_lef": True,
            },
            "package_manifest": {
                "status": manifest_status,
                "ok": manifest_evidence_ok,
                "evidence_ok": manifest_evidence_ok,
                "summary": manifest.get("summary") if isinstance(manifest, dict) else None,
                "report": _report_rel("pkg_manifest", variant),
                "manifest": True,
            },
            "system_pdn": {
                "status": statuses["system_pdn"],
                "ok": statuses["system_pdn"] == "PASS",
                "summary": system.get("summary"),
                "engine": system.get("engine"),
                "reason": system.get("reason") or reasons["system_pdn"],
                "droop_mv": (system.get("transient") or {}).get("droop_mv"),
                "zmax_mohm": (system.get("impedance") or {}).get("z_max_mohm"),
                "report": _report_rel("system_pdn", variant),
            },
            "thermal_signoff": {
                "status": statuses["thermal_signoff"],
                "ok": statuses["thermal_signoff"] == "PASS",
                "summary": (reports["thermal_signoff"] or {}).get("summary"),
                "report": _report_rel("thermal_signoff", variant),
            },
        },
        "product_signoff": {
            "status": "NOT_RUN",
            "reason": "Package evidence cannot close Product signoff",
        },
        "generated_at": utc_now(),
    }


def path_ledger(
    repo_root: Path,
    catalog: ArtifactCatalog,
    variant: str | None = None,
) -> dict[str, Any]:
    variant = _validate_variant(variant or active_variant(repo_root))
    sta, sta_reason = _load_live(repo_root, "sta_signoff", variant)
    sta_ir, sta_ir_reason = _load_live(repo_root, "sta_ir_aware", variant)
    dynamic, dynamic_reason = _load_live(repo_root, "dynamic_ir", variant)
    chip_ir, chip_reason = _load_live(repo_root, "pdn_chip_ir", variant)
    system, system_reason = _load_live(repo_root, "system_pdn", variant)
    finish = [
        ref for ref in catalog.list(limit=2000)
        if ref.authority == "finish" and ref.variant == variant
        and (
            ("/results/asap7/gcd/" if _is_lab_variant(variant) else "/results/nangate45/gcd/")
            in f"/{ref.relative_path}"
        )
    ]
    hashes = [ref.content_hash or "" for ref in sorted(finish, key=lambda ref: ref.relative_path)]
    mesh_id = hash_text("variant=" + variant, *hashes)[:24]
    timing = (sta or {}).get("timing") or {}
    leftover = (sta or {}).get("leftover") or {}
    if _is_lab_variant(variant) and sta:
        # lab_asap7.json is a complete-flow report rather than the course
        # sta_signoff envelope. Its timing closure is authoritative only via
        # qor.timing_closed / qor.wns_ps; a completed GDS is not a timing pass.
        lab_qor = (sta.get("qor") or {}) if isinstance(sta.get("qor"), dict) else {}
        if not timing:
            timing = {
                "wns_ns": (
                    float(lab_qor["wns_ps"]) / 1000.0
                    if lab_qor.get("wns_ps") is not None
                    else None
                ),
                "tns": lab_qor.get("tns_ps"),
                "setup_violations": lab_qor.get("setup_violations"),
                "worst_endpoint": None,
            }
        timing_closed = lab_qor.get("timing_closed")
        if timing_closed is None and lab_qor.get("wns_ps") is not None:
            timing_closed = float(lab_qor["wns_ps"]) >= 0
        timing_status = "PASS" if timing_closed is True else "FAIL" if timing_closed is False else "NOT_RUN"
    else:
        timing_status = (
            "GAP"
            if sta_reason
            else "NOT_RUN"
            if not sta
            else "FAIL"
            if leftover.get("setup_open") is True
            else "PASS"
        )
    entries = [
        {
            "id": "worst-timing-endpoint",
            "endpoint": timing.get("worst_endpoint"),
            "net": None,
            "status": timing_status,
            "wns_ns": timing.get("wns_ns"),
            "tns": timing.get("tns"),
            "setup_violations": timing.get("setup_violations"),
            "reason": (
                leftover.get("note")
                or "timing closure is open in the selected ASAP7 live report"
                if _is_lab_variant(variant) and timing_status == "FAIL"
                else leftover.get("note") if timing_status == "FAIL" else sta_reason
            ),
            "sources": [
                _report_rel("sta_signoff", variant),
                "tools/OpenROAD-flow-scripts/flow/results/"
                + ("asap7/gcd/" if _is_lab_variant(variant) else "nangate45/gcd/")
                + variant
                + "/6_final.spef",
            ],
        },
        {
            "id": "timing-ir-aware",
            "endpoint": timing.get("worst_endpoint"),
            "status": (
                "GAP"
                if sta_ir_reason
                else "NOT_RUN"
                if not sta_ir
                else "PASS"
                if sta_ir.get("ok") is True
                else "FAIL"
            ),
            "slack_ns": sta_ir.get("slack_ns") if sta_ir else None,
            "slack_ir_ns": sta_ir.get("slack_ir_ns") if sta_ir else None,
            "n_joined": sta_ir.get("n_joined") if sta_ir else None,
            "reason": sta_ir_reason,
            "sources": [_report_rel("sta_ir_aware", variant)],
        },
    ]
    meshes = []
    for ident, report, reason, mesh_label in (
        ("dynamic_ir", dynamic, dynamic_reason, "live Dynamic IR mesh"),
        ("chip_pdn", chip_ir, chip_reason, "live write_pg_spice chip mesh"),
        ("system_pdn", system, system_reason, "live VRM-to-package ladder"),
    ):
        status = _status(report, reason)
        meshes.append(
            {
                "id": ident,
                "mesh_id": mesh_id if ident == "dynamic_ir" else None,
                "label": mesh_label,
                "status": status,
                "report": _report_rel(
                    "pdn_chip_ir" if ident == "chip_pdn" else ident,
                    variant,
                ),
                "reason": reason or (report or {}).get("reason"),
                "comparable_to": ["dynamic_ir"] if ident == "dynamic_ir" else [],
            }
        )
    ledger_statuses = [item["status"] for item in entries + meshes]
    ledger_status = (
        "GAP"
        if "GAP" in ledger_statuses
        else "FAIL"
        if "FAIL" in ledger_statuses
        else "NOT_RUN"
        if "NOT_RUN" in ledger_statuses
        else "PASS"
        if ledger_statuses and all(status == "PASS" for status in ledger_statuses)
        else "WARN"
    )
    return {
        "schema_version": 1,
        "scope": "flow",
        "variant": variant,
        "status": ledger_status,
        "ok": False,
        "mesh_id": mesh_id,
        "oracle": "current-finish-snapshot",
        "comparison_scope": "same-live-invocation",
        "entries": entries,
        "meshes": meshes,
        "note": "No historical report or different mesh is used as a baseline.",
        "generated_at": utc_now(),
    }
