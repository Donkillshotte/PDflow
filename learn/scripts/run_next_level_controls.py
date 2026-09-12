#!/usr/bin/env python3
"""Next Level live controls: Yosys equiv, injected finish, optional floorplan.

Every comparison is made against artifacts read at the start of the same
invocation. No committed result outside that invocation is used as a target.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn"))

from dse.arch_plugins import plugin  # noqa: E402
from dse.equiv import equiv_rtl_pair  # noqa: E402
from dse.f6_finish import finish_artifact_paths, hash_file, parse_6_report, parse_floorplan, run_f6_current  # noqa: E402
from dse.geometry import current_geometry_env, load_current_geometry  # noqa: E402
from dse.live_paths import current_run_dir  # noqa: E402


def _dump(path: Path, blob: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2) + "\n")


def run_equiv(run_dir: Path) -> dict:
    reference = _ROOT / "learn/flowlab/gcd.v"
    ident = equiv_rtl_pair(reference, reference)
    dest = Path(tempfile.mkdtemp(prefix="dse-nl-eq-")) / "sub.v"
    plugin("sub_twos_complement").emit(reference, dest)
    sub = equiv_rtl_pair(reference, dest)
    dest2 = Path(tempfile.mkdtemp(prefix="dse-nl-eq-")) / "eqz.v"
    plugin("eqz_or_reduce").emit(reference, dest2)
    eqz = equiv_rtl_pair(reference, dest2)
    out = {
        "identity": ident.to_dict(),
        "sub_twos_complement": sub.to_dict(),
        "eqz_or_reduce": eqz.to_dict(),
        "ok": ident.status == "pass" and sub.status == "pass" and eqz.status == "pass",
    }
    _dump(run_dir / "equivalence.json", out)
    return out


def run_ainj(run_dir: Path) -> dict:
    base_report, base_odb = finish_artifact_paths("flowlab")
    before = {"report": hash_file(base_report), "odb": hash_file(base_odb)}
    netlist = _ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"
    if not netlist.is_file():
        raise FileNotFoundError(netlist)
    proc = run_f6_current(netlist, variant="flowlab_dse_ainj", target="finish", timeout_s=600.0)
    log = run_dir / "ainj.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
    after = {"report": hash_file(base_report), "odb": hash_file(base_odb)}
    rep_path = _ROOT / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab_dse_ainj/6_report.json"
    blob = parse_6_report(rep_path) if proc.returncode == 0 and rep_path.is_file() else {}
    a = parse_6_report(base_report) if base_report.is_file() else {}
    out = {
        "ok": proc.returncode == 0 and bool(blob),
        "exit": proc.returncode,
        "variant": "flowlab_dse_ainj",
        "netlist": str(netlist),
        "finish": blob,
        "reference_wns_ns": a.get("wns_setup_ns"),
        "delta_wns_ps": None,
        "reference_artifacts_unchanged": after == before,
    }
    if blob.get("wns_setup_ns") is not None:
        if a.get("wns_setup_ns") is not None:
            out["delta_wns_ps"] = 1000.0 * (float(blob["wns_setup_ns"]) - float(a["wns_setup_ns"]))
    _dump(run_dir / "ainj.json", out)
    return out


def run_current_floorplan(run_dir: Path) -> dict:
    """Evaluate the current floorplan contract without loading a saved scene."""
    base_report, base_odb = finish_artifact_paths("flowlab")
    before = {"report": hash_file(base_report), "odb": hash_file(base_odb)}
    netlist = _ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"
    if not netlist.is_file():
        raise FileNotFoundError(netlist)
    env = os.environ.copy()
    env.update(current_geometry_env("gcd", "flowlab"))
    env["FLOW_VARIANT"] = "flowlab_dse_current_floorplan"
    env["SYNTH_NETLIST_FILES"] = str(netlist)
    proc = run_f6_current(
        netlist,
        variant="flowlab_dse_current_floorplan",
        target="floorplan",
        die_area=env["DIE_AREA"],
        core_area=env["CORE_AREA"],
        timeout_s=600.0,
    )
    fp_path = _ROOT / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab_dse_current_floorplan/2_1_floorplan.json"
    fp = parse_floorplan(fp_path) if fp_path.is_file() else {}
    current = load_current_geometry("gcd", "flowlab")
    after = {"report": hash_file(base_report), "odb": hash_file(base_odb)}
    die = fp.get("die_um2")
    out = {
        "ok": proc.returncode == 0 and die is not None and abs(float(die) - float(current["die_um2"])) < 1.0,
        "exit": proc.returncode,
        "variant": "flowlab_dse_current_floorplan",
        "target": "floorplan",
        "die_um2": die,
        "core_um2": fp.get("core_um2"),
        "current_die_um2": current["die_um2"],
        "current_artifacts_unchanged": after == before,
        "stderr_tail": (proc.stderr or "")[-1500:],
    }
    _dump(run_dir / "current-floorplan.json", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--equiv", action="store_true")
    ap.add_argument("--ainj", action="store_true")
    ap.add_argument("--current-floorplan", action="store_true")
    args = ap.parse_args()
    if not (args.equiv or args.ainj or args.current_floorplan):
        args.equiv = True
    run_dir = current_run_dir("next-level")
    rc = 0
    if args.equiv:
        eq = run_equiv(run_dir)
        print("EQUIV", json.dumps({k: v.get("status") if isinstance(v, dict) else v for k, v in eq.items()}))
        if not eq.get("ok"):
            rc = 1
    if args.current_floorplan:
        fx = run_current_floorplan(run_dir)
        print("CURRENT_FP", json.dumps({k: fx[k] for k in fx if k != "stderr_tail"}))
        if not fx.get("ok"):
            rc = 1
    if args.ainj:
        aj = run_ainj(run_dir)
        print("AINJ", json.dumps({k: aj[k] for k in aj if k != "finish"} | {"wns": (aj.get("finish") or {}).get("wns_setup_ns")}))
        if not aj.get("ok"):
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
