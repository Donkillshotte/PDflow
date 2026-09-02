"""Shared product cook: official netlist, pinned die, place then maybe finish."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .experiments import DESIGN_CATALOG, Experiment, ExperimentLog, fill_from_logs
from .f6_finish import parse_place_dp
from .fidelity_policy import decide
from .floorplan import FLOORPLAN_RECIPES, official_box, uses_floorplan_def
from .knob_catalog import by_id, config_mk_for, parse_config_defaults, resolve_many, titles_of
from .recipe_labels import synth_method_from_exploration
from .tune_space import fingerprint, project_knobs, title_of_params, variant_name
from .tune_transfer import infer_walls, params_blocked, recipes_blocked

REPO = Path(__file__).resolve().parents[2]
LEARN = Path(__file__).resolve().parents[1]


def base_netlist(design: str) -> Path:
    orfs = DESIGN_CATALOG.get(design, {}).get("orfs_design") or design
    cand = [
        REPO / "tools/OpenROAD-flow-scripts/flow/results/nangate45" / orfs / f"camp_{design}_base" / "1_2_yosys.v",
        REPO / "tools/OpenROAD-flow-scripts/flow/results/nangate45" / orfs / "flowlab" / "1_2_yosys.v",
    ]
    for p in cand:
        if p.is_file():
            return p
    raise FileNotFoundError(f"no official yosys netlist for {design}")


def base_finish_ns(design: str, clock_ns: float, log: ExperimentLog | None = None) -> float | None:
    log = log or ExperimentLog()
    clk = f"{float(clock_ns):.3f}"
    for e in log.all():
        if e.design != design or e.role != "base" or e.finish_wns_ns is None:
            continue
        if f"{float(e.clock_ns):.3f}" == clk:
            return float(e.finish_wns_ns)
    return None


def needs_fresh_synth(recipe_ids: list[str]) -> bool:
    for rid in recipe_ids:
        rec = by_id(rid)
        if rec["stage"] == "synth" and rid != "synth_area":
            return True
    return False


def _run_wrapper(design: str, variant: str, clock_ns: float, target: str, env_knobs: dict[str, str], net: Path | None) -> tuple[int, float]:
    env = os.environ.copy()
    env.update(
        {
            "DESIGN": design,
            "FLOW_VARIANT": variant,
            "SDC_NS": str(clock_ns),
            **env_knobs,
        }
    )
    if net is not None:
        env["SYNTH_NETLIST_FILES"] = str(net)
    t0 = time.time()
    proc = subprocess.run(
        ["bash", str(REPO / "scripts/run_design_finish.sh"), target],
        cwd=str(REPO),
        env=env,
        check=False,
    )
    return proc.returncode, time.time() - t0


def _place_wns(design: str, variant: str) -> float | None:
    orfs = DESIGN_CATALOG.get(design, {}).get("orfs_design") or design
    path = REPO / "tools/OpenROAD-flow-scripts/flow/logs/nangate45" / orfs / variant / "3_5_place_dp.json"
    if not path.is_file():
        return None
    blob = parse_place_dp(path)
    v = blob.get("place_wns_ns")
    return float(v) if v is not None else None


def pin_knobs(design: str, knobs: dict[str, str]) -> dict[str, str]:
    out = dict(knobs)
    out.pop("CORE_UTILIZATION", None)
    out.pop("CORE_ASPECT_RATIO", None)
    if uses_floorplan_def(design):
        # Official DEF already pins the die. DIE_AREA + DEF is illegal.
        out.pop("DIE_AREA", None)
        out.pop("CORE_AREA", None)
    else:
        box = official_box(design)
        if box is not None:
            out["DIE_AREA"] = box["DIE_AREA"]
            out["CORE_AREA"] = box["CORE_AREA"]
        else:
            defaults = parse_config_defaults(config_mk_for(design))
            if "CORE_UTILIZATION" not in out and "CORE_UTILIZATION" in defaults:
                out["CORE_UTILIZATION"] = str(defaults["CORE_UTILIZATION"])
    synth = synth_method_from_exploration()
    if "ABC_SPEED" not in out and "ABC_AREA" not in out:
        out["ABC_AREA"] = str(synth["ABC_AREA"])
        out["ABC_SPEED"] = str(synth["ABC_SPEED"])
    return out


_KEPT = frozenset({"done", "stopped_by_policy"})


def _variant_kept(log: ExperimentLog, variant: str, phase: str | None = None) -> bool:
    """True if this FLOW_VARIANT already has a usable row. Failed cooks may retry."""
    return any(
        e.variant == variant and (phase is None or e.phase == phase) and e.status in _KEPT
        for e in log.all()
    )


def cook_one(
    design: str,
    *,
    recipes: list[str] | None = None,
    knobs: dict[str, str] | None = None,
    phase: str = "J1",
    variant: str | None = None,
    clock_ns: float | None = None,
    extra: dict[str, Any] | None = None,
    log: ExperimentLog | None = None,
    skip_if_variant: bool = False,
) -> dict[str, Any]:
    """Place, maybe finish, record. recipes XOR knobs."""
    rids = list(recipes or [])
    raw_knobs = dict(knobs or {})
    if bool(rids) == bool(raw_knobs):
        return {"ok": False, "refuse": "need exactly one of recipes or knobs", "exit_code": 2}
    if any(rid in FLOORPLAN_RECIPES for rid in rids):
        return {
            "ok": False,
            "refuse": "floorplan recipes are lab-only",
            "exit_code": 2,
        }
    clock = float(clock_ns if clock_ns is not None else DESIGN_CATALOG[design]["clk_ns"])
    log = log or ExperimentLog()
    walls = infer_walls(log.all())
    blocked_rec = recipes_blocked(rids, walls)
    if blocked_rec is not None:
        return {
            "ok": False,
            "refuse": f"walled recipe {blocked_rec.value}",
            "exit_code": 2,
        }
    defaults = parse_config_defaults(config_mk_for(design))
    if rids:
        resolved = resolve_many(rids, defaults)
        title = titles_of(rids)
        var = variant or f"camp_{design}_{'_'.join(rids)}"
        fresh = needs_fresh_synth(rids)
        fp = None
    else:
        projected = project_knobs(raw_knobs, defaults)
        if projected is None:
            return {"ok": False, "refuse": "knobs move the floorplan", "exit_code": 2}
        blocked = params_blocked(projected, walls)
        if blocked is not None:
            return {
                "ok": False,
                "refuse": f"walled {blocked.kind}={blocked.value}",
                "exit_code": 2,
            }
        resolved = dict(raw_knobs)
        title = (extra or {}).get("title") or title_of_params(projected)
        var = variant or variant_name(design, projected, defaults)
        fresh = False
        fp = fingerprint(projected, defaults)
    env = pin_knobs(design, resolved)
    if skip_if_variant and _variant_kept(log, var):
        return {"ok": True, "skipped": True, "variant": var, "phase": phase, "exit_code": 0}
    if _variant_kept(log, var, phase):
        return {"ok": True, "skipped": True, "variant": var, "phase": phase, "exit_code": 0}

    net = None if fresh else base_netlist(design)
    base_ns = base_finish_ns(design, clock, log)
    print(
        json.dumps(
            {
                "start": True,
                "variant": var,
                "title": title,
                "knobs": env,
                "netlist": str(net) if net else None,
                "fresh_synth": net is None,
            },
            indent=2,
        )
    )
    ec_p, t_p = _run_wrapper(design, var, clock, "place", env, net)
    place_ns = _place_wns(design, var)
    dec = decide(design=design, place_wns_ns=place_ns, baseline_finish_ns=base_ns)
    print(
        json.dumps(
            {"place_exit": ec_p, "place_s": round(t_p, 2), "place_wns_ns": place_ns, "policy": dec.to_dict()},
            indent=2,
        )
    )

    blob = {
        **(extra or {}),
        "recipe_ids": rids,
        "recipe_id": rids[0] if len(rids) == 1 else None,
        "title": title,
        "knobs": env,
        "policy": dec.to_dict(),
        "transfer_design": True,
        "fresh_synth": net is None,
    }
    if rids:
        blob["recipe_ids"] = rids
        blob["recipe_id"] = rids[0] if len(rids) == 1 else None
    else:
        blob["recipe_ids"] = []
        blob["recipe_id"] = None
        blob.setdefault("tuner", "tpe")
        if fp:
            blob["fingerprint"] = fp
    how = "Fresh Yosys (synth knob)." if net is None else "Official yosys netlist."
    rec_cmd = [
        sys.executable,
        str(LEARN / "scripts" / "record_experiment.py"),
        "--phase",
        phase,
        "--design",
        design,
        "--variant",
        var,
        "--role",
        "knob",
        "--clock",
        str(clock),
        "--extra",
        json.dumps(blob),
        "--notes",
        f"{title}. Transfer cook. {how} Policy {dec.action}.",
    ]
    if net is not None:
        rec_cmd += ["--netlist", str(net)]

    if ec_p != 0 or place_ns is None:
        rec_cmd += ["--exit-code", str(ec_p or 1), "--status", "failed", "--runtime-s", str(t_p)]
        rc = subprocess.run(rec_cmd, check=False).returncode or 1
        return {"ok": False, "variant": var, "title": title, "status": "failed", "exit_code": rc}

    if dec.action == "STOP":
        rec_cmd += ["--exit-code", "0", "--status", "stopped_by_policy", "--runtime-s", str(t_p)]
        subprocess.run(rec_cmd, check=False)
        print(json.dumps({"ok": True, "variant": var, "title": title, "stopped": True}))
        return {
            "ok": True,
            "variant": var,
            "title": title,
            "stopped": True,
            "status": "stopped_by_policy",
            "exit_code": 0,
        }

    ec_f, t_f = _run_wrapper(design, var, clock, "finish", env, net)
    rec_cmd += ["--exit-code", str(ec_f), "--runtime-s", str(t_p + t_f)]
    if ec_f != 0:
        rec_cmd += ["--status", "failed"]
    rc = subprocess.run(rec_cmd, check=False).returncode
    exp = Experiment(id="tmp", phase=phase, design=design, clock_ns=clock, variant=var, role="knob")
    fill_from_logs(exp, root=REPO)
    ok = exp.finish_wns_ns is not None and ec_f == 0
    print(
        json.dumps(
            {
                "ok": ok,
                "variant": var,
                "title": title,
                "finish_wns_ns": exp.finish_wns_ns,
                "area": exp.stdcell_um2,
                "ir_mean_v": exp.ir_mean_v,
                "record_rc": rc,
            },
            default=str,
        )
    )
    return {
        "ok": ok,
        "variant": var,
        "title": title,
        "status": "done" if ok else "failed",
        "finish_wns_ns": exp.finish_wns_ns,
        "exit_code": 0 if ok else 1,
    }
