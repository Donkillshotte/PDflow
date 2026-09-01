#!/usr/bin/env python3
"""Cook one design-agnostic catalog recipe. Place first, finish only if EVALUATE.

Does not rewrite Verilog. Reuses the official Yosys netlist of the same-clock
base. Variant names are camp_<design>_<recipe_id> (readable).

Usage:
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/cook_recipe.py \
        --design spi --recipes place_denser --phase J1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_LEARN = Path(__file__).resolve().parents[1]
_ROOT = _LEARN.parent
if str(_LEARN) not in sys.path:
    sys.path.insert(0, str(_LEARN))

from dse.experiments import DESIGN_CATALOG, ExperimentLog, fill_from_logs, Experiment  # noqa: E402
from dse.f6_finish import parse_place_dp  # noqa: E402
from dse.fidelity_policy import decide  # noqa: E402
from dse.knob_catalog import (  # noqa: E402
    config_mk_for,
    parse_config_defaults,
    resolve_many,
    titles_of,
)
from dse.recipe_labels import synth_method_from_exploration  # noqa: E402


def _base_netlist(design: str) -> Path:
    orfs = DESIGN_CATALOG.get(design, {}).get("orfs_design") or design
    # Prefer the campaign base yosys; never flowlab for non-gcd.
    cand = [
        _ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45" / orfs / f"camp_{design}_base" / "1_2_yosys.v",
        _ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45" / orfs / "flowlab" / "1_2_yosys.v",
    ]
    for p in cand:
        if p.is_file():
            return p
    raise FileNotFoundError(f"no official yosys netlist for {design}")


def _base_finish_ns(design: str, clock_ns: float) -> float | None:
    log = ExperimentLog()
    clk = f"{float(clock_ns):.3f}"
    for e in log.all():
        if e.design != design or e.role != "base" or e.finish_wns_ns is None:
            continue
        if f"{float(e.clock_ns):.3f}" == clk:
            return float(e.finish_wns_ns)
    return None


def _run_wrapper(design: str, variant: str, clock_ns: float, target: str, env_knobs: dict[str, str], net: Path) -> tuple[int, float]:
    env = os.environ.copy()
    env.update(
        {
            "DESIGN": design,
            "FLOW_VARIANT": variant,
            "SDC_NS": str(clock_ns),
            "SYNTH_NETLIST_FILES": str(net),
            **env_knobs,
        }
    )
    t0 = time.time()
    proc = subprocess.run(
        ["bash", str(_ROOT / "scripts/run_design_finish.sh"), target],
        cwd=str(_ROOT),
        env=env,
        check=False,
    )
    return proc.returncode, time.time() - t0


def _place_wns(design: str, variant: str) -> float | None:
    orfs = DESIGN_CATALOG.get(design, {}).get("orfs_design") or design
    path = _ROOT / "tools/OpenROAD-flow-scripts/flow/logs/nangate45" / orfs / variant / "3_5_place_dp.json"
    if not path.is_file():
        return None
    blob = parse_place_dp(path)
    v = blob.get("place_wns_ns")
    return float(v) if v is not None else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--design", required=True)
    p.add_argument("--recipes", nargs="+", required=True)
    p.add_argument("--phase", default="J1")
    p.add_argument("--clock", type=float, default=None)
    p.add_argument("--variant", default=None, help="override FLOW_VARIANT")
    args = p.parse_args(argv)

    design = args.design
    rids = list(args.recipes)
    clock = float(args.clock if args.clock is not None else DESIGN_CATALOG[design]["clk_ns"])
    variant = args.variant or f"camp_{design}_{'_'.join(rids)}"
    title = titles_of(rids)
    if ExperimentLog().has(variant, args.phase):
        print(json.dumps({"skipped": True, "variant": variant, "phase": args.phase}))
        return 0

    defaults = parse_config_defaults(config_mk_for(design))
    knobs = resolve_many(rids, defaults)
    # Pin floorplan util unless a recipe moved it — same die as the official config.
    if "CORE_UTILIZATION" not in knobs and "CORE_UTILIZATION" in defaults:
        knobs["CORE_UTILIZATION"] = str(defaults["CORE_UTILIZATION"])
    synth = synth_method_from_exploration()
    if "ABC_SPEED" not in knobs and "ABC_AREA" not in knobs:
        knobs["ABC_AREA"] = str(synth["ABC_AREA"])
        knobs["ABC_SPEED"] = str(synth["ABC_SPEED"])
    net = _base_netlist(design)
    base_ns = _base_finish_ns(design, clock)

    print(json.dumps({"start": True, "variant": variant, "title": title, "knobs": knobs, "netlist": str(net)}, indent=2))
    ec_p, t_p = _run_wrapper(design, variant, clock, "place", knobs, net)
    place_ns = _place_wns(design, variant)
    dec = decide(design=design, place_wns_ns=place_ns, baseline_finish_ns=base_ns)
    print(json.dumps({"place_exit": ec_p, "place_s": round(t_p, 2), "place_wns_ns": place_ns, "policy": dec.to_dict()}, indent=2))

    extra = {
        "recipe_ids": rids,
        "recipe_id": rids[0] if len(rids) == 1 else None,
        "title": title,
        "knobs": knobs,
        "policy": dec.to_dict(),
        "transfer_design": True,
    }
    rec_cmd = [
        sys.executable,
        str(_LEARN / "scripts/record_experiment.py"),
        "--phase",
        args.phase,
        "--design",
        design,
        "--variant",
        variant,
        "--role",
        "knob",
        "--clock",
        str(clock),
        "--netlist",
        str(net),
        "--extra",
        json.dumps(extra),
        "--notes",
        f"{title}. Transfer cook. Official yosys netlist. Policy {dec.action}.",
    ]

    if ec_p != 0 or place_ns is None:
        rec_cmd += ["--exit-code", str(ec_p or 1), "--status", "failed", "--runtime-s", str(t_p)]
        return subprocess.run(rec_cmd, check=False).returncode or 1

    if dec.action == "STOP":
        rec_cmd += ["--exit-code", "0", "--status", "stopped_by_policy", "--runtime-s", str(t_p)]
        subprocess.run(rec_cmd, check=False)
        print(json.dumps({"ok": True, "variant": variant, "title": title, "stopped": True}))
        return 0

    ec_f, t_f = _run_wrapper(design, variant, clock, "finish", knobs, net)
    rec_cmd += ["--exit-code", str(ec_f), "--runtime-s", str(t_p + t_f)]
    if ec_f != 0:
        rec_cmd += ["--status", "failed"]
    rc = subprocess.run(rec_cmd, check=False).returncode
    # Confirm finish landed.
    exp = Experiment(id="tmp", phase=args.phase, design=design, clock_ns=clock, variant=variant, role="knob")
    fill_from_logs(exp, root=_ROOT)
    print(json.dumps({
        "ok": exp.finish_wns_ns is not None and ec_f == 0,
        "variant": variant,
        "title": title,
        "finish_wns_ns": exp.finish_wns_ns,
        "area": exp.stdcell_um2,
        "ir_mean_v": exp.ir_mean_v,
        "record_rc": rc,
    }, default=str))
    return 0 if exp.finish_wns_ns is not None and ec_f == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
