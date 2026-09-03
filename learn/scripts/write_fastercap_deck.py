#!/usr/bin/env python3
"""Emit a FasterCap 3D two-trace-over-ground deck (meters)."""

from __future__ import annotations

from pathlib import Path


def _quad(name: str, pts: list[tuple[float, float, float]]) -> str:
    flat = " ".join(f"{c:.8e}" for p in pts for c in p)
    return f"Q {name} {flat}\n"


def write_box(path: Path, name: str, x0: float, y0: float, z0: float,
              dx: float, dy: float, dz: float) -> None:
    x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
    faces = [
        [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
        [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
        [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
        [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
        [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
    ]
    path.write_text("".join(_quad(name, f) for f in faces))


def write_plate(path: Path, name: str, x0: float, y0: float, z0: float,
                dx: float, dy: float) -> None:
    pts = [(x0, y0, z0), (x0 + dx, y0, z0), (x0 + dx, y0 + dy, z0), (x0, y0 + dy, z0)]
    path.write_text(_quad(name, pts))


def write_two_trace_deck(
    out_dir: Path,
    *,
    w: float,
    t: float,
    h: float,
    s: float,
    length: float,
    epsr: float,
    scale: float = 1e-6,
) -> Path:
    """w/t/h/s/length in µm. Writes out_dir/two_trace.lst."""
    out_dir.mkdir(parents=True, exist_ok=True)
    wm, tm, hm, sm, lm = (v * scale for v in (w, t, h, s, length))
    margin = 4.0 * hm
    write_plate(
        out_dir / "gnd.txt",
        "gnd",
        -margin,
        -margin,
        0.0,
        wm + sm + wm + 2 * margin,
        lm + 2 * margin,
    )
    write_box(out_dir / "trace_a.txt", "a", 0.0, 0.0, hm, wm, lm, tm)
    write_box(out_dir / "trace_b.txt", "b", wm + sm, 0.0, hm, wm, lm, tm)
    lst = out_dir / "two_trace.lst"
    lst.write_text(
        "* Educational 2-trace over ground (FasterCap). Units: meters.\n"
        f"* W={w} T={t} H={h} S={s} L={length} um  epsr={epsr}\n"
        f"C gnd.txt {epsr} 0 0 0\n"
        f"C trace_a.txt {epsr} 0 0 0\n"
        f"C trace_b.txt {epsr} 0 0 0\n"
    )
    return lst
