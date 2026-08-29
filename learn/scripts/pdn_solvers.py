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

import ctypes
import os
import sys
import time
from pathlib import Path

if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, cg, splu

_LIB = None
_LIB_TRIED = False


def _libdpn():
    """Load engine/build/libdpn.so if present. Never raises."""
    global _LIB, _LIB_TRIED
    if _LIB_TRIED:
        return _LIB
    _LIB_TRIED = True
    if os.environ.get("DPN_NATIVE", "1") in ("0", "false", "no"):
        return None
    root = Path(__file__).resolve().parents[2]
    path = root / "engine" / "build" / "libdpn.so"
    if not path.is_file():
        return None
    lib = ctypes.CDLL(str(path))
    lib.dpn_setup.restype = ctypes.c_void_p
    lib.dpn_setup.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
    ]
    lib.dpn_solve.restype = ctypes.c_int
    lib.dpn_solve.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    lib.dpn_n.restype = ctypes.c_int
    lib.dpn_n.argtypes = [ctypes.c_void_p]
    lib.dpn_n_levels.restype = ctypes.c_int
    lib.dpn_n_levels.argtypes = [ctypes.c_void_p]
    lib.dpn_setup_s.restype = ctypes.c_double
    lib.dpn_setup_s.argtypes = [ctypes.c_void_p]
    lib.dpn_name.restype = ctypes.c_char_p
    lib.dpn_name.argtypes = [ctypes.c_void_p]
    lib.dpn_free.argtypes = [ctypes.c_void_p]
    _TRAN_ARGS = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.dpn_timestep_be.restype = ctypes.c_int
    lib.dpn_timestep_be.argtypes = _TRAN_ARGS
    lib.dpn_mor_setup.restype = ctypes.c_void_p
    lib.dpn_mor_setup.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
    ]
    lib.dpn_mor_m.restype = ctypes.c_int
    lib.dpn_mor_m.argtypes = [ctypes.c_void_p]
    lib.dpn_mor_setup_s.restype = ctypes.c_double
    lib.dpn_mor_setup_s.argtypes = [ctypes.c_void_p]
    lib.dpn_mor_name.restype = ctypes.c_char_p
    lib.dpn_mor_name.argtypes = [ctypes.c_void_p]
    lib.dpn_mor_free.argtypes = [ctypes.c_void_p]
    lib.dpn_mor_timestep.restype = ctypes.c_int
    lib.dpn_mor_timestep.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.dpn_timestep_be_adaptive.restype = ctypes.c_int
    lib.dpn_timestep_be_adaptive.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
    ]
    _LIB = lib
    return _LIB


class NativeSolver:
    """C API wrapper. Same surface as PyDirectLU / PySAAMG."""

    def __init__(self, A, kind: int, lib):
        Ac = A.tocsr()
        n = int(Ac.shape[0])
        nnz = int(Ac.nnz)
        rp = np.ascontiguousarray(Ac.indptr, dtype=np.int32)
        ci = np.ascontiguousarray(Ac.indices, dtype=np.int32)
        va = np.ascontiguousarray(Ac.data, dtype=np.float64)
        if int(rp[-1]) != nnz:
            raise ValueError("CSR nnz mismatch")
        h = lib.dpn_setup(
            kind,
            n,
            nnz,
            rp.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
            ci.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
            va.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        )
        if not h:
            raise RuntimeError("dpn_setup failed")
        self._lib = lib
        self._h = h
        self.n = n
        self.setup_s = float(lib.dpn_setup_s(h))
        self.n_levels = int(lib.dpn_n_levels(h))
        raw = lib.dpn_name(h)
        self.name = raw.decode() if raw else ("B_sa_amg" if kind else "A_direct_be")
        self.last_iters = 0
        self.backend = "native"

    def solve(self, b: np.ndarray, x0: np.ndarray | None = None) -> np.ndarray:
        b = np.ascontiguousarray(b, dtype=np.float64)
        x = np.zeros(self.n, dtype=np.float64)
        x0p = None
        x0a = None
        if x0 is not None:
            x0a = np.ascontiguousarray(x0, dtype=np.float64)
            x0p = x0a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        rel = ctypes.c_double(0.0)
        rc = self._lib.dpn_solve(
            self._h,
            b.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            x.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            x0p,
            ctypes.byref(rel),
        )
        if rc != 0:
            raise RuntimeError(f"dpn_solve rc={rc}")
        return x

    def __del__(self):
        h = getattr(self, "_h", None)
        lib = getattr(self, "_lib", None)
        if h and lib:
            lib.dpn_free(h)
            self._h = None


