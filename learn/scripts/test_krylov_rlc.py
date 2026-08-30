#!/usr/bin/env python3
"""Krylov/MOR RLC stamp is a real function — not a leftover NameError."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Isolate system SciPy (1.x) from DSE NumPy 2 — same as dse.f4_oracle.
_DIST = "/usr/lib/python3/dist-packages"
_LOCAL = "/usr/local/lib/python3.12/dist-packages"
if _LOCAL in sys.path:
    sys.path.remove(_LOCAL)
sys.path.insert(0, _DIST)
sys.path.insert(0, str(REPO / "learn" / "scripts"))

import numpy as np  # noqa: E402
from scipy import sparse  # noqa: E402
from pdn_solvers import PyMor, _descriptor_rlc  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        FAILS.append(msg)


def main() -> int:
    G = sparse.csr_matrix([[2.0, -1.0], [-1.0, 2.0]], dtype=np.float64)
    A, n, p = _descriptor_rlc(G, [0], 0.05)
    check(n == 2 and p == 1 and A.shape == (3, 3), f"RLC stamp is n+p, got n={n} p={p} {A.shape}")
    C = np.array([50e-15, 50e-15], dtype=np.float64)
    starts = np.ones((2, 1), dtype=np.float64)
    shifts = np.array([0.0, 1e9], dtype=np.float64)
    sys_be = {
        "pkg_l": 2e-10,
        "pkg_r": 0.05,
        "bump": [0],
        "bump_v": [1.1],
        "G_mesh": G,
        "dt": 10e-12,
        "leak": np.zeros(2, dtype=np.float64),
    }
    mor = PyMor(G, C, starts, shifts, n_moments=2, sys=sys_be)
    check(mor.rlc and mor.name == "C_rational_krylov_rlc", f"PyMor takes the RLC path, rlc={mor.rlc} name={mor.name}")
    ev = [{"idx": 0, "t50_s": 0.1e-9, "dur_s": 0.08e-9, "i_pulse": 1e-3}]
    out = mor.timestep(sys_be, ev, 1.1, 0.3e-9)
    check(out.get("worst_droop") is not None and float(out["worst_droop"]) >= 0.0, f"RLC Krylov droop is paid, got {out.get('worst_droop')}")
    check(out.get("solver") == "C_rational_krylov_rlc", f"solver name stays RLC Krylov, got {out.get('solver')}")
    if FAILS:
        print(f"{len(FAILS)} FAILED")
        return 1
    print("ALL test_krylov_rlc PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
