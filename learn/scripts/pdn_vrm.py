#!/usr/bin/env python3
"""Lumped VRM → package → die descriptor (N4).

On a 0.46 ns GCD clock window a 47 µF VRM capacitor is a stiff voltage
source — N3 (ideal Vsrc + bump R+L) is the right gold for that slice.
N4 is the coupled MNA of a VRM ladder + die node, for µs load-steps and
for architecture (one descriptor, not a second ngspice-only world).

Stamp (unsymmetric, same as engine RLC MOR):
  C v' + G v − i = −I
  L i' + R i + v_plus − v_minus = 0   (or = Vsrc for the VRM branch)
On-die strap L uses the same descriptor (Grover partial self + cutoff mutual).
Never ML.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CFG = _ROOT / "learn" / "system_pdn" / "default.json"


def load_vrm_cfg(path: Path | None = None) -> dict:
    p = path or _DEFAULT_CFG
    if p.is_file():
        return json.loads(p.read_text())
    return {
        "vdd": 1.1,
        "vrm": {"r_out": 0.015, "l_out": 2e-9, "c_out": 47e-6, "esr_cout": 0.008},
        "package": {"r_pkg": 0.04, "l_pkg": 0.3e-9},
        "die": {"c_die": 50e-12},
    }


def compact_vrm_die(*, vdd: float, r_vrm: float, l_vrm: float, c_vrm: float, r_pkg: float, l_pkg: float, c_die: float):
    """2-voltage, 2-inductor MNA: Vsrc—R—L—n_vrm—C_vrm; n_vrm—R—L—n_die—C_die.

    x = [v_vrm, v_die, i_vrm, i_pkg]
    """
    n_v, n_i = 2, 2
    N = n_v + n_i
    E = np.zeros(N)
    E[0] = max(c_vrm, 1e-18)
    E[1] = max(c_die, 1e-18)
    E[2] = max(l_vrm, 1e-18)
    E[3] = max(l_pkg, 1e-18)
    rows, cols, data = [], [], []

    def put(i, j, v):
        rows.append(i)
        cols.append(j)
        data.append(v)

    # n_vrm: C v' - i_vrm + i_pkg = 0
    put(0, 2, -1.0)
    put(0, 3, 1.0)
    # n_die: C v' - i_pkg = -I_die
    put(1, 3, -1.0)
    # L_vrm: L i' + R i + v_vrm = Vsrc
    put(2, 0, 1.0)
    put(2, 2, max(r_vrm, 1e-9))
    # L_pkg: L i' + R i + v_die - v_vrm = 0
    put(3, 1, 1.0)
    put(3, 0, -1.0)
    put(3, 3, max(r_pkg, 1e-9))
    A = sparse.coo_matrix((data, (rows, cols)), shape=(N, N)).tocsc()
    names = ["n_vrm", "n_die", "i_vrm", "i_pkg"]
    return {
        "E": E,
        "A": A,
        "n_v": n_v,
        "n_i": n_i,
        "n_die": 1,
        "vdd": vdd,
        "names": names,
        "die_idx": 1,
        "iv": n_v,  # i_vrm; KVL row gets +Vsrc
    }


def assemble_n4_mesh(G_mesh, C_die, bumps, *, vdd: float, pkg_r: float, pkg_l: float, r_vrm: float, l_vrm: float, c_vrm: float):
    """On-die G,C plus one VRM node and per-bump R+L to that node.

    x = [v_die(n), v_vrm, i_vrm, i_bump(p)]
    """
    G_mesh = G_mesh.tocsr().astype(np.float64)
    C_die = np.asarray(C_die, dtype=np.float64)
    bumps = [int(b) for b in bumps]
    n = G_mesh.shape[0]
    p = len(bumps)
    n_v = n + 1
    iv = n_v  # i_vrm index
    ib0 = n_v + 1
    N = n_v + 1 + p
    E = np.zeros(N)
    E[:n] = C_die
    E[n] = max(c_vrm, 1e-18)
    E[iv] = max(l_vrm, 1e-18)
    for k in range(p):
        E[ib0 + k] = max(pkg_l, 1e-18)
    rows, cols, data = [], [], []

    def put(i, j, v):
        rows.append(i)
        cols.append(j)
        data.append(v)

    Gcoo = G_mesh.tocoo()
    for i, j, v in zip(Gcoo.row, Gcoo.col, Gcoo.data):
        put(int(i), int(j), float(v))
    # n_vrm KCL: C v' - i_vrm + sum i_bump = 0
    put(n, iv, -1.0)
    for k, b in enumerate(bumps):
        put(n, ib0 + k, 1.0)
        # die bump: -i_bump (current enters die from VRM)
        put(b, ib0 + k, -1.0)
        # bump inductor: L i' + R i + v_bump - v_vrm = 0
        put(ib0 + k, b, 1.0)
        put(ib0 + k, n, -1.0)
        put(ib0 + k, ib0 + k, max(pkg_r, 1e-9))
    # VRM inductor: L i' + R i + v_vrm = Vsrc
    put(iv, n, 1.0)
    put(iv, iv, max(r_vrm, 1e-9))
    A = sparse.coo_matrix((data, (rows, cols)), shape=(N, N)).tocsc()
    return {
        "E": E,
        "A": A,
        "n_v": n_v,
        "n_die": n,
        "n_i": 1 + p,
        "vdd": vdd,
        "die_idx": None,
        "iv": iv,
        "p": p,
    }


def as_e_csr(E, n: int):
    """Accept a dense diagonal, a dense n×n, or a scipy sparse E."""
    if sparse.issparse(E):
        M = E.tocsr().astype(np.float64)
        if M.shape != (n, n):
            raise ValueError(f"E shape {M.shape} != ({n}, {n})")
        return M
    e = np.asarray(E, dtype=np.float64)
    if e.ndim == 1:
        if e.size != n:
            raise ValueError(f"E length {e.size} != {n}")
        return sparse.diags(e, format="csr")
    if e.ndim != 2 or e.shape != (n, n):
        raise ValueError(f"E shape {getattr(e, 'shape', None)} != ({n}, {n})")
    return sparse.csr_matrix(e)


def assemble_strap_rlc(
    G_mesh,
    C,
    idx: dict,
    voltages: dict,
    straps: list,
    *,
    pkg_r: float,
    pkg_l: float,
    dt: float,
    vdd: float,
    pad: str = "companion",
    mutual: list | None = None,
):
    """Descriptor Eẋ+Ax=u with Grover strap L+M. Unsymmetric → SparseLU, never AMG.

    Unstamps converted R from G, then:
      pad=companion: N3 g_eq on bump diagonals + u_const = g_eq·Vdd (native gen OK).
      pad=inductor:  N bump R+L states (contiguous iv[0:p)); native +Vdd on each KVL row.
    Vias and unlisted R stay in G. Mutual is sparse off-diag in E (cutoff pairs).
    """
    from pdn_solvers import rl_companion

    G_mesh = G_mesh.tocsr().astype(np.float64)
    C = np.asarray(C, dtype=np.float64)
    n = G_mesh.shape[0]
    straps = [s for s in straps if s.get("a") in idx and s.get("b") in idx and float(s.get("L_h") or 0) > 0]
    Grest = G_mesh.tolil(copy=True)
    for s in straps:
        ia, ib = int(idx[s["a"]]), int(idx[s["b"]])
        g = 1.0 / max(float(s["r_ohm"]), 1e-18)
        Grest[ia, ia] -= g
        Grest[ib, ib] -= g
        Grest[ia, ib] += g
        Grest[ib, ia] += g
    bump = [int(idx[nm]) for nm in voltages if nm in idx]
    m = len(straps)
    rows, cols, data = [], [], []

    def put(i, j, v):
        rows.append(int(i))
        cols.append(int(j))
        data.append(float(v))

    pairs = []
    if mutual:
        for rec in mutual:
            i, j = int(rec["i"]), int(rec["j"])
            if 0 <= i < m and 0 <= j < m and i != j:
                pairs.append((i, j, float(rec["M_h"])))

    def stamp_straps(E_lil, i_strap0: int):
        for k, s in enumerate(straps):
            ia, ib = int(idx[s["a"]]), int(idx[s["b"]])
            ik = i_strap0 + k
            E_lil[ik, ik] = max(float(s["L_h"]), 1e-18)
            put(ia, ik, -1.0)
            put(ib, ik, 1.0)
            put(ik, ia, 1.0)
            put(ik, ib, -1.0)
            put(ik, ik, max(float(s["r_ohm"]), 1e-9))
        for i, j, Mh in pairs:
            ii, jj = i_strap0 + i, i_strap0 + j
            E_lil[ii, jj] += Mh
            E_lil[jj, ii] += Mh

    if pad == "inductor":
        if not bump:
            raise ValueError("pad=inductor requires at least one bump")
        p = len(bump)
        N = n + p + m
        E_lil = sparse.lil_matrix((N, N), dtype=np.float64)
        for i in range(n):
            E_lil[i, i] = C[i]
        Gcoo = Grest.tocoo()
        for i, j, v in zip(Gcoo.row, Gcoo.col, Gcoo.data):
            put(int(i), int(j), float(v))
        for q, b0 in enumerate(bump):
            ik = n + q
            E_lil[ik, ik] = max(pkg_l, 1e-18)
            put(b0, ik, -1.0)
            put(ik, b0, 1.0)
            put(ik, ik, max(pkg_r, 1e-9))
        stamp_straps(E_lil, n + p)
        A = sparse.coo_matrix((data, (rows, cols)), shape=(N, N)).tocsc()
        iv_list = list(range(n, n + p))
        return {
            "E": E_lil.tocsr(),
            "A": A,
            "n_v": n,
            "n_die": n,
            "n_i": p + m,
            "vdd": vdd,
            "die_idx": None,
            "iv": n,
            "n_iv": p,
            "iv_list": iv_list,
            "u_const": None,
            "n_straps": m,
            "n_mutual": len(pairs),
            "n_bumps": p,
            "pad": "inductor",
            "via": (
                f"descriptor BE on-die Grover L+M ({len(pairs)} pairs) + {p} bump R+L "
                "(unsymmetric SparseLU)"
            ),
        }

    g_eq, _hsc = rl_companion(pkg_r, pkg_l, dt)
    for i in bump:
        Grest[i, i] += g_eq
    N = n + m
    E_lil = sparse.lil_matrix((N, N), dtype=np.float64)
    for i in range(n):
        E_lil[i, i] = C[i]
    Gcoo = Grest.tocoo()
    for i, j, v in zip(Gcoo.row, Gcoo.col, Gcoo.data):
        put(int(i), int(j), float(v))
    stamp_straps(E_lil, n)
    A = sparse.coo_matrix((data, (rows, cols)), shape=(N, N)).tocsc()
    u_const = np.zeros(N)
    for i in bump:
        u_const[i] = g_eq * vdd
    return {
        "E": E_lil.tocsr(),
        "A": A,
        "n_v": n,
        "n_die": n,
        "n_i": m,
        "vdd": vdd,
        "die_idx": None,
        "iv": -1,
        "n_iv": 0,
        "iv_list": [],
        "u_const": u_const,
        "n_straps": m,
        "n_mutual": len(pairs),
        "g_pad": g_eq,
        "pad": "companion",
        "via": (
            f"descriptor BE on-die Grover L+M ({len(pairs)} pairs) + N3 pad companion "
            "(native gen; not AMG)"
        ),
    }


def timestep_descriptor(sys: dict, i_die, dt: float, t_end: float, vdd: float, leak=None, events=None) -> dict:
    """Fixed-Δt BE on Eẋ + A x = u(t). UIC: voltages = Vdd, currents = 0.

    i_die is either a callable t→float (compact 1-node) or t→ndarray of length n_die.
    When `events` is given, libdpn descriptor BE is preferred (sparse E, u_const, n_iv).
    """
    if events is not None:
        from pdn_solvers import native_descriptor

        nat = native_descriptor(sys, events, vdd, t_end, dt, leak=leak)
        if nat is not None:
            return nat

    A = sys["A"].tocsc()
    n = A.shape[0]
    E = as_e_csr(sys["E"], n)
    n_die = int(sys.get("n_die") or (1 if sys.get("die_idx") is not None else sys["n_v"]))
    steps = max(2, int(np.ceil(t_end / dt)))
    K = (A + E / dt).tocsc()
    lu = splu(K)
    x = np.zeros(n)
    n_v = int(sys["n_v"])
    for i in range(n_v):
        x[i] = vdd
    worst_v, worst_t, worst_i = vdd, 0.0, 0
    worst_Vdie = np.full(n_die, vdd)
    wave_t, wave_v = [], []
    u0 = sys.get("u_const")
    u0 = None if u0 is None else np.asarray(u0, dtype=np.float64)
    iv_list = sys.get("iv_list")
    if iv_list is None:
        iv = int(sys.get("iv", sys.get("n_v", 0)))
        n_iv = int(sys.get("n_iv", 1 if iv >= 0 else 0))
        iv_list = list(range(iv, iv + n_iv)) if n_iv > 0 and iv >= 0 else []
    for s in range(steps):
        t = s * dt
        u = np.zeros(n)
        if u0 is not None:
            u += u0
        idraw = i_die(t)
        if np.isscalar(idraw) or (isinstance(idraw, np.ndarray) and idraw.ndim == 0):
            die = int(sys["die_idx"])
            u[die] -= float(idraw)
            vmin_nodes = (die,)
        else:
            idraw = np.asarray(idraw, dtype=np.float64)
            u[:n_die] -= idraw
            vmin_nodes = range(n_die)
        for ivk in iv_list:
            u[int(ivk)] += vdd
        rhs = E.dot(x) / dt + u
        x = lu.solve(rhs)
        vdie = x[:n_die] if sys.get("die_idx") is None else np.array([x[int(sys["die_idx"])]])
        imin = int(np.argmin(vdie))
        v = float(vdie[imin])
        wave_t.append(t)
        wave_v.append(v)
        if v < worst_v:
            worst_v, worst_t, worst_i = v, t, imin
            worst_Vdie = np.asarray(vdie, dtype=np.float64).copy()
    return {
        "worst_voltage": worst_v,
        "worst_droop": vdd - worst_v,
        "worst_time_s": worst_t,
        "worst_node_idx": worst_i,
        "wave_t": wave_t,
        "wave_vmin": wave_v,
        "steps": steps,
        "V_worst": worst_Vdie,
        "via": sys.get("via") or "descriptor BE VRM+pkg+die (Python SparseLU)",
        "backend": "python",
        "timestep_loop": "python_desc",
    }


def ngspice_strap_rlc_gold(
    *,
    vdd=1.1,
    r_pkg=0.05,
    l_pkg=2e-10,
    r_s=0.38,
    l_s=1e-12,
    c0=50e-12,
    c1=50e-12,
    i_peak=5e-3,
    t50=0.2e-9,
    dur=0.2e-9,
    dt=10e-12,
    t_end=0.4e-9,
) -> dict:
    """2-node Grover strap R+L vs ngspice gear maxord=1. Pad is a descriptor inductor."""
    from pdn_current import triangle_above_leak
    from pdn_transient import build_system

    resistors = [("n0", "n1", r_s)]
    voltages = {"n0": vdd}
    _, idx, G = build_system(resistors, {"n1": 0.0}, voltages)
    C = np.array([c0, c1], dtype=np.float64)
    straps = [{"a": "n0", "b": "n1", "r_ohm": r_s, "L_h": l_s}]
    sysd = assemble_strap_rlc(
        G, C, idx, voltages, straps, pkg_r=r_pkg, pkg_l=l_pkg, dt=dt, vdd=vdd, pad="inductor"
    )
    i1 = idx["n1"]

    def i_die(t):
        i = np.zeros(2)
        i[i1] = triangle_above_leak(t, t50, dur, i_peak)
        return i

    be = timestep_descriptor(
        sysd,
        i_die,
        dt,
        t_end,
        vdd,
        events=[{"idx": i1, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}],
    )
    t0 = max(t50 - 0.5 * dur, 0.0)
    t1 = t50 + 0.5 * dur
    tmp = Path(tempfile.mkdtemp(prefix="dynir-strap-l-"))
    sp_path = tmp / "strap.sp"
    dat_path = tmp / "strap.dat"
    sp_path.write_text(
        f"""* 2-node on-die R+L strap (gear maxord=1 ≈ BE)
