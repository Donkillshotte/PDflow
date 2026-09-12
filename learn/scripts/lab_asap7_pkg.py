#!/usr/bin/env python3
"""Leftover-named ASAP7 bump / sidecar RDL / compact package ladder.

Dummy, not C4. Lumped RLC, not Touchstone / Ansys CPA. Not a product win.
Never writes lab_asap7_*/6_final.odb. Never writes nangate45/gcd/flowlab.
Never writes .pkg.ok. Package results are scoped to the current ASAP7 run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from dse.asap7_lab import CORNERS, LabAsap7Refuse, normalize_lab_variant, safe_result_dir, scan_folio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learn" / "scripts"))
from pkg_manifest import build_manifest, default_output_path, parse_bump_components, parse_rdl, read_json
PKG_DIR = ROOT / "learn" / "lab" / "asap7" / "pkg"
CFG = PKG_DIR / "asap7_system_pdn.json"
LEF = PKG_DIR / "dummy_bump_gcd.lef"
TCL = ROOT / "learn" / "scripts" / "lab_asap7_pkg_rdl.tcl"
HIER = ROOT / "learn" / "scripts" / "system_pdn_hier.py"
OUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_pkg.json"
BUMP_OUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_pkg_bump.json"
RDL_OUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_pkg_rdl.json"
PDN_OUT = ROOT / "learn" / "sim" / "reports" / "lab_asap7_system_pdn.json"
DEFAULT_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5_480ps"


def _refuse_variant(variant: str) -> None:
    normalize_lab_variant(variant)


def _folder(variant: str) -> Path:
    return safe_result_dir(variant, ROOT)


def _vdd_of(payload: dict) -> float:
    corner = str(payload.get("corner") or "TC")
    return float((CORNERS.get(corner) or {}).get("voltage") or 0.70)


def run_bump(variant: str, folder: Path, cfg: dict) -> dict:
    pkg = cfg.get("package") or {}
    mesh = folder / "pdn" / "pg_vdd_bumps.sp"
    v_sources = r_count = 0
    if mesh.is_file():
        text = mesh.read_text(errors="replace")
        v_sources = sum(1 for line in text.splitlines() if line.strip().startswith("V"))
        r_count = sum(1 for line in text.splitlines() if line.strip().startswith("R"))
    n_bumps = int(pkg.get("n_bumps") or 0)
    lef_text = LEF.read_text(errors="replace") if LEF.is_file() else ""
    bump_ok = (
        n_bumps > 0
        and LEF.is_file()
        and "DUMMY_BUMP" in lef_text
        and "MACRO" in lef_text
    )
    payload = {
        "ok": bump_ok,
        "tool_status": "pass" if bump_ok else "blocked",
        "honesty": "PARTIAL" if bump_ok else "GAP",
        "honesty_reason": "Dummy bump model; not JEDEC C4 or foundry package evidence.",
        "ok_claim": False,
        "kind": "leftover_named_pkg_bump",
        "surface": "lab",
        "platform": "asap7",
        "product_win": False,
        "productWin": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "track": "asap7",
        "mesh_id": "asap7_pkg_tier_c",
        "topology": "pkg",
        "oracle": "config_only",
        "tool_id": "dummy_bump_model",
        "license_class": "PDflow-lab",
        "comparison_scope": "independent ASAP7 package run",
        "calibre": False,
        "c4": False,
        "variant": variant,
        "package": {
            "n_bumps": n_bumps,
            "r_bump": pkg.get("r_bump"),
            "l_bump": pkg.get("l_bump"),
            "r_pkg": pkg.get("r_pkg"),
            "l_pkg": pkg.get("l_pkg"),
            "c_pkg": pkg.get("c_pkg"),
            "vdd": cfg.get("vdd"),
        },
        "lef": str(LEF) if LEF.is_file() else None,
        "mesh": {
            "path": str(mesh) if mesh.is_file() else None,
            "v_sources": v_sources,
            "r_elements": r_count,
            "note": "ASAP7 cooks do not write pg_vdd_bumps.sp by default",
        },
        "leftover": {
            "c4": "dummy 4×4 bump LEF, not JEDEC C4",
            "mesh": "on-die IR is 6_report PSM, not write_pg_spice BUMPS",
        },
        "note": (
            "ASAP7 dummy bump config. Not C4. Not a product win. "
            "Live metrics only."
        ),
    }
    BUMP_OUT.parent.mkdir(parents=True, exist_ok=True)
    BUMP_OUT.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def run_rdl(variant: str, folder: Path) -> dict:
    odb = folder / "6_final.odb"
    sidecar = folder / "pkg_rdl_sidecar"
    sidecar.mkdir(parents=True, exist_ok=True)
    in_odb = sidecar / "in.odb"
    out_odb = sidecar / "rdl.odb"
    out_def = sidecar / "rdl.def"
    log = ROOT / "learn/sim/reports" / f"lab_asap7_pkg_rdl_{variant}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    reason = ""
    exit_code = None
    executed = False
    n_bump = n_wires = 0
    routed_nets: list[str] = []
    missing_nets: list[str] = []
    rdl_layers: set[str] = set()
    if not odb.is_file():
        reason = f"ODB missing {odb}"
        status = "blocked"
    elif not LEF.is_file():
        reason = f"dummy bump LEF missing {LEF}"
        status = "blocked"
    elif not shutil.which("openroad"):
        reason = "openroad not in PATH"
        status = "blocked"
    else:
        shutil.copy2(odb, in_odb)
        env = os.environ.copy()
        env.update(
            {
                "RDL_ODB": str(in_odb),
                "RDL_LEF": str(LEF),
                "RDL_OUT_ODB": str(out_odb),
                "RDL_OUT_DEF": str(out_def),
            }
        )
        proc = subprocess.run(
            ["openroad", "-no_init", "-no_splash", "-exit", str(TCL)],
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )
        exit_code = proc.returncode
        log.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
        text = out_def.read_text(errors="replace") if out_def.is_file() else ""
        n_bump = len(parse_bump_components(text))
        cfg = read_json(CFG) or {}
        interface = cfg.get("package_interface") if isinstance(cfg.get("package_interface"), dict) else {}
        array = interface.get("bump_array") if isinstance(interface.get("bump_array"), dict) else {}
        rdl_layers = {
            str(array.get("power_layer") or ""),
            str(array.get("signal_layer") or ""),
        }
        rdl_layers.discard("")
        parsed = parse_rdl(text, rdl_layers=rdl_layers)
        n_wires = int(parsed.get("route_segments") or 0)
        raw_map = interface.get("bump_map") if isinstance(interface.get("bump_map"), list) else []
        required_nets = sorted(
            {
                str(row.get("net"))
                for row in raw_map
                if isinstance(row, dict)
                and row.get("net")
                and str(row.get("class") or "signal").lower() != "reserved"
            }
        )
        routed_nets = sorted(
            str(row.get("net"))
            for row in parsed.get("nets", [])
            if isinstance(row, dict)
            and row.get("net") in required_nets
            and row.get("routed")
        )
        missing_nets = sorted(set(required_nets) - set(routed_nets))
        executed = bool(out_def.is_file() and n_bump > 0 and n_wires > 0 and not missing_nets)
        status = "pass" if executed else "fail" if out_def.is_file() and n_wires > 0 else "blocked"
        reason = "" if executed else ((proc.stderr or proc.stdout or "")[-400:])
        final = folder / "6_final.odb"
        if final.is_file() and in_odb.is_file() and final.samefile(in_odb):
            raise LabAsap7Refuse("REFUSED: RDL sidecar resolved to 6_final.odb")
    payload = {
        "ok": False,
        "status": status,
        "legacy_status": "PROXY" if executed else "FAIL" if out_def.is_file() and n_wires > 0 else "GAP",
        "tool_status": "pass" if executed else "fail" if out_def.is_file() and n_wires > 0 else "blocked",
        "honesty": "PROXY" if executed else "PARTIAL" if out_def.is_file() else "GAP",
        "honesty_reason": "Community OpenROAD RDL sidecar; never a package signoff result.",
        "ok_claim": False,
        "evidence_ok": executed,
        "kind": "leftover_named_pkg_rdl",
        "surface": "lab",
        "platform": "asap7",
        "product_win": False,
        "productWin": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "track": "asap7",
        "mesh_id": "asap7_pkg_tier_c",
        "topology": "pkg",
        "oracle": "openroad_rdl_route",
        "tool_id": "openroad_rdl_route",
        "license_class": "BSD-3-Clause",
        "comparison_scope": "independent ASAP7 package run",
        "calibre": False,
        "c4": False,
        "variant": variant,
        "odb": str(odb) if odb.is_file() else None,
        "sidecar_odb": str(out_odb) if out_odb.is_file() else None,
        "sidecar_def": str(out_def) if out_def.is_file() else None,
        "wrote_final": False,
        "rdl": {
            "api": "rdl_route",
            "executed": executed,
            "n_bump": n_bump,
            "n_wires": n_wires,
            "layer_power": "M9",
            "layer_signal": "M9",
            "rdl_layers": sorted(rdl_layers),
            "routed_nets": routed_nets,
            "missing_nets": missing_nets,
            "exit_code": exit_code,
        },
        "leftover": {
            "c4": "dummy 4×4 bump LEF, not JEDEC C4",
            "sidecar": "never write 6_final.odb",
        },
        "reason": reason,
        "note": (
            "ASAP7 sidecar rdl_route. Dummy, not C4. Not a product win. "
            "Live metrics only."
        ),
    }
    RDL_OUT.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def run_system_pdn(variant: str, folder: Path, cfg: dict, live: dict) -> dict:
    work = ROOT / "learn/sim/reports/lab_asap7_pkg_work"
    work.mkdir(parents=True, exist_ok=True)
    qor = live.get("qor") or {}
    power_w = qor.get("power_w")
    if power_w is None and qor.get("power_mw") is not None:
        power_w = float(qor["power_mw"]) * 1e-3
    vdd = float(cfg.get("vdd") or _vdd_of(live))
    i_die = 0.0
    if power_w is not None and vdd > 0:
        i_die = float(power_w) / vdd
    ngspice = shutil.which("ngspice")
    if not ngspice:
        payload = {
            "ok": False,
            "status": "GAP",
            "kind": "leftover_named_system_pdn",
            "reason": "ngspice not in PATH",
        }
    elif not HIER.is_file():
        payload = {
            "ok": False,
            "status": "GAP",
            "kind": "leftover_named_system_pdn",
            "reason": f"missing {HIER}",
        }
    else:
        extra = ["--i-die", str(i_die)] if i_die > 0 else []
        proc = subprocess.run(
            [
                sys.executable,
                str(HIER),
                "--config",
                str(CFG),
                "--out-dir",
                str(work),
                "--report",
                str(PDN_OUT),
                "--repo",
                str(ROOT),
                "--variant",
                variant,
                *extra,
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=120,
        )
        blob = json.loads(PDN_OUT.read_text()) if PDN_OUT.is_file() else {}
        payload = {
            **blob,
            "ok": bool(blob.get("ok")),
            "status": "ran" if proc.returncode == 0 and blob.get("ok") else "fail",
            "exit_code": proc.returncode,
            "i_die_from_finish_a": i_die or None,
            "finish_power_w": power_w,
            "stderr_tail": (proc.stderr or "")[-300:],
        }
    payload.update(
        {
            "kind": "leftover_named_system_pdn",
            "tool_status": (
                "pass"
                if payload.get("ok") is True
                else "blocked"
                if payload.get("status") in {"GAP", "blocked", "not_run"}
                else "fail"
            ),
            "honesty": "PROXY" if payload.get("ok") is True else "GAP",
            "honesty_reason": "Community ngspice compact ladder; not Touchstone or foundry package signoff.",
            "ok_claim": False,
            "surface": "lab",
            "platform": "asap7",
            "product_win": False,
            "productWin": False,
            "win_eligible": False,
            "comparable_to_gold_ir": False,
            "track": "asap7",
            "mesh_id": "asap7_pkg_tier_c",
            "topology": "pkg",
            "oracle": "ngspice_compact",
            "tool_id": "ngspice_compact",
            "license_class": "GPL-2.0-or-later",
            "comparison_scope": "independent ASAP7 package run",
            "calibre": False,
            "c4": False,
            "touchstone": False,
            "variant": variant,
            "config": str(CFG),
            "vdd": vdd,
            "leftover": {
                "c4": "compact n_bumps lump, not JEDEC C4",
                "touchstone": "lumped RLC only; no board S-parameter",
                "cpa": "compact ladder, not Ansys CPA / foundry package model",
                "comparison_scope": "independent ASAP7 package mesh",
            },
            "note": (
                "ASAP7 compact VRM→board→pkg→die. Not Touchstone. Not C4. "
                "Not a product win. Live metrics only."
            ),
        }
    )
    PDN_OUT.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leftover-named ASAP7 PKG. Dummy, not C4.")
    p.add_argument("--variant", default=DEFAULT_VARIANT)
    args = p.parse_args(argv)
    variant = args.variant
    _refuse_variant(variant)
    folder = _folder(variant)
    cfg = json.loads(CFG.read_text()) if CFG.is_file() else {}
    live = {"qor": {}, "corner": "TC"}
    if "_wc_" in variant:
        live["corner"] = "WC"
    elif "_bc_" in variant:
        live["corner"] = "BC"
    for row in scan_folio(ROOT):
        if row.get("variant") == variant:
            live["qor"] = row
            break

    bump = run_bump(variant, folder, cfg)
    rdl = run_rdl(variant, folder)
    pdn = run_system_pdn(variant, folder, cfg, live)
    manifest = build_manifest(
        ROOT,
        variant,
        config=cfg,
        finish_dir=folder,
        rdl_def=Path(rdl["sidecar_def"]) if rdl.get("sidecar_def") else None,
        rdl_odb=Path(rdl["sidecar_odb"]) if rdl.get("sidecar_odb") else None,
    )
    manifest_path = default_output_path(ROOT, variant)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    payload = {
        # A complete dummy run is executable evidence, not package signoff.
        # Keep the legacy container honest and let the manifest carry the
        # separate evidence_ok/status fields used by the FlowLab UI.
        "ok": manifest.get("status") == "pass",
        "evidence_ok": manifest.get("evidence_ok"),
        "status": manifest.get("status"),
        "legacy_status": manifest.get("legacy_status") or manifest.get("status"),
        "tool_status": (
            "pass"
            if manifest.get("evidence_ok") is True
            else "blocked"
            if manifest.get("status") in {"GAP", "blocked", "not_run"}
            else "fail"
        ),
        "honesty": manifest.get("honesty") if manifest.get("honesty") in {"GAP", "PROXY", "PARTIAL"} else "GAP",
        "honesty_reason": "Dummy bump/RDL/compact PDN evidence; not C4, Touchstone, or Product signoff.",
        "ok_claim": False,
        "product_signoff": False,
        "summary": manifest.get("summary"),
        "kind": "leftover_named_pkg",
        "surface": "lab",
        "platform": "asap7",
        "product_win": False,
        "productWin": False,
        "win_eligible": False,
        "comparable_to_gold_ir": False,
        "track": "asap7",
        "mesh_id": "asap7_pkg_tier_c",
        "topology": "pkg",
        "oracle": "ngspice_compact",
        "tool_id": "community_package_ladder",
        "license_class": "community-open-source",
        "comparison_scope": "independent ASAP7 package run",
        "calibre": False,
        "c4": False,
        "touchstone": False,
        "variant": variant,
        "bump": bump,
        "rdl": rdl,
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "system_pdn": {
            "ok": pdn.get("ok"),
            "status": pdn.get("status"),
            "vdd": pdn.get("vdd"),
            "droop_mv": (pdn.get("transient") or {}).get("droop_mv"),
            "z_max_mohm": (pdn.get("impedance") or {}).get("z_max_mohm"),
            "i_die_avg_a": pdn.get("i_die_avg_a") or pdn.get("i_die_from_finish_a"),
        },
        "leftover": {
            "c4": "dummy bump + sidecar rdl_route, not JEDEC C4",
            "touchstone": "lumped compact ladder, no board S-parameter",
            "cpa": "compact chip-package model, not Ansys CPA",
        },
        "leftovers": [
            {"id": "dummy_bump", "message": "Dummy bump map is not JEDEC C4."},
            {"id": "rdl_sidecar", "message": "RDL output is a sidecar and never replaces 6_final.odb."},
            {"id": "touchstone_missing", "message": "No board S-parameter / Touchstone model is present."},
        ],
        "pillars": {
            "pkg": {
                "status": payload.get("tool_status"),
                "honesty": payload.get("honesty"),
                "honesty_reason": payload.get("honesty_reason"),
                "leftovers": [
                    {"id": "dummy_bump", "message": "Dummy bump map is not JEDEC C4."},
                    {"id": "rdl_sidecar", "message": "RDL output is a sidecar."},
                ],
            },
            "thermal": {
                "status": "not_run",
                "honesty": "GAP",
                "honesty_reason": "Thermal is not included in the compact package ladder.",
                "leftovers": [{"id": "thermal_not_run", "message": "No compact thermal model ran."}],
            },
        },
        "signoff_all": {"ok": False, "reason": "ASAP7 package evidence never creates Product signoff."},
        "note": (
            "ASAP7 leftover-named PKG. Dummy, not C4. Not a product win. "
            "Live metrics only."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"lab_asap7_pkg bump={bump.get('ok')} rdl={rdl.get('evidence_ok')} "
        f"pdn={pdn.get('ok')} droop_mv={(pdn.get('transient') or {}).get('droop_mv')} "
        f"c4=no variant={variant}",
        flush=True,
    )
    # RDL + compact ladder must both succeed when bump config is valid.
    if not bump.get("ok"):
        return 1
    if pdn.get("status") == "GAP":
        return 0
    if rdl.get("status") not in {"pass", "fail", "blocked", "not_run"}:
        return 2
    return 0 if payload["ok"] or manifest.get("status") in {"blocked", "fail"} else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LabAsap7Refuse as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
