#!/usr/bin/env python3
"""Cook one design-agnostic catalog recipe or a free knob vector.

Does not rewrite Verilog. Reuses the official Yosys netlist of the same-clock
base. Pins DIE_AREA/CORE_AREA from the official DEF. Floorplan catalog
recipes are refused.

Usage:
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/cook_recipe.py \
        --design spi --recipes place_denser --phase J1
    PYTHONPATH=learn:learn/scripts python3 learn/scripts/cook_recipe.py \
        --design gcd --knobs '{"PLACE_DENSITY_LB_ADDON":"0.22"}' --phase T1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LEARN = Path(__file__).resolve().parents[1]
if str(_LEARN) not in sys.path:
    sys.path.insert(0, str(_LEARN))

from dse.cook import cook_one  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--design", required=True)
    p.add_argument("--recipes", nargs="+", default=None)
    p.add_argument("--knobs", default=None, help="JSON object of ORFS env knobs")
    p.add_argument("--phase", default=None, help="Registry phase. Default J1 for recipes, T1 for knobs.")
    p.add_argument("--clock", type=float, default=None)
    p.add_argument("--variant", default=None, help="override FLOW_VARIANT")
    args = p.parse_args(argv)
    knobs = json.loads(args.knobs) if args.knobs else None
    extra = {"tuner": "tpe"} if knobs is not None else None
    phase = args.phase
    if phase is None:
        phase = "T1" if knobs is not None else "J1"
    out = cook_one(
        args.design,
        recipes=args.recipes,
        knobs=knobs,
        phase=phase,
        variant=args.variant,
        clock_ns=args.clock,
        extra=extra,
        skip_if_variant=knobs is not None,
    )
    if out.get("refuse"):
        print(f"refuse: {out['refuse']}", file=sys.stderr)
        return int(out.get("exit_code") or 2)
    if out.get("skipped"):
        print(json.dumps({"skipped": True, "variant": out.get("variant"), "phase": phase}))
        return 0
    return 0 if out.get("ok") else int(out.get("exit_code") or 1)


if __name__ == "__main__":
    raise SystemExit(main())