Vsrc src 0 DC {vdd}
Rpkg src a {r_pkg}
Lpkg a n0 {l_pkg}
C0 n0 0 {c0}
Rs n0 mid {r_s}
Ls mid n1 {l_s}
C1 n1 0 {c1}
Iload n1 0 PWL(0 0 {t0:.6e} 0 {t50:.6e} {i_peak:.6e} {t1:.6e} 0 {t_end:.6e} 0)
.control
option method=gear maxord=1
set filetype=ascii
tran {dt:.6e} {t_end:.6e}
wrdata {dat_path} v(n1)
quit
.endc
.end
"""
    )
    subprocess.run(["ngspice", "-b", str(sp_path)], capture_output=True, text=True, timeout=30)
    vmin = None
    for extra in [dat_path, *sorted(tmp.glob("strap.dat*"))]:
        if not extra.is_file():
            continue
        for line in extra.read_text(errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                v = float(parts[1])
            except ValueError:
                continue
            vmin = v if vmin is None else min(vmin, v)
        if vmin is not None:
            break
    if vmin is None:
        return {"ok": False, "be_vmin": be["worst_voltage"], "ngspice_vmin": None, "backend": be.get("backend")}
    err_mv = abs(be["worst_voltage"] - vmin) * 1e3
    return {
        "ok": err_mv < 5.0,
        "be_vmin": be["worst_voltage"],
        "ngspice_vmin": vmin,
        "abs_err_mv": err_mv,
        "be_droop_mv": be["worst_droop"] * 1e3,
        "n_straps": sysd.get("n_straps"),
        "backend": be.get("backend"),
        "method": "ngspice gear maxord=1 vs descriptor BE Grover strap R+L",
    }


def ngspice_vrm_die_gold(*, vdd, r_vrm, l_vrm, c_vrm, r_pkg, l_pkg, c_die, i_peak, t50, dur, dt, t_end) -> dict:
    """ngspice gear maxord=1 vs compact VRM+die BE."""
    from pdn_current import triangle_above_leak

    sysd = compact_vrm_die(
        vdd=vdd, r_vrm=r_vrm, l_vrm=l_vrm, c_vrm=c_vrm, r_pkg=r_pkg, l_pkg=l_pkg, c_die=c_die
    )
    be = timestep_descriptor(
        sysd,
        lambda t: triangle_above_leak(t, t50, dur, i_peak),
        dt,
        t_end,
        vdd,
        events=[{"idx": 0, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}],
    )
    t0 = max(t50 - 0.5 * dur, 0.0)
    t1 = t50 + 0.5 * dur
    tmp = Path(tempfile.mkdtemp(prefix="dynir-n4-gold-"))
    sp_path = tmp / "n4.sp"
    dat_path = tmp / "n4.dat"
    sp_path.write_text(
        f"""* N4 compact VRM+pkg+die (gear maxord=1 ≈ BE)
