"""Yosys sequential/combinational equiv helper for Next Level R1."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from .contracts import SemanticContract


def parse_equiv_log(log: str) -> bool:
    if re.search(r"Equivalence successfully proven", log, re.I):
        return True
    if re.search(r"are proven and 0 are unproven", log, re.I):
        return True
    return False


def equiv_rtl_pair(
    gold: Path | str,
    gate: Path | str,
    *,
    top: str = "gcd",
    timeout_s: float = 60.0,
) -> SemanticContract:
    gold, gate = Path(gold), Path(gate)
    if not gold.is_file() or not gate.is_file():
        return SemanticContract(status="fail", vs=str(gold), log="missing_rtl")
    script = f"""
read_verilog {gold}
hierarchy -check -top {top}
proc; flatten; opt_expr; opt_clean
design -save gold_rtl
read_verilog {gate}
hierarchy -check -top {top}
proc; flatten; opt_expr; opt_clean
design -save gate_rtl
design -copy-from gold_rtl -as gold {top}
design -copy-from gate_rtl -as gate {top}
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple
equiv_induct
equiv_status
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ys.log", delete=False) as fh:
        log_path = Path(fh.name)
    try:
        proc = subprocess.run(
            ["yosys", "-q", "-l", str(log_path), "-p", script],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        log = log_path.read_text(errors="replace") + (proc.stderr or "")
        ok = parse_equiv_log(log) and proc.returncode == 0
        return SemanticContract(
            status="pass" if ok else "fail",
            vs=str(gold),
            log=str(log_path),
            engine="yosys_equiv",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return SemanticContract(status="unsupported", vs=str(gold), log=str(exc), engine="yosys_equiv")
