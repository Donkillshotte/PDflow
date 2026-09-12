#!/usr/bin/env python3
"""Persist the current DSE result without importing data from another invocation.

The Studio view is deliberately a snapshot of the selected invocation. Any
design comparison must be produced by the current DSE controller from the
same input set and extract; this helper writes one current snapshot only.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"
DSE = ROOT / "learn/sim/dse"

KEYS = (
    "n_candidates",
    "n_f1",
    "n_f4",
    "n_f4_solve",
    "winning_static_mv",
    "winning_ir_pdn_mv",
    "ir_champ_amg_mv",
    "ir_champ_ras_mv",
    "ir_champ_krylov_mv",
    "ir_cell_champ_extract_mv",
    "ir_cell_champ_wns_ns",
    "spent_s",
)


def _number(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def snapshot_from_report(report: dict, *, role: str = "cook") -> dict:
    """Normalize one current report for the app-facing live snapshot."""
    shot = {
        "kind": "dse_live_run",
        "role": role,
        "ok": bool(report.get("ok")),
        "variant": report.get("variant") or "flowlab",
        "design_id": report.get("design_id") or "gcd",
        "run_id": report.get("run_id") or report.get("created_at") or time.time_ns(),
        "created_at": time.time(),
        "comparison_scope": "same-live-invocation",
        "summary": str(report.get("summary") or "")[:240],
    }
    for key in KEYS:
        value = report.get(key)
        shot[key] = int(value) if key.startswith("n_") and value is not None else (
            _number(value) if not key.startswith("n_") else None
        )
    return shot


def record(*, variant: str) -> dict:
    DSE.mkdir(parents=True, exist_ok=True)
    report = _read_json(REPORTS / f"dse_{variant}.json")
    if not report:
        return {"ok": False, "reason": "no current DSE report", "latest": None}
    shot = snapshot_from_report(report)
    path = DSE / f"live_run_{variant}.json"
    path.write_text(json.dumps(shot, indent=2) + "\n")
    return {"ok": True, "latest": shot, "path": str(path)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", default="flowlab")
    args = ap.parse_args()
    result = record(variant=args.variant)
    latest = result.get("latest") or {}
    print(
        f"DSE_LIVE_RUN ok={result.get('ok')} role={latest.get('role')} "
        f"ir={latest.get('winning_ir_pdn_mv')} n_cand={latest.get('n_candidates')}"
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
