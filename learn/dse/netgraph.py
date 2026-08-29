"""Fast physical oracle on a mapped netlist (F2-fast).

Not OpenROAD GPL and not GRT. Anchored barycenter + star HPWL + RUDY-class
bin demand, in the spirit of AutoDMP's cheap proxies before an expensive EDA
eval. Structure of the *candidate* netlist changes the metric — ingest of a
finished layout is a different observation.

Never claims Dynamic IR.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path


_PORT = re.compile(r"\.([A-Za-z0-9_]+)\s*\(\s*([^)]+?)\s*\)")
_INST_HEAD = re.compile(
    r"([A-Za-z_][A-Za-z0-9_$]*)\s+(\\[^\s]+\s|[A-Za-z_][A-Za-z0-9_$]*)\s*\("
)
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
    "function",
    "endfunction",
    "task",
    "endtask",
    "primitive",
    "if",
    "for",
    "while",
    "case",
    "casex",
    "casez",
}
_LIBERTY_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*_X\d+$")


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
        return sum(1 for t in self.types.values() if "DFF" in t.upper())

    def n_liberty_types(self) -> int:
        return len({t for t in self.types.values() if _LIBERTY_TYPE.match(t)})


def strip_verilog_comments(text: str) -> str:
    """Drop // and /* */ so a Yosys banner cannot become a fake instance."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                break
            out.append(" ")
            i = j + 2
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _balanced_ports(text: str, open_paren: int) -> tuple[str, int] | None:
    depth = 0
    j = open_paren
    n = len(text)
    while j < n:
        ch = text[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : j], j + 1
        j += 1
    return None


def parse_mapped_verilog(path: Path) -> NetlistGraph:
    """Paren-balanced instance scan. Comments stripped. Assign soup is not cells."""
    text = strip_verilog_comments(Path(path).read_text(errors="replace"))
    g = NetlistGraph()
    i = 0
    while True:
        m = _INST_HEAD.search(text, i)
        if not m:
            break
        kind = m.group(1)
        name = m.group(2).strip().lstrip("\\").rstrip()
        if kind.lower() in _SKIP:
            i = m.end()
            continue
        found = _balanced_ports(text, m.end() - 1)
        if found is None:
            break
        ports, nxt = found
        i = nxt
        if not name or name in g.types:
            continue
        g.cells.append(name)
        g.types[name] = kind
        for pm in _PORT.finditer(ports):
            net = pm.group(2).strip().strip("{} ").split()[0]
            net = net.strip("\\")
            if not net or net in ("1'b0", "1'b1", "1'bx"):
                continue
            g.nets.setdefault(net, set()).add(name)
    g.nets = {n: cs for n, cs in g.nets.items() if len(cs) >= 2}
    return g


def is_gate_cell_netlist(path: Path) -> bool:
    """True when Yosys wrote liberty instances, not assign-lowered gates."""
    p = Path(path)
    if not p.is_file():
        return False
    text = p.read_text(errors="replace")
    if "write_verilog" in text and "-noexpr" in text:
        pass
    g = parse_mapped_verilog(p)
    if g.n_liberty_types() >= 6 and g.n_cells >= 80:
        return True
    if g.n_cells >= 40 and g.n_nets >= max(20, g.n_cells // 4) and g.n_liberty_types() >= 4:
        return True
    return False


def barycenter_place(
    g: NetlistGraph, *, util: float = 0.35, iters: int = 24
) -> dict[str, tuple[float, float]]:
    """Analytic place with a grid *anchor* so a connected graph cannot collapse.

    0.55 neighbor + 0.25 original slot + 0.20 momentum, then scale onto a
    fixed outline (not the collapsed bbox). Deterministic.
    """
    n = max(g.n_cells, 1)
    side = math.sqrt(n / max(util, 0.15))
    cols = max(1, int(math.ceil(math.sqrt(n))))
    rows = max(1, int(math.ceil(n / cols)))
    grid: dict[str, list[float]] = {}
    pos: dict[str, list[float]] = {}
    for i, c in enumerate(g.cells):
        slot = [float(i % cols), float(i // cols)]
        grid[c] = slot
        pos[c] = list(slot)
    nbrs: dict[str, set[str]] = {c: set() for c in g.cells}
    for cells in g.nets.values():
        cl = list(cells)
        for a in cl:
            for b in cl:
                if a != b:
                    nbrs[a].add(b)
    for _ in range(iters):
        nxt: dict[str, list[float]] = {}
        for c, (x, y) in pos.items():
            gx, gy = grid[c]
            adj = nbrs[c]
            if not adj:
                nxt[c] = [0.85 * x + 0.15 * gx, 0.85 * y + 0.15 * gy]
                continue
            sx = sum(pos[a][0] for a in adj) / len(adj)
            sy = sum(pos[a][1] for a in adj) / len(adj)
            nxt[c] = [0.20 * x + 0.55 * sx + 0.25 * gx, 0.20 * y + 0.55 * sy + 0.25 * gy]
        pos = nxt
    out: dict[str, tuple[float, float]] = {}
    dx = max(cols - 1, 1)
    dy = max(rows - 1, 1)
    for c, (x, y) in pos.items():
        out[c] = (x / dx * side, y / dy * side)
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
    """Peak/mean − 1 (RUDY-class). 0 = uniform. Not GRT overflow."""
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
        "n_liberty_types": g.n_liberty_types(),
    }


def estimate_physical(path: Path, *, util: float = 0.35) -> dict:
    g = parse_mapped_verilog(path)
    pos = barycenter_place(g, util=util)
    rudy = rudy_congestion(g, pos)
    return {
        **features(g),
        "hpwl": hpwl(g, pos),
        "hpwl_units": "grid",
        "rudy_excess": rudy,
        "congestion": rudy / (1.0 + rudy),
        "via": "anchored-barycenter+HPWL+RUDY — F2-fast, not GRT, not IR",
    }
