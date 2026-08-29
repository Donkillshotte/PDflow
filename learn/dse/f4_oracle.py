"""Budgeted Dynamic IR restamp. Solver A on the cached GCD extract.

The PI stack (system SciPy) is isolated in `learn/scripts/dse_f4_worker.py`
so DSE's NumPy 2 never imports the 1.x scipy.sparse extension.

Same write_pg_spice mesh as the gold run. We may change PDN knobs
(c_decap, pkg L) or scale triangle I(t) by an F3 power ratio.

This is a *candidate* F4 observation — never written over gold 45.298 mV.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
SCRIPTS = REPO / "learn" / "scripts"
ORFS = REPO / "tools/OpenROAD-flow-scripts/flow"
WORKER = SCRIPTS / "dse_f4_worker.py"
GOLD_MV = 45.298
_DIST = "/usr/lib/python3/dist-packages"


def spice_paths(variant: str = "flowlab") -> dict[str, Path]:
    res = ORFS / "results" / "nangate45" / "gcd" / variant
    plat = ORFS / "platforms" / "nangate45"
    return {
        "spice": res / "pdn" / "pg_vdd_bumps.sp",
        "insts": res / "pdn" / "inst_power_map.json",
        "sta": REPO / "learn" / "sim" / "reports" / f"sta_arrivals_{variant}.json",
        "lef": plat / "lef" / "NangateOpenCellLibrary.tech.lef",
        "spef": res / "6_final.spef",
    }


def available(variant: str = "flowlab") -> bool:
    p = spice_paths(variant)
    return p["spice"].is_file() and p["insts"].is_file() and p["sta"].is_file() and WORKER.is_file()


def solve_f4(
    *,
    variant: str = "flowlab",
    pkg_r: float = 0.05,
    pkg_l: float = 2e-10,
    c_decap: float = 50e-15,
    i_scale: float = 1.0,
    dt_ps: float = 10.0,
    timeout_s: float = 90.0,
) -> dict:
    """Solver A only. Same extract; knobs/current scale may change. Not gold."""
    if not available(variant):
        return {
            "status": "GAP",
            "reason": "cached write_pg_spice / STA arrivals missing — not a new extract",
            "gold": False,
            "via": "f4_oracle",
        }
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{_DIST}:{SCRIPTS}"
    cmd = [
        sys.executable,
        str(WORKER),
        "--variant",
        variant,
        "--pkg-r",
        str(pkg_r),
        "--pkg-l",
        str(pkg_l),
        "--c-decap",
        str(c_decap),
        "--i-scale",
        str(i_scale),
        "--dt-ps",
        str(dt_ps),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"status": "fail", "reason": f"F4 worker timeout {timeout_s}s", "gold": False, "via": "f4_oracle"}
    text = (proc.stdout or "").strip().splitlines()
    payload = None
    for line in reversed(text):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if payload is None:
        err = (proc.stderr or proc.stdout or "no json")[-400:]
        return {"status": "fail", "reason": err, "gold": False, "via": "f4_oracle", "rc": proc.returncode}
    payload.setdefault("gold", False)
    return payload
