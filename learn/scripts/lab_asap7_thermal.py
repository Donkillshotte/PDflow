#!/usr/bin/env python3
"""Emit an explicit ASAP7 Lab thermal GAP row.

No temperature oracle is synthesized here.  A future HotSpot PROXY must be a
separate reviewed run carrying its own model_id and powermap_kind.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from lab_asap7_bspdn_proxy import ProxyContractError, validate_mesh_id, validate_variant


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_thermal.json"
THERMAL_REPORT_RE = re.compile(r"^lab_asap7_thermal(?:_[a-z0-9][a-z0-9_.+-]*)?\.json$")


def build_report(
    *,
    variant: str,
    run_id: str | None = None,
    mesh_id: str = "asap7_bspdn_proxy_m89",
) -> dict[str, Any]:
    variant = validate_variant(variant)
    mesh_id = validate_mesh_id(mesh_id)
    run_id = run_id or os.environ.get("PD_FLOW_RUN_ID") or f"thermal-gap-{variant}"
    if not isinstance(run_id, str) or not run_id.strip() or "/" in run_id or ".." in run_id:
        raise ProxyContractError("run_id is invalid")
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    leftovers = [
        {
            "id": "thermal_model_missing",
            "message": "No reviewed compact HotSpot model was executed for this ASAP7 proxy.",
        },
        {
            "id": "temperature_oracle_forbidden",
            "message": "No fixed Celsius threshold or temperature oracle is emitted.",
        },
    ]
    return {
        "schema_version": 1,
        "report_id": f"asap7-thermal-gap-{variant}",
        "run_id": run_id,
        "created_at": now,
        "scope": "lab",
        "surface": "lab_asap7",
        "platform": "asap7",
        "track": "asap7_bspdn",
        "variant": variant,
        "status": "not_run",
        "ok": False,
        "tool_id": "hotspot_compact",
        "license_class": "not_run",
        "mesh_id": mesh_id,
        "topology": "proxy",
        "honesty": "GAP",
        "honesty_reason": "Thermal model is not part of the current Ladder B run.",
        "ok_claim": False,
        "product_win": False,
        "productWin": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "pillars": {
            "thermal": {
                "status": "not_run",
                "honesty": "GAP",
                "honesty_reason": "No reviewed compact HotSpot model was executed.",
                "model_id": None,
                "powermap_kind": None,
                "leftovers": leftovers,
            }
        },
        "thermal": {
            "status": "not_run",
            "honesty": "GAP",
            "model_id": None,
            "powermap_kind": None,
            "leftovers": leftovers,
        },
        "leftovers": leftovers,
        "signoff_all": {"ok": False, "reason": "Thermal GAP cannot be signoff."},
        "lab_admit": {"ok": False, "reason": "Thermal-only row is not an IR admission row."},
        "report_paths": ["learn/sim/reports/lab_asap7_thermal.json"],
        "results_dir": (
            "tools/OpenROAD-flow-scripts/flow/results/asap7/"
            f"{'gcd' if '_gcd_' in variant else 'asap7-lab-design'}/"
            "lab_asap7_bspdn_proxy_m89"
        ),
        "wrote_finish": False,
        "finish_write": False,
    }


def write_report(path: Path, report: dict[str, Any]) -> Path:
    path = path.expanduser().resolve()
    if path.name != "lab_asap7_thermal.json" and not THERMAL_REPORT_RE.fullmatch(path.name):
        raise ProxyContractError("thermal report filename is not allowlisted")
    if path.suffix != ".json":
        raise ProxyContractError("thermal output must be JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with open(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        Path(temporary).replace(path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="lab_asap7_gcd_tc_rvt_nldm_7p5")
    parser.add_argument("--run-id")
    parser.add_argument("--mesh-id", default="asap7_bspdn_proxy_m89")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        report = build_report(variant=args.variant, run_id=args.run_id, mesh_id=args.mesh_id)
        output = write_report(args.out, report)
    except (OSError, ProxyContractError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(
        "lab_asap7_thermal",
        f"mesh_id={report['mesh_id']}",
        "status=not_run",
        "honesty=GAP",
        f"out={output}",
        "product_win=false",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
