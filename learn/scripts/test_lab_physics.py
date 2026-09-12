#!/usr/bin/env python3
"""Tests for live-only physical validation."""

from __future__ import annotations

import json
from pathlib import Path

from validate_lab_physics import _evidence_usable, validate

ROOT = Path(__file__).resolve().parents[2]


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    check(
        _evidence_usable({"status": "PROXY", "ok": False, "evidence_status": "PASS"}),
        "PROXY report with PASS evidence remains measurement-usable",
    )
    check(
        not _evidence_usable({"status": "PROXY", "ok": False, "evidence_status": "GAP"}),
        "PROXY report with GAP evidence remains unusable",
    )
    report = validate()
    by = {row["id"]: row for row in report["checks"]}
    check(report["ok"] is True, "live validator has no FAIL checks")
    check("live_dynamic_ir" in by and by["live_dynamic_ir"]["ok"], "current Dynamic IR is positive")
    check("solver_direct_vs_amg" in by and by["solver_direct_vs_amg"]["ok"], "DirectLU and AMG agree on this extract")
    check("sta_ir_path" in by and by["sta_ir_path"]["ok"], "STA IR path is joined on current artifacts")
    if "sta_ir_reconstruct" in by:
        check(by["sta_ir_reconstruct"]["ok"], "STA IR delay reconstructs from current path gates")
    if "sta_ir_alpha_law" in by:
        check(by["sta_ir_alpha_law"]["ok"], "STA IR uses the declared voltage law")
    check(not any(key.startswith(("legacy_", "fixed_")) for key in report), "validator has no persisted metric fields")
    for row in report["checks"]:
        check("comparison" not in row["id"].lower(), f"check id is measurement-only: {row['id']}")

    ledger = json.loads((ROOT / "learn/sim/reports/power_signoff_flowlab.json").read_text())
    embedded = ledger.get("ir_mesh_ledger") or {}
    check("comparison_scope" in embedded, "power report embeds comparison scope")
    ids = {m.get("id") for m in embedded.get("meshes") or []}
    check("dynamic_ir" in ids, "ledger names current Dynamic IR")
    check("chip_pdn" in ids, "ledger names current chip mesh")
    check(not any(str(mesh_id).startswith(("legacy_", "fixed_")) for mesh_id in ids), "ledger has no persisted mesh")
    check("comparison_scope" in embedded, "ledger explicitly declares scope")
    print("ALL test_lab_physics PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
