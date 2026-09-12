#!/usr/bin/env python3
"""Emit the ASAP7 Ladder B backside-power PROXY report.

This is a Lab-only analytical experiment.  It deliberately does not launch a
native EDA tool, write a design artifact, or claim Product signoff.  The
emitter is kept self-contained so that its provenance contract can be tested
without relying on a finish tree or a historical metric.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
RECIPE_PATH = ROOT / "bspdn" / "reviews" / "ladder-b-proxy-recipe.md"
REPORT_DIR = ROOT / "learn" / "sim" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "lab_asap7_bspdn_proxy.json"

RECIPE_ID = "asap7_proxy_bpr_bs_m89_v0"
MODEL_ID = "asap7_bspdn_proxy_m89"
MESH_PREFIX = "asap7_bspdn_proxy_"
PROXY_TOOL_ID = "analytical_two_node_rc"
PROXY_LICENSE_CLASS = "Apache-2.0"
FORBIDDEN_MESH_IDS = frozenset({"asap7_bpr_chip", "asap7_bspdn_chip"})
ALLOWED_STATUSES = frozenset({"pass", "fail", "blocked", "not_run"})
VARIANT_RE = re.compile(r"^lab_asap7_[a-z0-9][a-z0-9_+.]*[a-z0-9]$")
MESH_RE = re.compile(r"^asap7_bspdn_proxy_[a-z0-9][a-z0-9_]*$")


class ProxyContractError(ValueError):
    """Raised when the Ladder B contract would be violated."""


def _finite_float(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ProxyContractError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ProxyContractError(f"{name} must be finite")
    return result


def validate_variant(variant: str) -> str:
    """Validate a lab variant before it is recorded in provenance."""
    if not isinstance(variant, str) or not VARIANT_RE.fullmatch(variant):
        raise ProxyContractError(
            "variant must match lab_asap7_<design>_<corner>_<vt>_<model>_<track>"
        )
    if ".." in variant or "/" in variant or "\\" in variant or ":" in variant:
        raise ProxyContractError("variant contains a path token")
    return variant


def validate_mesh_id(mesh_id: str) -> str:
    """Allow only Ladder B proxy mesh IDs; never silently accept a chip ID."""
    if not isinstance(mesh_id, str) or not MESH_RE.fullmatch(mesh_id):
        raise ProxyContractError(
            f"mesh_id must match {MESH_PREFIX}<short>; Ladder A chip IDs are reserved"
        )
    if mesh_id in FORBIDDEN_MESH_IDS or mesh_id.endswith("_chip"):
        raise ProxyContractError(f"mesh_id is emit-forbidden before Ladder A: {mesh_id}")
    return mesh_id


def _slug(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value)).strip("-")
    return result or "run"


def _relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT.resolve()))
    except ValueError:
        return str(resolved)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProxyInputs:
    """Inputs to the deliberately small, transparent analytical model."""

    n_r: int = 89
    n_sources: int = 4
    grid_pitch_um: float = 7.5
    rail_length_um: float = 1.0
    rail_model_id: str = "gupta_ted20_edu_range_v0"
    rail_r_ohm_per_um: float = 120.0
    via_model_id: str = "literature_via_range_v0"
    via_r_ohm: float = 0.02
    thermal_model_id: str | None = None
    current_a: float = 0.010
    stack_id: str = "asap7_7p5t_proxy_stack_v0"
    bm_model_id: str = "backside_metal_remap_edu_v0"
    bump_model_id: str = "proxy_bump_array_v0"
    load_model_id: str = "uniform_load_v0"
    pdk_rev: str = "asap7-oss-7p5t"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "ProxyInputs":
        raw = raw or {}
        known = {
            "n_r",
            "n_sources",
            "grid_pitch_um",
            "rail_length_um",
            "rail_model_id",
            "rail_r_ohm_per_um",
            "via_model_id",
            "via_r_ohm",
            "thermal_model_id",
            "current_a",
            "stack_id",
            "bm_model_id",
            "bump_model_id",
            "load_model_id",
            "pdk_rev",
        }
        values = {key: raw[key] for key in known if key in raw}
        if values.get("thermal_model_id") == "":
            values["thermal_model_id"] = None
        try:
            result = cls(**values)
        except TypeError as exc:
            raise ProxyContractError(f"invalid proxy input: {exc}") from exc
        result.validate()
        return result

    def validate(self) -> None:
        if not isinstance(self.n_r, int) or isinstance(self.n_r, bool) or self.n_r <= 0:
            raise ProxyContractError("n_r must be a positive integer")
        if (
            not isinstance(self.n_sources, int)
            or isinstance(self.n_sources, bool)
            or self.n_sources <= 0
        ):
            raise ProxyContractError("n_sources must be a positive integer")
        if self.n_sources > self.n_r:
            raise ProxyContractError("n_sources cannot exceed n_r")
        for name in (
            "grid_pitch_um",
            "rail_length_um",
            "rail_r_ohm_per_um",
            "via_r_ohm",
            "current_a",
        ):
            if _finite_float(getattr(self, name), name) <= 0:
                raise ProxyContractError(f"{name} must be greater than zero")
        for name in (
            "rail_model_id",
            "via_model_id",
            "stack_id",
            "bm_model_id",
            "bump_model_id",
            "load_model_id",
            "pdk_rev",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ProxyContractError(f"{name} is required")
        if self.thermal_model_id is not None:
            raise ProxyContractError(
                "Ladder B thermal_model_id must be null until a thermal proxy is reviewed"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_r": self.n_r,
            "n_sources": self.n_sources,
            "grid_pitch_um": self.grid_pitch_um,
            "rail_length_um": self.rail_length_um,
            "rail_model_id": self.rail_model_id,
            "rail_r_ohm_per_um": self.rail_r_ohm_per_um,
            "via_model_id": self.via_model_id,
            "via_r_ohm": self.via_r_ohm,
            "thermal_model_id": self.thermal_model_id,
            "current_a": self.current_a,
            "stack_id": self.stack_id,
            "bm_model_id": self.bm_model_id,
            "bump_model_id": self.bump_model_id,
            "load_model_id": self.load_model_id,
            "pdk_rev": self.pdk_rev,
        }


def calculate_proxy(inputs: ProxyInputs) -> dict[str, float]:
    """Calculate transparent proxy metrics without a hidden reference value."""
    inputs.validate()
    rail_eq = inputs.rail_r_ohm_per_um * inputs.rail_length_um / inputs.n_sources
    via_eq = inputs.via_r_ohm / inputs.n_sources
    equivalent = rail_eq + via_eq
    droop = inputs.current_a * equivalent * 1000.0
    return {
        "r_rail_eq_ohm": rail_eq,
        "r_via_eq_ohm": via_eq,
        "r_eq_ohm": equivalent,
        "droop_proxy_mv": droop,
        "current_a": inputs.current_a,
    }


def fingerprint_inputs(
    *, mesh_id: str, inputs: ProxyInputs, recipe_id: str = RECIPE_ID, model_id: str = MODEL_ID
) -> dict[str, Any]:
    validate_mesh_id(mesh_id)
    if recipe_id != RECIPE_ID:
        raise ProxyContractError(f"unsupported recipe_id: {recipe_id}")
    if model_id != MODEL_ID:
        raise ProxyContractError(f"unsupported model_id: {model_id}")
    inputs.validate()
    return {
        "recipe_id": recipe_id,
        "model_id": model_id,
        "mesh_id": mesh_id,
        "platform": "asap7",
        "topology": "proxy",
        "stack_id": inputs.stack_id,
        "bm_model_id": inputs.bm_model_id,
        "grid_pitch_um": inputs.grid_pitch_um,
        "n_r": inputs.n_r,
        "n_sources": inputs.n_sources,
        "rail_model_id": inputs.rail_model_id,
        "via_model_id": inputs.via_model_id,
        "thermal_model_id": inputs.thermal_model_id,
        "bump_model_id": inputs.bump_model_id,
        "load_model_id": inputs.load_model_id,
        "pdk_rev": inputs.pdk_rev,
    }


def mesh_fingerprint(*, mesh_id: str, inputs: ProxyInputs) -> tuple[str, dict[str, Any]]:
    values = fingerprint_inputs(mesh_id=mesh_id, inputs=inputs)
    return f"sha256:{_canonical_hash(values)}", values


def _canonical_recipe(path: Path = RECIPE_PATH) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise ProxyContractError(f"canonical Ladder B recipe is missing: {path}")
    text = path.read_text(encoding="utf-8")
    for token in (RECIPE_ID, MODEL_ID, MESH_PREFIX, "thermal_model_id", "product_win"):
        if token not in text:
            raise ProxyContractError(f"canonical recipe is incomplete: missing {token}")
    return path


def _safe_output_path(path: Path) -> Path:
    """Reject finish/result targets before any write occurs."""
    path = path.expanduser().resolve()
    protected_roots = (
        ROOT / "tools" / "OpenROAD-flow-scripts" / "flow" / "results",
        ROOT / "tools" / "OpenROAD-flow-scripts" / "flow" / "logs",
    )
    for root in protected_roots:
        if path.is_relative_to(root.resolve()):
            raise ProxyContractError(f"refusing output below protected EDA tree: {path}")
    if path.suffix.lower() not in {".json", ".jsonl"}:
        raise ProxyContractError("proxy emitter output must be a JSON report")
    return path


def _run_id(value: str | None) -> str:
    if value:
        result = _slug(value)
        if len(result) > 120:
            raise ProxyContractError("run_id is too long")
        return result
    env_value = os.environ.get("PD_FLOW_RUN_ID")
    if env_value:
        return _run_id(env_value)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"proxy-{stamp}"


def build_report(
    *,
    variant: str,
    run_id: str,
    inputs: ProxyInputs | None = None,
    mesh_id: str = "asap7_bspdn_proxy_m89",
    output_path: Path | None = None,
    recipe_path: Path = RECIPE_PATH,
) -> dict[str, Any]:
    """Build one complete, self-describing Ladder B report."""
    variant = validate_variant(variant)
    mesh_id = validate_mesh_id(mesh_id)
    if run_id != _slug(run_id):
        raise ProxyContractError("run_id contains unsupported characters")
    inputs = inputs or ProxyInputs()
    inputs.validate()
    recipe_path = _canonical_recipe(recipe_path)
    recipe_hash = _sha256_file(recipe_path)
    fingerprint, fingerprint_values = mesh_fingerprint(mesh_id=mesh_id, inputs=inputs)
    metrics = calculate_proxy(inputs)
    output = _safe_output_path(output_path or DEFAULT_OUTPUT)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report_key = _canonical_hash(
        {"run_id": run_id, "variant": variant, "mesh_fingerprint": fingerprint}
    )[:16]
    report_id = f"{mesh_id}-{_slug(run_id)}-{report_key}"
    leftover_items = [
        {
            "id": "backside_geometry_unmodeled",
            "message": "Backside metal/via geometry is represented by a remapped lumped model.",
        },
        {
            "id": "thermal_model_missing",
            "message": "No compact thermal model was executed; thermal honesty remains GAP.",
        },
        {
            "id": "no_foundry_signoff_deck",
            "message": "This community analytical experiment has no foundry signoff deck.",
        },
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_id": report_id,
        "run_id": run_id,
        "scope": "lab",
        "surface": "lab_asap7",
        "platform": "asap7",
        "track": "asap7_bspdn",
        "variant": variant,
        "design": "gcd" if "_gcd_" in variant else "asap7-lab-design",
        "nickname": "gcd" if "_gcd_" in variant else "asap7-lab-design",
        "pdk": "asap7",
        "results_dir": (
            "tools/OpenROAD-flow-scripts/flow/results/asap7/"
            f"{'gcd' if '_gcd_' in variant else 'asap7-lab-design'}/"
            "lab_asap7_bspdn_proxy_m89"
        ),
        "created_at": now,
        "operation": "emit_ladder_b_proxy",
        "status": "pass",
        "ok": True,
        "execution_status": "COMPLETED",
        "evidence_status": "PASS",
        "requirement_status": "GAP",
        "signoff_status": "PROXY",
        "ok_claim": False,
        "recipe_id": RECIPE_ID,
        "model_id": MODEL_ID,
        "mesh_id": mesh_id,
        "topology": "proxy",
        "oracle": "analytical",
        "honesty": "PROXY",
        "honesty_reason": (
            "Ladder B analytical stand-in: rail and via models are educational "
            "lumped estimates, not physical backside extraction."
        ),
        "tool_id": PROXY_TOOL_ID,
        "license_class": PROXY_LICENSE_CLASS,
        "recipe_path": _relative_or_absolute(recipe_path),
        "recipe_sha256": recipe_hash,
        "mesh_fingerprint": fingerprint,
        "mesh_fingerprint_inputs": fingerprint_values,
        "inputs": inputs.to_dict(),
        "metrics": metrics,
        "ir": {
            "status": "pass",
            "honesty": "PROXY",
            "oracle": "analytical",
            "droop_proxy_mv": metrics["droop_proxy_mv"],
            "leftovers": leftover_items,
        },
        "pillars": {
            "ir": {
                "status": "pass",
                "honesty": "PROXY",
                "honesty_reason": "Analytical lumped IR proxy on the declared mesh fingerprint.",
                "oracle": "analytical",
                "leftovers": leftover_items,
            },
            "thermal": {
                "status": "blocked",
                "honesty": "GAP",
                "honesty_reason": "No reviewed compact thermal model is part of Ladder B.",
                "model_id": None,
                "leftovers": [leftover_items[1]],
            },
        },
        "leftovers": leftover_items,
        "lab_admit": {
            "ok": True,
            "reason": "IR proxy schema/provenance is valid; thermal GAP is explicit and non-promoting.",
        },
        "signoff_all": {
            "ok": False,
            "reason": "Lab proxy evidence is not Product signoff; thermal honesty is GAP.",
        },
        "product_signoff": False,
        "product_win": False,
        "productWin": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "comparison_scope": "not-comparable",
        "comparison": {
            "comparable_to_gold_ir": False,
            "reason": "Proxy mesh and analytical oracle are not a Product gold-IR comparison.",
        },
        "input_artifacts": [_relative_or_absolute(recipe_path)],
        "input_artifact_refs": [
            {
                "kind": "recipe",
                "path": _relative_or_absolute(recipe_path),
                "sha256": recipe_hash,
            }
        ],
        "output_artifacts": [_relative_or_absolute(output)],
        "report_paths": [_relative_or_absolute(output)],
        "ir_report_paths": [_relative_or_absolute(output)],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "native_tools_used": [],
        },
        "tool_versions": {PROXY_TOOL_ID: "1.0", "python": platform.python_version()},
        "wrote_finish": False,
        "finish_write": False,
        "chip_emit": {
            "allowed": False,
            "reason": "Ladder A is not stamped; *_chip mesh IDs remain GAP-reserved.",
        },
        "research": {
            "ladder": "B",
            "claim_class": "PROXY",
            "lab_only": True,
            "independent_of_upstream_backside_ingest": True,
        },
        "report_path": _relative_or_absolute(output),
    }
    return report


def write_report(path: Path, report: Mapping[str, Any]) -> Path:
    """Atomically write a generated JSON report after safety validation."""
    path = _safe_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            Path(temporary).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def _input_mapping(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if args.input_json:
        input_path = Path(args.input_json).expanduser().resolve()
        try:
            raw = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProxyContractError(f"cannot read --input-json: {input_path}") from exc
        if not isinstance(raw, dict):
            raise ProxyContractError("--input-json must contain an object")
        values.update(raw)
    for name in (
        "n_r",
        "n_sources",
        "grid_pitch_um",
        "rail_length_um",
        "rail_model_id",
        "rail_r_ohm_per_um",
        "via_model_id",
        "via_r_ohm",
        "thermal_model_id",
        "current_a",
        "stack_id",
        "bm_model_id",
        "bump_model_id",
        "load_model_id",
        "pdk_rev",
    ):
        value = getattr(args, name)
        if value is not None:
            values[name] = value
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="lab_asap7_gcd_tc_rvt_nldm_7p5_480ps")
    parser.add_argument("--run-id")
    parser.add_argument("--mesh-id", default="asap7_bspdn_proxy_m89")
    parser.add_argument("--recipe-id", default=RECIPE_ID)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--input-json", default="")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--n-r", dest="n_r", type=int)
    parser.add_argument("--n-sources", dest="n_sources", type=int)
    parser.add_argument("--grid-pitch-um", dest="grid_pitch_um", type=float)
    parser.add_argument("--rail-length-um", dest="rail_length_um", type=float)
    parser.add_argument("--rail-model-id", dest="rail_model_id")
    parser.add_argument("--rail-r-ohm-per-um", dest="rail_r_ohm_per_um", type=float)
    parser.add_argument("--via-model-id", dest="via_model_id")
    parser.add_argument("--via-r-ohm", dest="via_r_ohm", type=float)
    parser.add_argument("--thermal-model-id", dest="thermal_model_id")
    parser.add_argument("--current-a", dest="current_a", type=float)
    parser.add_argument("--stack-id", dest="stack_id")
    parser.add_argument("--bm-model-id", dest="bm_model_id")
    parser.add_argument("--bump-model-id", dest="bump_model_id")
    parser.add_argument("--load-model-id", dest="load_model_id")
    parser.add_argument("--pdk-rev", dest="pdk_rev")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.recipe_id != RECIPE_ID:
        raise ProxyContractError(
            f"unsupported recipe_id={args.recipe_id}; use {RECIPE_ID}"
        )
    if args.model_id != MODEL_ID:
        raise ProxyContractError(f"unsupported model_id={args.model_id}; use {MODEL_ID}")
    run_id = _run_id(args.run_id)
    inputs = ProxyInputs.from_mapping(_input_mapping(args))
    report = build_report(
        variant=args.variant,
        run_id=run_id,
        inputs=inputs,
        mesh_id=args.mesh_id,
        output_path=args.out,
    )
    path = write_report(args.out, report)
    print(
        "lab_asap7_bspdn_proxy",
        f"mesh_id={report['mesh_id']}",
        f"recipe_id={report['recipe_id']}",
        f"status={report['status']}",
        f"honesty={report['honesty']}",
        f"thermal_honesty={report['pillars']['thermal']['honesty']}",
        f"droop_proxy_mv={report['metrics']['droop_proxy_mv']:.6f}",
        f"out={path}",
        "product_win=false",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProxyContractError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
