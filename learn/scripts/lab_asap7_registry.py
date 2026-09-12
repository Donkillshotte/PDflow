#!/usr/bin/env python3
"""Build and validate a Lab-only registry row for an ASAP7 report.

The registry is deliberately separate from the Product suite registry.  This
module is small and dependency-free so CI and Studio smoke tests can apply the
same path, comparison, and Product-firewall rules without launching EDA.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from lab_asap7_bspdn_proxy import ProxyContractError, validate_mesh_id
from validate_lab_asap7_bspdn_proxy import validate_report


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_bspdn_proxy.json"
DEFAULT_OUTPUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_registry.json"
ASAP7_RESULTS_RE = re.compile(
    r"^tools/OpenROAD-flow-scripts/flow/results/asap7/[^/]+/lab_asap7_[^/]+$"
)
LAB_VARIANT_RE = re.compile(r"^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$")
ALLOWED_TRACKS = frozenset({"asap7", "asap7_bspdn", "asap7_bpr", "asap7_pkg"})
FORBIDDEN_CHIP_MESHES = frozenset({"asap7_bpr_chip", "asap7_bspdn_chip"})


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _false_firewall(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("productWin", "product_win", "win_eligible", "comparable_to_gold_ir"):
        if row.get(key) is not False:
            errors.append(f"{key} must be exactly false")
    return errors


def _identity(row: Mapping[str, Any]) -> dict[str, str | None]:
    return {
        "mesh_id": row.get("mesh_id") if isinstance(row.get("mesh_id"), str) else None,
        "mesh_fingerprint": (
            row.get("mesh_fingerprint")
            if isinstance(row.get("mesh_fingerprint"), str)
            else None
        ),
        "platform": row.get("platform") if isinstance(row.get("platform"), str) else None,
        "design": row.get("design") if isinstance(row.get("design"), str) else None,
        "nickname": (
            row.get("nickname")
            if isinstance(row.get("nickname"), str)
            else row.get("nick")
            if isinstance(row.get("nick"), str)
            else None
        ),
        "topology": row.get("topology") if isinstance(row.get("topology"), str) else None,
    }


def same_mesh(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Strict Lab relative-comparison predicate; missing identity fails closed."""
    a = _identity(left)
    b = _identity(right)
    required = ("mesh_id", "mesh_fingerprint", "platform", "design")
    if any(not a[key] or not b[key] for key in required):
        return False
    if any(a[key] != b[key] for key in required):
        return False
    if a["platform"] != "asap7":
        return False
    if (a["nickname"] or a["design"]) != (b["nickname"] or b["design"]):
        return False
    if a["topology"] and b["topology"] and a["topology"] != b["topology"]:
        return False
    return True


def comparison_allowed(left: Mapping[str, Any], right: Mapping[str, Any], *, strict: bool = False) -> bool:
    """Refuse cross-PDK, cross-topology, candidate-vs-FS, and Nangate pairs."""
    a = _identity(left)
    b = _identity(right)
    if not a["mesh_id"] or not b["mesh_id"]:
        return False
    if not a["mesh_id"].startswith("asap7_") or not b["mesh_id"].startswith("asap7_"):
        return False
    if a["mesh_id"] in FORBIDDEN_CHIP_MESHES or b["mesh_id"] in FORBIDDEN_CHIP_MESHES:
        return False
    if a["mesh_id"].startswith("nangate_") or b["mesh_id"].startswith("nangate_"):
        return False
    if a["platform"] != "asap7" or b["platform"] != "asap7":
        return False
    if a["topology"] and b["topology"] and a["topology"] != b["topology"]:
        return False
    candidate_a = a["mesh_id"].startswith("asap7_candidate_")
    candidate_b = b["mesh_id"].startswith("asap7_candidate_")
    if candidate_a != candidate_b:
        return False
    return same_mesh(left, right) if strict else True


