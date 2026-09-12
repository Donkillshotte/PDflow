#!/usr/bin/env python3
"""Record one experiment from the current invocation's on-disk ORFS logs.

Never launches make finish and never reads a previous experiment to decide the
result. Pass ``--jsonl`` when several records belong to the same invocation.

Usage:
    PYTHONPATH=learn python3 learn/scripts/record_experiment.py \
        --phase P0 --design spi --variant live_spi_base --role base --clock 1.0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LEARN = Path(__file__).resolve().parents[1]
_ROOT = _LEARN.parent
if str(_LEARN) not in sys.path:
    sys.path.insert(0, str(_LEARN))

from dse.experiments import (  # noqa: E402
    DESIGN_CATALOG,
    Experiment,
    ExperimentLog,
    fill_from_logs,
    new_id,
    validate_variant,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", required=True)
    p.add_argument("--design", required=True)
    p.add_argument("--variant", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--clock", type=float, default=None)
    p.add_argument("--netlist", default=None)
    p.add_argument("--orfs-variant", default=None)
    p.add_argument("--orfs-design", default=None)
    p.add_argument("--proxy-wns-ns", type=float, default=None)
    p.add_argument("--runtime-s", type=float, default=0.0)
    p.add_argument("--exit-code", type=int, default=0)
    p.add_argument("--notes", default="")
    p.add_argument("--extra", default=None, help="JSON object stored on Experiment.extra")
    p.add_argument("--status", default=None, help="override (timeout/refused/oom/…)")
    p.add_argument("--jsonl", type=Path, default=None)
    args = p.parse_args(argv)

    validate_variant(args.variant)
    cat = DESIGN_CATALOG.get(args.design, {})
    clock = float(args.clock if args.clock is not None else cat.get("clk_ns") or 0.0)
    exp = Experiment(
        id=new_id(),
        phase=args.phase,
        design=args.design,
        clock_ns=clock,
        variant=args.variant,
        role=args.role,
        netlist=args.netlist,
        runtime_s=float(args.runtime_s),
        exit_code=int(args.exit_code),
        proxy_wns_ns=args.proxy_wns_ns,
        orfs_variant=args.orfs_variant,
        orfs_design=args.orfs_design or cat.get("orfs_design"),
        notes=args.notes,
        extra=json.loads(args.extra) if args.extra else {},
    )
    fill_from_logs(exp, root=_ROOT)
    if args.status in ("timeout", "refused", "oom", "missing_logs", "stopped_by_policy"):
        exp.status = args.status
    elif exp.finish_wns_ns is None:
        exp.status = args.status or ("failed" if args.exit_code else "missing_logs")
    else:
        exp.status = "done"
    log = ExperimentLog(args.jsonl)
    log.append(exp)
    print(json.dumps({"ok": exp.status == "done", "experiment": exp.to_dict()}, default=str))
    return 0 if exp.status in ("done", "timeout", "refused", "oom", "missing_logs", "stopped_by_policy") else 1


if __name__ == "__main__":
    raise SystemExit(main())
