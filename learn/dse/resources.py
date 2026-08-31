"""Single DSE resource gate. Wraps heavy_analysis; does not duplicate estimates.

Callers that know ``n_r`` must go through ``admit_solve`` before launching
F4. AES Krylov on a 15 GiB VM is refused here, not after thrash.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from heavy_analysis import (  # noqa: E402
    check_krylov,
    check_large_mesh,
    check_rss_budget,
    estimate_solve_rss_bytes,
    pick_bounded_solver,
)


def admit_solve(
    n_r: int | None = None,
    *,
    n_nodes: int | None = None,
    solver: str | None = None,
    device: str = "cpu",
) -> dict:
    """Admit or refuse an F4 solve. Never labels a CPU run as CUDA.

    Returns a dict the controller can store on ``artifacts`` / ``SolveResult``:
    admitted, solver, status, reason, backend_requested, backend_actual,
    fallback_reason, estimated_rss_mib.
    """
    requested = str(device or "cpu")
    out = {
        "admitted": False,
        "solver": solver,
        "status": "REFUSED",
        "reason": None,
        "backend_requested": requested,
        "backend_actual": "cpu",
        "fallback_reason": None,
        "estimated_rss_mib": None,
        "via": "dse.resources.admit_solve",
    }
    if requested == "cuda":
        from .f4_oracle import solver_devices

        if not solver_devices().get("cuda"):
            out["status"] = "GAP"
            out["fallback_reason"] = "no CUDA device — not claiming a GPU solve, not gold"
            out["reason"] = out["fallback_reason"]
            return out
        out["backend_actual"] = "cuda"

    est = estimate_solve_rss_bytes(n_r=n_r, n_nodes=n_nodes, solver=solver)
    out["estimated_rss_mib"] = round(est / (1 << 20), 1) if est else 0.0

    if solver:
        if ("krylov" in str(solver).lower() or solver == "mor") and not n_r:
            out["reason"] = "REFUSED: Krylov without n_r — admit_solve requires mesh size"
            return out
        mesh_msg = check_krylov(n_r, solver) if "krylov" in str(solver).lower() or solver == "mor" else (
            check_large_mesh(n_r, kind=solver) if n_r else None
        )
        rss_msg = check_rss_budget(n_r=n_r, n_nodes=n_nodes, solver=solver)
        if mesh_msg or rss_msg:
            out["reason"] = rss_msg or mesh_msg
            return out
        out["admitted"] = True
        out["status"] = "ok"
        out["solver"] = solver
        return out

    if not n_r:
        out["admitted"] = True
        out["status"] = "ok"
        out["solver"] = "direct"
        out["reason"] = "no mesh size — DirectLU default, caller must re-admit with n_r"
        return out

    kind, why = pick_bounded_solver(int(n_r), n_nodes=n_nodes)
    if kind is None:
        out["reason"] = why
        return out
    out["admitted"] = True
    out["status"] = "ok"
    out["solver"] = kind
    if solver and kind != solver:
        out["fallback_reason"] = why or f"requested {solver}, admitted {kind}"
    return out
