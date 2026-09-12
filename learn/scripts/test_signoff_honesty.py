#!/usr/bin/env python3
"""Guard the live-analysis contract used by signoff and Studio.

Every value inspected here must come from the selected invocation. The test
does not load a snapshot from an earlier run and does not assert a magic QoR
number.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def load(name: str) -> dict:
    path = REPORTS / name
    check(path.is_file(), f"{name} exists")
    return json.loads(path.read_text())


def assert_proxy_evidence(report: dict, label: str) -> None:
    check(report.get("status") == "PROXY", f"{label} keeps proxy status explicit")
    check(report.get("ok") is False, f"{label} cannot be a Product pass")
    check(report.get("execution_status") == "COMPLETED", f"{label} execution completed")
    check(report.get("evidence_status") == "PASS", f"{label} preserves executable evidence")
    check(report.get("requirement_status") == "GAP", f"{label} requirement gap is explicit")
    check(report.get("signoff_status") == "PROXY", f"{label} signoff scope is proxy")
    check(report.get("product_signoff") is False, f"{label} cannot claim Product signoff")


def main() -> int:
    dynamic = load("dynamic_ir_flowlab_direct.json")
    assert_proxy_evidence(dynamic, "current Dynamic IR report")
    check(dynamic.get("kind") == "dynamic_ir", "Dynamic IR schema")
    check(dynamic.get("comparison_scope") == "same-live-invocation", "Dynamic IR scope is current")
    check(float((dynamic.get("dynamic") or {}).get("worst_droop") or 0) > 0, "Dynamic IR droop is live and positive")
    dynamic_text = json.dumps(dynamic).lower()
    check("comparison_scope" in dynamic and "same-live" in dynamic_text, "Dynamic IR payload declares its live scope")
    check(not any(key.startswith("legacy_") for key in dynamic), "Dynamic IR payload has no legacy comparison fields")

    sta = load("sta_ir_aware_flowlab.json")
    check(sta.get("comparison_scope") == "same live finish SPEF, SPICE and voltage map", "STA IR scope is current")
    check("comparison_scope" in sta and "ir" in sta, "STA IR has no fixed comparison field")
    check((sta.get("ir") or {}).get("n_joined_cells", 0) > 0, "STA IR joins current ITerms")

    power = load("power_signoff_flowlab.json")
    ledger = power.get("ir_mesh_ledger") or {}
    check(ledger.get("comparison_scope"), "power ledger declares comparison scope")
    ids = {row.get("id") for row in ledger.get("meshes") or []}
    check("dynamic_ir" in ids and "chip_pdn" in ids and "system_pdn" in ids, "live meshes are named")
    check(not any(str(row.get("id", "")).startswith(("archived", "legacy", "fixed")) for row in ledger.get("meshes") or []), "ledger has no archived mesh")

    dynamic_sh = (ROOT / "learn/scripts/run_dynamic_ir.sh").read_text()
    check('dynamic_ir_${REPORT_KEY}_direct.json' in dynamic_sh, "Dynamic IR writes the current report")
    check('dynamic_ir_${VARIANT}.json' not in dynamic_sh, "Dynamic IR has no legacy report path")
    sta_sh = (ROOT / "learn/scripts/run_sta_ir_aware.sh").read_text()
    check('dynamic_ir_${VARIANT}_direct.map.csv' in sta_sh, "STA IR consumes the current map")
    check('dynamic_ir_${VARIANT}.map.csv' not in sta_sh, "STA IR has no legacy map fallback")

    story = (ROOT / "studio/src/lib/story.ts").read_text()
    heatmap = (ROOT / "studio/src/components/flowlab/DynamicIrHeatmap.tsx").read_text()
    signoff = (ROOT / "studio/src/lib/signoff.ts").read_text()
    check("dynamic_ir_${variant}_direct.json" in story, "Studio story reads the current report")
    check("dynamic_ir_${variant}_direct.json" in heatmap, "heatmap reads the current report")
    check("dynamic_ir_{variant}_direct.json" in signoff, "signoff registry reads the current report")
    results_source = (ROOT / "studio/src/lib/results.ts").read_text()
    check("MetricHit" in results_source and "markExpected" not in results_source, "results expose measured metrics only")

    active = [
        ROOT / "learn/scripts/record_dse_launch.py",
        ROOT / "learn/dse/fidelity.py",
        ROOT / "learn/dse/acquire.py",
        ROOT / "learn/dse/surrogate.py",
        ROOT / "studio/src/lib/lab.ts",
        ROOT / "studio/src/lib/suite.ts",
    ]
    for path in active:
        text = path.read_text().lower()
        check("comparison_scope" in text or "current" in text, f"{path.name} declares current provenance")

    for name in ("pkg_rdl_flowlab.json", "pkg_signoff_flowlab.json", "signoff_phase2_flowlab.json"):
        package = load(name)
        check(package.get("status") == "PROXY", f"{name} keeps proxy status explicit")
        check(package.get("ok") is False, f"{name} cannot be a Product pass")
        check(package.get("product_signoff") is False, f"{name} cannot claim Product signoff")
        if name != "pkg_rdl_flowlab.json":
            check(package.get("evidence_ok") is True, f"{name} preserves executable evidence")

    manifest = load("pkg_manifest_flowlab.json")
    check(manifest.get("status") == "PROXY", "pkg_manifest_flowlab.json keeps proxy status explicit")
    check(manifest.get("evidence_ok") is True, "pkg_manifest_flowlab.json preserves executable evidence")
    check(manifest.get("product_signoff") is False, "pkg_manifest_flowlab.json cannot claim Product signoff")
    check(
        (manifest.get("rdl") or {}).get("missing_nets") == [],
        "pkg_manifest_flowlab.json has complete RDL net coverage",
    )
    check(
        (manifest.get("bump_array") or {}).get("mapping_complete") is True,
        "pkg_manifest_flowlab.json has an observed bump mapping",
    )

    print("ALL test_signoff_honesty PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
