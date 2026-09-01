#!/usr/bin/env python3
"""Next Level live controls: Yosys equiv, A-injected finish, optional fixed floorplan.

Never writes FLOW_VARIANT=flowlab / learn. Never AES/Krylov. One heavy job
when --ainj is set (GCD make finish of A's own 1_2_yosys.v).
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
from dse.f6_finish import (  # noqa: E402
    BASELINE_6_ODB_SHA,
    BASELINE_6_REPORT_SHA,
    assert_baseline_frozen,
    parse_6_report,
    parse_floorplan,
    refuse_locked_variant,
    run_f6_handoff,
)
from dse.geometry import load_geometry_a, orfs_lock_env  # noqa: E402


def _dump(path: Path, blob: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2) + "\n")


def run_equiv() -> dict:
    gold = _ROOT / "learn/flowlab/gcd.v"
    ident = equiv_rtl_pair(gold, gold)
    dest = Path(tempfile.mkdtemp(prefix="dse-nl-eq-")) / "sub.v"
    plugin("sub_twos_complement").emit(gold, dest)
    sub = equiv_rtl_pair(gold, dest)
    dest2 = Path(tempfile.mkdtemp(prefix="dse-nl-eq-")) / "eqz.v"
    plugin("eqz_or_reduce").emit(gold, dest2)
    eqz = equiv_rtl_pair(gold, dest2)
    out = {
        "identity": ident.to_dict(),
        "sub_twos_complement": sub.to_dict(),
        "eqz_or_reduce": eqz.to_dict(),
        "ok": ident.status == "pass" and sub.status == "pass" and eqz.status == "pass",
    }
    _dump(_ROOT / "learn/dse/next_level_equiv.json", out)
    return out


def run_ainj() -> dict:
    refuse_locked_variant("flowlab_dse_ainj")
    before = assert_baseline_frozen()
    netlist = _ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"
    if not netlist.is_file():
        raise FileNotFoundError(netlist)
    proc = run_f6_handoff(netlist, variant="flowlab_dse_ainj", target="finish", timeout_s=900.0)
    log = (_ROOT / "learn/sim/reports/handoff_ainj.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""))
    after = assert_baseline_frozen()
    rep_path = _ROOT / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab_dse_ainj/6_report.json"
    blob = parse_6_report(rep_path) if proc.returncode == 0 and rep_path.is_file() else {}
    a = json.loads((_ROOT / "learn/dse/handoff_baseline_a.json").read_text())["finish"]
    out = {
        "ok": proc.returncode == 0 and bool(blob),
        "exit": proc.returncode,
        "variant": "flowlab_dse_ainj",
        "netlist": str(netlist),
        "finish": blob,
        "baseline_wns_ns": a["wns_setup_ns"],
        "delta_wns_ps": None,
        "baseline_untouched": after == before
        and after["sha256_6_report"] == BASELINE_6_REPORT_SHA
        and after["sha256_6_final_odb"] == BASELINE_6_ODB_SHA,
    }
    if blob.get("wns_setup_ns") is not None:
        out["delta_wns_ps"] = 1000.0 * (float(blob["wns_setup_ns"]) - float(a["wns_setup_ns"]))
    _dump(_ROOT / "learn/dse/handoff_ainj.json", out)
    return out


def run_fixed_floorplan() -> dict:
    """B netlist on A's die — floorplan only, not a second full finish."""
    refuse_locked_variant("flowlab_dse_fixedb")
    before = assert_baseline_frozen()
    netlist = Path("/workspace/learn/sim/dse/netlists/54142494d890.v")
    if not netlist.is_file():
        netlist = _ROOT / "learn/sim/dse/netlists/54142494d890.v"
    env = os.environ.copy()
    env.update(orfs_lock_env())
    env["FLOW_VARIANT"] = "flowlab_dse_fixedb"
    env["SYNTH_NETLIST_FILES"] = str(netlist)
    proc = run_f6_handoff(
        netlist,
        variant="flowlab_dse_fixedb",
        target="floorplan",
        die_area=env["DIE_AREA"],
        core_area=env["CORE_AREA"],
        timeout_s=180.0,
    )
    fp_path = _ROOT / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab_dse_fixedb/2_1_floorplan.json"
    fp = parse_floorplan(fp_path) if fp_path.is_file() else {}
    ga = load_geometry_a()
    after = assert_baseline_frozen()
    die = fp.get("die_um2")
    out = {
        "ok": proc.returncode == 0 and die is not None and abs(float(die) - float(ga["die_um2"])) < 1.0,
        "exit": proc.returncode,
        "variant": "flowlab_dse_fixedb",
        "target": "floorplan",
        "die_um2": die,
        "core_um2": fp.get("core_um2"),
        "expected_die_um2": ga["die_um2"],
        "baseline_untouched": after["sha256_6_report"] == before["sha256_6_report"],
        "stderr_tail": (proc.stderr or "")[-1500:],
    }
    _dump(_ROOT / "learn/dse/handoff_fixedb_floorplan.json", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--equiv", action="store_true")
    ap.add_argument("--ainj", action="store_true")
    ap.add_argument("--fixed-floorplan", action="store_true")
    args = ap.parse_args()
    if not (args.equiv or args.ainj or args.fixed_floorplan):
        args.equiv = True
    rc = 0
    if args.equiv:
        eq = run_equiv()
        print("EQUIV", json.dumps({k: v.get("status") if isinstance(v, dict) else v for k, v in eq.items()}))
        if not eq.get("ok"):
            rc = 1
    if args.fixed_floorplan:
        fx = run_fixed_floorplan()
        print("FIXED_FP", json.dumps({k: fx[k] for k in fx if k != "stderr_tail"}))
        if not fx.get("ok"):
            rc = 1
    if args.ainj:
        aj = run_ainj()
        print("AINJ", json.dumps({k: aj[k] for k in aj if k != "finish"} | {"wns": (aj.get("finish") or {}).get("wns_setup_ns")}))
        if not aj.get("ok"):
            rc = 1
    assert_baseline_frozen()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