Vsrc src 0 DC {vdd}
Rv src midv {r_vrm}
Lv midv nv {l_vrm}
Cv nv 0 {c_vrm}
Rp nv midp {r_pkg}
Lp midp nd {l_pkg}
Cd nd 0 {c_die}
Iload nd 0 PWL(0 0 {t0:.6e} 0 {t50:.6e} {i_peak:.6e} {t1:.6e} 0 {t_end:.6e} 0)
.control
option method=gear maxord=1
set filetype=ascii
tran {dt:.6e} {t_end:.6e}
wrdata {dat_path} v(nd)
quit
.endc
.end
"""
    )
    subprocess.run(["ngspice", "-b", str(sp_path)], capture_output=True, text=True, timeout=30)
    vmin = None
    for extra in [dat_path, *sorted(tmp.glob("n4.dat*"))]:
        if not extra.is_file():
            continue
        for line in extra.read_text(errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                v = float(parts[1])
            except ValueError:
                continue
            vmin = v if vmin is None else min(vmin, v)
        if vmin is not None:
            break
    if vmin is None:
        return {"ok": False, "be_vmin": be["worst_voltage"], "ngspice_vmin": None}
    err_mv = abs(be["worst_voltage"] - vmin) * 1e3
    return {
        "ok": err_mv < 5.0,
        "be_vmin": be["worst_voltage"],
        "ngspice_vmin": vmin,
        "abs_err_mv": err_mv,
        "be_droop_mv": be["worst_droop"] * 1e3,
        "method": "ngspice gear maxord=1 vs descriptor BE VRM+die",
    }


def _read_vmin_wrdata(paths) -> float | None:
    vmin = None
    for extra in paths:
        if not extra.is_file():
            continue
        for line in extra.read_text(errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                v = float(parts[1])
            except ValueError:
                continue
            vmin = v if vmin is None else min(vmin, v)
        if vmin is not None:
            return vmin
    return None


def ngspice_coupled_l_gold(
    *,
    vdd=1.1,
    r_pkg=0.05,
    l_pkg=2e-10,
    r_s=0.38,
    l_s=1e-12,
    k=0.3,
    c0=50e-12,
    c1=50e-12,
    i_peak=5e-3,
    t50=0.2e-9,
    dur=0.2e-9,
    dt=10e-12,
    t_end=0.4e-9,
) -> dict:
    """Two parallel Grover straps with K coupling vs ngspice gear maxord=1."""
    from pdn_current import triangle_above_leak
    from pdn_transient import build_system

    resistors = [("n0", "n1", r_s), ("n0", "n1", r_s)]
    voltages = {"n0": vdd}
    _, idx, G = build_system(resistors, {"n1": 0.0}, voltages)
    C = np.array([c0, c1], dtype=np.float64)
    straps = [
        {"a": "n0", "b": "n1", "r_ohm": r_s, "L_h": l_s},
        {"a": "n0", "b": "n1", "r_ohm": r_s, "L_h": l_s},
    ]
    M = k * l_s
    sysd = assemble_strap_rlc(
        G,
        C,
        idx,
        voltages,
        straps,
        pkg_r=r_pkg,
        pkg_l=l_pkg,
        dt=dt,
        vdd=vdd,
        pad="inductor",
        mutual=[{"i": 0, "j": 1, "M_h": M, "k": k}],
    )
    i1 = idx["n1"]

    def i_die(t):
        i = np.zeros(2)
        i[i1] = triangle_above_leak(t, t50, dur, i_peak)
        return i

    be = timestep_descriptor(
        sysd,
        i_die,
        dt,
        t_end,
        vdd,
        events=[{"idx": i1, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}],
    )
    t0 = max(t50 - 0.5 * dur, 0.0)
    t1 = t50 + 0.5 * dur
    tmp = Path(tempfile.mkdtemp(prefix="dynir-strap-k-"))
    sp_path = tmp / "strapk.sp"
    dat_path = tmp / "strapk.dat"
    sp_path.write_text(
        f"""* 2 parallel on-die R+L straps with K coupling (gear maxord=1 ≈ BE)
