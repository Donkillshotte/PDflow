#!/usr/bin/env python3
"""Autonomous DSE controller: layered search + ingested physical oracles."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "learn") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn"))
if str(_ROOT / "learn" / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "learn" / "scripts"))

from dse.campaign import run_campaign  # noqa: E402
from dse.controller import run_controller  # noqa: E402
from heavy_analysis import require_heavy  # noqa: E402
from dse.flow_role import validate_variant  # noqa: E402


def live_memory_path(variant: str) -> Path:
    """Allocate an isolated memory file for one invocation."""
    safe = validate_variant(variant)
    return _ROOT / "learn" / "sim" / "dse" / "live" / safe / uuid.uuid4().hex / "memory.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-fidelity hardware DSE (layered, not flat)")
    ap.add_argument("--variant", default=os.environ.get("FLOW_VARIANT", "flowlab"))
    ap.add_argument("--budget-s", type=float, default=float(os.environ.get("DSE_BUDGET_S", "45")))
    ap.add_argument("--f1-max", type=int, default=int(os.environ.get("DSE_F1_MAX", "6")))
    ap.add_argument("--rtl", type=Path, default=None)
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="kept for compatibility; every invocation already receives isolated live memory",
    )
    ap.add_argument(
        "--campaign",
        action="store_true",
        help="outer loop on the same JSONL until gated HV stalls (default: one controller pass)",
    )
    ap.add_argument("--campaign-inner", type=int, default=int(os.environ.get("DSE_CAMPAIGN_INNER", "8")))
    ap.add_argument(
        "--wall-s",
        type=float,
        default=None,
        help="campaign total wall seconds (default: campaign-inner × budget-s)",
    )
    ap.add_argument("--hv-eps", type=float, default=float(os.environ.get("DSE_HV_EPS", "0.001")))
    ap.add_argument(
        "--stop-metric",
        default=os.environ.get("DSE_STOP_METRIC", "logic"),
        choices=("logic", "f6"),
        help="campaign HV on logic F3 (legacy) or finish F6",
    )
    ap.add_argument(
        "--next-level",
        action="store_true",
        help="event-driven funnel/scheduler (separate *_nl.jsonl; does not replace the controller tour)",
    )
    ap.add_argument(
        "--launch-finish",
        action="store_true",
        help="with --next-level, allow isolated F6 handoff (never flowlab/learn/AES)",
    )
    ap.add_argument("--finish-shots", type=int, default=int(os.environ.get("DSE_FINISH_SHOTS", "1")))
    args = ap.parse_args()
    args.variant = validate_variant(args.variant)
    rtl_name = str(args.rtl or os.environ.get("DESIGN_ID") or "").lower()
    if "aes" in rtl_name:
        require_heavy("DSE on AES (not GCD FlowLab)")
    if args.next_level:
        if "aes" in str(args.variant).lower():
            require_heavy("DSE Next Level on AES (not GCD FlowLab)")
        from dse.next_level import make_live_runner, run_next_level

        mem_path = live_memory_path(args.variant)
        wall = args.wall_s if args.wall_s is not None else max(float(args.budget_s), 30.0)
        report = run_next_level(
            memory_path=mem_path,
            wall_s=wall,
            runner=make_live_runner(launch_finish=args.launch_finish),
            finish_shots=args.finish_shots,
        )
        print("DSE_NEXT_LEVEL_DONE")
        print(
            f"stop={report.get('stop')} n_actions={report.get('n_actions')} "
            f"shots_left={report.get('finish_shots_left')}"
        )
        print(f"memory → {report.get('memory')}")
        return 0 if report.get("ok") else 1
    if args.campaign:
        wall = args.wall_s
        if wall is None:
            wall = float(args.campaign_inner) * float(args.budget_s)
        mem_path = live_memory_path(args.variant)
        report = run_campaign(
            variant=args.variant,
            inner_budget_s=args.budget_s,
            f1_max_per_run=args.f1_max,
            rtl=args.rtl,
            memory_path=mem_path,
            fresh=True,
            wall_s=wall,
            hv_eps=args.hv_eps,
            max_inner=args.campaign_inner,
            design_id=os.environ.get("DESIGN_ID") or "gcd",
            stop_metric=args.stop_metric,
        )
        print("DSE_CAMPAIGN_DONE")
        print(
            f"stop={report.get('stop')} n_inner={report.get('n_inner')} "
            f"start_inner={report.get('start_inner')} hv={report.get('hv')}"
        )
        print(f"memory → {report.get('memory')}")
        return 0 if report.get("ok") else 1
    report = run_controller(
        variant=args.variant,
        budget_s=args.budget_s,
        f1_max=args.f1_max,
        rtl=args.rtl,
        memory_path=live_memory_path(args.variant),
        fresh=True,
    )
    print("DSE_DONE")
    print(report["summary"])
    print(f"report → {report.get('report')}")
    print(f"memory → {report.get('memory')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
