#!/usr/bin/env python3
"""Emit a coarse HotSpot .flp + .ptrace from GCD DIEAREA + report_power watts.

Architecture compact model (UVA HotSpot). Not Ansys / not foundry.
Dimensions stay in meters. Power is split across a 2×2 grid of the die.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def die_m(def_path: Path) -> tuple[float, float]:
    text = def_path.read_text(errors="replace")
    m = re.search(r"DIEAREA\s*\(\s*(\d+)\s+(\d+)\s*\)\s*\(\s*(\d+)\s+(\d+)\s*\)", text)
    if not m:
        raise SystemExit(f"no DIEAREA in {def_path}")
    # Nangate DEF is 2000 dbu/µm
    dbu = 2000.0
    w_um = (int(m.group(3)) - int(m.group(1))) / dbu
    h_um = (int(m.group(4)) - int(m.group(2))) / dbu
    return w_um * 1e-6, h_um * 1e-6


def total_watts(activity_log: Path | None, fallback: float) -> float:
    if activity_log and activity_log.is_file():
        text = activity_log.read_text(errors="replace")
        for line in text.splitlines():
            if line.startswith("Total") and "Power" not in line:
                parts = line.split()
                for tok in reversed(parts):
                    try:
                        w = float(tok)
                    except ValueError:
                        continue
                    if 0 < w < 2:
                        return w
    return fallback


def write_deck(flp: Path, ptrace: Path, w: float, h: float, watts: float) -> dict:
    nx = ny = 2
    bw, bh = w / nx, h / ny
    names = []
    lines = [
        "# FlowLab GCD architecture floorplan (meters). HotSpot compact model.",
    ]
    share = watts / (nx * ny)
    ptrace_vals = []
    for j in range(ny):
        for i in range(nx):
            name = f"blk_{i}_{j}"
            names.append(name)
            lines.append(f"{name}\t{bw:.8e}\t{bh:.8e}\t{i * bw:.8e}\t{j * bh:.8e}")
            ptrace_vals.append(f"{share:.6e}")
    flp.write_text("\n".join(lines) + "\n")
    ptrace.write_text("\t".join(names) + "\n" + "\t".join(ptrace_vals) + "\n")
    return {
        "die_w_m": w,
        "die_h_m": h,
        "n_blocks": nx * ny,
        "watts_total": watts,
        "watts_per_block": share,
        "flp": str(flp),
        "ptrace": str(ptrace),
    }


def parse_steady(path: Path) -> dict:
    """HotSpot steady-state: name\\ttemperature_K (or similar)."""
    temps: dict[str, float] = {}
    if not path.is_file():
        return {"ok": False, "reason": f"missing {path}"}
    for raw in path.read_text(errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.replace(",", " ").split()
        if len(parts) < 2:
            continue
        try:
            t = float(parts[-1])
        except ValueError:
            continue
        name = parts[0]
        # Skip header-ish
        if name.lower() in {"unit", "name", "node"}:
            continue
        temps[name] = t
    if not temps:
        return {"ok": False, "reason": f"no temperatures in {path}", "raw": path.read_text()[:400]}
    tmax = max(temps.values())
    tmin = min(temps.values())
    # HotSpot reports Kelvin
    return {
        "ok": True,
        "t_max_k": tmax,
        "t_min_k": tmin,
        "t_max_c": tmax - 273.15,
        "t_min_c": tmin - 273.15,
        "n_nodes": len(temps),
        "by_node": temps,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--def", dest="defn", required=True)
    ap.add_argument("--activity-log")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--watts", type=float, default=0.00817)
    ap.add_argument("--parse")
    args = ap.parse_args()
    if args.parse:
        rec = parse_steady(Path(args.parse))
        print(json.dumps(rec, indent=2))
        return 0 if rec.get("ok") else 1
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    w, h = die_m(Path(args.defn))
    watts = total_watts(Path(args.activity_log) if args.activity_log else None, args.watts)
    meta = write_deck(out / "gcd.flp", out / "gcd.ptrace", w, h, watts)
    (out / "deck.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