Vsrc src 0 DC {vdd}
Rpkg src a {r_pkg}
Lpkg a n0 {l_pkg}
C0 n0 0 {c0}
Rs1 n0 mid1 {r_s}
Ls1 mid1 n1 {l_s}
Rs2 n0 mid2 {r_s}
Ls2 mid2 n1 {l_s}
C1 n1 0 {c1}
K12 Ls1 Ls2 {k}
Iload n1 0 PWL(0 0 {t0:.6e} 0 {t50:.6e} {i_peak:.6e} {t1:.6e} 0 {t_end:.6e} 0)
.control
option method=gear maxord=1
set filetype=ascii
tran {dt:.6e} {t_end:.6e}
wrdata {dat_path} v(n1)
quit
.endc
.end
"""
    )
    subprocess.run(["ngspice", "-b", str(sp_path)], capture_output=True, text=True, timeout=30)
    vmin = _read_vmin_wrdata([dat_path, *sorted(tmp.glob("strapk.dat*"))])
    if vmin is None:
        return {
            "ok": False,
            "be_vmin": be["worst_voltage"],
            "ngspice_vmin": None,
            "backend": be.get("backend"),
            "n_mutual": sysd.get("n_mutual"),
        }
    err_mv = abs(be["worst_voltage"] - vmin) * 1e3
    return {
        "ok": err_mv < 5.0,
        "be_vmin": be["worst_voltage"],
        "ngspice_vmin": vmin,
        "abs_err_mv": err_mv,
        "be_droop_mv": be["worst_droop"] * 1e3,
        "n_straps": sysd.get("n_straps"),
        "n_mutual": sysd.get("n_mutual"),
        "backend": be.get("backend"),
        "method": "ngspice gear maxord=1 vs descriptor BE Grover strap K coupling",
    }


def xyce_in_path() -> str | None:
    """Xyce binary if installed. Never a fake solver."""
    import shutil

    found = shutil.which("Xyce") or shutil.which("xyce")
    if found:
        return found
    local = Path(__file__).resolve().parents[2] / "learn/tools/xyce/bin/Xyce"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return None


def _xyce_env() -> dict:
    """LD_LIBRARY_PATH for a local learn/tools/xyce prefix."""
    env = os.environ.copy()
    exe = xyce_in_path()
    if not exe:
        return env
    lib = Path(exe).resolve().parent.parent / "lib"
    if lib.is_dir():
        env["LD_LIBRARY_PATH"] = f"{lib}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"
    return env


def write_xyce_rlc_deck(
    path: Path,
    *,
    vdd: float,
    r_vrm: float,
    l_vrm: float,
    c_vrm: float,
    r_pkg: float,
    l_pkg: float,
    c_die: float,
    i_peak: float,
    t50: float,
    dur: float,
    dt: float,
    t_end: float,
) -> str:
    """Xyce-format TRAN deck: R/L/C/PWL/.TRAN/.PRINT. Same circuit as ngspice N4 gold."""
    t0 = max(t50 - 0.5 * dur, 0.0)
    t1 = t50 + 0.5 * dur
    csv_path = path.with_suffix(".csv")
    text = f"""* Xyce N4 compact VRM+pkg+die (contract deck; not a fake solver)
