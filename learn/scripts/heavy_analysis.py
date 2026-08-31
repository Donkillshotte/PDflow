"""Guards that keep Cloud Agent setup off AES / 73k-R Krylov work.

A prior setup session expired after a Krylov MOR solve on an AES ~73k-R
mesh thrashed the VM. Setup and default E2E must never enter that path.
"""

from __future__ import annotations

import os
import sys

# AES candidate extract that crashed a Cloud Agent was ~73k resistors.
# GCD finish meshes stay well below this; refuse anything larger unless opted in.
HEAVY_MESH_R = 20_000


def heavy_allowed() -> bool:
    return os.environ.get("ALLOW_HEAVY_ANALYSIS") == "1"


def refusal_for_heavy(reason: str) -> str:
    return (
        f"REFUSED: {reason}. "
        "Set ALLOW_HEAVY_ANALYSIS=1 to run this "
        "(not part of Cloud Agent setup or the GCD E2E)."
    )


def check_large_mesh(n_r: int | None, *, kind: str = "PDN mesh") -> str | None:
    """Return a refusal message, or None if the mesh is allowed."""
    if n_r is None:
        return None
    n = int(n_r)
    if n > HEAVY_MESH_R and not heavy_allowed():
        return refusal_for_heavy(f"{kind} n_r={n} > {HEAVY_MESH_R}")
    return None


def check_krylov(n_r: int | None, solver: str | None) -> str | None:
    name = (solver or "").lower()
    if name not in ("krylov", "mor") and "krylov" not in name:
        return None
    return check_large_mesh(n_r, kind=f"Krylov/MOR solver on mesh")


def refuse(reason: str, *, code: int = 2) -> None:
    print(reason, file=sys.stderr)
    raise SystemExit(code)


def require_heavy(reason: str = "heavy PDN/AES/DSE analysis") -> None:
    if not heavy_allowed():
        refuse(refusal_for_heavy(reason))


def refuse_large_mesh(n_r: int | None, *, kind: str = "PDN mesh") -> None:
    msg = check_large_mesh(n_r, kind=kind)
    if msg:
        refuse(msg)


def refuse_krylov(n_r: int | None, solver: str | None) -> None:
    msg = check_krylov(n_r, solver)
    if msg:
        refuse(msg)