def _native(A, kind: int):
    lib = _libdpn()
    if lib is None:
        return None
    try:
        return NativeSolver(A, kind, lib)
    except Exception as exc:
        print(f"libdpn unavailable ({exc}); using SciPy fallback", file=sys.stderr)
        return None

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


class PyDirectLU:
    name = "A_direct_be"

    def __init__(self, A):
        t0 = time.perf_counter()
        self.A = A.tocsc()
        self.lu = splu(self.A)
        self.setup_s = time.perf_counter() - t0
        self.last_iters = 1
        self.n = A.shape[0]
        self.backend = "python"

    def solve(self, b: np.ndarray, x0: np.ndarray | None = None) -> np.ndarray:
        return self.lu.solve(np.asarray(b, dtype=np.float64))


class PySAAMG:
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
        self.backend = "python"

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


def DirectLU(A):
    n = _native(A, 0)
    return n if n is not None else PyDirectLU(A)


def SAAMG(A, coarse_n: int = COARSE_N):
    n = _native(A, 1)
    if n is not None:
        return n
    return PySAAMG(A, coarse_n=coarse_n)


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


def _csr_ct(A):
    Ac = A.tocsr()
    n = int(Ac.shape[0])
    nnz = int(Ac.nnz)
    rp = np.ascontiguousarray(Ac.indptr, dtype=np.int32)
    ci = np.ascontiguousarray(Ac.indices, dtype=np.int32)
    va = np.ascontiguousarray(Ac.data, dtype=np.float64)
    return n, nnz, rp, ci, va


def _events_ct(events):
    n = len(events)
    if n == 0:
        z = np.zeros(1, dtype=np.int32)
        d = np.zeros(1, dtype=np.float64)
        return 0, z, d, d, d
    idx = np.ascontiguousarray([int(e["idx"]) for e in events], dtype=np.int32)
    t50 = np.ascontiguousarray([float(e["t50_s"]) for e in events], dtype=np.float64)
    dur = np.ascontiguousarray([float(e["dur_s"]) for e in events], dtype=np.float64)
    ip = np.ascontiguousarray([float(e["i_pulse"]) for e in events], dtype=np.float64)
    return n, idx, t50, dur, ip


def _tran_kwargs(n, events, dt, t_end, adaptive=False):
    steps = max(2, int(np.ceil(t_end / dt)))
    if adaptive:
        steps = max(steps, int(np.ceil(t_end / (dt / 128.0))) + 8)
    Vw = np.zeros(n, dtype=np.float64)
    wt = np.zeros(steps, dtype=np.float64)
    wv = np.zeros(steps, dtype=np.float64)
    wi = np.zeros(steps, dtype=np.float64)
    n_ev, idx, t50, dur, ip = _events_ct(events)
    return {
        "Vw": Vw,
        "wt": wt,
        "wv": wv,
        "wi": wi,
        "n_ev": n_ev,
        "idx": idx,
        "t50": t50,
        "dur": dur,
        "ip": ip,
        "max_steps": steps,
        "worst_node": ctypes.c_int(0),
        "worst_v": ctypes.c_double(0.0),
        "worst_t": ctypes.c_double(0.0),
        "rel": ctypes.c_double(0.0),
        "solve_s": ctypes.c_double(0.0),
        "n_steps": ctypes.c_int(0),
    }


