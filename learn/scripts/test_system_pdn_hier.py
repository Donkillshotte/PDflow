#!/usr/bin/env python3
"""Focused regression tests for the hierarchical System PDN contract."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from system_pdn_hier import (  # noqa: E402
    ConfigError,
    _decode_ac,
    _decode_tran,
    _ladder,
    _validate_variant,
    analyze,
    load_cfg,
    validate_config,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok  {message}")


def main() -> int:
    cfg = load_cfg(ROOT / "learn/system_pdn/default.json")
    warnings = validate_config(cfg)
    check(cfg["schema_version"] == 2, "default config uses schema version 2")
    check(any("ESL" in warning for warning in warnings), "default model declares missing capacitor ESL")

    asap7_cfg = load_cfg(ROOT / "learn/lab/asap7/pkg/asap7_system_pdn.json")
    validate_config(asap7_cfg)
    check(abs(asap7_cfg["vdd"] - 0.70) < 1e-12, "legacy ASAP7 package config remains supported")
    check("V_VRM n_vrm_src 0 DC 0.7" in "\n".join(_ladder(asap7_cfg)), "ASAP7 uses the same hierarchical ladder engine")
    check(_validate_variant("lab_asap7_tc-480ps") == "lab_asap7_tc-480ps", "variant names remain path-safe")
    try:
        _validate_variant("../outside")
    except ConfigError:
        print("ok  path traversal variants are rejected")
    else:
        check(False, "path traversal variants are rejected")

    ladder = "\n".join(_ladder(cfg))
    check("R_ESR_VRM n_vrm_l" in ladder, "VRM ESR is inside a shunt decap branch")
    check("C_VRM n_vrm_l_vrm_esr 0" in ladder, "VRM capacitor returns to ground")
    check("R_PLANE n_vrm_l n_board" in ladder, "board plane starts after the VRM output node")
    check("L_PLANE n_board n_board_out" in ladder, "board plane inductance remains in the forward path")
    check("R_ESR_VRM n_vrm_l n_board_in" not in ladder, "legacy series-ESR topology is absent")

    custom = deepcopy(cfg)
    custom["package"]["decaps"] = [
        {
            "name": "local",
            "c_f": 100e-12,
            "esr_ohm": 0.01,
            "esl_h": 0.2e-9,
            "node": "pkg",
            "spice_label": "pkg_local",
        }
    ]
    custom_ladder = "\n".join(_ladder(custom))
    check("L_ESL_PKG_LOCAL" in custom_ladder, "custom package ESL is emitted")
    check("C_PKG_LOCAL" in custom_ladder and "n_pkg_l" in custom_ladder, "custom package decap accepts node aliases")

    duplicate = deepcopy(cfg)
    duplicate["die"]["decaps"] = [{"c_f": 1e-12, "spice_label": "VRM"}]
    try:
        validate_config(duplicate)
    except ConfigError as exc:
        check("duplicate SPICE decap label" in str(exc), "duplicate SPICE labels fail validation")
    else:
        check(False, "duplicate SPICE labels fail validation")

    tran_rows = [
        [0.0, 1.1, 0.0, 1.1, 0.0, 1.1, 0.0, 1.1],
        [20e-9, 1.099, 1.098, 1.097, 1.096],
        [22e-9, 1.098, 1.096, 1.095, 1.090],
        [80e-9, 1.099, 1.098, 1.097, 1.095],
        [102e-9, 1.099, 1.098, 1.097, 1.096],
    ]
    ac_rows = [
        [1e3, 0.01, 0.0, 1e3, 0.01],
        [1e4, 0.2, 0.0, 1e4, 0.2],
        [1e5, 0.03, 0.0, 1e5, 0.03],
        [1e6, 0.04, 0.0, 1e6, 0.04],
    ]
    tran = _decode_tran(tran_rows)
    ac = _decode_ac(ac_rows)
    check(len(tran) == 5 and len(ac) == 4, "wrdata decoders accept pair and complex AC rows")
    report = analyze(cfg, tran_rows, ac_rows, 0.002, run_id="unit")
    check(report["evidence_ok"] is True, "synthetic report has live evidence")
    check(report["transient"]["droop_mv"] > 0, "synthetic transient reports positive die droop")
    check(report["impedance"]["resonance_peaks"], "synthetic AC report exposes resonance peaks")
    check(report["target_impedance"]["configured_pass"] is False, "target exceedance is explicit")
    check(report["product_signoff"] is False, "compact System PDN is not product signoff")

    derived_only = deepcopy(cfg)
    derived_only["ac"].pop("z_target_mohm")
    derived_only["target"]["rail_ripple_pct"] = 0.0001
    derived_only["target"]["vrm_regulation_pct"] = 0.0
    derived_report = analyze(derived_only, tran_rows, ac_rows, 0.002, run_id="derived")
    check(derived_report["target_impedance"]["derived_pass"] is False, "derived target is a real requirement when configured target is absent")
    check(derived_report["requirement_ok"] is False, "derived target miss affects overall requirement status")

    empty_report = analyze(cfg, [], [], 0.002, run_id="empty")
    check(empty_report["status"] == "FAIL" and empty_report["evidence_class"] == "GAP", "empty measurements are classified as a data gap")

    print("ALL test_system_pdn_hier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
