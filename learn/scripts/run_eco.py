#!/usr/bin/env python3
"""Minimal post-finish ECO loop.

propose (default): read STA on the finished variant and write a plan.
apply: refuse locked variants (flowlab/learn/base), copy the ODB, run
OpenROAD repair_timing, write finish artifacts on the copy.

Never calls signoff_all. Never stamps .lvs.ok. After apply, the next
step is `FLOW_VARIANT=<copy> ./learn/scripts/run_signoff_all.sh`.
Unlocked apply writes 6_final.{odb,def,v,cdl,gds} (SPEF when OpenRCX
works) under results/.../<copy>/ — never under flowlab/learn/base.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn"))
from dse.flow_role import LOCKED_VARIANTS, SIGNOFF_ORCHESTRATOR, is_locked_variant  # noqa: E402

FLOW = _ROOT / "tools/OpenROAD-flow-scripts/flow"
TCL = _ROOT / "learn/scripts/eco_repair.tcl"
STREAM = _ROOT / "learn/scripts/eco_stream_gds.py"


def _install_unlocked(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _variant() -> str:
    return os.environ.get("FLOW_VARIANT", "flowlab")


def _sta(variant: str) -> dict:
    path = _ROOT / "learn/sim/reports" / f"sta_signoff_{variant}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def _plan(sta: dict) -> list[dict]:
    timing = sta.get("timing") or sta.get("metrics") or {}
    wns = timing.get("wns_ns")
    if wns is None:
        wns = (sta.get("sta") or {}).get("wns_ns")
    tns = timing.get("tns_ns")
    viol = timing.get("n_viol") or timing.get("violations")
    setup = wns is not None and float(wns) < 0
    steps = [
        {
            "step": "repair_timing",
            "args": "-setup",
            "reason": (
                f"WNS {wns} ns"
                if wns is not None
                else "STA WNS unavailable — no setup repair without STA"
            ),
            "enabled": bool(setup),
        },
        {
            "step": "repair_timing",
            "args": "-hold",
            "reason": "hold not reported on this educational STA — off unless ECO_HOLD=1",
            "enabled": os.environ.get("ECO_HOLD") == "1",
        },
        {
            "step": "detailed_placement",
            "args": "",
            "reason": "legalize cells moved by repair_timing",
            "enabled": True,
        },
    ]
    return steps


def propose(variant: str) -> dict:
    res = FLOW / "results/nangate45/gcd" / variant
    odb = res / "6_final.odb"
    sta = _sta(variant)
    steps = _plan(sta)
    return {
        "kind": "eco",
        "mode": "propose",
        "variant": variant,
        "ok": odb.is_file(),
        "signoff": False,
        "signoff_required": SIGNOFF_ORCHESTRATOR,
        "locked": is_locked_variant(variant),
        "source_odb": str(odb) if odb.is_file() else None,
        "source_sta": {
            "report": str(_ROOT / "learn/sim/reports" / f"sta_signoff_{variant}.json"),
            "ok": sta.get("ok"),
            "summary": sta.get("summary"),
        },
        "proposed": steps,
        "apply": (
            "refused on locked variants; set FLOW_VARIANT to a copy "
            "(not flowlab/learn/base) and ECO_MODE=apply"
        ),
        "summary": (
            "ECO propose · "
            + ("locked source" if is_locked_variant(variant) else "unlocked")
            + " · signoff_all still required"
        ),
    }


def apply(variant: str) -> dict:
    if is_locked_variant(variant):
        return {
            "kind": "eco",
            "mode": "apply",
            "variant": variant,
            "ok": False,
            "signoff": False,
            "error": f"refuse apply on locked FLOW_VARIANT={variant}",
            "locked": list(sorted(LOCKED_VARIANTS)),
            "summary": f"ECO apply refused on {variant}",
        }
    src = FLOW / "results/nangate45/gcd" / variant / "6_final.odb"
    if not src.is_file():
        # Fall back to flowlab ODB as the read-only source for a new variant name.
        src = FLOW / "results/nangate45/gcd/flowlab/6_final.odb"
    if not src.is_file():
        return {
            "kind": "eco",
            "mode": "apply",
            "ok": False,
            "signoff": False,
            "error": "missing 6_final.odb",
            "summary": "ECO apply missing ODB",
        }
    obj = FLOW / "objects/nangate45/gcd" / variant
    obj.mkdir(parents=True, exist_ok=True)
    work = obj / "eco_in.odb"
    out = obj / "eco_out.odb"
    shutil.copy2(src, work)
    exe = shutil.which("openroad") or "openroad"
    env = os.environ.copy()
    env["ECO_ODB"] = str(work)
    env["ECO_ODB_OUT"] = str(out)
    env["ECO_SETUP"] = "1"
    env["ECO_HOLD"] = os.environ.get("ECO_HOLD", "0")
    env["ECO_LIB"] = str(FLOW / "platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib")
    env["ECO_SDC"] = str(FLOW / "designs/nangate45/gcd-tutorial/constraint.sdc")
    env["ECO_RC"] = str(FLOW / "platforms/nangate45/setRC.tcl")
    env["ECO_FILL"] = "FILLCELL_X1 FILLCELL_X2 FILLCELL_X4 FILLCELL_X8 FILLCELL_X16 FILLCELL_X32"
    def_out = obj / "eco_out.def"
    v_out = obj / "eco_out.v"
    cdl_out = obj / "eco_out.cdl"
    spef_out = obj / "eco_out.spef"
    env["ECO_DEF_OUT"] = str(def_out)
    env["ECO_V_OUT"] = str(v_out)
    env["ECO_CDL_OUT"] = str(cdl_out)
    env["ECO_CDL_MASTERS"] = str(FLOW / "platforms/nangate45/cdl/NangateOpenCellLibrary.cdl")
    env["ECO_SPEF_OUT"] = str(spef_out)
    env["ECO_RCX"] = str(FLOW / "platforms/nangate45/rcx_patterns.rules")
    proc = subprocess.run(
        [exe, "-exit", str(TCL)],
        capture_output=True,
        text=True,
        env=env,
        timeout=420,
    )
    log = obj / "eco_apply.log"
    chunks = [(proc.stdout or "") + "\n" + (proc.stderr or "")]
    wrote = out.is_file() and proc.returncode == 0
    wrote_v = wrote and v_out.is_file()
    wrote_def = wrote and def_out.is_file()
    wrote_cdl = wrote and cdl_out.is_file()
    wrote_spef = wrote and spef_out.is_file()
    gds_out = obj / "eco_out.gds"
    wrote_gds = False
    if wrote and wrote_def:
        lyt = FLOW / "objects/nangate45/gcd/flowlab/klayout.lyt"
        if not lyt.is_file():
            lyt = FLOW / "platforms/nangate45/FreePDK45.lyt"
        cells = FLOW / "platforms/nangate45/gds/NangateOpenCellLibrary.gds"
        g_env = os.environ.copy()
        g_env["ECO_DEF"] = str(def_out)
        g_env["ECO_GDS"] = str(gds_out)
        g_env["ECO_LYT"] = str(lyt)
        g_env["ECO_CELL_GDS"] = str(cells)
        gds_proc = subprocess.run(
            ["klayout", "-zz", "-rm", str(STREAM)],
            capture_output=True,
            text=True,
            env=g_env,
            timeout=180,
        )
        chunks.append((gds_proc.stdout or "") + "\n" + (gds_proc.stderr or ""))
        wrote_gds = gds_out.is_file() and gds_proc.returncode == 0
    log.write_text("\n".join(chunks))
    err = None
    if not wrote:
        combined = chunks[0]
        for line in reversed(combined.splitlines()):
            if "ERROR" in line or line.startswith("FAIL"):
                err = line.strip()
                break
    elif not wrote_gds:
        err = "GDS streamout failed — signoff_all cannot run LVS/DRC yet"

    res = FLOW / "results/nangate45/gcd" / variant
    installed: list[str] = []
    if wrote and not is_locked_variant(variant):
        pairs = [
            (out, "6_final.odb", "odb"),
            (def_out, "6_final.def", "def"),
            (v_out, "6_final.v", "verilog"),
            (cdl_out, "6_final.cdl", "cdl"),
            (spef_out, "6_final.spef", "spef"),
            (gds_out, "6_final.gds", "gds"),
        ]
        for src_art, name, kind in pairs:
            if src_art.is_file():
                _install_unlocked(src_art, res / name)
                installed.append(kind)
        sdc_src = FLOW / "designs/nangate45/gcd-tutorial/constraint.sdc"
        if sdc_src.is_file():
            _install_unlocked(sdc_src, res / "6_final.sdc")

    rewrote = installed or ((["odb"] if wrote else []) + (["verilog"] if wrote_v else []))
    needed = {"odb", "def", "verilog", "gds"}
    ok = needed.issubset(set(rewrote))
    missing = sorted(needed - set(rewrote))
    return {
        "kind": "eco",
        "mode": "apply",
        "variant": variant,
        "ok": ok,
        "signoff": False,
        "signoff_required": SIGNOFF_ORCHESTRATOR,
        "source_odb": str(src),
        "output_odb": str(out) if wrote else None,
        "output_verilog": str(v_out) if wrote_v else None,
        "output_def": str(def_out) if wrote_def else None,
        "output_cdl": str(cdl_out) if wrote_cdl else None,
        "output_spef": str(spef_out) if wrote_spef else None,
        "output_gds": str(gds_out) if wrote_gds else None,
        "results_dir": str(res) if installed else None,
        "log": str(log),
        "rc": proc.returncode,
        "error": err,
        "rewrote": rewrote,
        "not_rewritten": [k for k in ("spef", "cdl", "gds") if k not in rewrote],
        "summary": (
            "ECO apply wrote "
            + "+".join(rewrote)
            + " · run signoff_all next"
            if ok
            else ("ECO apply failed" + (f" · missing {missing}" if missing else ""))
        ),
    }


def main() -> int:
    variant = _variant()
    mode = os.environ.get("ECO_MODE", "propose")
    report = apply(variant) if mode == "apply" else propose(variant)
    name = f"eco_apply_{variant}.json" if mode == "apply" else f"eco_{variant}.json"
    out = _ROOT / "learn/sim/reports" / name
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(report["summary"])
    print("WROTE", out)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
