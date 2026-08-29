#!/usr/bin/env python3
"""Replaceable activity layer: when each ITerm switches.

Default: synthetic clock / spatial / simultaneous t50.
VCD/FSDB/SAIF are probed, never mapped onto unnamed gate pins.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

COORD_RE = re.compile(r"(ITermNode|Node)_metal(\d+)_(-?\d+)_(-?\d+)")


def node_xy(name: str) -> tuple[float, float] | None:
    m = COORD_RE.search(name)
    if not m:
        return None
    return float(m.group(3)), float(m.group(4))


def load_insts(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    blob = json.loads(path.read_text())
    return blob.get("insts") or []


def nearest_inst(x: float, y: float, insts: list[dict], max_dbu: float = 800.0):
    best = None
    best_d = max_dbu
    for inst in insts:
        if inst.get("filler"):
            continue
        d = math.hypot(float(inst["x"]) - x, float(inst["y"]) - y)
        if d < best_d:
            best_d = d
            best = inst
    return best


def probe_activity_trace(path: Path | None) -> dict:
    """What a VCD/SAIF/FSDB file can (not) drive. Does not invent pin times."""
    if path is None or not Path(path).is_file():
        return {
            "status": "GAP",
            "kind": "missing",
            "path": None,
            "note": "no VCD/SAIF/FSDB — synthetic t50 only",
        }
    p = Path(path)
    head = p.read_bytes()[:4096]
    kind = "unknown"
    if head.startswith(b"$date") or b"$var" in head:
        kind = "vcd"
    elif b"(SAIF" in head or b"(SAIFILE" in head:
        kind = "saif"
    elif p.suffix.lower() in {".fsdb", ".vf"}:
        kind = "fsdb"
    return {
        "status": "GAP",
        "kind": kind,
        "path": str(p),
        "note": (
            f"{kind} present but RTL/netlist names do not match gate ITerms on this PDN; "
            "no silent pin mapping"
        ),
    }


def plan_events(
    currents: dict[str, float],
    idx: dict[str, int],
    insts: list[dict],
    *,
    mode: str,
    peak_factor: float,
    leak_frac: float,
    period_s: float,
    dur_s: float,
    t50_s: float,
) -> list[dict]:
    """Synthetic vectorless t50. Not STA arrival windows."""
    loads = [(n, i) for n, i in currents.items() if n != "0" and n in idx and i > 0]
    xs = []
    for n, _ in loads:
        xy = node_xy(n)
        xs.append(xy[0] if xy else 0.0)
    xmin, xmax = (min(xs), max(xs)) if xs else (0.0, 1.0)
    span = max(xmax - xmin, 1.0)

    events = []
    for n, i_avg in loads:
        xy = node_xy(n)
        inst = nearest_inst(xy[0], xy[1], insts) if xy else None
        seq = bool(inst and inst.get("seq"))
        leak = leak_frac * i_avg
        q_switch = max(0.0, (i_avg - leak) * period_s)
        i_from_q = (2.0 * q_switch / dur_s) if dur_s > 0 else 0.0
        i_pulse = min(peak_factor * i_avg, i_from_q if i_from_q > 0 else peak_factor * i_avg)
        i_pulse = max(i_pulse, 0.0)
        if mode == "simultaneous":
            t50 = t50_s
        elif mode == "spatial":
            nx = ((xy[0] - xmin) / span) if xy else 0.0
            t50 = t50_s + nx * 0.35 * period_s
        else:
            nx = ((xy[0] - xmin) / span) if xy else 0.0
            if seq:
                t50 = t50_s
            else:
                t50 = t50_s + 0.22 * period_s + nx * 0.25 * period_s
        events.append(
            {
                "node": n,
                "idx": idx[n],
                "i_avg": i_avg,
                "i_leak": leak,
                "i_peak": leak + i_pulse,
                "i_pulse": i_pulse,
                "t50_s": t50,
                "dur_s": dur_s,
                "seq": seq,
                "cell": (inst or {}).get("cell"),
                "inst": (inst or {}).get("name"),
                "x": xy[0] if xy else None,
                "y": xy[1] if xy else None,
            }
        )
    return events
