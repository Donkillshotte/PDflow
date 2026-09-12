#!/usr/bin/env python3
"""Focused contract tests for the live package manifest."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pkg_manifest import build_manifest, parse_rdl, validate_variant


class PackageManifestTests(unittest.TestCase):
    def test_variant_validation_is_allowlisted(self) -> None:
        self.assertEqual(validate_variant("flowlab"), "flowlab")
        self.assertEqual(validate_variant("enterprise-e2e"), "enterprise-e2e")
        self.assertEqual(validate_variant("installer-e2e"), "installer-e2e")
        self.assertEqual(
            validate_variant("lab_asap7_gcd_tc_rvt_nldm_7p5_320ps"),
            "lab_asap7_gcd_tc_rvt_nldm_7p5_320ps",
        )
        with self.assertRaises(ValueError):
            validate_variant("../../flowlab")
        with self.assertRaises(ValueError):
            validate_variant("lab_asap7_bad/path")

    def test_rdl_parser_only_counts_configured_package_layers(self) -> None:
        text = """\
VERSION 5.8 ;
UNITS DISTANCE MICRONS 1000 ;
SPECIALNETS 2 ;
    - VDD ( BUMP_0_0 PAD ) + USE POWER
      + ROUTED metal4 100 ( 0 0 ) ( 100 0 )
      NEW M9 80 ( 100 0 ) ( 200 0 ) ;
    - clk ( BUMP_0_1 PAD ) + USE SIGNAL
      + ROUTED M9 40 ( 0 0 ) ( 200 0 ) ;
END SPECIALNETS
"""
        parsed = parse_rdl(text, rdl_layers={"M9"})
        self.assertEqual(parsed["route_segments"], 2)
        self.assertEqual(parsed["layers"], ["M9"])
        by_net = {row["net"]: row for row in parsed["nets"]}
        self.assertEqual(by_net["VDD"]["route_segments"], 1)
        self.assertTrue(by_net["clk"]["routed"])

    def test_build_manifest_requires_every_configured_net(self) -> None:
        config = {
            "vdd": 1.1,
            "package_interface": {
                "bump_array": {
                    "master": "DUMMY_BUMP",
                    "rows": 2,
                    "columns": 2,
                    "origin_um": [1.0, 1.0],
                    "pitch_um": [4.0, 4.0],
                    "power_layer": "M9",
                    "signal_layer": "M9",
                },
                "bump_map": [
                    {"instance": "BUMP_0_0", "net": "VDD", "class": "power"},
                    {"instance": "BUMP_0_1", "net": "VSS", "class": "ground"},
                    {"instance": "BUMP_1_0", "net": "clk", "class": "signal"},
                ],
            },
            "package": {
                "n_bumps": 2,
                "r_bump": 0.01,
                "l_bump": 0.1e-9,
                "r_pkg": 0.02,
                "l_pkg": 0.2e-9,
                "c_pkg": 40e-12,
            },
        }
        finish_def = """\
VERSION 5.8 ;
UNITS DISTANCE MICRONS 1000 ;
DIEAREA ( 0 0 ) ( 10000 8000 ) ;
PINS 3 ;
    - VDD + NET VDD + DIRECTION INOUT + USE POWER ;
    - VSS + NET VSS + DIRECTION INOUT + USE GROUND ;
    - clk + NET clk + DIRECTION INPUT + USE SIGNAL ;
END PINS
"""
        rdl_def = """\
VERSION 5.8 ;
UNITS DISTANCE MICRONS 1000 ;
COMPONENTS 3 ;
    - BUMP_0_0 DUMMY_BUMP + FIXED ( 1000 1000 ) N ;
    - BUMP_0_1 DUMMY_BUMP + FIXED ( 1000 5000 ) N ;
    - BUMP_1_0 DUMMY_BUMP + FIXED ( 5000 1000 ) N ;
END COMPONENTS
SPECIALNETS 3 ;
    - VDD ( BUMP_0_0 PAD ) + USE POWER
      + ROUTED M9 80 ( 1000 1000 ) ( 2000 1000 ) ;
    - VSS ( BUMP_0_1 PAD ) + USE GROUND
      + ROUTED M9 80 ( 1000 5000 ) ( 2000 5000 ) ;
    - clk ( BUMP_1_0 PAD ) + USE SIGNAL
      + ROUTED M9 40 ( 5000 1000 ) ( 6000 1000 ) ;
END SPECIALNETS
"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            finish = root / "finish"
            finish.mkdir()
            (finish / "6_final.odb").write_bytes(b"odb")
            (finish / "6_final.def").write_text(finish_def)
            rdl = root / "rdl.def"
            rdl.write_text(rdl_def)
            rdl_odb = root / "rdl.odb"
            rdl_odb.write_bytes(b"sidecar")
            report = root / "learn/sim/reports/system_pdn_flowlab.json"
            report.parent.mkdir(parents=True)
            report.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "engine": "ngspice",
                        "transient": {"droop_mv": 4.0, "droop_pct": 0.4},
                        "impedance": {
                            "z_max_mohm": 60.0,
                            "f_at_zmax_hz": 1e6,
                            "z_target_mohm": 80.0,
                            "pass_target": True,
                        },
                    }
                )
            )
            manifest = build_manifest(
                root,
                "flowlab",
                config=config,
                finish_dir=finish,
                rdl_def=rdl,
                rdl_odb=rdl_odb,
            )
        self.assertEqual(manifest["status"], "PROXY")
        self.assertTrue(manifest["evidence_ok"])
        self.assertEqual(manifest["rdl"]["routed_nets"], ["VDD", "VSS", "clk"])
        self.assertEqual(manifest["bump_array"]["observed_component_count"], 3)
        self.assertEqual(manifest["bump_array"]["configured_observed_count"], 3)
        self.assertTrue(manifest["bump_array"]["mapping_complete"])
        self.assertFalse(manifest["product_signoff"])


if __name__ == "__main__":
    unittest.main()