Vsrc src 0 {vdd}
Rv src midv {r_vrm}
Lv midv nv {l_vrm}
Cv nv 0 {c_vrm}
Rp nv midp {r_pkg}
Lp midp nd {l_pkg}
Cd nd 0 {c_die}
Iload nd 0 PWL(0 0 {t0:.6e} 0 {t50:.6e} {i_peak:.6e} {t1:.6e} 0 {t_end:.6e} 0)
.TRAN {dt:.6e} {t_end:.6e}
.PRINT TRAN FORMAT=CSV FILE={csv_path.name} V(nd)
.END
"""
    path.write_text(text)
    return text


def xyce_vrm_die_gold(**kwargs) -> dict:
    """Run the Xyce N4 deck if Xyce is in PATH; otherwise GAP with the deck as the contract."""
    from pdn_current import triangle_above_leak

    vdd = kwargs.get("vdd", 1.1)
    r_vrm = kwargs.get("r_vrm", 0.015)
    l_vrm = kwargs.get("l_vrm", 2e-10)
    c_vrm = kwargs.get("c_vrm", 50e-12)
    r_pkg = kwargs.get("r_pkg", 0.05)
    l_pkg = kwargs.get("l_pkg", 2e-10)
    c_die = kwargs.get("c_die", 50e-12)
    i_peak = kwargs.get("i_peak", 5e-3)
    t50 = kwargs.get("t50", 0.2e-9)
    dur = kwargs.get("dur", 0.2e-9)
    dt = kwargs.get("dt", 10e-12)
    t_end = kwargs.get("t_end", 0.4e-9)
    sysd = compact_vrm_die(
        vdd=vdd, r_vrm=r_vrm, l_vrm=l_vrm, c_vrm=c_vrm, r_pkg=r_pkg, l_pkg=l_pkg, c_die=c_die
    )
    be = timestep_descriptor(
        sysd,
        lambda t: triangle_above_leak(t, t50, dur, i_peak),
        dt,
        t_end,
        vdd,
        events=[{"idx": 0, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}],
    )
    tmp = Path(tempfile.mkdtemp(prefix="dynir-xyce-n4-"))
    deck = tmp / "n4_xyce.cir"
    text = write_xyce_rlc_deck(
        deck,
        vdd=vdd,
        r_vrm=r_vrm,
        l_vrm=l_vrm,
        c_vrm=c_vrm,
        r_pkg=r_pkg,
        l_pkg=l_pkg,
        c_die=c_die,
        i_peak=i_peak,
        t50=t50,
        dur=dur,
        dt=dt,
        t_end=t_end,
    )
    has_rlc = all(tok in text for tok in ("Rv ", "Lv ", "Cv ", "Rp ", "Lp ", "Cd ", "PWL", ".TRAN"))
    exe = xyce_in_path()
    if not exe:
        return {
            "ok": False,
            "status": "GAP",
            "reason": "Xyce not in PATH",
            "deck_ok": has_rlc,
            "deck": str(deck),
            "be_vmin": be["worst_voltage"],
            "backend": be.get("backend"),
            "method": "Xyce deck contract (R/L/C/PWL/.TRAN/.PRINT); solver not installed",
        }
    proc = subprocess.run(
        [exe, str(deck)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(tmp),
        env=_xyce_env(),
    )
    vmin = None
    csv_path = tmp / "n4_xyce.csv"
    if csv_path.is_file():
        for line in csv_path.read_text(errors="replace").splitlines():
            if line.startswith("INDEX") or line.startswith("TIME") or not line.strip():
                continue
            parts = [p.strip() for p in line.replace(",", " ").split()]
            if len(parts) < 2:
                continue
            try:
                v = float(parts[-1])
            except ValueError:
                continue
            vmin = v if vmin is None else min(vmin, v)
    if vmin is None:
        return {
            "ok": False,
            "status": "GAP",
            "reason": f"Xyce rc={proc.returncode}",
            "deck_ok": has_rlc,
            "be_vmin": be["worst_voltage"],
        }
    err_mv = abs(be["worst_voltage"] - vmin) * 1e3
    return {
        "ok": err_mv < 5.0,
        "status": "READY",
        "be_vmin": be["worst_voltage"],
        "xyce_vmin": vmin,
        "abs_err_mv": err_mv,
        "deck_ok": has_rlc,
        "method": "Xyce TRAN vs descriptor BE VRM+die",
    }
