"""Budgeted Dynamic IR restamp. Solver A on a write_pg_spice extract.

The PI stack (system SciPy) is isolated in `learn/scripts/dse_f4_worker.py`
so DSE's NumPy 2 never imports the 1.x scipy.sparse extension.

Default: same finish mesh as the gold run. Pass spice/insts for a
*candidate* extract (place_pins+GPL+DP+pdngen). Knobs (c_decap, pkg L)
or I(t)×F3 power may change.

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


def solver_devices() -> dict:
    """CPU is the F4 default. CUDA is reported, never claimed as sign-off."""
    import shutil

    cuda = False
    why = "no nvidia-smi"
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            proc = subprocess.run([smi, "-L"], capture_output=True, text=True, timeout=4)
            cuda = proc.returncode == 0 and "GPU" in (proc.stdout or "")
            why = (proc.stdout or "").strip().splitlines()[0] if cuda else "nvidia-smi listed no GPU"
        except (OSError, subprocess.TimeoutExpired):
            why = "nvidia-smi failed"
    return {
        "cpu": True,
        "cuda": cuda,
        "default_solver": "direct",
        "via": "f4_oracle.solver_devices",
        "note": why if not cuda else f"CUDA visible ({why}) — DirectLU remains the default F4 solver, gold unrestamped",
        "not": "a GPU voltage map / gold restamp",
    }


def spice_paths(variant: str = "flowlab", design_id: str = "gcd") -> dict[str, Path]:
    from .designs import resolve

    spec = resolve(design_id)
    res = ORFS / "results" / spec.platform / spec.orfs_design / variant
    plat = ORFS / "platforms" / spec.platform
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


def extract_ready(spice: Path | str | None, insts: Path | str | None) -> bool:
    return bool(spice and insts and Path(spice).is_file() and Path(insts).is_file() and WORKER.is_file())


def solve_f4(
    *,
    variant: str = "flowlab",
    pkg_r: float = 0.05,
    pkg_l: float = 2e-10,
    c_decap: float = 50e-15,
    i_scale: float = 1.0,
    dt_ps: float = 10.0,
    timeout_s: float = 90.0,
    spice: Path | str | None = None,
    insts: Path | str | None = None,
    extract_kind: str = "finish",
    solver: str = "direct",
    sta: Path | str | None = None,
    device: str = "cpu",
    design_id: str = "gcd",
) -> dict:
    """Named extract + named solver (direct/amg/bicg/ras/krylov). Not gold."""
    if str(device or "cpu") == "cuda" and not solver_devices().get("cuda"):
        return {
            "status": "GAP",
            "reason": "no CUDA device — not claiming a GPU solve, not gold",
            "gold": False,
            "via": "f4_oracle",
            "device": "cpu",
        }
    from .designs import resolve as _resolve_design

    period_ns = float(_resolve_design(design_id).clk_period_ns)
    kind = "candidate" if spice or insts else extract_kind
    if spice or insts:
        if not extract_ready(spice, insts):
            return {
                "status": "GAP",
                "reason": "candidate write_pg_spice / inst map missing — not launching finish",
                "gold": False,
                "extract": "candidate",
                "via": "f4_oracle",
            }
    elif not available(variant):
        return {
            "status": "GAP",
            "reason": "cached write_pg_spice / STA arrivals missing — not a new extract",
            "gold": False,
            "extract": "finish",
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
        "--extract-kind",
        kind,
        "--solver",
        str(solver or "direct"),
        "--period-ns",
        str(period_ns),
    ]
    if spice:
        cmd.extend(["--spice", str(spice), "--no-spef"])
        if sta:
            cmd.extend(["--sta", str(sta)])
        else:
            cmd.append("--no-sta")
    if insts:
        cmd.extend(["--insts", str(insts)])
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
    payload.setdefault("extract", kind)
    return payload