def registry_errors(row: Mapping[str, Any]) -> list[str]:
    """Return all Lab registry violations without mutating the row."""
    if not isinstance(row, Mapping):
        return ["registry row must be an object"]
    errors = _false_firewall(row)
    for key in ("version", "runId", "variant", "design", "resultsDir"):
        if not _nonempty(row.get(key)):
            errors.append(f"{key} must be non-empty")
    if row.get("surface") not in {"lab", "lab_asap7"}:
        errors.append("surface must be lab or lab_asap7")
    if row.get("pdk") != "asap7":
        errors.append("pdk must be asap7")
    if row.get("track") not in ALLOWED_TRACKS:
        errors.append("track is not an admit-capable Lab track")
    if not isinstance(row.get("ok"), bool):
        errors.append("ok must be boolean")
    variant = row.get("variant")
    if not isinstance(variant, str) or not LAB_VARIANT_RE.fullmatch(variant):
        errors.append("variant must be a lab_asap7 variant")
    results_dir = row.get("resultsDir")
    if not isinstance(results_dir, str) or not ASAP7_RESULTS_RE.fullmatch(results_dir):
        errors.append("resultsDir is outside the ASAP7 Lab pathGuard")
    mesh_id = row.get("mesh_id")
    if mesh_id is not None and not isinstance(mesh_id, str):
        errors.append("mesh_id must be a string when present")
    if isinstance(mesh_id, str):
        if mesh_id in FORBIDDEN_CHIP_MESHES or mesh_id.endswith("_chip"):
            errors.append("*_chip mesh IDs are emit-forbidden until Ladder A")
        if mesh_id == "asap7_pkg_tier_c" and row.get("track") not in {"asap7_pkg", "asap7"}:
            errors.append("package tier mesh is not valid on this track")
        if mesh_id.startswith("asap7_bspdn_proxy_"):
            try:
                validate_mesh_id(mesh_id)
            except ProxyContractError as exc:
                errors.append(str(exc))
            for key in ("honesty", "honesty_reason", "tool_id", "license_class"):
                if not _nonempty(row.get(key)):
                    errors.append(f"proxy registry row requires {key}")
            if row.get("honesty") != "PROXY":
                errors.append("proxy registry row honesty must be PROXY")
    if row.get("track") == "asap7_bb":
        errors.append("asap7_bb is citation/EDU-only")
    if row.get("honesty") is not None and row.get("honesty") not in {"GAP", "PROXY", "PARTIAL"}:
        errors.append("honesty must be GAP, PROXY, or PARTIAL")
    if row.get("status") is not None and row.get("status") not in {"pass", "fail", "blocked", "not_run"}:
        errors.append("status must be a tool outcome, never PROXY")
    if row.get("status") == "PROXY":
        errors.append("PROXY belongs on honesty, not status")
    report_paths = row.get("reportPaths")
    if not isinstance(report_paths, list) or not all(isinstance(item, str) for item in report_paths):
        errors.append("reportPaths must be a string array")
    return errors


def validate_registry_row(row: Mapping[str, Any]) -> None:
    errors = registry_errors(row)
    if errors:
        raise ProxyContractError("; ".join(errors))


def build_registry_row(report: Mapping[str, Any], *, report_path: str | None = None) -> dict[str, Any]:
    """Project a validated report into the Studio Lab registry shape."""
    validate_report(report)
    report_path = report_path or str(report.get("report_path") or "learn/sim/reports/lab_asap7_bspdn_proxy.json")
    row = {
        "version": "lab-bspdn-v0",
        "runId": report["run_id"],
        "surface": report["surface"],
        "variant": report["variant"],
        "design": report.get("design") or "asap7-lab-design",
        "nickname": report.get("nickname") or report.get("design") or "asap7-lab-design",
        "pdk": "asap7",
        "ok": report.get("ok") is True,
        "productWin": False,
        "product_win": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "reportPaths": [report_path],
        "resultsDir": report.get("results_dir"),
        "track": report.get("track"),
        "status": report.get("status"),
        "ir_report_paths": report.get("ir_report_paths") or report.get("report_paths") or [report_path],
        "mesh_id": report.get("mesh_id"),
        "oracle": report.get("oracle"),
        "topology": report.get("topology"),
        "mesh_fingerprint": report.get("mesh_fingerprint"),
        "honesty": report.get("honesty"),
        "honesty_reason": report.get("honesty_reason"),
        "tool_id": report.get("tool_id"),
        "license_class": report.get("license_class"),
        "pillars": report.get("pillars"),
        "signoff_all": report.get("signoff_all"),
    }
    validate_registry_row(row)
    return row


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path = path.expanduser().resolve()
    if path.suffix != ".json":
        raise ProxyContractError("registry output must be a JSON file")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with open(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        Path(temporary).replace(path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(report, Mapping):
            raise ProxyContractError("report JSON must contain an object")
        row = build_registry_row(report, report_path=str(args.report))
        output = _write_json(args.out, row)
    except (OSError, json.JSONDecodeError, ProxyContractError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(
        "VALID ASAP7 Lab registry",
        f"runId={row['runId']}",
        f"mesh_id={row['mesh_id']}",
        f"honesty={row['honesty']}",
        "productWin=false",
        f"out={output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
