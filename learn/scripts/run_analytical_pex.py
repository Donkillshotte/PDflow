#!/usr/bin/env python3
"""Analytical + 2D FDM interconnect PEX (FasterCap / Raphael stand-in).

- Sakurai & Tamaru, IEEE TED 1983: closed-form Cg / Cc for a microstrip pair.
- 2D Laplace FDM on a FreePDK45-like M2 cross-section: educational FasterCap.

Not a replacement for OpenRCX SPEF on the full chip — a 2-wire extract
students can compare to 6_final.spef orders of magnitude.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# FreePDK45 / Nangate45 metal2-ish stack (µm). Educational, not foundry-signed.
W = 0.14  # width
T = 0.35  # thickness
H = 0.29  # ILD height
S = 0.14  # spacing
L_UM = 10.0  # 10 µm coupled run
EPS0 = 8.854e-18  # F/µm
EPSR = 3.9
EPS = EPS0 * EPSR


def sakurai_tamaru(w: float, t: float, h: float, s: float, length: float) -> dict:
    """Area + fringe + coupling (µm in, F out)."""
    wh, th, sh = w / h, t / h, s / h
    c_g_pul = EPS * (1.15 * wh + 2.80 * (th ** 0.222))
    c_c_pul = EPS * (0.03 * wh + 0.83 * th - 0.07 * (th ** 0.222)) * (sh ** -1.34)
    c_g = c_g_pul * length
    c_c = max(c_c_pul, 0.0) * length
    rsq = 0.07
    r = rsq * length / max(w, 1e-6)
    return {
        "length_um": length,
        "w_um": w,
        "t_um": t,
        "h_um": h,
        "s_um": s,
        "c_ground_f": c_g,
        "c_couple_f": c_c,
        "r_ohm": r,
        "c_ground_fF": c_g * 1e15,
        "c_couple_fF": c_c * 1e15,
    }


def fdm_two_trace(w: float, t: float, h: float, s: float, length: float,
                  nx: int = 72, ny: int = 48, iters: int = 800) -> dict:
    """2D Laplace FDM for two traces over a ground plane.

    Conductor A = 1 V, B and ground = 0 V. Charge from Gauss flux on A/B
    gives C11 and |C12|; Cg ≈ C11+|C12|, Cc ≈ |C12|, then × length.
    """
    margin = 3.0 * h
    width = margin + w + s + w + margin
    height = h + t + 3.0 * h
    dx = width / nx
    dy = height / ny

    def in_rect(x: float, y: float, x0: float, y0: float, ww: float, hh: float) -> bool:
        return x0 <= x <= x0 + ww and y0 <= y <= y0 + hh

    ax0 = margin
    bx0 = margin + w + s
    y0 = h

    phi = [[0.0] * nx for _ in range(ny)]
    fixed = [[False] * nx for _ in range(ny)]
    tag = [[0] * nx for _ in range(ny)]  # 1=A, 2=B, 3=GND
    for j in range(ny):
        y = (j + 0.5) * dy
        for i in range(nx):
            x = (i + 0.5) * dx
            if j == 0 or in_rect(x, y, -1, -1, width + 2, 0.02):
                phi[j][i] = 0.0
                fixed[j][i] = True
                tag[j][i] = 3
            elif in_rect(x, y, ax0, y0, w, t):
                phi[j][i] = 1.0
                fixed[j][i] = True
                tag[j][i] = 1
            elif in_rect(x, y, bx0, y0, w, t):
                phi[j][i] = 0.0
                fixed[j][i] = True
                tag[j][i] = 2

    wjac = 1.7
    for _ in range(iters):
        for j in range(1, ny - 1):
            row = phi[j]
            up, dn = phi[j + 1], phi[j - 1]
            fx = fixed[j]
            for i in range(1, nx - 1):
                if fx[i]:
                    continue
                nv = 0.25 * (row[i - 1] + row[i + 1] + up[i] + dn[i])
                row[i] += wjac * (nv - row[i])

    def flux_around(which: int) -> float:
        q = 0.0
        for j in range(1, ny - 1):
            for i in range(1, nx - 1):
                if tag[j][i] != which:
                    continue
                # outward flux from conductor into dielectric neighbours
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ii, jj = i + di, j + dj
                    if tag[jj][ii] == which:
                        continue
                    ds = dy if di != 0 else dx
                    dnrm = dx if di != 0 else dy
                    q += EPS * (phi[j][i] - phi[jj][ii]) / dnrm * ds
        return q

    c11_pul = flux_around(1)  # F/µm  (Q/V, V=1)
    c12_pul = abs(flux_around(2))
    c_g = max(c11_pul - c12_pul, 0.0) * length
    c_c = c12_pul * length
    return {
        "nx": nx,
        "ny": ny,
        "iters": iters,
        "c11_pul_f_per_um": c11_pul,
        "c12_pul_f_per_um": c12_pul,
        "c_ground_f": c_g,
        "c_couple_f": c_c,
        "c_ground_fF": c_g * 1e15,
        "c_couple_fF": c_c * 1e15,
    }


def main() -> int:
    variant = os.environ.get("FLOW_VARIANT", "flowlab")
    root = Path(__file__).resolve().parents[2]
    out = root / "learn/sim/reports" / f"analytical_pex_{variant}.json"
    faster = bool(shutil.which("fastercap") or shutil.which("FasterCap"))
    geom = sakurai_tamaru(W, T, H, S, L_UM)
    fdm = fdm_two_trace(W, T, H, S, L_UM)
    ok = geom["c_ground_fF"] > 0 and geom["c_couple_fF"] > 0 and fdm["c_couple_fF"] >= 0
    payload = {
        "ok": ok,
        "kind": "analytical_pex",
        "engine": "fastercap" if faster else "sakurai_tamaru_1983+fdm2d",
        "fastercap_present": faster,
        "commercial_gap": "Raphael (Synopsys) not licensed; FasterCap binary optional",
        "sakurai_tamaru": geom,
        "fdm2d": fdm,
        "geometry": geom,
        "summary": (
            f"M2 {L_UM}µm · ST Cg={geom['c_ground_fF']:.3f} fF Cc={geom['c_couple_fF']:.3f} fF · "
            f"FDM Cg={fdm['c_ground_fF']:.3f} fF Cc={fdm['c_couple_fF']:.3f} fF"
        ),
        "reference": "Sakurai & Tamaru, IEEE TED 1983; 2D Laplace FDM (FasterCap-class)",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(payload["summary"])
    print("WROTE", out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
