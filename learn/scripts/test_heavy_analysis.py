#!/usr/bin/env python3
"""Guards: AES / large-mesh analysis stays opt-in; RSS budget even when opted in."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from heavy_analysis import (  # noqa: E402
    AES_F4_N_NODES,
    AES_F4_N_R,
    HEAVY_MESH_R,
    check_krylov,
    check_large_mesh,
    check_rss_budget,
    heavy_allowed,
    pick_bounded_solver,
    refusal_for_heavy,
    resolve_solve_timeout_s,
)


def check(ok: bool, msg: str) -> None:
    print(("OK  " if ok else "FAIL ") + msg)
    if not ok:
        raise SystemExit(1)


def main() -> int:
    os.environ.pop("ALLOW_HEAVY_ANALYSIS", None)
    os.environ.pop("ALLOW_OOM_ANALYSIS", None)
    os.environ.pop("PDN_SOLVE_TIMEOUT_S", None)
    os.environ.pop("PDN_FAKE_RAM_BYTES", None)
    check(not heavy_allowed(), "default disallows heavy analysis")
    check(check_large_mesh(1000) is None, "GCD-sized mesh 1000 R allowed")
    check(check_large_mesh(HEAVY_MESH_R) is None, f"mesh == {HEAVY_MESH_R} allowed")
    msg = check_large_mesh(73_000)
    check(msg is not None and "73000" in msg, "AES 73k-R mesh refused without flag")
    check(check_krylov(73_000, "krylov") is not None, "Krylov on 73k refused")
    check(check_krylov(1000, "direct") is None, "DirectLU on small mesh allowed")
    os.environ["ALLOW_HEAVY_ANALYSIS"] = "1"
    check(heavy_allowed(), "flag enables heavy analysis")
    check(check_large_mesh(73_000) is None, "73k allowed when opted in")
    check("ALLOW_HEAVY_ANALYSIS=1" in refusal_for_heavy("x"), "refusal names the flag")

    check(resolve_solve_timeout_s(90.0) == 90.0, "timeout default 90")
    os.environ["PDN_SOLVE_TIMEOUT_S"] = "1800"
    check(resolve_solve_timeout_s(90.0) == 1800.0, "PDN_SOLVE_TIMEOUT_S raises timeout")
    os.environ.pop("PDN_SOLVE_TIMEOUT_S", None)

    os.environ["PDN_FAKE_RAM_BYTES"] = str(15 * (1 << 30))
    kry = check_rss_budget(n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver="krylov")
    check(kry is not None and "estimated RSS" in kry, "AES Krylov refused on 15 GiB RSS budget")
    amg = check_rss_budget(n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver="amg")
    check(amg is None, "AES AMG estimated RSS fits 40% of 15 GiB")
    direct = check_rss_budget(n_r=1000, n_nodes=800, solver="direct")
    check(direct is None, "GCD DirectLU fits")
    kind, why = pick_bounded_solver(AES_F4_N_R, n_nodes=AES_F4_N_NODES)
    check(kind == "direct", f"AES on 15 GiB picks DirectLU not Krylov (got {kind} {why})")
    os.environ["PDN_FAKE_RAM_BYTES"] = str(64 * (1 << 30))
    kind64, why64 = pick_bounded_solver(AES_F4_N_R, n_nodes=AES_F4_N_NODES)
    check(kind64 == "direct", f"AES on 64 GiB still prefers DirectLU (got {kind64} {why64})")
    os.environ["PDN_FAKE_RAM_BYTES"] = str(400 * (1 << 20))
    kind_tiny, why_tiny = pick_bounded_solver(AES_F4_N_R, n_nodes=AES_F4_N_NODES)
    check(kind_tiny is None, f"AES on 400 MiB has no bounded solver (got {kind_tiny} {why_tiny})")
    os.environ["PDN_FAKE_RAM_BYTES"] = str(15 * (1 << 30))
    os.environ["ALLOW_OOM_ANALYSIS"] = "1"
    check(
        check_rss_budget(n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, solver="krylov") is None,
        "ALLOW_OOM_ANALYSIS bypasses RSS budget",
    )
    print("HEAVY_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
