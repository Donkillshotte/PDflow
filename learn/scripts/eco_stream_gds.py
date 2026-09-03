#!/usr/bin/env python3
"""Stream a GDS from an ECO DEF using the same KLayout merge as ORFS finish.

Env: ECO_DEF, ECO_GDS, ECO_LYT, ECO_CELL_GDS
Run under `klayout -zz -rm` so `pya` is available. Does not call signoff.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
UTIL = _ROOT / "tools/OpenROAD-flow-scripts/flow/util"
if str(UTIL) not in sys.path:
    sys.path.insert(0, str(UTIL))

import def2stream  # noqa: E402

try:
    import pya
except ImportError:
    print("FAIL eco_stream_gds.py must run under klayout (no pya)")
    raise SystemExit(2)

required = ("ECO_DEF", "ECO_GDS", "ECO_LYT", "ECO_CELL_GDS")
missing = [k for k in required if not os.environ.get(k)]
if missing:
    print("FAIL missing", " ".join(missing))
    raise SystemExit(2)

errors = def2stream.merge_gds(
    pya_mod=pya,
    tech_file=os.environ["ECO_LYT"],
    layer_map="",
    in_def=os.environ["ECO_DEF"],
    design_name="gcd",
    in_files=os.environ["ECO_CELL_GDS"],
    seal_file="",
    out_file=os.environ["ECO_GDS"],
)
print(f"ECO_STREAM_GDS errors={errors} out={os.environ['ECO_GDS']}")
raise SystemExit(0 if errors == 0 else 1)
