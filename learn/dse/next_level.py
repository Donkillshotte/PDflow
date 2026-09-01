"""Next-level campaign loop: scheduler decides, evaluators run.

Does not replace ``run_controller`` in one night; it is the new decision
loop. Live F6 launch is opt-in and never targets FLOW_VARIANT=flowlab.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .contracts import stamp_evidence
from .equiv import equiv_rtl_pair
from .f6_finish import assert_baseline_frozen, evaluate_f6, ingest_finish, parse_place_dp, refuse_locked_variant
from .funnel import promote_or_reject
from .memory import DesignMemory
from .scheduler import Action, apply_rejection, next_action

Runner = Callable[[Action, DesignMemory], dict]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_nl_memory(variant: str = "flowlab") -> Path:
    return repo_root() / "learn" / "sim" / "dse" / f"memory_{variant}_nl.jsonl"


def seed_bakeoff(mem: DesignMemory) -> dict[str, Any]:
    """Ingest existing A/B/C finish logs. Does not launch ORFS."""
    assert_baseline_frozen()
    seeded = []
    for variant, geom in (
        ("flowlab", "product"),
        ("flowlab_dse_small", "product"),
        ("flowlab_dse_fast", "product"),
    ):
        logs = repo_root() / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd" / variant / "6_report.json"
        if not logs.is_file():
            continue
        if any((c.knobs or {}).get("variant") == variant and c.fidelity == "F6" for c in mem.all()):
            continue
        c = ingest_finish(mem, variant=variant, parent=None, geometry_kind=geom)
        if variant == "flowlab":
            c.semantic_contract = {"status": "pass", "kind": "same_latency", "vs": "orfs_gcd_rtl", "engine": "baseline"}
            mem.touch(c)
        seeded.append(variant)
    return {"seeded": seeded}


def make_live_runner(
    *,
    launch_finish: bool = False,
    gold_rtl: Path | None = None,
) -> Runner:
    """Real evaluators. Finish launch is opt-in; GNN/bandit are not consulted."""
    gold = Path(gold_rtl) if gold_rtl else repo_root() / "learn/flowlab/gcd.v"

    def runner(action: Action, mem: DesignMemory) -> dict:
        if action.kind == "generate":
            return seed_bakeoff(mem)
        c = mem.get(action.candidate_id) if action.candidate_id else None
        if c is None:
            return {"ok": False, "reason": "missing_candidate"}
        if action.kind == "equiv":
            rtl = None
            for cand in (
                (c.artifacts or {}).get("rtl"),
                c.rtl_fp,
            ):
                if cand and Path(str(cand)).is_file():
                    rtl = Path(str(cand))
                    break
            if rtl is None:
                c.semantic_contract = {
                    "status": "unsupported",
                    "kind": "same_latency",
                    "log": "no_rtl_file",
                    "engine": "yosys_equiv",
                }
                mem.touch(c)
                return {"semantic": c.semantic_contract}
            sem = equiv_rtl_pair(gold, rtl)
            c.semantic_contract = sem.to_dict()
            mem.touch(c)
            return {"semantic": sem.to_dict()}
        if action.kind == "place":
            variant = str((c.knobs or {}).get("variant") or "")
            if not variant:
                return {"ok": False, "reason": "no_variant_for_place"}
            place_path = (
                repo_root()
                / "tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd"
                / variant
                / "3_5_place_dp.json"
            )
            if not place_path.is_file():
                return {"ok": False, "reason": "no_place_log"}
            blob = parse_place_dp(place_path)
            c.artifacts = dict(c.artifacts or {}, **blob)
            if blob.get("place_wns_ns") is not None:
                stamp_evidence(c, "place_wns", float(blob["place_wns_ns"]), "place", str(place_path))
            mem.touch(c)
            return blob
        if action.kind == "finish":
            variant = str((c.knobs or {}).get("variant") or "flowlab_dse_nl")
            if not launch_finish:
                return {"skipped": "finish_launch_disabled"}
            refuse_locked_variant(variant)
            nl = (c.artifacts or {}).get("mapped_v") or c.netlist_fp
            child = evaluate_f6(mem, c, variant=variant, netlist=nl, launch=True)
            return {"id": child.id, "status": child.status}
        if action.kind == "pdn":
            return {"skipped": "pdn_same_extract_only_after_closed_finish"}
        return {"ok": False, "reason": f"unhandled_{action.kind}"}

    return runner


def run_next_level(
    *,
    memory_path: Path,
    wall_s: float,
    runner: Runner,
    finish_shots: int = 1,
    profile: str = "balanced",
) -> dict:
    path = Path(memory_path)
    mem = DesignMemory(path)
    t_end = time.time() + float(wall_s)
    actions: list[dict] = []
    shots_left = int(finish_shots)
    stop = "wall"
    while time.time() < t_end:
        left = t_end - time.time()
        act = next_action(mem, budget_s=left, finish_shots_left=shots_left, profile=profile)
        actions.append(act.to_dict())
        if act.kind == "stop":
            stop = "stop"
            break
        if act.kind == "reject":
            apply_rejection(mem, act)
            continue
        if act.kind == "finish":
            if shots_left <= 0:
                stop = "finish_shots"
                break
            shots_left -= 1
        info = runner(act, mem) or {}
        if act.candidate_id:
            c = mem.get(act.candidate_id)
            if c is not None:
                if act.kind == "pdn":
                    c.artifacts = dict(c.artifacts or {}, pdn_done=True)
                    if info.get("skipped"):
                        c.artifacts["pdn_skipped"] = True
                promote_or_reject(c)
                mem.touch(c)
        if info.get("stop"):
            stop = str(info["stop"])
            break
        if info.get("skipped") and act.kind == "finish":
            stop = "finish_skipped"
            break
    else:
        stop = "wall"
    return {
        "ok": True,
        "stop": stop,
        "n_actions": len(actions),
        "actions": actions,
        "finish_shots_left": shots_left,
        "memory": str(path),
    }
