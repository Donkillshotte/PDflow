#!/usr/bin/env python3
"""Validate a Ladder B ASAP7 BSPDN PROXY report against the frozen contract."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from lab_asap7_bspdn_proxy import (
    ALLOWED_STATUSES,
    MODEL_ID,
    MESH_PREFIX,
    PROXY_LICENSE_CLASS,
    PROXY_TOOL_ID,
    RECIPE_ID,
    RECIPE_PATH,
    ProxyContractError,
    _canonical_hash,
    _canonical_recipe,
    validate_mesh_id,
)


FALSE_FIELDS = (
    "product_win",
    "productWin",
    "win_eligible",
    "comparable_to_gold_ir",
    "product_signoff",
    "ok_claim",
)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_positive(value: Any) -> bool:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(result) and result > 0


def validation_errors(
    report: Mapping[str, Any], *, recipe_path: Path = RECIPE_PATH
) -> list[str]:
    """Return all contract violations without mutating the report."""
    errors: list[str] = []
    if not isinstance(report, Mapping):
        return ["report must be an object"]

    try:
        recipe = _canonical_recipe(recipe_path)
    except ProxyContractError as exc:
        errors.append(str(exc))
        recipe = None
    if recipe is not None:
        import hashlib

        if not _nonempty(report.get("recipe_path")):
            errors.append("recipe_path must identify the canonical recipe")
        if not _nonempty(report.get("recipe_sha256")):
            errors.append("recipe_sha256 is required")
        else:
            digest = hashlib.sha256(recipe.read_bytes()).hexdigest()
            if report.get("recipe_sha256") != digest:
                errors.append("recipe_sha256 does not match the canonical recipe")

    if report.get("scope") != "lab":
        errors.append("scope must be lab")
    if report.get("surface") not in {"lab", "lab_asap7"}:
        errors.append("surface must be lab or lab_asap7")
    if report.get("platform") != "asap7":
        errors.append("platform must be asap7")
    if report.get("track") == "asap7_bb":
        errors.append("asap7_bb is education-only and cannot be admitted")
    if report.get("track") != "asap7_bspdn":
        errors.append("track must be asap7_bspdn")

    for key, expected in (
        ("recipe_id", RECIPE_ID),
        ("model_id", MODEL_ID),
        ("tool_id", PROXY_TOOL_ID),
        ("license_class", PROXY_LICENSE_CLASS),
        ("topology", "proxy"),
        ("oracle", "analytical"),
        ("honesty", "PROXY"),
        ("comparison_scope", "not-comparable"),
    ):
        if report.get(key) != expected:
            errors.append(f"{key} must be {expected!r}")
    for key in ("report_id", "run_id", "variant", "honesty_reason"):
        if not _nonempty(report.get(key)):
            errors.append(f"{key} must be non-empty")
    if not isinstance(report.get("ir_report_paths"), list) or not report.get("ir_report_paths"):
        errors.append("ir_report_paths must be a non-empty list")
    if not isinstance(report.get("report_paths"), list) or not report.get("report_paths"):
        errors.append("report_paths must be a non-empty list")
    results_dir = report.get("results_dir")
    if not isinstance(results_dir, str) or not re.fullmatch(
        r"tools/OpenROAD-flow-scripts/flow/results/asap7/[^/]+/lab_asap7_[^/]+",
        results_dir,
    ):
        errors.append("results_dir must be under the ASAP7 Lab result tree")

    mesh_id = report.get("mesh_id")
    try:
        validate_mesh_id(mesh_id)
    except (ProxyContractError, TypeError) as exc:
        errors.append(str(exc))
    if isinstance(mesh_id, str) and not mesh_id.startswith(MESH_PREFIX):
        errors.append("mesh_id is outside the Ladder B proxy family")
    for key in FALSE_FIELDS:
        if report.get(key) is not False:
            errors.append(f"{key} must be exactly false")

    status = report.get("status")
    if not isinstance(status, str) or status not in ALLOWED_STATUSES:
        errors.append("status must be pass, fail, blocked, or not_run")
    if not isinstance(report.get("ok"), bool):
        errors.append("ok must be boolean")
    if status == "pass" and report.get("ok") is not True:
        errors.append("status=pass requires ok=true for the analytical invocation")
    if report.get("execution_status") != "COMPLETED":
        errors.append("execution_status must be COMPLETED")
    if report.get("evidence_status") != "PASS":
        errors.append("evidence_status must be PASS for a completed analytical run")
    if report.get("requirement_status") != "GAP":
        errors.append("requirement_status must remain GAP")
    if report.get("signoff_status") != "PROXY":
        errors.append("signoff_status must remain PROXY")

    leftovers = report.get("leftovers")
    if not isinstance(leftovers, list) or not leftovers:
        errors.append("leftovers must be a non-empty list")
    else:
        for index, item in enumerate(leftovers):
            if not isinstance(item, Mapping) or not _nonempty(item.get("id")):
                errors.append(f"leftovers[{index}] must have a non-empty id")

    pillars = report.get("pillars")
    if not isinstance(pillars, Mapping):
        errors.append("pillars must be an object")
        pillars = {}
    ir = pillars.get("ir")
    thermal = pillars.get("thermal")
    if not isinstance(ir, Mapping):
        errors.append("pillars.ir must be an object")
    else:
        if ir.get("honesty") != "PROXY":
            errors.append("pillars.ir.honesty must be PROXY")
        if ir.get("status") != status:
            errors.append("pillars.ir.status must match report status")
        if not isinstance(ir.get("leftovers"), list) or not ir.get("leftovers"):
            errors.append("pillars.ir.leftovers must be non-empty")
    if not isinstance(thermal, Mapping):
        errors.append("pillars.thermal must be an object")
    else:
        if thermal.get("honesty") != "GAP":
            errors.append("pillars.thermal.honesty must be GAP")
        ir_honesty = ir.get("honesty") if isinstance(ir, Mapping) else None
        if thermal.get("honesty") == ir_honesty:
            errors.append("thermal honesty must not inherit IR honesty")
        if thermal.get("status") not in {"blocked", "not_run"}:
            errors.append("thermal status must be blocked or not_run")
        if thermal.get("model_id") is not None:
            errors.append("thermal model_id must be null for Ladder B")

    if not isinstance(report.get("signoff_all"), Mapping) or report["signoff_all"].get("ok") is not False:
        errors.append("signoff_all.ok must be false")
    if not isinstance(report.get("lab_admit"), Mapping) or report["lab_admit"].get("ok") is not True:
        errors.append("valid proxy must be Lab-admissible without becoming Product signoff")

    fingerprint = report.get("mesh_fingerprint")
    fingerprint_inputs = report.get("mesh_fingerprint_inputs")
    if not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:"):
        errors.append("mesh_fingerprint must be a sha256:<hex> string")
    if not isinstance(fingerprint_inputs, Mapping):
        errors.append("mesh_fingerprint_inputs must be an object")
        fingerprint_inputs = {}
    required_fingerprint_keys = (
        "rail_model_id",
        "via_model_id",
        "thermal_model_id",
        "recipe_id",
        "model_id",
        "mesh_id",
        "topology",
    )
    for key in required_fingerprint_keys:
        if key not in fingerprint_inputs:
            errors.append(f"mesh fingerprint is missing {key}")
    if not _nonempty(fingerprint_inputs.get("rail_model_id")):
        errors.append("mesh fingerprint rail_model_id is required")
    if not _nonempty(fingerprint_inputs.get("via_model_id")):
        errors.append("mesh fingerprint via_model_id is required")
    if "thermal_model_id" in fingerprint_inputs and fingerprint_inputs.get("thermal_model_id") is not None:
        errors.append("mesh fingerprint thermal_model_id must be null")
    if isinstance(fingerprint, str) and isinstance(fingerprint_inputs, Mapping):
        try:
            expected = f"sha256:{_canonical_hash(dict(fingerprint_inputs))}"
        except (TypeError, ValueError):
            errors.append("mesh_fingerprint_inputs must be JSON-serializable")
        else:
            if fingerprint != expected:
                errors.append("mesh_fingerprint does not match mesh_fingerprint_inputs")

    metrics = report.get("metrics")
    if not isinstance(metrics, Mapping):
        errors.append("metrics must be an object")
    elif status == "pass" and not _finite_positive(metrics.get("droop_proxy_mv")):
        errors.append("pass report requires a finite positive droop_proxy_mv")

    text = json.dumps(report, sort_keys=True)
    if "expected_mv" in text or "gold_mv" in text:
        errors.append("proxy report must not contain expected_mv or gold_mv")
    if "10547" in text:
        errors.append("proxy report must not depend on an upstream issue identifier")
    for key in ("wrote_finish", "finish_write"):
        if report.get(key) is not False:
            errors.append(f"{key} must be false")
    chip_emit = report.get("chip_emit")
    if not isinstance(chip_emit, Mapping) or chip_emit.get("allowed") is not False:
        errors.append("chip_emit.allowed must be false until Ladder A")
    return errors


def validate_report(report: Mapping[str, Any], *, recipe_path: Path = RECIPE_PATH) -> None:
    errors = validation_errors(report, recipe_path=recipe_path)
    if errors:
        raise ProxyContractError("; ".join(errors))


def validate_report_file(path: Path, *, recipe_path: Path = RECIPE_PATH) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProxyContractError(f"cannot read report: {path}") from exc
    if not isinstance(report, Mapping):
        raise ProxyContractError("report JSON must contain an object")
    validate_report(report, recipe_path=recipe_path)
    return dict(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    report = validate_report_file(args.report)
    print(
        "VALID ASAP7 Ladder B PROXY",
        f"mesh_id={report['mesh_id']}",
        f"status={report['status']}",
        f"honesty={report['honesty']}",
        f"thermal_honesty={report['pillars']['thermal']['honesty']}",
        "product_win=false",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProxyContractError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        raise SystemExit(1)
