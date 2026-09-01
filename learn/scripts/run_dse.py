#!/usr/bin/env python3
"""Autonomous DSE controller: layered search + ingested physical oracles."""

from __future__ import annotations

import argparse
import os
import sys
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-fidelity hardware DSE (layered, not flat)")
    ap.add_argument("--variant", default=os.environ.get("FLOW_VARIANT", "flowlab"))
    ap.add_argument("--budget-s", type=float, default=float(os.environ.get("DSE_BUDGET_S", "45")))
    ap.add_argument("--f1-max", type=int, default=int(os.environ.get("DSE_F1_MAX", "6")))
    ap.add_argument("--rtl", type=Path, default=None)
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="wipe the JSONL design memory before this run (default is resume)",
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
    args = ap.parse_args()
    rtl_name = str(args.rtl or os.environ.get("DESIGN_ID") or "").lower()
    if "aes" in rtl_name:
        require_heavy("DSE on AES (not GCD FlowLab)")
    if args.campaign:
        wall = args.wall_s
        if wall is None:
            wall = float(args.campaign_inner) * float(args.budget_s)
        mem_path = _ROOT / "learn" / "sim" / "dse" / f"memory_{args.variant}.jsonl"
        report = run_campaign(
            variant=args.variant,
            inner_budget_s=args.budget_s,
            f1_max_per_run=args.f1_max,
            rtl=args.rtl,
            memory_path=mem_path,
            fresh=args.fresh or os.environ.get("DSE_FRESH") == "1",
            wall_s=wall,
            hv_eps=args.hv_eps,
            max_inner=args.campaign_inner,
            design_id=os.environ.get("DESIGN_ID") or "gcd",
        )
        print("DSE_CAMPAIGN_DONE")
        print(f"stop={report.get('stop')} n_inner={report.get('n_inner')} hv={report.get('hv')}")
        print(f"memory → {report.get('memory')}")
        return 0 if report.get("ok") else 1
    report = run_controller(
        variant=args.variant,
        budget_s=args.budget_s,
        f1_max=args.f1_max,
        rtl=args.rtl,
        fresh=args.fresh or os.environ.get("DSE_FRESH") == "1",
    )
    print("DSE_DONE")
    print(report["summary"])
    print(f"report → {report.get('report')}")
    print(f"memory → {report.get('memory')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
