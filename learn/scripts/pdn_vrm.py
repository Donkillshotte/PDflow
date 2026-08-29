#!/usr/bin/env python3
"""Lumped VRM → package → die descriptor (N4).

On a 0.46 ns GCD clock window a 47 µF VRM capacitor is a stiff voltage
source — N3 (ideal Vsrc + bump R+L) is the right gold for that slice.
N4 is the coupled MNA of a VRM ladder + die node, for µs load-steps and
for architecture (one descriptor, not a second ngspice-only world).

Stamp (unsymmetric, same as engine RLC MOR):
  C v' + G v − i = −I
  L i' + R i + v_plus − v_minus = 0   (or = Vsrc for the VRM branch)
On-die strap L uses the same descriptor (Grover partial self, no mutual).
Never ML.
"""

from __future__ import annotations

import json
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
):
    """Descriptor Eẋ+Ax=u with Grover strap L. Unsymmetric → SparseLU, never AMG.

    Unstamps converted R from G, then:
      pad=companion: N3 g_eq on bump diagonals + u_const = g_eq·Vdd (Python TRAN).
      pad=inductor:  one bump R+L state (native-compatible; iv = that KVL row).
    Vias and unlisted R stay in G. No mutual L.
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

    if pad == "inductor":
        if len(bump) != 1:
            raise ValueError("pad=inductor requires exactly one bump (native +Vdd on one KVL row)")
        b0 = bump[0]
        N = n + 1 + m
        E = np.zeros(N)
        E[:n] = C
        E[n] = max(pkg_l, 1e-18)
        Gcoo = Grest.tocoo()
        for i, j, v in zip(Gcoo.row, Gcoo.col, Gcoo.data):
            put(int(i), int(j), float(v))
        put(b0, n, -1.0)
        put(n, b0, 1.0)
        put(n, n, max(pkg_r, 1e-9))
        i0 = n + 1
        for k, s in enumerate(straps):
            ia, ib = int(idx[s["a"]]), int(idx[s["b"]])
            ik = i0 + k
            E[ik] = max(float(s["L_h"]), 1e-18)
            put(ia, ik, -1.0)
            put(ib, ik, 1.0)
            put(ik, ia, 1.0)
            put(ik, ib, -1.0)
            put(ik, ik, max(float(s["r_ohm"]), 1e-9))
        A = sparse.coo_matrix((data, (rows, cols)), shape=(N, N)).tocsc()
        return {
            "E": E,
            "A": A,
            "n_v": n,
            "n_die": n,
            "n_i": 1 + m,
            "vdd": vdd,
            "die_idx": None,
            "iv": n,
            "u_const": None,
            "n_straps": m,
            "pad": "inductor",
            "via": "descriptor BE on-die Grover L + bump R+L (unsymmetric SparseLU)",
        }

    g_eq, _hsc = rl_companion(pkg_r, pkg_l, dt)
    for i in bump:
        Grest[i, i] += g_eq
    N = n + m
    E = np.zeros(N)
    E[:n] = C
    Gcoo = Grest.tocoo()
    for i, j, v in zip(Gcoo.row, Gcoo.col, Gcoo.data):
        put(int(i), int(j), float(v))
    for k, s in enumerate(straps):
        ia, ib = int(idx[s["a"]]), int(idx[s["b"]])
        ik = n + k
        E[ik] = max(float(s["L_h"]), 1e-18)
        put(ia, ik, -1.0)
        put(ib, ik, 1.0)
        put(ik, ia, 1.0)
        put(ik, ib, -1.0)
        put(ik, ik, max(float(s["r_ohm"]), 1e-9))
    A = sparse.coo_matrix((data, (rows, cols)), shape=(N, N)).tocsc()
    u_const = np.zeros(N)
    for i in bump:
        u_const[i] = g_eq * vdd
    return {
        "E": E,
        "A": A,
        "n_v": n,
        "n_die": n,
        "n_i": m,
        "vdd": vdd,
        "die_idx": None,
        "iv": -1,
        "u_const": u_const,
        "n_straps": m,
        "g_pad": g_eq,
        "pad": "companion",
        "via": "descriptor BE on-die Grover L + N3 pad companion (Python; not AMG)",
    }


def timestep_descriptor(sys: dict, i_die, dt: float, t_end: float, vdd: float, leak=None, events=None) -> dict:
    """Fixed-Δt BE on Eẋ + A x = u(t). UIC: voltages = Vdd, currents = 0.

    i_die is either a callable t→float (compact 1-node) or t→ndarray of length n_die.
    When `events` is given, libdpn descriptor BE is preferred unless u_const/iv<0.
    """
    iv = int(sys.get("iv", sys.get("n_v", 0)))
    use_native = events is not None and sys.get("u_const") is None and iv >= 0
    if use_native:
        from pdn_solvers import native_descriptor

        nat = native_descriptor(sys, events, vdd, t_end, dt, leak=leak)
        if nat is not None:
            return nat

    E = np.asarray(sys["E"], dtype=np.float64)
    A = sys["A"].tocsc()
    n = A.shape[0]
    n_die = int(sys.get("n_die") or (1 if sys.get("die_idx") is not None else sys["n_v"]))
    steps = max(2, int(np.ceil(t_end / dt)))
    K = (A + sparse.diags(E / dt)).tocsc()
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
        if iv >= 0:
            u[iv] += vdd
        rhs = (E / dt) * x + u
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
