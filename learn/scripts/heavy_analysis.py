"""Guards that keep Cloud Agent setup off AES / 73k-R Krylov work.

A prior setup session expired after a Krylov MOR solve on an AES ~73k-R
mesh thrashed the VM. Setup and default E2E must never enter that path.

Timeouts can be raised via PDN_SOLVE_TIMEOUT_S. Cloud Agent VM RAM cannot:
the environment.json schema has no memory/cpu fields, and this pod is a
fixed ~15 GiB profile. Raising the solver timeout without an RSS budget
is how the previous session died (AMG 180s → Krylov thrash).
"""

from __future__ import annotations

import os
import sys

# AES candidate extract that crashed a Cloud Agent was ~73k resistors.
# GCD finish meshes stay well below this; refuse anything larger unless opted in.
HEAVY_MESH_R = 20_000

# Empirically, AES F4 Krylov on n_nodes=54241 exhausted a 15 GiB Cloud Agent.
# Bytes/node includes MOR dense blocks + fill-in, not just the sparse CSR.
KRYLOV_BYTES_PER_NODE = 280_000
AMG_BYTES_PER_NODE = 80_000
DIRECT_BYTES_PER_NODE = 16_000
# Leave headroom so `cat` still works; the prior crash made even that time out.
RSS_FRACTION = 0.40
AES_F4_N_R = 73_139
AES_F4_N_NODES = 54_241


def heavy_allowed() -> bool:
    return os.environ.get("ALLOW_HEAVY_ANALYSIS") == "1"


def oom_allowed() -> bool:
    """Bypass the RSS budget. Do not set this on a 15 GiB Cloud Agent."""
    return os.environ.get("ALLOW_OOM_ANALYSIS") == "1"


def refusal_for_heavy(reason: str) -> str:
    return (
        f"REFUSED: {reason}. "
        "Set ALLOW_HEAVY_ANALYSIS=1 to run this "
        "(not part of Cloud Agent setup or the GCD E2E)."
    )


def resolve_solve_timeout_s(requested: float = 90.0) -> float:
    """F4 worker wall-clock. PDN_SOLVE_TIMEOUT_S overrides when set."""
    raw = os.environ.get("PDN_SOLVE_TIMEOUT_S")
    if raw is not None and str(raw).strip() != "":
        return float(raw)
    return float(requested)


def available_ram_bytes() -> int:
    fake = os.environ.get("PDN_FAKE_RAM_BYTES")
    if fake is not None and str(fake).strip() != "":
        return int(fake)
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) * 1024
        return total
    except OSError:
        return 0


def estimate_solve_rss_bytes(
    n_r: int | None = None,
    n_nodes: int | None = None,
    solver: str | None = None,
) -> int:
    n = int(n_nodes) if n_nodes else int(round(int(n_r or 0) * 0.74))
    if n <= 0:
        return 0
    name = (solver or "direct").lower()
    if name in ("krylov", "mor") or "krylov" in name:
        per = KRYLOV_BYTES_PER_NODE
    elif name in ("amg", "b", "b_sa_amg") or name.endswith("amg"):
        per = AMG_BYTES_PER_NODE
    else:
        per = DIRECT_BYTES_PER_NODE
    return n * per


def check_rss_budget(
    n_r: int | None = None,
    n_nodes: int | None = None,
    solver: str | None = None,
) -> str | None:
    """Refuse a solve that is predicted to thrash this VM.

    Independent of ALLOW_HEAVY_ANALYSIS: that flag opts into AES, not into OOM.
    Set ALLOW_OOM_ANALYSIS=1 only on a machine with enough RAM.
    """
    if oom_allowed():
        return None
    est = estimate_solve_rss_bytes(n_r=n_r, n_nodes=n_nodes, solver=solver)
    if est <= 0:
        return None
    avail = available_ram_bytes()
    budget = int(avail * RSS_FRACTION)
    if budget <= 0:
        return None
    if est > budget:
        name = solver or "direct"
        return (
            f"REFUSED: {name} on n_r={n_r} n_nodes={n_nodes} "
            f"estimated RSS {est / (1 << 20):.0f} MiB > "
            f"{100 * RSS_FRACTION:.0f}% of available RAM "
            f"({avail / (1 << 20):.0f} MiB). "
            "Cloud Agent VM RAM is not configurable via environment.json. "
            "Set ALLOW_OOM_ANALYSIS=1 only on a larger machine — "
            "raising PDN_SOLVE_TIMEOUT_S on 15 GiB will thrash, not finish."
        )
    return None


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
    return check_large_mesh(n_r, kind="Krylov/MOR solver on mesh")


def pick_bounded_solver(
    n_r: int,
    *,
    n_nodes: int | None = None,
    max_r_direct: int = 40_000,
) -> tuple[str | None, str | None]:
    """Choose a solver that fits this VM's RSS. None means static-only.

    DirectLU is preferred even above ``max_r_direct`` when the RSS budget
    fits. A 54k-node 2D grid factored in 0.36s / 164 MiB on this Cloud Agent;
    the previous crash was Krylov MOR, not LU. ``max_r_direct`` only skips
    straight to AMG/Krylov when DirectLU itself is predicted to OOM.
    """
    if not n_r:
        return None, "no mesh"
    last = "no bounded solver"
    order = ("direct", "amg", "krylov")
    if n_r <= max_r_direct:
        order = ("direct",)
    for kind in order:
        mesh_msg = None
        if kind == "krylov":
            mesh_msg = check_krylov(n_r, kind)
        elif n_r > HEAVY_MESH_R:
            mesh_msg = check_large_mesh(n_r, kind=kind)
        rss_msg = check_rss_budget(n_r=n_r, n_nodes=n_nodes, solver=kind)
        if mesh_msg is None and rss_msg is None:
            return kind, None
        last = rss_msg or mesh_msg
    return None, last


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


def refuse_rss(
    n_r: int | None = None,
    n_nodes: int | None = None,
    solver: str | None = None,
) -> None:
    msg = check_rss_budget(n_r=n_r, n_nodes=n_nodes, solver=solver)
    if msg:
        refuse(msg)
