#!/usr/bin/env python3
"""Linear solvers for the GCD PDN backward-Euler operator.

Solver A — sparse LU (golden).
Solver B — smoothed-aggregation AMG V-cycle + CG (workhorse).
The BE matrix A = G + C/Δt + g_eq is SPD. Package R+L uses a companion
g_eq=1/(R+L/Δt) with inductor current i_L on the RHS (not memoryless L/Δt).

Solver C — rational Krylov MOR. RC: reduced BE on δv. RLC: descriptor
Eẋ + A x = u on x=[v; i_L] matching the companion (A unsymmetric).

Solver D — restricted additive Schwarz on the BE operator. Graph-grown
subdomains on the undirected sparsity graph A∪Aᵀ (needed for unsymmetric
descriptor K), overlapping local SparseLU of the real operator A, RAS
restriction, GMRES (not CG: RAS is not SPD). ndom=1 falls back to one LU of A.
kind=2 on descriptor K is the same RAS; never AMG.

Not Ginkgo, not pyamg, not a fork of ESPSim. Classic Vaněk–Mandel–Brezina
SA plus damped Jacobi, coarse LU when n is small. kind=3 is Eigen BiCGSTAB+ILUT
for unsymmetric descriptor operators (CPU Krylov workhorse). Ginkgo GPU is GAP.
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
from scipy.sparse.linalg import LinearOperator, bicgstab, cg, splu, spilu

_LIB = None
_LIB_TRIED = False
_C_IDX = ctypes.c_int64
_P_IDX = ctypes.POINTER(_C_IDX)
_NP_IDX = np.int64


def droop_pct(vdd: float, worst_v: float) -> float | None:
    """(Vdd−Vmin)/Vdd as percent. None on a 0 V return rail (undefined)."""
    if abs(float(vdd)) < 1e-18:
        return None
    return 100.0 * (float(vdd) - float(worst_v)) / float(vdd)


def rl_companion(pkg_r: float, pkg_l: float, dt: float) -> tuple[float, float]:
    """BE series R+L companion: g_eq = 1/(R+L/Δt), hist_scale = g_eq·L/Δt."""
    ldt = (pkg_l / dt) if pkg_l > 0.0 and dt > 0.0 else 0.0
    g_eq = 1.0 / max(pkg_r + ldt, 1e-9)
    return g_eq, g_eq * ldt


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
    if not hasattr(lib, "dpn_index_width"):
        return None
    lib.dpn_index_width.restype = ctypes.c_int
    lib.dpn_index_width.argtypes = []
    if int(lib.dpn_index_width()) != 64:
        return None
    lib.dpn_setup.restype = ctypes.c_void_p
    lib.dpn_setup.argtypes = [
        ctypes.c_int,
        _C_IDX,
        _C_IDX,
        _P_IDX,
        _P_IDX,
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
    lib.dpn_n.restype = _C_IDX
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
        _C_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
    ]
    lib.dpn_timestep_be.restype = ctypes.c_int
    lib.dpn_timestep_be.argtypes = _TRAN_ARGS
    lib.dpn_timestep_be_hist.restype = ctypes.c_int
    lib.dpn_timestep_be_hist.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
        _P_IDX,
        _C_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
        _C_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    if hasattr(lib, "dpn_timestep_be_hist_cmat"):
        lib.dpn_timestep_be_hist_cmat.restype = ctypes.c_int
        lib.dpn_timestep_be_hist_cmat.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_double),
            _C_IDX,
            _P_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_double,
            ctypes.c_double,
            _P_IDX,
            _C_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_double,
            ctypes.c_double,
            ctypes.POINTER(ctypes.c_double),
            _C_IDX,
            _C_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
        ]
    if hasattr(lib, "dpn_timestep_thermal_be"):
        lib.dpn_timestep_thermal_be.restype = ctypes.c_int
        lib.dpn_timestep_thermal_be.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_double,
            ctypes.c_double,
            ctypes.POINTER(ctypes.c_double),
            _C_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _P_IDX,
        ]
    lib.dpn_mor_setup.restype = ctypes.c_void_p
    lib.dpn_mor_setup.argtypes = [
        _C_IDX,
        _C_IDX,
        _P_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
    ]
    lib.dpn_mor_setup_rlc.restype = ctypes.c_void_p
    lib.dpn_mor_setup_rlc.argtypes = [
        _C_IDX,
        _C_IDX,
        _P_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        _C_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
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
        _C_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
    ]
    lib.dpn_timestep_be_adaptive.restype = ctypes.c_int
    lib.dpn_timestep_be_adaptive.argtypes = [
        _C_IDX,
        _C_IDX,
        _P_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        _C_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        _C_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
    ]
    lib.dpn_timestep_descriptor.restype = ctypes.c_int
    lib.dpn_timestep_descriptor.argtypes = [
        _C_IDX,
        _C_IDX,
        _P_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),  # Aval
        ctypes.POINTER(ctypes.c_double),  # E
        ctypes.c_int,  # n_v
        ctypes.c_int,  # n_die
        _C_IDX,  # die_idx
        ctypes.c_int,  # iv
        ctypes.c_double,  # dt
        ctypes.c_double,  # t_end
        ctypes.c_double,  # vdd
        ctypes.POINTER(ctypes.c_double),  # leak
        _C_IDX,  # n_events
        _P_IDX,  # ev_idx
        ctypes.POINTER(ctypes.c_double),  # ev_t50
        ctypes.POINTER(ctypes.c_double),  # ev_dur
        ctypes.POINTER(ctypes.c_double),  # ev_ipulse
        ctypes.POINTER(ctypes.c_double),  # V_worst
        _P_IDX,  # worst_node
        ctypes.POINTER(ctypes.c_double),  # worst_v
        ctypes.POINTER(ctypes.c_double),  # worst_t
        ctypes.POINTER(ctypes.c_double),  # rel_res_max
        ctypes.POINTER(ctypes.c_double),  # solve_s
        ctypes.c_int,  # max_steps
        ctypes.POINTER(ctypes.c_double),  # wave_t
        ctypes.POINTER(ctypes.c_double),  # wave_vmin
        ctypes.POINTER(ctypes.c_double),  # wave_itot
        _P_IDX,  # n_steps
    ]
    if hasattr(lib, "dpn_timestep_descriptor_gen"):
        lib.dpn_timestep_descriptor_gen.restype = ctypes.c_int
        lib.dpn_timestep_descriptor_gen.argtypes = [
            _C_IDX,
            _C_IDX,
            _P_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            _C_IDX,
            _P_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.c_int,
            _C_IDX,
            _C_IDX,
            _P_IDX,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _C_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            _P_IDX,
        ]
    _desc_head = [
        _C_IDX,
        _C_IDX,
        _P_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        _C_IDX,
        _P_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.c_int,
        _C_IDX,
        _C_IDX,
        _P_IDX,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    _desc_ev = [
        _C_IDX,
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    _desc_tail = [
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        _P_IDX,
    ]
    if hasattr(lib, "dpn_timestep_descriptor_workhorse"):
        lib.dpn_timestep_descriptor_workhorse.restype = ctypes.c_int
        lib.dpn_timestep_descriptor_workhorse.argtypes = (
            _desc_head + [ctypes.c_int] + _desc_ev + _desc_tail
        )
    if hasattr(lib, "dpn_timestep_descriptor_adaptive"):
        lib.dpn_timestep_descriptor_adaptive.restype = ctypes.c_int
        lib.dpn_timestep_descriptor_adaptive.argtypes = (
            _desc_head + [ctypes.c_double, ctypes.c_double] + _desc_ev + _desc_tail
        )
    if hasattr(lib, "dpn_mor_setup_gen"):
        lib.dpn_mor_setup_gen.restype = ctypes.c_void_p
        lib.dpn_mor_setup_gen.argtypes = [
            _C_IDX,
            _C_IDX,
            _P_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            _C_IDX,
            _P_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.c_int,
            _C_IDX,
            _C_IDX,
            _P_IDX,
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
        ]
    _LIB = lib
    return _LIB


def native_index_width() -> int | None:
    """libdpn StorageIndex width in bits, or None if the native library is missing."""
    lib = _libdpn()
    if lib is None or not hasattr(lib, "dpn_index_width"):
        return None
    return int(lib.dpn_index_width())


class NativeSolver:
    """C API wrapper. Same surface as PyDirectLU / PySAAMG."""

    def __init__(self, A, kind: int, lib):
        Ac = A.tocsr()
        n = int(Ac.shape[0])
        nnz = int(Ac.nnz)
        rp = np.ascontiguousarray(Ac.indptr, dtype=_NP_IDX)
        ci = np.ascontiguousarray(Ac.indices, dtype=_NP_IDX)
        va = np.ascontiguousarray(Ac.data, dtype=np.float64)
        if ci.size == 0:
            ci = np.zeros(1, dtype=_NP_IDX)
        if int(rp[-1]) != nnz:
            raise ValueError("CSR nnz mismatch")
        h = lib.dpn_setup(
            kind,
            n,
            nnz,
            rp.ctypes.data_as(_P_IDX),
            ci.ctypes.data_as(_P_IDX),
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
        fallback = {0: "A_direct_be", 1: "B_sa_amg", 2: "D_ras_schwarz", 3: "E_bicgstab"}.get(
            kind, "solver"
        )
        self.name = raw.decode() if raw else fallback
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


class PyBicgSTAB:
    """SciPy BiCGSTAB + ILU (diag fallback). Unsymmetric CPU Krylov — not Ginkgo."""

    name = "E_bicgstab"

    def __init__(self, A):
        t0 = time.perf_counter()
        self.A = A.tocsr().astype(np.float64)
        self.n = self.A.shape[0]
        self.Mop = None
        try:
            ilu = spilu(self.A.tocsc())
            self.Mop = LinearOperator(self.A.shape, matvec=ilu.solve)
        except Exception:
            self.Mop = None
        self.setup_s = time.perf_counter() - t0
        self.last_iters = 0
        self.backend = "python"

    def solve(self, b: np.ndarray, x0: np.ndarray | None = None) -> np.ndarray:
        b = np.asarray(b, dtype=np.float64)
        x, info = bicgstab(
            self.A,
            b,
            x0=x0,
            M=self.Mop,
            tol=1e-10,
            atol=1e-12,
            maxiter=max(200, 8 * self.n),
        )
        self.last_iters = 0 if info == 0 else int(info)
        if info != 0:
            x, info = bicgstab(self.A, b, x0=x0, tol=1e-8, atol=1e-10, maxiter=max(400, 16 * self.n))
        return np.asarray(x, dtype=np.float64)


def BicgSTAB(A):
    n = _native(A, 3)
    return n if n is not None else PyBicgSTAB(A)


def DirectLU(A):
    n = _native(A, 0)
    return n if n is not None else PyDirectLU(A)


def SAAMG(A, coarse_n: int = COARSE_N):
    n = _native(A, 1)
    if n is not None:
        return n
    return PySAAMG(A, coarse_n=coarse_n)


def _ras_ndom(n: int) -> int:
    if n < 8:
        return 1
    if n <= 64:
        return 2
    return min(8, max(2, n // 32))


def _ras_undirected_csr(A):
    """Binary A ∪ Aᵀ for partition/halo. Unsymmetric descriptor K needs both directions."""
    A = A.tocsr()
    B = (A + A.T).tocsr()
    B.data[:] = 1.0
    return B


def _ras_partition(A, ndom: int) -> np.ndarray:
    """Graph-growing owners. Not index stripes — undirected sparsity graph."""
    G = _ras_undirected_csr(A)
    n = int(G.shape[0])
    owner = np.full(n, -1, dtype=np.int32)
    unassigned = n
    seed = 0
    indptr, indices = G.indptr, G.indices
    for s in range(ndom):
        if unassigned <= 0:
            break
        while seed < n and owner[seed] >= 0:
            seed += 1
        if seed >= n:
            break
        want = max(1, unassigned // (ndom - s))
        q = [int(seed)]
        owner[seed] = s
        unassigned -= 1
        taken = 1
        qi = 0
        while qi < len(q) and taken < want:
            i = q[qi]
            qi += 1
            for k in range(int(indptr[i]), int(indptr[i + 1])):
                j = int(indices[k])
                if owner[j] < 0:
                    owner[j] = s
                    unassigned -= 1
                    taken += 1
                    q.append(j)
                    if taken >= want:
                        break
    owner[owner < 0] = max(ndom - 1, 0)
    return owner


class PyRASDD:
    """Restricted additive Schwarz: overlapping local LU, RAS restriction, GMRES.

    Not AMG, not a stripe split. Subdomains grow on the sparsity graph.
    RAS is not SPD, so the outer iteration is GMRES (not CG).
    """

    name = "D_ras_schwarz"

    def __init__(self, A, hops: int = 2):
        t0 = time.perf_counter()
        self.A = A.tocsr().astype(np.float64)
        self.n = int(self.A.shape[0])
        self.ndom = _ras_ndom(self.n)
        self.n_levels = self.ndom
        self.backend = "python"
        self.last_iters = 0
        owner = _ras_partition(self.A, self.ndom)
        self.doms = []
        G = _ras_undirected_csr(self.A)
        g_indptr, g_indices = G.indptr, G.indices
        indptr, indices, data = self.A.indptr, self.A.indices, self.A.data
        for s in range(self.ndom):
            interior = np.flatnonzero(owner == s)
            in_set = np.zeros(self.n, dtype=bool)
            in_set[interior] = True
            for _ in range(hops):
                nxt = in_set.copy()
                for i in np.flatnonzero(in_set):
                    sl, sr = int(g_indptr[i]), int(g_indptr[i + 1])
                    nxt[g_indices[sl:sr]] = True
                in_set = nxt
            all_idx = np.flatnonzero(in_set).astype(np.int32)
            if all_idx.size == 0:
                continue
            loc = np.full(self.n, -1, dtype=np.int32)
            loc[all_idx] = np.arange(all_idx.size, dtype=np.int32)
            ti, tj, tv = [], [], []
            for gi in all_idx:
                i = int(loc[gi])
                sl, sr = int(indptr[gi]), int(indptr[gi + 1])
                for k in range(sl, sr):
                    gj = int(indices[k])
                    j = int(loc[gj])
                    if j < 0:
                        continue
                    ti.append(i)
                    tj.append(j)
                    tv.append(float(data[k]))
            locA = sparse.csr_matrix((tv, (ti, tj)), shape=(all_idx.size, all_idx.size))
            self.doms.append(
                {
                    "all": all_idx,
                    "interior": interior.astype(np.int32),
                    "loc": loc,
                    "lu": splu(locA.tocsc()),
                }
            )
        self.setup_s = time.perf_counter() - t0

    def _apply(self, r: np.ndarray) -> np.ndarray:
        z = np.zeros(self.n, dtype=np.float64)
        r = np.asarray(r, dtype=np.float64)
        for D in self.doms:
            rs = r[D["all"]]
            es = D["lu"].solve(rs)
            inter = D["interior"]
            z[inter] += es[D["loc"][inter]]
        return z

    def solve(self, b: np.ndarray, x0: np.ndarray | None = None) -> np.ndarray:
        b = np.asarray(b, dtype=np.float64)
        if self.ndom == 1 and self.doms:
            self.last_iters = 1
            return self.doms[0]["lu"].solve(b)
        from scipy.sparse.linalg import gmres as sp_gmres

        x0 = np.zeros_like(b) if x0 is None else np.asarray(x0, dtype=np.float64)
        M = LinearOperator((self.n, self.n), matvec=self._apply, dtype=np.float64)
        x, info = sp_gmres(self.A, b, x0=x0, M=M, restart=32, maxiter=256, atol=0.0, tol=1e-10)
        self.last_iters = 0 if info == 0 else abs(int(info))
        return x


def RASDD(A):
    n = _native(A, 2)
    return n if n is not None else PyRASDD(A)


def make_solver(A, kind: str):
    if kind in ("a", "A", "direct", "lu", "A_direct_be"):
        return DirectLU(A)
    if kind in ("b", "B", "amg", "B_sa_amg"):
        return SAAMG(A)
    if kind in ("d", "D", "ras", "schwarz", "D_ras_schwarz"):
        return RASDD(A)
    if kind in ("e", "E", "bicg", "bicgstab", "E_bicgstab"):
        return BicgSTAB(A)
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
    rp = np.ascontiguousarray(Ac.indptr, dtype=_NP_IDX)
    ci = np.ascontiguousarray(Ac.indices, dtype=_NP_IDX)
    va = np.ascontiguousarray(Ac.data, dtype=np.float64)
    if ci.size == 0:
        ci = np.zeros(1, dtype=_NP_IDX)
    return n, nnz, rp, ci, va


def _events_ct(events):
    n = len(events)
    if n == 0:
        z = np.zeros(1, dtype=_NP_IDX)
        d = np.zeros(1, dtype=np.float64)
        return 0, z, d, d, d
    idx = np.ascontiguousarray([int(e["idx"]) for e in events], dtype=_NP_IDX)
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
        "worst_node": _C_IDX(0),
        "worst_v": ctypes.c_double(0.0),
        "worst_t": ctypes.c_double(0.0),
        "rel": ctypes.c_double(0.0),
        "solve_s": ctypes.c_double(0.0),
        "n_steps": _C_IDX(0),
    }


def _bump_arrays(sys: dict, vdd: float):
    bumps = np.ascontiguousarray(sys.get("bump") or [], dtype=_NP_IDX)
    n_bumps = int(bumps.size)
    raw = sys.get("bump_v")
    if n_bumps <= 0:
        bump_v = np.zeros(1, dtype=np.float64)
    elif raw is None or len(raw) != n_bumps:
        bump_v = np.full(n_bumps, float(vdd), dtype=np.float64)
    else:
        bump_v = np.ascontiguousarray(raw, dtype=np.float64)
    return bumps, n_bumps, bump_v


def _tran_result(kw, n, solver_name, setup_s, n_levels, vdd, dt, t_end, backend, loop, extra=None):
    ns = int(kw["n_steps"].value)
    Vw = kw["Vw"]
    worst_v = float(kw["worst_v"].value)
    out = {
        "worst_voltage": worst_v,
        "worst_droop": vdd - worst_v,
        "worst_droop_pct": droop_pct(vdd, worst_v),
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
    if extra:
        out.update(extra)
    return out


def _needs_cmat_hist(sys: dict) -> bool:
    if sys.get("C_mat") is not None:
        return True
    if sys.get("v_init") is not None:
        return True
    return int(sys.get("n_rail0") or 0) > 0


def native_timestep(solver, sys, events, vdd: float, t_end: float):
    """BE loop inside libdpn. Uses inductor-current history when bumps exist.

    Sparse C (rail-to-rail) and mixed-rail UIC go through dpn_timestep_be_hist_cmat.
    Never fall back to diagonal-C hist when C_mat is set — that would drop C_rr.
    """
    if getattr(solver, "backend", "") != "native" or not hasattr(solver, "_h"):
        return None
    lib = getattr(solver, "_lib", None)
    if lib is None:
        return None
    n = int(sys["n"])
    C = np.ascontiguousarray(sys["C"], dtype=np.float64)
    leak = np.ascontiguousarray(sys["leak"], dtype=np.float64)
    dt = float(sys["dt"])
    kw = _tran_kwargs(n, events, dt, t_end)
    bumps, n_bumps, bump_v = _bump_arrays(sys, vdd)
    extra = {}
    rc = -1
    loop = "native"
    if _needs_cmat_hist(sys):
        if n_bumps <= 0 or not hasattr(lib, "dpn_timestep_be_hist_cmat"):
            return None
        Cmat = sys.get("C_mat")
        if Cmat is None:
            nnz_c = 0
            rp = np.zeros(n + 1, dtype=_NP_IDX)
            ci = np.zeros(1, dtype=_NP_IDX)
            va = np.zeros(1, dtype=np.float64)
        else:
            _, nnz_c, rp, ci, va = _csr_ct(Cmat)
        v_init = sys.get("v_init")
        if v_init is None:
            v_init = np.full(n, float(vdd), dtype=np.float64)
        else:
            v_init = np.ascontiguousarray(v_init, dtype=np.float64)
        n_rail0 = int(sys.get("n_rail0") or 0)
        ilabs = ctypes.c_double(0.0)
        ilw = np.zeros(max(n_bumps, 1), dtype=np.float64)
        Vw1 = np.zeros(n, dtype=np.float64)
        wn1 = _C_IDX(0)
        wv1 = ctypes.c_double(0.0)
        wt1 = ctypes.c_double(0.0)
        rc = lib.dpn_timestep_be_hist_cmat(
            solver._h,
            C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            nnz_c,
            rp.ctypes.data_as(_P_IDX),
            ci.ctypes.data_as(_P_IDX),
            va.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            leak.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            dt,
            float(t_end),
            bumps.ctypes.data_as(_P_IDX),
            n_bumps,
            bump_v.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            float(sys.get("pkg_r") or 0.0),
            float(sys.get("pkg_l") or 0.0),
            v_init.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            n_rail0,
            kw["n_ev"],
            kw["idx"].ctypes.data_as(_P_IDX),
            kw["t50"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["dur"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["ip"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["Vw"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            ctypes.byref(kw["worst_node"]),
            ctypes.byref(kw["worst_v"]),
            ctypes.byref(kw["worst_t"]),
            Vw1.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            ctypes.byref(wn1),
            ctypes.byref(wv1),
            ctypes.byref(wt1),
            ctypes.byref(kw["rel"]),
            ctypes.byref(kw["solve_s"]),
            kw["max_steps"],
            kw["wt"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["wv"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            kw["wi"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            ctypes.byref(kw["n_steps"]),
            ctypes.byref(ilabs),
            ilw.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        )
        if rc != 0:
            print(f"dpn_timestep_be_hist_cmat rc={rc}; not using diagonal-C hist", file=sys.stderr)
            return None
        loop = "native_hist_cmat"
        extra = {
            "i_L_absmax": float(ilabs.value),
            "i_L_worst": ilw.copy(),
            "worst_voltage_rail1": float(wv1.value),
            "worst_time_s_rail1": float(wt1.value),
            "worst_node_idx_rail1": int(wn1.value),
            "V_worst_rail1": Vw1.copy(),
        }
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
            loop,
            extra=extra,
        )
    if n_bumps > 0 and hasattr(lib, "dpn_timestep_be_hist"):
        ilabs = ctypes.c_double(0.0)
        ilw = np.zeros(n_bumps, dtype=np.float64)
        rc = lib.dpn_timestep_be_hist(
            solver._h,
            C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            leak.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            dt,
            float(t_end),
            bumps.ctypes.data_as(_P_IDX),
            n_bumps,
            bump_v.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            float(sys.get("pkg_r") or 0.0),
            float(sys.get("pkg_l") or 0.0),
            kw["n_ev"],
            kw["idx"].ctypes.data_as(_P_IDX),
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
            ctypes.byref(ilabs),
            ilw.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        )
        if rc == 0:
            loop = "native_hist"
            extra = {"i_L_absmax": float(ilabs.value), "i_L_worst": ilw.copy()}
        else:
            print(f"dpn_timestep_be_hist rc={rc}; falling back to memoryless BE", file=sys.stderr)
    if rc != 0:
        pad = np.ascontiguousarray(sys["pad"], dtype=np.float64)
        rc = lib.dpn_timestep_be(
            solver._h,
            C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            leak.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            pad.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            dt,
            float(t_end),
            float(vdd),
            kw["n_ev"],
            kw["idx"].ctypes.data_as(_P_IDX),
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
        loop = "native"
        extra = {}
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
        loop,
        extra=extra,
    )


def native_timestep_thermal(solver, C, P, dt: float, t_end: float, T0=None, n_track: int = 0):
    """Thermal BE inside libdpn. Tracks max ΔT, not electrical min V. Constant P only."""
    if getattr(solver, "backend", "") != "native" or not hasattr(solver, "_h"):
        return None
    lib = getattr(solver, "_lib", None)
    if lib is None or not hasattr(lib, "dpn_timestep_thermal_be"):
        return None
    n = int(solver.n)
    C = np.ascontiguousarray(C, dtype=np.float64)
    P = np.ascontiguousarray(P, dtype=np.float64)
    if C.size != n or P.size != n:
        return None
    dt = float(dt)
    t_end = float(t_end)
    steps = max(2, int(np.ceil(t_end / dt)))
    Tf = np.zeros(n, dtype=np.float64)
    Tw = np.zeros(n, dtype=np.float64)
    wt = np.zeros(steps, dtype=np.float64)
    wT = np.zeros(steps, dtype=np.float64)
    wn = _C_IDX(0)
    wrost = ctypes.c_double(0.0)
    wt0 = ctypes.c_double(0.0)
    rel = ctypes.c_double(0.0)
    ts = ctypes.c_double(0.0)
    ns = _C_IDX(0)
    t0p = None
    t0a = None
    if T0 is not None:
        t0a = np.ascontiguousarray(T0, dtype=np.float64)
        if t0a.size != n:
            return None
        t0p = t0a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    rc = lib.dpn_timestep_thermal_be(
        solver._h,
        C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        P.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        dt,
        t_end,
        t0p,
        int(n_track or 0),
        Tf.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        Tw.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(wn),
        ctypes.byref(wrost),
        ctypes.byref(wt0),
        ctypes.byref(rel),
        ctypes.byref(ts),
        steps,
        wt.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        wT.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(ns),
    )
    if rc != 0:
        print(f"dpn_timestep_thermal_be rc={rc}", file=sys.stderr)
        return None
    n_out = int(ns.value) if ns.value else steps
    return {
        "T": Tf,
        "T_worst": Tw,
        "dT_absmax_k": float(wrost.value),
        "worst_time_s": float(wt0.value),
        "worst_node": int(wn.value),
        "steps": n_out,
        "dt": dt,
        "rel_res_max": float(rel.value),
        "solve_s": float(ts.value),
        "wave_t": wt[:n_out].tolist(),
        "wave_tmax": wT[:n_out].tolist(),
        "backend": "native",
        "timestep_loop": "native_thermal",
        "via": "thermal BE C/Δt + G_th (libdpn SparseLU; max ΔT, not min V)",
    }


def native_adaptive(sys, events, vdd: float, t_end: float, atol: float = 1e-4, rtol: float = 1e-3):
    lib = _libdpn()
    if lib is None or "G_mesh" not in sys:
        return None
    G = sys["G_mesh"]
    n, nnz, rp, ci, va = _csr_ct(G)
    C = np.ascontiguousarray(sys["C"], dtype=np.float64)
    leak = np.ascontiguousarray(sys["leak"], dtype=np.float64)
    bumps, n_bumps, bump_v = _bump_arrays(sys, vdd)
    if n_bumps == 0:
        bumps = np.zeros(1, dtype=_NP_IDX)
        bump_v = np.array([vdd], dtype=np.float64)
    dt = float(sys["dt"])
    kw = _tran_kwargs(n, events, dt, t_end, adaptive=True)
    rc = lib.dpn_timestep_be_adaptive(
        n,
        nnz,
        rp.ctypes.data_as(_P_IDX),
        ci.ctypes.data_as(_P_IDX),
        va.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        bumps.ctypes.data_as(_P_IDX),
        n_bumps,
        bump_v.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        float(sys["pkg_r"]),
        float(sys["pkg_l"]),
        float(vdd),
        leak.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        dt,
        float(t_end),
        float(atol),
        float(rtol),
        kw["n_ev"],
        kw["idx"].ctypes.data_as(_P_IDX),
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


def _descriptor_prep(sys, events, vdd, t_end, dt, leak=None, adaptive=False):
    from pdn_vrm import as_e_csr

    A = sys.get("A")
    Eraw = sys.get("E")
    if A is None or Eraw is None:
        return None
    n, nnz, rp, ci, va = _csr_ct(A)
    try:
        Ecsr = as_e_csr(Eraw, n)
    except ValueError:
        return None
    n_v = int(sys["n_v"])
    die_idx = -1 if sys.get("die_idx") is None else int(sys["die_idx"])
    n_die = int(sys.get("n_die") or (1 if die_idx >= 0 else n_v))
    if leak is None:
        leak_a = np.zeros(max(n_die, 1), dtype=np.float64)
    else:
        leak_a = np.ascontiguousarray(leak, dtype=np.float64)
    kw = _tran_kwargs(max(n_die, 1), events, dt, t_end, adaptive=adaptive)
    u0 = sys.get("u_const")
    iv_list = sys.get("iv_list")
    if iv_list is None:
        iv = int(sys.get("iv", n_v))
        n_iv = int(sys.get("n_iv", 1 if iv >= 0 else 0))
        if n_iv > 0 and iv >= 0:
            iv_list = list(range(iv, iv + n_iv))
        else:
            iv_list = []
            n_iv = 0
    else:
        iv_list = [int(k) for k in iv_list]
        n_iv = len(iv_list)
    n_e, nnz_e, erp, eci, eva = _csr_ct(Ecsr)
    if n_e != n:
        return None
    if eci.size == 0:
        eci = np.zeros(1, dtype=_NP_IDX)
        eva = np.zeros(1, dtype=np.float64)
    iv_arr = np.ascontiguousarray(iv_list if n_iv else [0], dtype=_NP_IDX)
    u_ptr = None
    u_arr = None
    if u0 is not None:
        u_arr = np.ascontiguousarray(u0, dtype=np.float64)
        if u_arr.size != n:
            return None
        u_ptr = u_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    return {
        "n": n,
        "nnz": nnz,
        "rp": rp,
        "ci": ci,
        "va": va,
        "nnz_e": nnz_e,
        "erp": erp,
        "eci": eci,
        "eva": eva,
        "n_v": n_v,
        "n_die": n_die,
        "die_idx": die_idx,
        "n_iv": n_iv,
        "iv_arr": iv_arr,
        "iv_list": iv_list,
        "leak_a": leak_a,
        "u_ptr": u_ptr,
        "u_arr": u_arr,
        "kw": kw,
        "Ecsr": Ecsr,
        "u0": u0,
    }


def _descriptor_common_args(p):
    return [
        p["n"],
        p["nnz"],
        p["rp"].ctypes.data_as(_P_IDX),
        p["ci"].ctypes.data_as(_P_IDX),
        p["va"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        p["nnz_e"],
        p["erp"].ctypes.data_as(_P_IDX),
        p["eci"].ctypes.data_as(_P_IDX),
        p["eva"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        p["n_v"],
        p["n_die"],
        p["die_idx"],
        p["n_iv"],
        p["iv_arr"].ctypes.data_as(_P_IDX),
    ]


def _descriptor_wave_args(p, vdd, t_end, dt):
    kw = p["kw"]
    return [
        float(dt),
        float(t_end),
        float(vdd),
        p["leak_a"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        p["u_ptr"],
    ], [
        kw["n_ev"],
        kw["idx"].ctypes.data_as(_P_IDX),
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
    ]


def native_descriptor(sys, events, vdd: float, t_end: float, dt: float, leak=None, solver_kind: int = 0):
    """Native BE on Eẋ+Ax=u. Sparse-E gen API. solver_kind 0=SparseLU gold, 2=RAS, 3=BiCGSTAB. Never AMG."""
    lib = _libdpn()
    if lib is None or not hasattr(lib, "dpn_timestep_descriptor"):
        return None
    if solver_kind not in (0, 2, 3):
        return None
    p = _descriptor_prep(sys, events, vdd, t_end, dt, leak=leak)
    if p is None:
        return None
    mid, tail = _descriptor_wave_args(p, vdd, t_end, dt)
    use_wh = solver_kind in (2, 3) and hasattr(lib, "dpn_timestep_descriptor_workhorse")
    use_gen = hasattr(lib, "dpn_timestep_descriptor_gen")
    if use_wh:
        rc = lib.dpn_timestep_descriptor_workhorse(
            *_descriptor_common_args(p), *mid, int(solver_kind), *tail
        )
        if rc != 0:
            print(f"dpn_timestep_descriptor_workhorse rc={rc}", file=sys.stderr)
            return None
        label = "D_ras_schwarz_descriptor" if solver_kind == 2 else "E_bicgstab_descriptor"
        via = (
            "descriptor BE sparse-E (libdpn RAS+GMRES)"
            if solver_kind == 2
            else "descriptor BE sparse-E (libdpn BiCGSTAB)"
        )
        out = _tran_result(
            p["kw"], p["n_die"], label, None, 1, vdd, dt, t_end, "native",
            "native_desc",
        )
        out["via"] = via
        return out
    if solver_kind in (2, 3):
        return None
    if use_gen:
        rc = lib.dpn_timestep_descriptor_gen(*_descriptor_common_args(p), *mid, *tail)
        if rc != 0:
            print(f"dpn_timestep_descriptor_gen rc={rc}", file=sys.stderr)
            return None
        out = _tran_result(
            p["kw"], p["n_die"], "N4_descriptor_be", None, 1, vdd, dt, t_end, "native", "native_desc"
        )
        out["via"] = "descriptor BE sparse-E (libdpn SparseLU)"
        return out
    if p["n_iv"] != 1 or p["u0"] is not None:
        return None
    E = np.ascontiguousarray(np.asarray(p["Ecsr"].diagonal()), dtype=np.float64)
    if E.size != p["n"]:
        return None
    iv = int(p["iv_list"][0]) if p["iv_list"] else -1
    kw = p["kw"]
    rc = lib.dpn_timestep_descriptor(
        p["n"],
        p["nnz"],
        p["rp"].ctypes.data_as(_P_IDX),
        p["ci"].ctypes.data_as(_P_IDX),
        p["va"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        E.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        p["n_v"],
        p["n_die"],
        p["die_idx"],
        iv,
        float(dt),
        float(t_end),
        float(vdd),
        p["leak_a"].ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        kw["n_ev"],
        kw["idx"].ctypes.data_as(_P_IDX),
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
        print(f"dpn_timestep_descriptor rc={rc}", file=sys.stderr)
        return None
    out = _tran_result(kw, p["n_die"], "N4_descriptor_be", None, 1, vdd, dt, t_end, "native", "native_desc")
    out["via"] = "descriptor BE VRM+pkg+die (libdpn SparseLU)"
    return out


def native_descriptor_adaptive(
    sys, events, vdd: float, t_end: float, dt0: float, leak=None, atol: float = 1e-4, rtol: float = 0.01
):
    """Adaptive Δt descriptor BE. LTE on voltage states. Not the fixed-Δt gold when L>0."""
    lib = _libdpn()
    if lib is None or not hasattr(lib, "dpn_timestep_descriptor_adaptive"):
        return None
    p = _descriptor_prep(sys, events, vdd, t_end, dt0, leak=leak, adaptive=True)
    if p is None:
        return None
    mid, tail = _descriptor_wave_args(p, vdd, t_end, dt0)
    rc = lib.dpn_timestep_descriptor_adaptive(
        *_descriptor_common_args(p), *mid, float(atol), float(rtol), *tail
    )
    if rc != 0:
        print(f"dpn_timestep_descriptor_adaptive rc={rc}", file=sys.stderr)
        return None
    out = _tran_result(
        p["kw"], p["n_die"], "N4_descriptor_be_adaptive", None, 1, vdd, dt0, t_end, "native",
        "adaptive",
    )
    out["via"] = "descriptor BE sparse-E adaptive Δt (libdpn SparseLU; not gold when L>0)"
    return out


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

    def __init__(self, G, C, starts, shifts, n_moments: int, lib, sys=None):
        Gc = G.tocsr()
        n, nnz, rp, ci, va = _csr_ct(Gc)
        if nnz == 0:
            ci = np.zeros(1, dtype=_NP_IDX)
            va = np.zeros(1, dtype=np.float64)
        C = np.ascontiguousarray(C, dtype=np.float64)
        starts = np.asfortranarray(starts, dtype=np.float64)
        if starts.ndim != 2 or starts.shape[0] != n:
            raise ValueError("starts must be n × n_starts")
        shifts = np.ascontiguousarray(shifts, dtype=np.float64)
        bumps, n_bumps, bump_v = _bump_arrays(sys or {}, 0.0)
        pkg_l = float((sys or {}).get("pkg_l") or 0.0)
        use_rlc = sys is not None and pkg_l > 0.0 and n_bumps > 0 and hasattr(lib, "dpn_mor_setup_rlc")
        if use_rlc:
            h = lib.dpn_mor_setup_rlc(
                n,
                nnz,
                rp.ctypes.data_as(_P_IDX),
                ci.ctypes.data_as(_P_IDX),
                va.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                C.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                bumps.ctypes.data_as(_P_IDX),
                n_bumps,
                bump_v.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                float(sys.get("pkg_r") or 0.0),
                pkg_l,
                int(starts.shape[1]),
                starts.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                int(shifts.size),
                shifts.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                int(n_moments),
            )
            if not h:
                raise RuntimeError("dpn_mor_setup_rlc failed")
        else:
            h = lib.dpn_mor_setup(
                n,
                nnz,
                rp.ctypes.data_as(_P_IDX),
                ci.ctypes.data_as(_P_IDX),
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
        self._keep = (rp, ci, va, C, starts, shifts, bumps, bump_v)

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
            kw["idx"].ctypes.data_as(_P_IDX),
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


class NativeMorGen:
    """Sparse-E descriptor MOR (mutual L, n_iv, u_const). Not GCD Solver C."""

    name = "C_rational_krylov_rlc"
    backend = "native"

    def __init__(self, sys, starts, shifts, n_moments, lib):
        from pdn_vrm import as_e_csr

        A = sys["A"]
        n, nnz, rp, ci, va = _csr_ct(A)
        Ecsr = as_e_csr(sys["E"], n)
        n_e, nnz_e, erp, eci, eva = _csr_ct(Ecsr)
        if n_e != n:
            raise ValueError("E rows != A rows")
        if eci.size == 0:
            eci = np.zeros(1, dtype=_NP_IDX)
            eva = np.zeros(1, dtype=np.float64)
        n_v = int(sys["n_v"])
        die_idx = -1 if sys.get("die_idx") is None else int(sys["die_idx"])
        n_die = int(sys.get("n_die") or (1 if die_idx >= 0 else n_v))
        iv_list = sys.get("iv_list")
        if iv_list is None:
            iv = int(sys.get("iv", n_v))
            n_iv = int(sys.get("n_iv", 1 if iv >= 0 else 0))
            iv_list = list(range(iv, iv + n_iv)) if n_iv > 0 and iv >= 0 else []
            n_iv = len(iv_list)
        else:
            iv_list = [int(k) for k in iv_list]
            n_iv = len(iv_list)
        iv_arr = np.ascontiguousarray(iv_list if n_iv else [0], dtype=_NP_IDX)
        u0 = sys.get("u_const")
        u_ptr = None
        u_arr = None
        if u0 is not None:
            u_arr = np.ascontiguousarray(u0, dtype=np.float64)
            if u_arr.size != n:
                raise ValueError("u_const length")
            u_ptr = u_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        starts = np.asfortranarray(starts, dtype=np.float64)
        if starts.ndim != 2 or starts.shape[0] != n_v:
            raise ValueError("starts must be n_v × n_starts")
        shifts = np.ascontiguousarray(shifts, dtype=np.float64)
        h = lib.dpn_mor_setup_gen(
            n,
            nnz,
            rp.ctypes.data_as(_P_IDX),
            ci.ctypes.data_as(_P_IDX),
            va.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            nnz_e,
            erp.ctypes.data_as(_P_IDX),
            eci.ctypes.data_as(_P_IDX),
            eva.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            n_v,
            n_die,
            die_idx,
            n_iv,
            iv_arr.ctypes.data_as(_P_IDX),
            u_ptr,
            int(starts.shape[1]),
            starts.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            int(shifts.size),
            shifts.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            int(n_moments),
        )
        if not h:
            raise RuntimeError("dpn_mor_setup_gen failed")
        self._lib = lib
        self._h = h
        self.n = n_v
        self.n_die = n_die
        self.m = int(lib.dpn_mor_m(h))
        self.setup_s = float(lib.dpn_mor_setup_s(h))
        raw = lib.dpn_mor_name(h)
        self.name = raw.decode() if raw else self.name
        self._keep = (rp, ci, va, erp, eci, eva, starts, shifts, iv_arr, u_arr)

    def timestep(self, sys, events, vdd: float, t_end: float) -> dict:
        n_leak = max(int(sys.get("n_die") or self.n_die), 1)
        leak_raw = sys.get("leak")
        if leak_raw is None or isinstance(leak_raw, str):
            leak = np.zeros(n_leak, dtype=np.float64)
        else:
            leak = np.ascontiguousarray(leak_raw, dtype=np.float64)
        pad_raw = sys.get("pad")
        if pad_raw is None or isinstance(pad_raw, str):
            pad = np.zeros(self.n, dtype=np.float64)
        else:
            pad = np.ascontiguousarray(pad_raw, dtype=np.float64)
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
            kw["idx"].ctypes.data_as(_P_IDX),
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
        out = _tran_result(kw, self.n, self.name, self.setup_s, 1, vdd, dt, t_end, "native", "mor")
        out["n_levels"] = self.m
        out["m"] = self.m
        out["via"] = "sparse-E descriptor MOR (libdpn; not GCD Solver C)"
        return out

    def __del__(self):
        h = getattr(self, "_h", None)
        lib = getattr(self, "_lib", None)
        if h and lib:
            lib.dpn_mor_free(h)
            self._h = None


class PyMorDescriptor:
    """SciPy fallback: rational Arnoldi on sparse E (same stamp as libdpn gen MOR)."""

    name = "C_rational_krylov_rlc"
    backend = "python"

    def __init__(self, sys, starts, shifts, n_moments: int = 4):
        from pdn_vrm import as_e_csr

        t0 = time.perf_counter()
        self.Aop = sys["A"].tocsr().astype(np.float64)
        n = int(self.Aop.shape[0])
        self.E = as_e_csr(sys["E"], n)
        self.n_v = int(sys["n_v"])
        self.n_aug = n
        self.n = self.n_v
        self.die_idx = -1 if sys.get("die_idx") is None else int(sys["die_idx"])
        self.n_die = int(sys.get("n_die") or (1 if self.die_idx >= 0 else self.n_v))
        iv_list = sys.get("iv_list")
        if iv_list is None:
            iv = int(sys.get("iv", self.n_v))
            n_iv = int(sys.get("n_iv", 1 if iv >= 0 else 0))
            iv_list = list(range(iv, iv + n_iv)) if n_iv > 0 and iv >= 0 else []
        self.iv_list = [int(k) for k in iv_list]
        u0 = sys.get("u_const")
        self.u_const = None if u0 is None else np.asarray(u0, dtype=np.float64)
        starts = np.asarray(starts, dtype=np.float64)
        if starts.ndim == 1:
            starts = starts.reshape(self.n_v, 1)
        ns = []
        for j in self.iv_list:
            e = np.zeros(n)
            if 0 <= j < n:
                e[j] = 1.0
            ns.append(e)
        for b in range(starts.shape[1]):
            e = np.zeros(n)
            nv = min(self.n_v, n)
            e[:nv] = starts[:nv, b]
            ns.append(e)
        e = np.zeros(n)
        e[: min(self.n_v, n)] = 1.0 / np.sqrt(max(self.n_v, 1))
        ns.append(e)
        starts_use = np.column_stack(ns)
        cap = min(n, 96)
        Vcols = []
        moments = max(1, n_moments)
        for s in np.asarray(shifts, dtype=np.float64):
            K = (self.Aop + s * self.E).tocsc()
            lu = splu(K)
            for b in range(starts_use.shape[1]):
                rhs = starts_use[:, b].copy()
                for mom in range(moments):
                    if mom > 0:
                        rhs = self.E @ Vcols[-1]
                    x = lu.solve(rhs)
                    x = PyMor._mgs(Vcols, x)
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
        self.Ar = self.V.T @ (self.Aop @ self.V)
        self.Er = self.V.T @ (self.E @ self.V)
        self.setup_s = time.perf_counter() - t0

    def timestep(self, sys, events, vdd: float, t_end: float) -> dict:
        dt = float(sys["dt"])
        n_leak = max(self.n_die, 1)
        leak = np.asarray(sys.get("leak") if sys.get("leak") is not None else np.zeros(n_leak), dtype=np.float64)
        steps = max(2, int(np.ceil(t_end / dt)))
        Kr = self.Ar + self.Er / dt
        dsolve = np.linalg.solve
        x0 = np.zeros(self.n_aug)
        x0[: self.n_v] = vdd
        Ex = self.V.T @ (self.E @ x0)
        z = dsolve(self.Er, Ex)
        worst_v, worst_t, worst_i = vdd, 0.0, 0
        worst_V = np.full(self.n_v, vdd)
        wave_t, wave_vmin, wave_itot = [], [], []
        t0 = time.perf_counter()
        n_ev, idx, t50, dur, ip = _events_ct(events)
        for s in range(steps):
            t = s * dt
            I = np.zeros(n_leak)
            if leak.size:
                I[: min(leak.size, n_leak)] = leak[: min(leak.size, n_leak)]
            for e in range(n_ev):
                i = int(idx[e])
                if 0 <= i < n_leak:
                    I[i] += _py_triangle(t, float(t50[e]), float(dur[e]), float(ip[e]))
            u = np.zeros(self.n_aug)
            if self.die_idx >= 0:
                u[self.die_idx] = -I[0]
            else:
                nd = min(n_leak, self.n_aug)
                u[:nd] = -I[:nd]
            if self.u_const is not None:
                u = u + self.u_const
            for j in self.iv_list:
                if 0 <= j < self.n_aug:
                    u[j] += vdd
            f = self.V.T @ u
            rhs = (self.Er @ z) / dt + f
            z = dsolve(Kr, rhs)
            V = self.V[: self.n_v, :] @ z
            if self.die_idx >= 0 and self.die_idx < self.n_v:
                vmin = float(V[self.die_idx])
                imin = 0
            else:
                nd = min(self.n_die, self.n_v)
                imin = int(np.argmin(V[:nd]))
                vmin = float(V[imin])
            wave_t.append(float(t))
            wave_vmin.append(vmin)
            wave_itot.append(float(np.sum(I)))
            if vmin < worst_v:
                worst_v = vmin
                worst_t = float(t)
                worst_i = imin
                worst_V = np.asarray(V, dtype=np.float64).copy()
        return {
            "worst_voltage": worst_v,
            "worst_droop": vdd - worst_v,
            "worst_droop_pct": droop_pct(vdd, worst_v),
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
            "via": "sparse-E descriptor MOR (SciPy; not GCD Solver C)",
        }


def _py_triangle(t, t50, dur, ipulse):
    if dur <= 0.0 or ipulse == 0.0:
        return 0.0
    half = 0.5 * dur
    tau = t - t50
    if abs(tau) >= half:
        return 0.0
    return ipulse * (1.0 - abs(tau) / half)


def native_mor_descriptor(sys, starts, shifts, n_moments: int = 4):
    """Sparse-E descriptor MOR. Opt-in for on-die L+M; GCD Solver C stays package-L RLC MOR."""
    lib = _libdpn()
    if lib is not None and hasattr(lib, "dpn_mor_setup_gen"):
        try:
            return NativeMorGen(sys, starts, shifts, n_moments, lib)
        except Exception as exc:
            print(f"libdpn gen MOR unavailable ({exc}); using SciPy fallback", file=sys.stderr)
    return PyMorDescriptor(sys, starts, shifts, n_moments)


def _descriptor_rlc(Gmesh, bumps, pkg_r: float):
    """Unsymmetric MNA: C v' + G v − i = −I, L i' + R i + v = Vsrc."""
    Gmesh = Gmesh.tocsr().astype(np.float64)
    n = Gmesh.shape[0]
    bumps = np.asarray(bumps, dtype=np.int32)
    p = int(bumps.size)
    R = max(float(pkg_r), 1e-9)
    rows, cols, data = [], [], []
    Gcoo = Gmesh.tocoo()
    rows.extend(Gcoo.row.tolist())
    cols.extend(Gcoo.col.tolist())
    data.extend(Gcoo.data.tolist())
    for k, b in enumerate(bumps):
        b = int(b)
        if b < 0 or b >= n:
            continue
        ik = n + k
        rows.extend([b, ik, ik])
        cols.extend([ik, b, ik])
        data.extend([-1.0, 1.0, R])
    A = sparse.coo_matrix((data, (rows, cols)), shape=(n + p, n + p)).tocsr()
    return A, n, p


class PyMor:
    """SciPy fallback: same rational Arnoldi + reduced BE as libdpn (RC and RLC)."""

    name = "C_rational_krylov_mor"
    backend = "python"

    def __init__(self, G, C, starts, shifts, n_moments: int = 4, sys=None):
        t0 = time.perf_counter()
        self.C = np.asarray(C, dtype=np.float64)
        n = int(self.C.shape[0])
        starts = np.asarray(starts, dtype=np.float64)
        if starts.ndim == 1:
            starts = starts.reshape(n, 1)
        pkg_l = float((sys or {}).get("pkg_l") or 0.0)
        bumps = np.asarray((sys or {}).get("bump") or [], dtype=np.int32)
        self.rlc = bool(sys is not None and pkg_l > 0.0 and bumps.size > 0)
        if self.rlc:
            Gmesh = (sys.get("G_mesh") if sys and "G_mesh" in sys else G).tocsr()
            A, n, p = _descriptor_rlc(Gmesh, bumps, float(sys.get("pkg_r") or 0.0))
            E = np.zeros(n + p, dtype=np.float64)
            E[:n] = self.C
            E[n:] = pkg_l
            self.bump_v = np.asarray(sys.get("bump_v"), dtype=np.float64).reshape(-1)
            ns = []
            for k in range(p):
                e = np.zeros(n + p)
                e[n + k] = 1.0
                ns.append(e)
            for b in range(starts.shape[1]):
                e = np.zeros(n + p)
                e[:n] = starts[:, b]
                ns.append(e)
            e = np.zeros(n + p)
            e[:n] = 1.0 / np.sqrt(max(n, 1))
            ns.append(e)
            starts_use = np.column_stack(ns)
            self.Aop = A
            self.Ediag = E
            self.n = n
            self.n_aug = n + p
            self.name = "C_rational_krylov_rlc"
            cap = min(self.n_aug, 96)
        else:
            self.Aop = G.tocsr().astype(np.float64)
            self.Ediag = self.C
            self.n = n
            self.n_aug = n
            starts_use = starts
            cap = min(n, 96)
        Vcols = []
        moments = max(1, n_moments)
        for s in np.asarray(shifts, dtype=np.float64):
            K = (self.Aop + sparse.diags(s * self.Ediag)).tocsc()
            lu = splu(K)
            for b in range(starts_use.shape[1]):
                rhs = starts_use[:, b].copy()
                for mom in range(moments):
                    if mom > 0:
                        rhs = self.Ediag * Vcols[-1]
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
            x = np.ones(self.n_aug) / np.sqrt(self.n_aug)
            Vcols = [x]
        self.V = np.column_stack(Vcols)
        self.m = self.V.shape[1]
        AV = np.column_stack([self.Aop @ self.V[:, k] for k in range(self.m)])
        self.Ar = self.V.T @ AV
        self.Er = self.V.T @ (self.Ediag[:, None] * self.V)
        self.setup_s = time.perf_counter() - t0

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
        Kr = self.Ar + self.Er / dt
        dsolve = np.linalg.solve
        z = np.zeros(self.m)
        if self.rlc:
            Ex = np.zeros(self.m)
            for k in range(self.m):
                Ex[k] = float(np.dot(self.V[:n, k], self.Ediag[:n] * vdd))
            z = dsolve(self.Er, Ex)
        V = np.full(n, vdd)
        worst_v, worst_t, worst_i = vdd, 0.0, 0
        worst_V = V.copy()
        wave_t, wave_vmin, wave_itot = [], [], []
        t0 = time.perf_counter()
        p = self.n_aug - n
        for s in range(steps):
            t = s * dt
            I = leak.copy()
            for ev in events:
                tau = t - ev["t50_s"]
                dur = ev["dur_s"]
                half = 0.5 * dur
                if dur > 0 and ev["i_pulse"] > 0 and abs(tau) < half:
                    I[ev["idx"]] += ev["i_pulse"] * (1.0 - abs(tau) / half)
            if self.rlc:
                u = np.zeros(self.n_aug)
                u[:n] = -I
                for k in range(p):
                    u[n + k] = float(self.bump_v[k]) if k < self.bump_v.size else vdd
                f = self.V.T @ u
                rhs = (self.Er @ z) / dt + f
                z = dsolve(Kr, rhs)
                V = self.V[:n, :] @ z
            else:
                f = self.V.T @ I
                rhs = (self.Er @ z) / dt - f
                z = dsolve(Kr, rhs)
                V = vdd + self.V @ z
            vmin = float(np.min(V))
            wave_t.append(float(t))
            wave_vmin.append(vmin)
            wave_itot.append(float(np.sum(I)))
            if vmin < worst_v:
                worst_v = vmin
                worst_t = float(t)
                worst_i = int(np.argmin(V))
                worst_V = np.asarray(V, dtype=np.float64).copy()
        return {
            "worst_voltage": worst_v,
            "worst_droop": vdd - worst_v,
            "worst_droop_pct": droop_pct(vdd, worst_v),
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


def RationalKrylov(G, C, starts, shifts, n_moments: int = 4, sys=None):
    lib = _libdpn()
    Guse = G
    if sys is not None and float(sys.get("pkg_l") or 0.0) > 0.0 and "G_mesh" in sys:
        Guse = sys["G_mesh"]
    if lib is not None:
        try:
            return NativeMor(Guse, C, starts, shifts, n_moments, lib, sys=sys)
        except Exception as exc:
            print(f"libdpn MOR unavailable ({exc}); using SciPy fallback", file=sys.stderr)
    return PyMor(Guse, C, starts, shifts, n_moments, sys=sys)