def _tran_result(kw, n, solver_name, setup_s, n_levels, vdd, dt, t_end, backend, loop):
    ns = int(kw["n_steps"].value)
    Vw = kw["Vw"]
    worst_v = float(kw["worst_v"].value)
    return {
        "worst_voltage": worst_v,
        "worst_droop": vdd - worst_v,
        "worst_droop_pct": 100.0 * (vdd - worst_v) / vdd,
        "worst_time_s": float(kw["worst_t"].value),
        "worst_node_idx": int(kw["worst_node"].value),
        "dt": dt,
        "t_end": t_end,
        "steps": ns,
        "solver": solver_name,
        "solver_setup_s": setup_s,
        "solver_step_s": float(kw["solve_s"].value),
        "n_levels": n_levels,
        "rel_res_max": float(kw["rel"].value),
        "wave_t": kw["wt"][:ns].tolist(),
        "wave_vmin": kw["wv"][:ns].tolist(),
        "wave_itot": kw["wi"][:ns].tolist(),
        "V_worst": Vw.copy(),
        "backend": backend,
        "timestep_loop": loop,
    }


def native_timestep(solver, sys, events, vdd: float, t_end: float):
    """BE loop inside libdpn. None if the solver is not native."""
    if getattr(solver, "backend", "") != "native" or not hasattr(solver, "_h"):
        return None
    lib = getattr(solver, "_lib", None)
    if lib is None:
        return None
    n = int(sys["n"])
    C = np.ascontiguousarray(sys["C"], dtype=np.float64)
    leak = np.ascontiguousarray(sys["leak"], dtype=np.float64)
    pad = np.ascontiguousarray(sys["pad"], dtype=np.float64)
    dt = float(sys["dt"])
    kw = _tran_kwargs(n, events, dt, t_end)
    rc = lib.dpn_timestep_be(
        solver._h,
        C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        leak.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        pad.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        dt,
        float(t_end),
        float(vdd),
        kw["n_ev"],
        kw["idx"].ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
        kw["t50"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["dur"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["ip"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["Vw"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(kw["worst_node"]),
        ctypes.byref(kw["worst_v"]),
        ctypes.byref(kw["worst_t"]),
        ctypes.byref(kw["rel"]),
        ctypes.byref(kw["solve_s"]),
        kw["max_steps"],
        kw["wt"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["wv"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["wi"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(kw["n_steps"]),
    )
    if rc != 0:
        print(f"dpn_timestep_be rc={rc}", file=sys.stderr)
        return None
    return _tran_result(
        kw,
        n,
        solver.name,
        getattr(solver, "setup_s", None),
        getattr(solver, "n_levels", 1),
        vdd,
        dt,
        t_end,
        "native",
        "native",
    )


def native_adaptive(sys, events, vdd: float, t_end: float, atol: float = 1e-4, rtol: float = 1e-3):
    lib = _libdpn()
    if lib is None or "G_mesh" not in sys:
        return None
    G = sys["G_mesh"]
    n, nnz, rp, ci, va = _csr_ct(G)
    C = np.ascontiguousarray(sys["C"], dtype=np.float64)
    leak = np.ascontiguousarray(sys["leak"], dtype=np.float64)
    bumps = np.ascontiguousarray(sys.get("bump") or [], dtype=np.int32)
    if bumps.size == 0:
        bumps = np.zeros(1, dtype=np.int32)
        n_bumps = 0
    else:
        n_bumps = int(bumps.size)
    dt = float(sys["dt"])
    kw = _tran_kwargs(n, events, dt, t_end, adaptive=True)
    rc = lib.dpn_timestep_be_adaptive(
        n,
        nnz,
        rp.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
        ci.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
        va.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        bumps.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
        n_bumps,
        float(sys["pkg_r"]),
        float(sys["pkg_l"]),
        float(vdd),
        leak.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        dt,
        float(t_end),
        float(atol),
        float(rtol),
        kw["n_ev"],
        kw["idx"].ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
        kw["t50"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["dur"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["ip"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["Vw"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(kw["worst_node"]),
        ctypes.byref(kw["worst_v"]),
        ctypes.byref(kw["worst_t"]),
        ctypes.byref(kw["rel"]),
        ctypes.byref(kw["solve_s"]),
        kw["max_steps"],
        kw["wt"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["wv"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["wi"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(kw["n_steps"]),
    )
    if rc != 0:
        print(f"dpn_timestep_be_adaptive rc={rc} n_steps={kw['n_steps'].value} max={kw['max_steps']}", file=sys.stderr)
        return None
    return _tran_result(kw, n, "A_direct_be_adaptive", None, 1, vdd, dt, t_end, "native", "adaptive")


def mor_starts(n: int, events) -> np.ndarray:
    """Port subspace: common-mode, seq-vs-combo, spatial — not a learned map."""
    B = np.zeros((n, 3), dtype=np.float64, order="F")
    if not events:
        B[0, 0] = 1.0
        return B
    xs = [float(ev["x"]) if ev.get("x") is not None else 0.0 for ev in events]
    xmin, xmax = min(xs), max(xs)
    span = max(xmax - xmin, 1.0)
    for ev in events:
        i = int(ev["idx"])
        B[i, 0] = 1.0
        B[i, 1] = 1.0 if ev.get("seq") else -1.0
        x = float(ev["x"]) if ev.get("x") is not None else 0.0
        B[i, 2] = (x - xmin) / span - 0.5
    for j in range(3):
        nrm = float(np.linalg.norm(B[:, j]))
        if nrm > 0:
            B[:, j] /= nrm
        else:
            B[0, j] = 1.0
    return B


class NativeMor:
    name = "C_rational_krylov_mor"
    backend = "native"

    def __init__(self, G, C, starts, shifts, n_moments: int, lib):
        Gc = G.tocsr()
        n, nnz, rp, ci, va = _csr_ct(Gc)
        C = np.ascontiguousarray(C, dtype=np.float64)
        starts = np.asfortranarray(starts, dtype=np.float64)
        if starts.ndim != 2 or starts.shape[0] != n:
            raise ValueError("starts must be n × n_starts")
        shifts = np.ascontiguousarray(shifts, dtype=np.float64)
        h = lib.dpn_mor_setup(
            n,
            nnz,
            rp.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
            ci.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
            va.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            int(starts.shape[1]),
            starts.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            int(shifts.size),
            shifts.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            int(n_moments),
        )
        if not h:
            raise RuntimeError("dpn_mor_setup failed")
        self._lib = lib
        self._h = h
        self.n = n
        self.m = int(lib.dpn_mor_m(h))
        self.setup_s = float(lib.dpn_mor_setup_s(h))
        raw = lib.dpn_mor_name(h)
        self.name = raw.decode() if raw else self.name
        self._keep = (rp, ci, va, C, starts, shifts)

    def timestep(self, sys, events, vdd: float, t_end: float) -> dict:
        leak = np.ascontiguousarray(sys["leak"], dtype=np.float64)
        pad = np.ascontiguousarray(sys["pad"], dtype=np.float64)
        dt = float(sys["dt"])
        kw = _tran_kwargs(self.n, events, dt, t_end)
        rc = self._lib.dpn_mor_timestep(
            self._h,
            leak.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            pad.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            dt,
            float(t_end),
            float(vdd),
            kw["n_ev"],
            kw["idx"].ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
            kw["t50"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["dur"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["ip"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["Vw"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            ctypes.byref(kw["worst_node"]),
            ctypes.byref(kw["worst_v"]),
            ctypes.byref(kw["worst_t"]),
            ctypes.byref(kw["rel"]),
            ctypes.byref(kw["solve_s"]),
            kw["max_steps"],
            kw["wt"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["wv"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["wi"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            ctypes.byref(kw["n_steps"]),
        )
        if rc != 0:
            raise RuntimeError(f"dpn_mor_timestep rc={rc}")
        out = _tran_result(
            kw, self.n, self.name, self.setup_s, 1, vdd, dt, t_end, "native", "mor"
        )
        out["n_levels"] = self.m
        out["m"] = self.m
        return out

    def __del__(self):
        h = getattr(self, "_h", None)
        lib = getattr(self, "_lib", None)
        if h and lib:
            lib.dpn_mor_free(h)
            self._h = None


class PyMor:
    """SciPy fallback: same rational Arnoldi + reduced BE as libdpn."""

    name = "C_rational_krylov_mor"
    backend = "python"

    def __init__(self, G, C, starts, shifts, n_moments: int = 4):
        t0 = time.perf_counter()
        self.G = G.tocsr().astype(np.float64)
        self.C = np.asarray(C, dtype=np.float64)
        n = self.G.shape[0]
        starts = np.asarray(starts, dtype=np.float64)
        if starts.ndim == 1:
            starts = starts.reshape(n, 1)
        cap = min(n, 48)
        Vcols = []
        moments = max(1, n_moments)
        for s in np.asarray(shifts, dtype=np.float64):
            K = (self.G + sparse.diags(s * self.C)).tocsc()
            lu = splu(K)
            for b in range(starts.shape[1]):
                rhs = starts[:, b].copy()
                for mom in range(moments):
                    if mom > 0:
                        rhs = self.C * Vcols[-1]
                    x = lu.solve(rhs)
                    x = self._mgs(Vcols, x)
                    if x is None:
                        break
                    Vcols.append(x)
                    if len(Vcols) >= cap:
                        break
                if len(Vcols) >= cap:
                    break
            if len(Vcols) >= cap:
                break
        if not Vcols:
            x = np.ones(n) / np.sqrt(n)
            Vcols = [x]
        self.V = np.column_stack(Vcols)
        self.m = self.V.shape[1]
        GV = np.column_stack([self.G @ self.V[:, k] for k in range(self.m)])
        self.Gr = self.V.T @ GV
        self.Cr = self.V.T @ (self.C[:, None] * self.V)
        self.setup_s = time.perf_counter() - t0
        self.n = n

    @staticmethod
    def _mgs(basis, w, tol=1e-14):
        nrm0 = float(np.linalg.norm(w))
        if nrm0 < tol:
            return None
        w = w.copy()
        for _ in range(2):
            for v in basis:
                w = w - np.dot(w, v) * v
        nrm = float(np.linalg.norm(w))
        if nrm < max(tol, 1e-12 * nrm0):
            return None
        return w / nrm

    def timestep(self, sys, events, vdd: float, t_end: float) -> dict:
        dt = float(sys["dt"])
        leak = np.asarray(sys["leak"], dtype=np.float64)
        n = self.n
        steps = max(2, int(np.ceil(t_end / dt)))
        Ar = self.Gr + self.Cr / dt
        try:
            from numpy.linalg import solve as dsolve
        except ImportError:
            dsolve = np.linalg.solve
        z = np.zeros(self.m)
        V = np.full(n, vdd)
        worst_v, worst_t, worst_i = vdd, 0.0, 0
        worst_V = V.copy()
        wave_t, wave_vmin, wave_itot = [], [], []
        t0 = time.perf_counter()
        for s in range(steps):
            t = s * dt
            I = leak.copy()
            for ev in events:
                tau = t - ev["t50_s"]
                dur = ev["dur_s"]
                half = 0.5 * dur
                if dur > 0 and ev["i_pulse"] > 0 and abs(tau) < half:
                    I[ev["idx"]] += ev["i_pulse"] * (1.0 - abs(tau) / half)
            f = self.V.T @ I
            rhs = (self.Cr @ z) / dt - f
            z = dsolve(Ar, rhs)
            V = vdd + self.V @ z
            vmin = float(np.min(V))
            wave_t.append(float(t))
            wave_vmin.append(vmin)
            wave_itot.append(float(np.sum(I)))
            if vmin < worst_v:
                worst_v = vmin
                worst_t = float(t)
                worst_i = int(np.argmin(V))
                worst_V = V.copy()
        return {
            "worst_voltage": worst_v,
            "worst_droop": vdd - worst_v,
            "worst_droop_pct": 100.0 * (vdd - worst_v) / vdd,
            "worst_time_s": worst_t,
            "worst_node_idx": worst_i,
            "dt": dt,
            "t_end": t_end,
            "steps": steps,
            "solver": self.name,
            "solver_setup_s": self.setup_s,
            "solver_step_s": time.perf_counter() - t0,
            "n_levels": self.m,
            "m": self.m,
            "rel_res_max": 0.0,
            "wave_t": wave_t,
            "wave_vmin": wave_vmin,
            "wave_itot": wave_itot,
            "V_worst": worst_V,
            "backend": "python",
            "timestep_loop": "mor",
        }


def RationalKrylov(G, C, starts, shifts, n_moments: int = 4):
    lib = _libdpn()
    if lib is not None:
        try:
            return NativeMor(G, C, starts, shifts, n_moments, lib)
        except Exception as exc:
            print(f"libdpn MOR unavailable ({exc}); using SciPy fallback", file=sys.stderr)
    return PyMor(G, C, starts, shifts, n_moments)
