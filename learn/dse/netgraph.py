"""Fast physical oracle on a mapped netlist (F2-fast).

Not OpenROAD GPL and not GRT. Barycenter placement + star HPWL + RUDY-class
bin demand, in the spirit of AutoDMP's cheap proxies (RSMT/RUDY) before an
expensive EDA eval. Structure of the *candidate* netlist changes the metric —
ingest of a finished layout is a different observation.

Never claims Dynamic IR.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path


_PORT = re.compile(r"\.([A-Za-z0-9_]+)\s*\(\s*([^)]+?)\s*\)")
_SKIP = {
    "module",
    "endmodule",
    "wire",
    "input",
    "output",
    "inout",
    "assign",
    "reg",
    "supply0",
    "supply1",
}


@dataclass
class NetlistGraph:
    cells: list[str] = field(default_factory=list)
    types: dict[str, str] = field(default_factory=dict)
    nets: dict[str, set[str]] = field(default_factory=dict)

    @property
    def n_cells(self) -> int:
        return len(self.cells)

    @property
    def n_nets(self) -> int:
        return len(self.nets)

    def avg_degree(self) -> float:
        if not self.cells:
            return 0.0
        deg = {c: 0 for c in self.cells}
        for pins in self.nets.values():
            for c in pins:
                if c in deg:
                    deg[c] += 1
        return sum(deg.values()) / len(self.cells)

    def n_seq(self) -> int:
        return sum(1 for t in self.types.values() if t.upper().startswith("DFF") or "DFF" in t.upper())


def parse_mapped_verilog(path: Path) -> NetlistGraph:
    text = Path(path).read_text(errors="replace")
    g = NetlistGraph()
    # Flatten port lists that wrap lines
    blob = re.sub(r"\s+", " ", text)
    for m in re.finditer(
        r"([A-Za-z_][A-Za-z0-9_]*)\s+(\S+)\s*\((.*?)\)\s*;",
        blob,
    ):
        kind, name, ports = m.group(1), m.group(2).strip("\\"), m.group(3)
        if kind.lower() in _SKIP:
            continue
        if name in ("module",) or kind in ("wire",):
            continue
        g.cells.append(name)
        g.types[name] = kind
        for pm in _PORT.finditer(ports):
            net = pm.group(2).strip().strip("{} ").split()[0]
            net = net.strip("\\")
            if not net or net in ("1'b0", "1'b1", "1'bx"):
                continue
            g.nets.setdefault(net, set()).add(name)
    # drop nets that touch <2 cells (ports)
    g.nets = {n: cs for n, cs in g.nets.items() if len(cs) >= 2}
    return g


def barycenter_place(g: NetlistGraph, *, util: float = 0.35, iters: int = 24) -> dict[str, tuple[float, float]]:
    """Cheap analytic place: neighbor barycenter + box scale. Deterministic."""
    n = max(g.n_cells, 1)
    side = math.sqrt(n / max(util, 0.15))
    # grid init
    cols = max(1, int(math.ceil(math.sqrt(n))))
    pos: dict[str, list[float]] = {}
    for i, c in enumerate(g.cells):
        pos[c] = [float(i % cols), float(i // cols)]
    nbrs: dict[str, set[str]] = {c: set() for c in g.cells}
    for cells in g.nets.values():
        cl = list(cells)
        for a in cl:
            for b in cl:
                if a != b:
                    nbrs[a].add(b)
    for _ in range(iters):
        nxt = {}
        for c, (x, y) in pos.items():
            adj = nbrs[c]
            if not adj:
                nxt[c] = [x, y]
                continue
            sx = sum(pos[a][0] for a in adj)
            sy = sum(pos[a][1] for a in adj)
            nxt[c] = [0.35 * x + 0.65 * sx / len(adj), 0.35 * y + 0.65 * sy / len(adj)]
        pos = nxt
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    dx = max(maxx - minx, 1e-9)
    dy = max(maxy - miny, 1e-9)
    out = {}
    for c, (x, y) in pos.items():
        out[c] = ((x - minx) / dx * side, (y - miny) / dy * side)
    return out


def hpwl(g: NetlistGraph, pos: dict[str, tuple[float, float]]) -> float:
    total = 0.0
    for cells in g.nets.values():
        xs = [pos[c][0] for c in cells if c in pos]
        ys = [pos[c][1] for c in cells if c in pos]
        if len(xs) < 2:
            continue
        total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return float(total)


def rudy_congestion(g: NetlistGraph, pos: dict[str, tuple[float, float]], bins: int = 8) -> float:
    """Peak / mean bin demand (RUDY-class). 1.0 = uniform. Lower is better after we store peak/mean-1? 

    We store (peak/mean) so 1.0 is flat, larger is hotter. QoR minimizes congestion —
    use (peak/mean - 1) so uniform → 0.
    """
    if not pos:
        return 0.0
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    minx, maxx = min(xs), max(xs) + 1e-9
    miny, maxy = min(ys), max(ys) + 1e-9
    demand = [[0.0] * bins for _ in range(bins)]

    def bin_of(x, y):
        i = min(bins - 1, max(0, int((x - minx) / (maxx - minx) * bins)))
        j = min(bins - 1, max(0, int((y - miny) / (maxy - miny) * bins)))
        return i, j

    for cells in g.nets.values():
        pts = [pos[c] for c in cells if c in pos]
        if len(pts) < 2:
            continue
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        i0, j0 = bin_of(x0, y0)
        i1, j1 = bin_of(x1, y1)
        nbox = max(1, (i1 - i0 + 1) * (j1 - j0 + 1))
        share = 1.0 / nbox
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                demand[i][j] += share
    flat = [d for row in demand for d in row]
    mean = sum(flat) / len(flat) if flat else 1.0
    peak = max(flat) if flat else 0.0
    if mean <= 1e-12:
        return 0.0
    return float(peak / mean - 1.0)


def features(g: NetlistGraph) -> dict:
    return {
        "n_cells": g.n_cells,
        "n_nets": g.n_nets,
        "avg_degree": round(g.avg_degree(), 4),
        "n_seq": g.n_seq(),
        "n_comb": g.n_cells - g.n_seq(),
    }


def estimate_physical(path: Path, *, util: float = 0.35) -> dict:
    g = parse_mapped_verilog(path)
    pos = barycenter_place(g, util=util)
    return {
        **features(g),
        "hpwl": hpwl(g, pos),
        "congestion": rudy_congestion(g, pos),
        "via": "barycenter+HPWL+RUDY — F2-fast, not GRT, not IR",
    }
