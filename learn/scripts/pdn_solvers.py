#!/usr/bin/env python3
"""Linear solvers for the GCD PDN backward-Euler operator.

Solver A — sparse LU (golden).
Solver B — smoothed-aggregation AMG V-cycle + CG (workhorse).
The BE matrix A = G + C/Δt is SPD and independent of I(t), so one setup
serves every current scenario (the multi-scenario reuse of Solver C, without
a rational-Krylov reduced ODE).

Not Ginkgo, not pyamg, not a fork of ESPSim. Classic Vaněk–Mandel–Brezina
SA plus damped Jacobi, coarse LU when n is small.
"""

from __future__ import annotations

import sys
import time

if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, cg, splu

COARSE_N = 64
THETA = 0.25
JACOBI_OMEGA = 0.7
SMOOTH_OMEGA = 0.67
PRESWEEPS = 2
POSTSWEEPS = 2


def _diag_inv(A) -> np.ndarray:
    d = np.array(A.diagonal(), dtype=np.float64)
    d = np.where(np.abs(d) < 1e-30, 1.0, d)
    return 1.0 / d


def jacobi_sweeps(A, dinv: np.ndarray, b: np.ndarray, x: np.ndarray, sweeps: int) -> np.ndarray:
    for _ in range(sweeps):
        x = x + JACOBI_OMEGA * dinv * (b - A @ x)
    return x


def strength_neighbors(A, theta: float = THETA) -> list[list[int]]:
    """i strongly depends on j if -Aij >= theta * max_k(-Aik)."""
    A = A.tocsr()
    n = A.shape[0]
    out: list[list[int]] = [[] for _ in range(n)]
    indptr, indices, data = A.indptr, A.indices, A.data
    for i in range(n):
        sl, sr = indptr[i], indptr[i + 1]
        max_neg = 0.0
        for k in range(sl, sr):
            if indices[k] == i:
                continue
            v = -data[k]
            if v > max_neg:
                max_neg = v
        if max_neg <= 0:
            continue
        thresh = theta * max_neg
        nbrs = []
        for k in range(sl, sr):
            j = indices[k]
            if j == i:
                continue
            if -data[k] >= thresh:
                nbrs.append(int(j))
        out[i] = nbrs
    return out


def build_aggregates(n: int, strong: list[list[int]]) -> tuple[np.ndarray, int]:
    agg = np.full(n, -1, dtype=np.int32)
    nagg = 0
    for i in range(n):
        if agg[i] >= 0:
            continue
        members = [i]
        for j in strong[i]:
            if agg[j] < 0:
                members.append(j)
        for j in members:
            if agg[j] < 0:
                agg[j] = nagg
        nagg += 1
    for i in range(n):
        if agg[i] >= 0:
            continue
        placed = False
        for j in strong[i]:
            if agg[j] >= 0:
                agg[i] = agg[j]
                placed = True
                break
        if not placed:
            agg[i] = nagg
            nagg += 1
    return agg, int(nagg)


def tentative_p(agg: np.ndarray, nagg: int) -> sparse.csr_matrix:
    n = agg.shape[0]
    return sparse.csr_matrix(
        (np.ones(n, dtype=np.float64), (np.arange(n, dtype=np.int32), agg)),
        shape=(n, nagg),
    )


def smooth_prolongation(A, P, omega: float = SMOOTH_OMEGA) -> sparse.csr_matrix:
    dinv = sparse.diags(_diag_inv(A))
    Ps = (P - omega * (dinv @ (A @ P))).tocsr()
    Ps.eliminate_zeros()
    return Ps


class DirectLU:
    name = "A_direct_be"

    def __init__(self, A):
        t0 = time.perf_counter()
        self.A = A.tocsc()
        self.lu = splu(self.A)
        self.setup_s = time.perf_counter() - t0
        self.last_iters = 1
        self.n = A.shape[0]

    def solve(self, b: np.ndarray, x0: np.ndarray | None = None) -> np.ndarray:
        return self.lu.solve(np.asarray(b, dtype=np.float64))


class SAAMG:
    """Smoothed-aggregation AMG; CG on the fine grid, LU on the coarsest."""

    name = "B_sa_amg"

    def __init__(self, A, coarse_n: int = COARSE_N):
        t0 = time.perf_counter()
        self.A = A.tocsr().astype(np.float64)
        self.n = self.A.shape[0]
        self.levels: list[dict] = []
        cur = self.A
        while cur.shape[0] > coarse_n:
            strong = strength_neighbors(cur)
            agg, nagg = build_aggregates(cur.shape[0], strong)
            if nagg < 2 or nagg > 0.85 * cur.shape[0]:
                break
            Ptent = tentative_p(agg, nagg)
            P = smooth_prolongation(cur, Ptent)
            Ac = (P.T @ cur @ P).tocsr()
            self.levels.append({"A": cur, "P": P, "dinv": _diag_inv(cur)})
            cur = Ac
        self.coarse = cur.tocsc()
        self.coarse_lu = splu(self.coarse)
        self.setup_s = time.perf_counter() - t0
        self.last_iters = 0
        self.n_levels = len(self.levels) + 1

    def _vcycle(self, b: np.ndarray, x: np.ndarray, depth: int = 0) -> np.ndarray:
        if depth >= len(self.levels):
            return self.coarse_lu.solve(b)
        lvl = self.levels[depth]
        A, P, dinv = lvl["A"], lvl["P"], lvl["dinv"]
        x = jacobi_sweeps(A, dinv, b, x, PRESWEEPS)
        r = b - A @ x
        rc = P.T @ r
        ec = self._vcycle(rc, np.zeros_like(rc), depth + 1)
        x = x + P @ ec
        x = jacobi_sweeps(A, dinv, b, x, POSTSWEEPS)
        return x

    def _prec(self, r: np.ndarray) -> np.ndarray:
        return self._vcycle(r, np.zeros_like(r))

    def solve(self, b: np.ndarray, x0: np.ndarray | None = None) -> np.ndarray:
        b = np.asarray(b, dtype=np.float64)
        if self.n <= COARSE_N and not self.levels:
            self.last_iters = 1
            return self.coarse_lu.solve(b)
        x0 = np.zeros_like(b) if x0 is None else np.asarray(x0, dtype=np.float64)
        M = LinearOperator((self.n, self.n), matvec=self._prec, dtype=np.float64)
        x, info = cg(self.A, b, x0=x0, M=M, tol=1e-8, maxiter=64, atol=0.0)
        # scipy 1.11: info=0 success; >0 = iters hit; <0 illegal
        if info != 0:
            for _ in range(6):
                x = self._vcycle(b, x)
        self.last_iters = 64 if info > 0 else (0 if info < 0 else 8)
        return x


def make_solver(A, kind: str):
    if kind in ("a", "A", "direct", "lu", "A_direct_be"):
        return DirectLU(A)
    if kind in ("b", "B", "amg", "B_sa_amg"):
        return SAAMG(A)
    raise ValueError(f"unknown solver {kind}")


def residual_rel(A, x: np.ndarray, b: np.ndarray) -> float:
    nb = float(np.linalg.norm(b))
    if nb < 1e-18:
        return float(np.linalg.norm(A @ x - b))
    return float(np.linalg.norm(A @ x - b) / nb)
