"""Datapath e-graph / equality saturation (ROVER-class, not a fork).

ROVER and ASPEN are not open-source; SmoothE is an extractor, not a rewriter.
This module is a small e-graph for the operators that actually appear in the
GCD datapath (sub, unsigned lt, is-zero) so architecture search explores
*equivalent* implementations instead of inventing RTL.

Extraction:
  greedy   — bottom-up structural cost (ILP-class, no commercial ILP)
  softmax  — SmoothE-inspired expected-cost / temperature weights
  forced   — named rewrite for EDA feedback (ASPEN: extract, then measure)

Never a physical oracle. Cost is a relative gate-slice proxy.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ENode:
    op: str
    children: tuple[int, ...] = ()


# Relative 16-bit slice costs. Lower is cheaper. Not µm².
COST = {
    "a": 0.0,
    "b": 0.0,
    "sub": 16.0,
    "add": 16.0,
    "not": 8.0,
    "inc": 16.0,
    "lt": 12.0,
    "eqz": 8.0,
    "orred": 6.0,
    "borrow": 18.0,
}


class EGraph:
    def __init__(self) -> None:
        self._parent: list[int] = []
        self._rank: list[int] = []
        self._nodes: list[ENode] = []
        self._node_class: list[int] = []
        self._hash: dict[ENode, int] = {}
        self.rules_fired: int = 0

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def add(self, op: str, children: tuple[int, ...] = ()) -> int:
        children = tuple(self.find(c) for c in children)
        key = ENode(op, children)
        if key in self._hash:
            return self.find(self._hash[key])
        cid = len(self._parent)
        self._parent.append(cid)
        self._rank.append(0)
        nid = len(self._nodes)
        self._nodes.append(key)
        self._node_class.append(cid)
        self._hash[key] = cid
        return cid

    def merge(self, a: int, b: int) -> int:
        a, b = self.find(a), self.find(b)
        if a == b:
            return a
        if self._rank[a] < self._rank[b]:
            a, b = b, a
        self._parent[b] = a
        if self._rank[a] == self._rank[b]:
            self._rank[a] += 1
        return a

    def rebuild(self) -> None:
        changed = True
        while changed:
            changed = False
            seen: dict[ENode, int] = {}
            for nid, node in enumerate(self._nodes):
                canon = ENode(node.op, tuple(self.find(c) for c in node.children))
                cid = self.find(self._node_class[nid])
                if canon in seen:
                    other = self.find(seen[canon])
                    if other != cid:
                        self.merge(other, cid)
                        changed = True
                else:
                    seen[canon] = cid
        self._hash = {}
        for nid, node in enumerate(self._nodes):
            canon = ENode(node.op, tuple(self.find(c) for c in node.children))
            self._hash[canon] = self.find(self._node_class[nid])

    def members(self, cid: int) -> list[ENode]:
        r = self.find(cid)
        out = []
        for nid, node in enumerate(self._nodes):
            if self.find(self._node_class[nid]) == r:
                out.append(ENode(node.op, tuple(self.find(c) for c in node.children)))
        return out

    def has_op(self, cid: int, op: str) -> bool:
        return any(n.op == op for n in self.members(cid))

    def n_eclasses(self) -> int:
        return len({self.find(i) for i in range(len(self._parent))})

    def saturate(self, max_iter: int = 12) -> None:
        for _ in range(max_iter):
            n0, c0 = len(self._nodes), self.n_eclasses()
            snapshot = list(enumerate(self._nodes))
            for nid, node in snapshot:
                cid = self.find(self._node_class[nid])
                kids = tuple(self.find(c) for c in node.children)
                self._apply(cid, node.op, kids)
            self.rebuild()
            if len(self._nodes) == n0 and self.n_eclasses() == c0:
                return

    def _apply(self, cid: int, op: str, kids: tuple[int, ...]) -> None:
        if op == "sub" and len(kids) == 2:
            ny = self.add("not", (kids[1],))
            iy = self.add("inc", (ny,))
            alt = self.add("add", (kids[0], iy))
            if self.find(alt) != cid:
                self.merge(cid, alt)
                self.rules_fired += 1
        elif op == "add" and len(kids) == 2:
            for n in self.members(kids[1]):
                if n.op != "inc" or len(n.children) != 1:
                    continue
                for m in self.members(n.children[0]):
                    if m.op == "not" and len(m.children) == 1:
                        alt = self.add("sub", (kids[0], m.children[0]))
                        if self.find(alt) != cid:
                            self.merge(cid, alt)
                            self.rules_fired += 1
        elif op == "eqz" and len(kids) == 1:
            red = self.add("orred", kids)
            alt = self.add("not", (red,))
            if self.find(alt) != cid:
                self.merge(cid, alt)
                self.rules_fired += 1
        elif op == "not" and len(kids) == 1:
            for n in self.members(kids[0]):
                if n.op == "orred" and len(n.children) == 1:
                    alt = self.add("eqz", n.children)
                    if self.find(alt) != cid:
                        self.merge(cid, alt)
                        self.rules_fired += 1
                if n.op == "not" and len(n.children) == 1:
                    if self.find(n.children[0]) != cid:
                        self.merge(cid, n.children[0])
                        self.rules_fired += 1
        elif op == "lt" and len(kids) == 2:
            alt = self.add("borrow", kids)
            if self.find(alt) != cid:
                self.merge(cid, alt)
                self.rules_fired += 1
        elif op == "borrow" and len(kids) == 2:
            alt = self.add("lt", kids)
            if self.find(alt) != cid:
                self.merge(cid, alt)
                self.rules_fired += 1

    def extract_greedy(self, root: int) -> tuple[ENode, float]:
        """Min structural cost per e-class (sharing ignored — n is tiny)."""
        memo: dict[int, tuple[ENode, float]] = {}
        visiting: set[int] = set()

        def cost_of(cid: int) -> tuple[ENode, float]:
            cid = self.find(cid)
            if cid in memo:
                return memo[cid]
            if cid in visiting:
                return ENode("cycle"), 1e9
            visiting.add(cid)
            best: tuple[ENode, float] | None = None
            for n in self.members(cid):
                total = COST.get(n.op, 32.0)
                for ch in n.children:
                    _, cc = cost_of(ch)
                    total += cc
                if best is None or total < best[1] - 1e-12:
                    best = (n, total)
            if best is None:
                best = (ENode("?"), 1e9)
            visiting.discard(cid)
            memo[cid] = best
            return best

        return cost_of(root)

    def extract_softmax(self, root: int, temperature: float = 1.0) -> dict:
        """SmoothE-inspired: softmax over −cost/T, expected cost, entropy."""
        cid = self.find(root)
        rows = []
        for n in self.members(cid):
            c = COST.get(n.op, 32.0)
            for ch in n.children:
                _, cc = self.extract_greedy(ch)
                c += cc
            rows.append((n, c))
        if not rows:
            return {"node": None, "expected": None, "entropy": 0.0, "via": "empty"}
        t = max(float(temperature), 1e-6)
        m = min(c for _, c in rows)
        ws = [math.exp(-(c - m) / t) for _, c in rows]
        z = sum(ws) or 1.0
        ps = [w / z for w in ws]
        exp_c = sum(p * c for p, (_, c) in zip(ps, rows))
        ent = -sum(p * math.log(p) for p in ps if p > 1e-15)
        pick = max(range(len(rows)), key=lambda i: ps[i])
        return {
            "node": {"op": rows[pick][0].op, "children": rows[pick][0].children},
            "expected": exp_c,
            "entropy": ent,
            "temperature": t,
            "choices": [
                {"op": n.op, "cost": c, "p": p} for (n, c), p in zip(rows, ps)
            ],
            "via": "softmax expected cost (SmoothE-inspired, no GPU loop)",
        }


def gcd_dpath_egraph() -> tuple[EGraph, dict[str, int]]:
    """Seed the GCD datapath operators and saturate."""
    eg = EGraph()
    a = eg.add("a")
    b = eg.add("b")
    roots = {
        "a": a,
        "b": b,
        "sub": eg.add("sub", (a, b)),
        "lt": eg.add("lt", (a, b)),
        "eqz": eg.add("eqz", (b,)),
    }
    eg.saturate()
    return eg, roots


def available_extracts(eg: EGraph, roots: dict[str, int]) -> list[str]:
    """Named extracts that the e-graph actually discovered."""
    out: list[str] = []
    if eg.has_op(roots["sub"], "add"):
        out.append("sub_twos_complement")
    if eg.has_op(roots["eqz"], "not") or eg.has_op(roots["eqz"], "orred"):
        out.append("eqz_or_reduce")
    if eg.has_op(roots["lt"], "borrow"):
        out.append("lt_borrow")
    return out


def egraph_stats(eg: EGraph, roots: dict[str, int]) -> dict:
    greedy = {k: eg.extract_greedy(r)[0].op for k, r in roots.items() if k not in ("a", "b")}
    soft = {k: eg.extract_softmax(r) for k, r in roots.items() if k not in ("a", "b")}
    return {
        "n_enodes": len(eg._nodes),
        "n_eclasses": eg.n_eclasses(),
        "rules_fired": eg.rules_fired,
        "extracts": available_extracts(eg, roots),
        "greedy_ops": greedy,
        "softmax": {k: {"entropy": v.get("entropy"), "expected": v.get("expected")} for k, v in soft.items()},
        "note": "ROVER-class equality saturation on GCD dpath; not a neural extractor",
    }
