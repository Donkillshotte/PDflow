#!/usr/bin/env python3
"""Leftover-named ASAP7 bump / sidecar RDL / compact package ladder.

Dummy, not C4. Lumped RLC, not Touchstone / Ansys CPA. Not a product win.
Never writes lab_asap7_*/6_final.odb. Never writes nangate45/gcd/flowlab.
Never restamps gold Dynamic IR 45.298 mV. Never writes .pkg.ok.
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

from dse.asap7_lab import CORNERS, LabAsap7Refuse, result_dir_for_variant, scan_folio
from dse.flow_role import is_locked_variant

ROOT = Path(__file__).resolve().parents[2]
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
    if not variant.startswith("lab_asap7_"):
        raise LabAsap7Refuse(f"REFUSED: PKG variant must start with lab_asap7_ ({variant})")
    if is_locked_variant(variant):
        raise LabAsap7Refuse(f"REFUSED: locked variant {variant}")


def _folder(variant: str) -> Path:
    folder = result_dir_for_variant(variant, ROOT)
    if folder is None:
        return ROOT / "tools/OpenROAD-flow-scripts/flow/results/asap7/gcd" / variant
    return folder


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
    payload = {
        "ok": n_bumps > 0 and LEF.is_file(),
        "kind": "leftover_named_pkg_bump",
        "surface": "lab",
        "platform": "asap7",
        "product_win": False,
        "comparable_to_gold_ir": False,
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
            "c4": "dummy 2×2 bump LEF, not JEDEC C4",
            "mesh": "on-die IR is 6_report PSM, not write_pg_spice BUMPS",
        },
        "note": (
            "ASAP7 dummy bump config. Not C4. Not a product win. "
            "Live metrics only — no gold stamp."
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
    if not odb.is_file():
        reason = f"ODB missing {odb}"
        status = "GAP"
    elif not LEF.is_file():
        reason = f"dummy bump LEF missing {LEF}"
        status = "GAP"
    elif not shutil.which("openroad"):
        reason = "openroad not in PATH"
        status = "GAP"
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
        n_bump = len(re.findall(r"\bDUMMY_BUMP\b", text))
        n_wires = len(re.findall(r"ROUTED M9|NEW M9|ROUTED M4|NEW M4", text))
        executed = bool(out_def.is_file() and n_bump > 0 and n_wires > 0)
        status = "ran" if exit_code == 0 else "fail"
        reason = "" if executed else ((proc.stderr or proc.stdout or "")[-400:])
        final = folder / "6_final.odb"
        if final.is_file() and in_odb.is_file() and final.samefile(in_odb):
            raise LabAsap7Refuse("REFUSED: RDL sidecar resolved to 6_final.odb")
    payload = {
        "ok": executed,
        "status": status,
        "kind": "leftover_named_pkg_rdl",
        "surface": "lab",
        "platform": "asap7",
        "product_win": False,
        "comparable_to_gold_ir": False,
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
            "layer_signal": "M4",
            "exit_code": exit_code,
        },
        "leftover": {
            "c4": "dummy 2×2 bump LEF, not JEDEC C4",
            "sidecar": "never write 6_final.odb",
        },
        "reason": reason,
        "note": (
            "ASAP7 sidecar rdl_route. Dummy, not C4. Not a product win. "
            "Live metrics only — no gold stamp."
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
            "surface": "lab",
            "platform": "asap7",
            "product_win": False,
            "comparable_to_gold_ir": False,
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
                "gold_ir": "not comparable to Nangate 45.298 mV",
            },
            "note": (
                "ASAP7 compact VRM→board→pkg→die. Not Touchstone. Not C4. "
                "Not a product win. Live metrics only — no gold stamp."
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
    payload = {
        "ok": bool(bump.get("ok")) and bool(pdn.get("ok")),
        "kind": "leftover_named_pkg",
        "surface": "lab",
        "platform": "asap7",
        "product_win": False,
        "comparable_to_gold_ir": False,
        "calibre": False,
        "c4": False,
        "touchstone": False,
        "variant": variant,
        "bump": bump,
        "rdl": rdl,
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
        "note": (
            "ASAP7 leftover-named PKG. Dummy, not C4. Not a product win. "
            "Live metrics only — no gold stamp."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"lab_asap7_pkg bump={bump.get('ok')} rdl={rdl.get('ok')} "
        f"pdn={pdn.get('ok')} droop_mv={(pdn.get('transient') or {}).get('droop_mv')} "
        f"c4=no variant={variant}",
        flush=True,
    )
    # RDL wire count leftover does not fail the script. Missing compact ladder does.
    if not bump.get("ok"):
        return 1
    if pdn.get("status") == "GAP":
        return 0
    return 0 if pdn.get("ok") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LabAsap7Refuse as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
