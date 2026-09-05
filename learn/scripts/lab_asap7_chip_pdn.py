#!/usr/bin/env python3
"""Leftover-named ASAP7 on-die chip PDN mesh (tier B).

OpenROAD write_pg_spice + pdn_transient.py on lab_asap7_* finishes.
Not System PDN (tier C: lab_asap7_pkg). Not cook PDNSim alone (tier A: 6_report).
Never writes nangate45/gcd/flowlab. Never restamps gold Dynamic IR 45.298 mV.
Never writes .chip_pdn_ir.ok.
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
ORFS = ROOT / "tools/OpenROAD-flow-scripts/flow"
NLDM = ORFS / "platforms/asap7/lib/NLDM"
PKG_CFG = ROOT / "learn/lab/asap7/pkg/asap7_system_pdn.json"
OUT = ROOT / "learn/sim/reports/lab_asap7_chip_pdn.json"
DEFAULT_VARIANT = "lab_asap7_gcd_tc_rvt_nldm_7p5_480ps"
NLDM_FAMILIES = ("AO", "INVBUF", "OA", "SIMPLE", "SEQ")
WORST_IR_RE = re.compile(r"Worstcase IR drop:\s+([0-9.eE+-]+)\s+V")


def _refuse_variant(variant: str) -> None:
    if not variant.startswith("lab_asap7_"):
        raise LabAsap7Refuse(f"REFUSED: chip PDN variant must start with lab_asap7_ ({variant})")
    if is_locked_variant(variant):
        raise LabAsap7Refuse(f"REFUSED: locked variant {variant}")
    if "nangate45" in variant:
        raise LabAsap7Refuse(f"REFUSED: nangate path in variant {variant}")


def _folder(variant: str) -> Path:
    found = result_dir_for_variant(variant, ROOT)
    if found is not None:
        return found
    return ORFS / "results/asap7/gcd" / variant


def _corner_vt(variant: str) -> tuple[str, str]:
    corner = "TC"
    if "_wc_" in variant:
        corner = "WC"
    elif "_bc_" in variant:
        corner = "BC"
    vt = "RVT"
    for tag in ("SLVT", "LVT", "RVT", "SRAM"):
        if f"_{tag.lower()}_" in variant:
            vt = tag
            break
    return corner, vt


def _nldm_libs(corner: str, vt: str) -> list[Path]:
    lib_tag = str(CORNERS[corner]["lib"]).upper()
    picked: list[Path] = []
    for fam in NLDM_FAMILIES:
        prefix = f"asap7sc7p5t_{fam}_{vt}_{lib_tag}_nldm"
        cands = [
            p
            for p in NLDM.iterdir()
            if p.is_file()
            and p.name.startswith(prefix)
            and (p.suffix == ".lib" or p.name.endswith(".lib.gz"))
        ]
        if cands:
            picked.append(sorted(cands, key=lambda p: p.name)[0])
    return picked


def _vdd(corner: str) -> float:
    return float(CORNERS[corner]["voltage"])


def _power_w(variant: str, folder: Path) -> float | None:
    for row in scan_folio(ROOT):
        if row.get("variant") == variant:
            mw = row.get("power_mw")
            if mw is not None:
                return float(mw) * 1e-3
            pw = row.get("power_w")
            if pw is not None:
                return float(pw)
    rep = folder / "6_report.json"
    if rep.is_file():
        try:
            blob = json.loads(rep.read_text())
            for step in blob if isinstance(blob, list) else []:
                if step.get("name") == "finish" and step.get("power") is not None:
                    return float(step["power"])
        except json.JSONDecodeError:
            pass
    return None


def _pdnsim_6_report_mv(variant: str, folder: Path) -> float | None:
    for row in scan_folio(ROOT):
        if row.get("variant") == variant and row.get("ir_drop_vdd_mv") is not None:
            return float(row["ir_drop_vdd_mv"])
    rep = folder / "6_report.json"
    log_rep = ORFS / "logs/asap7/gcd" / variant / "6_report.json"
    rep = log_rep if log_rep.is_file() else rep
    if not rep.is_file():
        return None
    try:
        qor = json.loads(rep.read_text())
    except json.JSONDecodeError:
        return None
    key = "finish__design_powergrid__drop__worst__net:VDD__corner:default"
    val = qor.get(key) if isinstance(qor, dict) else None
    return float(val) * 1e3 if val is not None else None


def complete_asap7_mesh_spice(src: Path, dst: Path, vdd: float, i_total_a: float) -> dict:
    """ASAP7 write_pg_spice often stops at map::at before V/I. Complete honestly."""
    text = src.read_text(errors="replace")
    has_v = any(line.strip().startswith("V") for line in text.splitlines())
    has_i = any(line.strip().startswith("I") for line in text.splitlines())
    if has_v and has_i:
        if src != dst:
            dst.write_text(text)
        return {"patched": False, "n_bpin": 0, "n_iterm": 0, "reason": "mesh already complete"}

    bpin: set[str] = set()
    iterm: set[str] = set()
    for raw in text.splitlines():
        s = raw.strip()
        if not s.startswith("R"):
            continue
        parts = s.split()
        if len(parts) < 4:
            continue
        for node in (parts[1], parts[2]):
            if node.startswith("BPinNode_"):
                bpin.add(node)
            elif node.startswith("ITermNode_"):
                iterm.add(node)

    extras: list[str] = []
    for idx, node in enumerate(sorted(bpin)):
        extras.append(f"V{idx} {node} 0 DC {vdd:.6f}")
    n_load = len(iterm) or 1
    i_each = max(i_total_a, 0.0) / n_load
    for idx, node in enumerate(sorted(iterm)):
        extras.append(f"I{idx} {node} 0 DC {i_each:.9e}")

    if not extras:
        return {
            "patched": False,
            "n_bpin": 0,
            "n_iterm": 0,
            "reason": "no BPinNode or ITermNode in mesh",
        }

    lines = text.splitlines()
    if lines and lines[-1].strip() == "* Sinks":
        body = lines
    else:
        body = lines + ["", "* Sinks"]
    body.extend(extras)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(body) + "\n")
    return {
        "patched": True,
        "n_bpin": len(bpin),
        "n_iterm": len(iterm),
        "i_total_a": i_total_a,
        "i_each_a": i_each,
        "reason": "OpenROAD map::at left mesh without V/I — uniform ITerm load added",
    }


def _worst_ir_mv_from_log(log_text: str) -> float | None:
    for block in log_text.split("Net              : VDD"):
        m = WORST_IR_RE.search(block)
        if m:
            return float(m.group(1)) * 1e3
    m = WORST_IR_RE.search(log_text)
    return float(m.group(1)) * 1e3 if m else None


def run_openroad(
    variant: str,
    folder: Path,
    libs: list[Path],
    vdd: float,
    bump_dx: int,
    bump_dy: int,
    bump_size: int,
    bump_interval: int,
    pkg_r: float,
) -> dict:
    odb = folder / "6_final.odb"
    sdc = folder / "6_final.sdc"
    pdn_dir = folder / "pdn"
    pdn_dir.mkdir(parents=True, exist_ok=True)
    spice_raw = pdn_dir / "pg_vdd_bumps.sp"
    log = ROOT / "learn/sim/reports" / f"lab_asap7_chip_pdn_{variant}.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    if not odb.is_file():
        return {"ok": False, "status": "GAP", "reason": f"missing ODB {odb}"}
    if not sdc.is_file():
        return {"ok": False, "status": "GAP", "reason": f"missing SDC {sdc}"}
    if not shutil.which("openroad"):
        return {"ok": False, "status": "GAP", "reason": "openroad not in PATH"}
    missing = [str(p) for p in libs if not p.is_file()]
    if missing:
        return {"ok": False, "status": "GAP", "reason": f"liberty missing {missing[:2]}"}

    lib_cmds = "\n".join(f"read_liberty {p}" for p in libs)
    tcl = f"""
{lib_cmds}
read_db {odb}
read_sdc {sdc}
report_power
set_pdnsim_source_settings -bump_dx {bump_dx} -bump_dy {bump_dy} -bump_size {bump_size} -bump_interval {bump_interval} -external_resistance {pkg_r}
puts "=== STATIC BUMPS ==="
analyze_power_grid -net VDD -source_type BUMPS
puts "=== EXPORT write_pg_spice (BUMPS) ==="
write_pg_spice -net VDD -source_type BUMPS {spice_raw}
puts CHIP_PDN_OPENROAD_DONE
"""
    proc = subprocess.run(
        ["openroad", "-no_init", "-no_splash", "-exit"],
        input=tcl,
        cwd=str(ORFS),
        text=True,
        capture_output=True,
        timeout=300,
    )
    log_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    log.write_text(log_text)
    mesh_static_mv = _worst_ir_mv_from_log(log_text)
    n_r = sum(1 for line in spice_raw.read_text(errors="replace").splitlines() if line.strip().startswith("R")) if spice_raw.is_file() else 0
    return {
        "ok": proc.returncode == 0 and spice_raw.is_file() and n_r > 0,
        "status": "ran" if spice_raw.is_file() and n_r > 0 else "fail",
        "exit_code": proc.returncode,
        "spice_raw": str(spice_raw),
        "log": str(log),
        "n_r": n_r,
        "mesh_static_openroad_mv": mesh_static_mv,
        "openroad_done": "CHIP_PDN_OPENROAD_DONE" in log_text,
        "map_at": "map::at" in log_text,
        "stderr_tail": (proc.stderr or "")[-400:],
    }


def run_transient(
    spice: Path,
    out_json: Path,
    wave_csv: Path,
    vdd: float,
    pkg_r: float,
    pkg_l: float,
) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"/usr/lib/python3/dist-packages:{ROOT}/learn/scripts"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "learn/scripts/pdn_transient.py"),
            "--spice",
            str(spice),
            "--out",
            str(out_json),
            "--wave",
            str(wave_csv),
            "--vdd",
            str(vdd),
            "--pkg-r",
            str(pkg_r),
            "--pkg-l",
            str(pkg_l),
            "--mode",
            "BUMPS",
        ],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    blob: dict = {}
    if out_json.is_file():
        try:
            blob = json.loads(out_json.read_text())
        except json.JSONDecodeError:
            blob = {}
    return {
        "ok": proc.returncode == 0 and bool(blob),
        "exit_code": proc.returncode,
        "report": blob,
        "stdout_tail": (proc.stdout or "")[-400:],
        "stderr_tail": (proc.stderr or "")[-400:],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leftover-named ASAP7 chip PDN mesh. Not a product win.")
    p.add_argument("--variant", default=DEFAULT_VARIANT)
    args = p.parse_args(argv)
    variant = args.variant
    _refuse_variant(variant)

    folder = _folder(variant)
    corner, vt = _corner_vt(variant)
    vdd = _vdd(corner)
    libs = _nldm_libs(corner, vt)
    pdnsim_6_report_mv = _pdnsim_6_report_mv(variant, folder)
    power_w = _power_w(variant, folder)
    i_total = (power_w / vdd) if power_w is not None and vdd > 0 else 0.0

    bump_dx = int(os.environ.get("CHIP_PDN_BUMP_DX", "2"))
    bump_dy = int(os.environ.get("CHIP_PDN_BUMP_DY", "2"))
    bump_size = int(os.environ.get("CHIP_PDN_BUMP_SIZE", "1"))
    bump_interval = int(os.environ.get("CHIP_PDN_BUMP_INTERVAL", "1"))
    pkg_r = float(os.environ.get("PKG_R", "0.05"))
    pkg_l = float(os.environ.get("PKG_L", "2e-10"))

    or_out = run_openroad(variant, folder, libs, vdd, bump_dx, bump_dy, bump_size, bump_interval, pkg_r)
    spice_raw = Path(or_out.get("spice_raw") or (folder / "pdn/pg_vdd_bumps.sp"))
    spice_completed = folder / "pdn/pg_vdd_bumps_completed.sp"
    patch = {"patched": False, "reason": "no mesh"}
    transient_blob: dict = {}
    mesh_static_mv = None
    mesh_transient_mv = None
    n_sources = 0

    if spice_raw.is_file() and or_out.get("n_r", 0) > 0:
        patch = complete_asap7_mesh_spice(spice_raw, spice_completed, vdd, i_total)
        wave = ROOT / "learn/sim/reports" / f"lab_asap7_chip_pdn_{variant}.wave.csv"
        detail_json = ROOT / "learn/sim/reports" / f"lab_asap7_chip_pdn_{variant}.json"
        tr = run_transient(spice_completed, detail_json, wave, vdd, pkg_r, pkg_l)
        transient_blob = tr.get("report") or {}
        static = transient_blob.get("static") or {}
        dyn = transient_blob.get("transient") or {}
        mesh_static_mv = (static.get("worst_ir") or 0.0) * 1e3 if static else or_out.get("mesh_static_openroad_mv")
        mesh_transient_mv = (dyn.get("worst_droop") or 0.0) * 1e3 if dyn else None
        n_sources = int(static.get("sources") or 0)

    payload = {
        "ok": bool(or_out.get("ok")) and bool(transient_blob),
        "status": "ran" if transient_blob else or_out.get("status", "GAP"),
        "kind": "leftover_named_chip_pdn",
        "tier": "chip_mesh",
        "surface": "lab",
        "platform": "asap7",
        "product_win": False,
        "comparable_to_gold_ir": False,
        "variant": variant,
        "vdd": vdd,
        "corner": corner,
        "vt": vt,
        "pdnsim_6_report_mv": pdnsim_6_report_mv,
        "mesh_static_mv": mesh_static_mv,
        "mesh_static_openroad_mv": or_out.get("mesh_static_openroad_mv"),
        "mesh_transient_droop_mv": mesh_transient_mv,
        "n_r": or_out.get("n_r", 0),
        "n_sources": n_sources,
        "n_bpin": patch.get("n_bpin", 0),
        "n_iterm": patch.get("n_iterm", 0),
        "spice_path": str(spice_completed if spice_completed.is_file() else spice_raw),
        "spice_raw_path": str(spice_raw) if spice_raw.is_file() else None,
        "finish_power_w": power_w,
        "i_total_a": i_total,
        "bump": {
            "dx": bump_dx,
            "dy": bump_dy,
            "size": bump_size,
            "interval": bump_interval,
            "pkg_r": pkg_r,
            "pkg_l": pkg_l,
        },
        "openroad": or_out,
        "mesh_patch": patch,
        "transient": transient_blob,
        "leftover": {
            "gold_ir": "not comparable to Nangate 45.298 mV",
            "openroad_gap": "write_pg_spice map::at on ~9 µm die — mesh patched with BPin V + uniform ITerm I",
            "stamp": "no .chip_pdn_ir.ok",
        },
        "note": (
            "ASAP7 on-die chip PDN mesh (tier B). Not tier C PKG. Not a product win. "
            "Live metrics only — no gold stamp."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    per_variant = ROOT / "learn/sim/reports" / f"lab_asap7_chip_pdn_{variant}.json"
    per_variant.write_text(json.dumps(payload, indent=2) + "\n")

    print(
        "lab_asap7_chip_pdn",
        f"variant={variant}",
        f"n_r={payload['n_r']}",
        f"6_report_mv={pdnsim_6_report_mv}",
        f"mesh_static_mv={mesh_static_mv}",
        f"mesh_transient_mv={mesh_transient_mv}",
        f"patched={patch.get('patched')}",
        f"product_win=false",
        flush=True,
    )

    if or_out.get("status") == "GAP":
        return 0
    if not or_out.get("ok"):
        return 2
    if not transient_blob:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LabAsap7Refuse as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
