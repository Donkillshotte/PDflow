#!/usr/bin/env python3
"""Unit tests for requirement/evidence separation in signoff evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn" / "scripts"))

from signoff_eval import (  # noqa: E402
    evaluate_equivalence,
    evaluate_geometry,
    evaluate_power,
    evaluate_timing,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL " + message)
    print("ok  " + message)


def timing_policy() -> dict[str, float]:
    return {
        "wns_ns_min": 0.0,
        "tns_min": 0.0,
        "setup_violations_max": 0.0,
        "period_min_ns_min": 0.0,
    }


def main() -> int:
    context = {"policy": timing_policy(), "policy_source": "test"}
    failed = evaluate_timing(
        {"wns_ns": -0.15, "tns": -5.06, "setup_violations": 43},
        context,
    )
    check(failed["status"] == "FAIL", "negative WNS/TNS and setup violations fail timing")
    check(failed["ok"] is False, "failed timing cannot produce ok=true")
    check(all(item["evidence_ok"] for item in failed["checks"]), "parseable failing timing remains valid evidence")

    passed = evaluate_timing(
        {"wns_ns": 0.01, "tns": 0.0, "setup_violations": 0},
        context,
    )
    check(passed["status"] == "PASS", "timing passes only when every mandatory target passes")
    check(passed["ok"] is True, "complete timing evidence can close its pillar")

    missing = evaluate_timing({"wns_ns": 0.01}, context)
    check(missing["status"] == "GAP", "missing mandatory timing data is GAP")
    check("tns" in missing["missing"], "missing timing field is named")

    geometry = evaluate_geometry(
        {"route_drc_violations": 0, "gds_drc_violations": 2},
        {
            "policy": {
                "route_drc_violations_max": 0,
                "gds_drc_violations_max": 0,
            },
            "policy_source": "test",
        },
    )
    check(geometry["status"] == "FAIL", "non-zero GDS DRC fails geometry")

    power = evaluate_power(
        {"chip_static_ir_mv": 2.1, "chip_transient_droop_mv": 19.4},
        {"policy": {}, "policy_source": "test"},
    )
    check(power["status"] == "GAP", "power measurements without declared limits are GAP")
    check(power["ok"] is False, "power evidence without limits cannot close signoff")

    equivalence = evaluate_equivalence(
        {"lvs_pass": True},
        {"policy": {"lvs_pass_required": True}, "policy_source": "test"},
    )
    check(equivalence["status"] == "PASS", "typed LVS pass meets the declared policy")

    print("ALL test_signoff_policy PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
