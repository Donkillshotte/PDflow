#!/usr/bin/env python3
"""Print the validated lab ASAP7 spec as JSON. Exit 2 on refuse."""

from __future__ import annotations

import json
import sys

from dse.asap7_lab import LabAsap7Refuse, spec_from_env, validate


def main() -> int:
    try:
        spec = validate(spec_from_env())
    except LabAsap7Refuse as exc:
        print(exc, file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "variant": spec.variant,
                "design": spec.design,
                "config": spec.config_rel,
                "nickname": spec.nickname,
                "corner": spec.corner,
                "vt": " ".join(spec.vt),
                "lib_model": spec.lib_model,
                "track": spec.track,
                "cluster": int(spec.cluster_flops),
                "clk_ps": spec.clk_ps,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
