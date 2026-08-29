#!/usr/bin/env python3
"""Replaceable current-waveform layer for Dynamic IR.

GCD default: per-ITerm triangle from I_avg (NLDM). Liberty CCS/ECSM is
*probed and interpolated when tables exist*, never invented from NLDM —
Nangate45 has no current tables.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

CCS_RE = re.compile(r"\b(ccs_table|output_current|ccsn_first_stage|ecsm_cap)\b", re.I)
NLDM_RE = re.compile(r"\b(cell_rise|cell_fall|rise_transition|fall_transition)\b", re.I)
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_TABLE = re.compile(
    r"output_current_(?P<dir>rise|fall)\s*\([^)]*\)\s*\{(?P<body>[^{}]+)\}",
    re.I | re.S,
)


def triangle_above_leak(t: float, t50: float, dur: float, i_pulse: float) -> float:
    if dur <= 0 or i_pulse <= 0:
        return 0.0
    half = 0.5 * dur
    tau = t - t50
    if abs(tau) >= half:
        return 0.0
    return i_pulse * (1.0 - abs(tau) / half)


def _floats(s: str) -> list[float]:
    return [float(x) for x in _NUM.findall(s)]


def parse_ccs_output_current(text: str) -> list[dict]:
    """Parse Liberty output_current_rise/fall tables. Empty if none — never synthesized."""
    tables = []
    for m in _TABLE.finditer(text):
        body = m.group("body")
        idx1 = _floats(_index_blob(body, 1))
        idx2 = _floats(_index_blob(body, 2))
        vals = _floats(_values_blob(body))
        if len(idx1) < 1 or len(idx2) < 1 or not vals:
            continue
        need = len(idx1) * len(idx2)
        if len(vals) < need:
            continue
        grid = []
        k = 0
        for _ in idx1:
            row = vals[k : k + len(idx2)]
            grid.append(row)
            k += len(idx2)
        tables.append(
            {
                "direction": m.group("dir").lower(),
                "index_1": idx1,
                "index_2": idx2,
                "values": grid,
            }
        )
    return tables


def _index_blob(body: str, n: int) -> str:
    m = re.search(rf"index_{n}\s*\((.*?)\)", body, re.S)
    return m.group(1) if m else ""


def _values_blob(body: str) -> str:
    m = re.search(r"values\s*\((.*)\)\s*;", body, re.S)
    return m.group(1) if m else ""


def _interp1(xs: list[float], ys: list[float], x: float) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            if xs[i + 1] == xs[i]:
                return ys[i]
            u = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + u * (ys[i + 1] - ys[i])
    return ys[-1]


def interpolate_ccs_current(table: dict, x: float, y: float) -> float:
    """Bilinear I(index_1, index_2). Typical CCS: slew × Vout → I."""
    xs = table["index_1"]
    ys = table["index_2"]
    grid = table["values"]
    col = [_interp1(ys, grid[i], y) for i in range(len(xs))]
    return _interp1(xs, col, x)


def probe_liberty_current_model(path: Path | None) -> dict:
    """What current tables exist. Does not synthesize CCS from NLDM."""
    if path is None or not Path(path).is_file():
        return {
            "status": "GAP",
            "kind": "missing",
            "path": None,
            "ccs": False,
            "ecsm": False,
            "nldm_timing": False,
            "n_ccs_tables": 0,
            "note": "no Liberty file — cannot build I_cell(t) from tables",
        }
    p = Path(path)
    text = p.read_text(errors="replace")[:2_000_000]
    tables = parse_ccs_output_current(text)
    ccs = bool(CCS_RE.search(text) or tables)
    nldm = bool(NLDM_RE.search(text))
    if tables:
        kind, status = "ccs_output_current", "READY"
        note = (
            f"{len(tables)} output_current table(s) parsed — interpolator READY; "
            "GCD Nangate mesh still uses triangle unless a cell Vout(t) is supplied"
        )
    elif ccs:
        kind, status = "ccs_or_ecsm", "PARTIAL"
        note = "CCS/ECSM keywords present but no parseable output_current tables"
    elif nldm:
        kind, status = "nldm", "GAP"
        note = "NLDM delay/slew only — no CCS/ECSM current tables; triangle from I_avg is not a substitute"
    else:
        kind, status = "unknown", "GAP"
        note = "Liberty has no recognized NLDM or CCS current tables"
    return {
        "status": status if tables else ("PARTIAL" if ccs else "GAP"),
        "kind": kind,
        "path": str(p),
        "ccs": ccs,
        "ecsm": "ecsm" in text.lower(),
        "nldm_timing": nldm,
        "n_ccs_tables": len(tables),
        "note": note,
    }


def current_source_for_event(ev: dict, t: float, *, ccs_tables: list[dict] | None = None) -> float:
    """I_switch(t) above leak. CCS only when a table and (slew, vout) are given."""
    tables = ccs_tables or []
    slew = ev.get("slew_s")
    vout = ev.get("vout")
    if tables and slew is not None and vout is not None:
        direction = ev.get("direction") or "fall"
        tab = next((tb for tb in tables if tb["direction"] == direction), tables[0])
        return interpolate_ccs_current(tab, float(slew), float(vout))
    return triangle_above_leak(t, ev["t50_s"], ev["dur_s"], ev["i_pulse"])


SYNTHETIC_CCS_LIB = """
library (dpn_synth_ccs) {
  cell (INVX1) {
    pin (ZN) {
      direction : output;
      output_current_fall (dummy) {
        index_1 ("0.01, 0.05");
        index_2 ("0.0, 0.55, 1.1");
        values ("1.0e-3, 2.0e-3, 3.0e-3", "2.0e-3, 4.0e-3, 6.0e-3");
      }
    }
  }
}
"""
