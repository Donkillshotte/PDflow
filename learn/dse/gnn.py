"""Tiny GNN surrogate on the mapped hypergraph. Never physical truth.

Two mean-aggregate layers + mean/max readout, then ridge from embeddings
to F2-fast HPWL when enough teacher pairs exist. Uncertainty stays high
until n≥4. This is not a neural voltage map and not Dynamic IR gold.
"""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np

from .netgraph import NetlistGraph, parse_mapped_verilog


def graph_embedding(g: NetlistGraph) -> list[float]:
    """2-layer mean-aggregate readout (8-D). Deterministic, no learned weights."""
    n = g.n_cells
    if n == 0:
        return [0.0] * 8
    idx = {c: i for i, c in enumerate(g.cells)}
    is_seq = np.array([1.0 if "DFF" in g.types.get(c, "").upper() else 0.0 for c in g.cells])
    deg = np.zeros(n, dtype=float)
    adj: list[list[int]] = [[] for _ in range(n)]
    for cells in g.nets.values():
        ids = [idx[c] for c in cells if c in idx]
        for a in ids:
            deg[a] += 1.0
            for b in ids:
                if a != b:
                    adj[a].append(b)
    scale = max(float(deg.max()), 1.0)
    x = np.stack([is_seq, deg / scale], axis=1)

    def mean_agg(mat: np.ndarray) -> np.ndarray:
        y = np.zeros_like(mat)
        for i, nbr in enumerate(adj):
            if not nbr:
                y[i] = mat[i]
            else:
                y[i] = 0.5 * mat[i] + 0.5 * mat[nbr].mean(axis=0)
        return y

    h2 = mean_agg(mean_agg(x))
    return [
        float(n),
        float(g.n_nets),
        float(g.avg_degree()),
        float(g.n_seq()),
        float(h2[:, 0].mean()),
        float(h2[:, 1].mean()),
        float(h2[:, 0].max()),
        float(h2[:, 1].max()),
    ]


def embed_path(path) -> list[float]:
    return graph_embedding(parse_mapped_verilog(path))


def _ridge(xs: list[list[float]], ys: list[float], query: list[float], lam: float = 1e-2) -> tuple[float, float]:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    n, d = x.shape
    x1 = np.concatenate([np.ones((n, 1)), x], axis=1)
    q1 = np.concatenate([[1.0], np.asarray(query, dtype=float)])
    a = x1.T @ x1 + lam * np.eye(d + 1)
    try:
        w = np.linalg.solve(a, x1.T @ y)
    except np.linalg.LinAlgError:
        w = np.linalg.lstsq(a, x1.T @ y, rcond=None)[0]
    pred = float(q1 @ w)
    resid = y - x1 @ w
    dof = max(n - d, 1)
    std = float(math.sqrt(max(float(resid @ resid) / dof, 1e-9)))
    return pred, std


def predict_hpwl(
    teachers: Iterable[tuple[list[float], float]],
    query: list[float],
) -> dict:
    pairs = [(list(e), float(y)) for e, y in teachers if y is not None and y > 1.0]
    if not pairs:
        return {
            "metric": "hpwl",
            "mean": None,
            "std": None,
            "n": 0,
            "uncertainty": "high",
            "via": "GNN readout, no F2-fast teachers",
            "not": "Dynamic IR / a neural voltage map",
        }
    ys = [p[1] for p in pairs]
    mean = sum(ys) / len(ys)
    if len(pairs) < 4:
        var = sum((y - mean) ** 2 for y in ys) / max(len(ys) - 1, 1)
        return {
            "metric": "hpwl",
            "mean": mean,
            "std": math.sqrt(var) if len(ys) > 1 else None,
            "n": len(pairs),
            "uncertainty": "high",
            "via": "mean F2-fast HPWL (GNN waits for n≥4)",
            "not": "Dynamic IR / a neural voltage map",
        }
    mu, std = _ridge([p[0] for p in pairs], ys, query)
    return {
        "metric": "hpwl",
        "mean": mu,
        "std": std,
        "n": len(pairs),
        "uncertainty": "medium" if len(pairs) < 8 else "low",
        "via": "2-layer mean-aggregate GNN + ridge on F2-fast HPWL",
        "not": "Dynamic IR / a neural voltage map",
    }
