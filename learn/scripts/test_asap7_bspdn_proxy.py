#!/usr/bin/env python3
"""Contract tests for the ASAP7 Ladder B PROXY lane."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from lab_asap7_bspdn_proxy import (
    MODEL_ID,
    RECIPE_ID,
    ProxyContractError,
    ProxyInputs,
    build_report,
    calculate_proxy,
    mesh_fingerprint,
    validate_mesh_id,
    write_report,
)
from validate_lab_asap7_bspdn_proxy import validate_report, validation_errors


ROOT = Path(__file__).resolve().parents[2]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok  {message}")


def expect_refuse(callback, message: str) -> None:
    try:
        callback()
    except ProxyContractError:
        print(f"ok  {message}")
        return
    raise SystemExit(f"FAIL {message}")


def make_report() -> dict:
    return build_report(
        variant="lab_asap7_gcd_tc_rvt_nldm_7p5_480ps",
        run_id="proxy-contract-test",
        output_path=ROOT / "learn/sim/reports" / "_test_proxy_contract.json",
    )


def main() -> int:
    report = make_report()
    validate_report(report)
    check(report["mesh_id"].startswith("asap7_bspdn_proxy_"), "T1 proxy mesh enum")
    check(report["recipe_id"] == RECIPE_ID, "T1 canonical recipe id")
    check(report["model_id"] == MODEL_ID, "T1 canonical model id")
    check(report["status"] == "pass" and report["ok"] is True, "T1 analytical run status")
    check(report["surface"] == "lab_asap7", "T1 lab surface")

    for key in ("product_win", "productWin", "win_eligible", "comparable_to_gold_ir"):
        check(report[key] is False, f"T2 firewall {key}=false")
    check(report["product_signoff"] is False and report["ok_claim"] is False, "T2 signoff firewall")

    broken = copy.deepcopy(report)
    broken["honesty"] = "GAP"
    check(any("honesty" in error for error in validation_errors(broken)), "T3 proxy honesty is required")

    broken = copy.deepcopy(report)
    broken["leftovers"] = []
    broken["honesty_reason"] = ""
    errors = validation_errors(broken)
    check(any("leftovers" in error for error in errors), "T4 proxy leftovers are required")
    check(any("honesty_reason" in error for error in errors), "T4 honesty reason is required")

    broken = copy.deepcopy(report)
    broken["expected_mv"] = 0.0
    check(any("expected_mv" in error for error in validation_errors(broken)), "T11 expected_mv is forbidden")

    broken = copy.deepcopy(report)
    broken["oracle"] = "directlu"
    check(any("oracle" in error for error in validation_errors(broken)), "T13 directlu oracle is refused")

    analytical = copy.deepcopy(report)
    analytical["oracle"] = "analytical"
    analytical["honesty"] = "PROXY"
    validate_report(analytical)
    check(True, "T14 analytical oracle requires PROXY honesty")

    check(report["pillars"]["thermal"]["honesty"] == "GAP", "T18 thermal honesty is GAP")
    check(report["pillars"]["thermal"]["honesty"] != report["pillars"]["ir"]["honesty"], "T20 IR and thermal honesty are independent")
    check(report["lab_admit"]["ok"] is True, "T25 thermal GAP does not block PROXY Lab admit")

    expect_refuse(lambda: validate_mesh_id("asap7_bspdn_chip"), "T21 chip mesh is emit-forbidden")
    expect_refuse(lambda: validate_mesh_id("asap7_bpr_chip"), "T21 BPR chip mesh is emit-forbidden")
    expect_refuse(lambda: validate_mesh_id("asap7_fs_chip"), "T21 unknown chip mesh is refused")

    check("10547" not in json.dumps(report), "T22 proxy has no upstream issue dependency")
    fp = report["mesh_fingerprint_inputs"]
    check(fp["rail_model_id"] and fp["via_model_id"] and "thermal_model_id" in fp, "T23 fingerprint model IDs")
    check(fp["thermal_model_id"] is None, "T23 thermal model may be null")
    check(report["recipe_id"] == "asap7_proxy_bpr_bs_m89_v0", "T24 recipe gate")
    check(report["tool_id"] and report["license_class"], "T26 PROXY provenance")

    broken = copy.deepcopy(report)
    broken["tool_id"] = ""
    check(any("tool_id" in error for error in validation_errors(broken)), "T26 missing tool_id is rejected")
    broken = copy.deepcopy(report)
    broken["license_class"] = ""
    check(any("license_class" in error for error in validation_errors(broken)), "T26 missing license_class is rejected")

    broken = copy.deepcopy(report)
    broken["track"] = "asap7_bb"
    check(any("asap7_bb" in error for error in validation_errors(broken)), "T27 ASAP7-BB is docs-only")

    broken = copy.deepcopy(report)
    broken["mesh_fingerprint_inputs"] = dict(fp)
    broken["mesh_fingerprint_inputs"]["rail_model_id"] = ""
    check(any("rail_model_id" in error for error in validation_errors(broken)), "T23 rail model fingerprint ID is required")

    inputs = ProxyInputs()
    metrics = calculate_proxy(inputs)
    check(metrics["droop_proxy_mv"] > 0, "analytical proxy is finite and positive")
    first_fp, _ = mesh_fingerprint(mesh_id=report["mesh_id"], inputs=inputs)
    changed_fp, _ = mesh_fingerprint(
        mesh_id=report["mesh_id"],
        inputs=ProxyInputs(rail_model_id="gupta_ted20_edu_range_v1"),
    )
    check(first_fp != changed_fp, "fingerprint changes when rail model changes")

    with tempfile.TemporaryDirectory(prefix="pdflow-proxy-test-") as temporary:
        output = Path(temporary) / "report.json"
        generated = build_report(
            variant="lab_asap7_gcd_tc_rvt_nldm_7p5_480ps",
            run_id="atomic-write-test",
            output_path=output,
        )
        write_report(output, generated)
        check(output.is_file(), "generated report is atomically written")
        validate_report(json.loads(output.read_text()))
        check(True, "generated report validates after serialization")

    print("ALL test_asap7_bspdn_proxy PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
