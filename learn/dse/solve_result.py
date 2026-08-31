"""Standard F4 solver observation. Not a new DesignState.

DirectLU (A) is the numerical reference. AMG/RAS/Krylov are accelerators
and must carry ``abs_err_vs_reference_mv`` when A is known. Never treat a
fast solver as truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .fingerprint import sha256_file

ACTIVITY_REAL = "REAL"
ACTIVITY_PARTIAL = "PARTIAL"
ACTIVITY_SYNTHETIC = "SYNTHETIC"
ACTIVITY_ABSENT = "ABSENT"

_REFERENCE_SOLVERS = ("direct", "a_direct_be", "a")


def solver_role(solver: str | None, solver_kind: str | None = None) -> str:
    blob = f"{solver or ''} {solver_kind or ''}".lower().strip()
    if not blob:
        return "accelerator"
    if "krylov" in blob or blob.strip() in ("c",) or "rational_krylov" in blob:
        return "accelerator"
    if "amg" in blob or blob.strip() in ("b",):
        return "accelerator"
    if "ras" in blob or "schwarz" in blob or blob.strip() in ("d",):
        return "accelerator"
    kind = (solver_kind or solver or "direct").lower()
    if kind in _REFERENCE_SOLVERS or kind.startswith("a_"):
        return "reference"
    return "accelerator"


def activity_status_of(
    t50_via: dict | None = None,
    *,
    n_saif_idle: int = 0,
    n_vcd_join: int = 0,
    n_sta: int = 0,
) -> str:
    """REAL measured join, SYNTHETIC fallback, PARTIAL mix, ABSENT none.

    STA arrivals are measurements, not an invented RTL→ITerm remap.
    VCD/SAIF count only when name-joined. Idle-zeroed SAIF is PARTIAL.
    """
    t50 = t50_via or {}
    syn = int(t50.get("synthetic") or 0)
    sta = int(t50.get("sta_arrival") or n_sta or 0)
    vcd = int(t50.get("vcd_name_join") or n_vcd_join or 0)
    saif = int(t50.get("saif") or 0)
    idle = int(n_saif_idle or 0)
    total = syn + sta + vcd + saif
    if total == 0 and idle == 0:
        return ACTIVITY_ABSENT
    if idle and (sta or vcd or syn or saif):
        return ACTIVITY_PARTIAL
    if syn and (sta or vcd or saif):
        return ACTIVITY_PARTIAL
    if syn and not sta and not vcd and not saif:
        return ACTIVITY_SYNTHETIC
    return ACTIVITY_REAL


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _droop_mv(payload: dict) -> float | None:
    if payload.get("worst_droop_mv") is not None:
        return _f(payload.get("worst_droop_mv"))
    droop = payload.get("worst_droop")
    if droop is None:
        return None
    x = float(droop)
    # volts (GCD reports) vs already-mV
    return x * 1e3 if abs(x) < 1.5 else x


@dataclass
class SolveResult:
    status: str = "fail"
    solver_kind: str | None = None
    solver: str | None = None
    role: str = "accelerator"
    droop_mv: float | None = None
    static_ir_mv: float | None = None
    residual_norm: float | None = None
    abs_err_vs_reference_mv: float | None = None
    relative_error: float | None = None
    runtime_s: float | None = None
    peak_rss_mib: float | None = None
    timesteps: int | None = None
    m: int | None = None
    n_r: int | None = None
    n_i: int | None = None
    backend_requested: str = "cpu"
    backend_actual: str | None = None
    fallback_reason: str | None = None
    activity_status: str = ACTIVITY_ABSENT
    activity_via: dict = field(default_factory=dict)
    convergence_status: str | None = None
    gold: bool = False
    gold_ref_mv: float | None = 45.298
    extract: str | None = None
    mesh_fp: str | None = None
    via: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "SolveResult":
        d = d or {}
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


def normalize_solve(
    payload: dict | None,
    *,
    reference_droop_mv: float | None = None,
    backend_requested: str = "cpu",
    fallback_reason: str | None = None,
) -> SolveResult:
    """Lift a worker / report blob into SolveResult. Extra keys stay on the blob."""
    p = dict(payload or {})
    status = str(p.get("status") or ("ok" if p.get("ok") else "fail"))
    if status in ("True", "true"):
        status = "ok"
    solver_raw = p.get("solver") if p.get("solver") not in (None, "") else None
    kind = str(p.get("solver_kind") or p.get("kind") or "")
    solver_s = str(solver_raw or "")
    if not kind:
        low = solver_s.lower()
        if "krylov" in low:
            kind = "krylov"
        elif "amg" in low:
            kind = "amg"
        elif "ras" in low or "schwarz" in low:
            kind = "ras"
        elif solver_s or status == "ok":
            kind = "direct"
        else:
            kind = None
    solver = solver_s or kind
    droop = _droop_mv(p)
    err = _f(p.get("abs_err_vs_A_mv") if p.get("abs_err_vs_A_mv") is not None else p.get("abs_err_vs_reference_mv"))
    if err is None and reference_droop_mv is not None and droop is not None:
        err = abs(float(droop) - float(reference_droop_mv))
    rel = _f(p.get("relative_error"))
    if rel is None and err is not None and reference_droop_mv not in (None, 0):
        rel = abs(err) / abs(float(reference_droop_mv))
    t50 = p.get("t50_via") if isinstance(p.get("t50_via"), dict) else None
    act = p.get("activity_model") if isinstance(p.get("activity_model"), dict) else {}
    if t50 is None and isinstance(act.get("t50_via"), dict):
        t50 = act.get("t50_via")
    rss = _f(p.get("peak_rss_mib") if p.get("peak_rss_mib") is not None else p.get("parent_rss_mib"))
    spice = p.get("spice")
    mesh_fp = p.get("mesh_fp")
    if not mesh_fp and spice:
        mesh_fp = sha256_file(Path(str(spice)))
    actual = p.get("backend") or p.get("backend_actual") or p.get("device")
    conv = p.get("convergence_status")
    if conv is None and p.get("rel_res_max") is not None:
        conv = "ok" if status == "ok" else status
    return SolveResult(
        status=status,
        solver_kind=kind,
        solver=solver,
        role=solver_role(solver, kind),
        droop_mv=droop,
        static_ir_mv=_f(p.get("static_ir_mv")),
        residual_norm=_f(p.get("rel_res_max") if p.get("rel_res_max") is not None else p.get("rel_res")),
        abs_err_vs_reference_mv=err,
        relative_error=rel,
        runtime_s=_f(p.get("cost_s") if p.get("cost_s") is not None else p.get("setup_s")),
        peak_rss_mib=rss,
        timesteps=int(p["steps"]) if p.get("steps") is not None else None,
        m=int(p["m"]) if p.get("m") is not None else None,
        n_r=int(p["n_r"]) if p.get("n_r") is not None else None,
        n_i=int(p["n_i"]) if p.get("n_i") is not None else None,
        backend_requested=str(backend_requested or "cpu"),
        backend_actual=None if actual is None else str(actual),
        fallback_reason=fallback_reason or p.get("fallback_reason") or p.get("reason"),
        activity_status=activity_status_of(
            t50,
            n_saif_idle=int(p.get("n_saif_idle") or 0),
            n_vcd_join=int(p.get("n_vcd_join") or 0),
            n_sta=int(p.get("n_sta_applied") or 0),
        ),
        activity_via=dict(t50 or {}),
        convergence_status=None if conv is None else str(conv),
        gold=bool(p.get("gold") or False),
        gold_ref_mv=_f(p.get("gold_ref_mv")) if p.get("gold_ref_mv") is not None else 45.298,
        extract=None if p.get("extract") is None else str(p.get("extract")),
        mesh_fp=mesh_fp,
        via=None if p.get("via") is None else str(p.get("via")),
        reason=None if p.get("reason") is None else str(p.get("reason")),
    )


def from_dynamic_ir_report(report: dict) -> list[SolveResult]:
    """Normalize Solver A plus any B/C/D blocks. Does not launch a solve."""
    dyn = report.get("dynamic") if isinstance(report.get("dynamic"), dict) else {}
    activity = report.get("activity_model") if isinstance(report.get("activity_model"), dict) else {}
    em = report.get("em") if isinstance(report.get("em"), dict) else {}
    a_payload = {
        "status": "ok" if report.get("ok") and dyn else ("ok" if dyn.get("solver") else "fail"),
        "ok": bool(dyn),
        "solver": dyn.get("solver") or "A_direct_be",
        "solver_kind": "direct",
        "worst_droop": dyn.get("worst_droop"),
        "static_ir_mv": (report.get("static") or {}).get("worst_ir"),
        "rel_res_max": dyn.get("rel_res_max"),
        "backend": dyn.get("backend"),
        "steps": dyn.get("steps"),
        "n_r": em.get("n_branches"),
        "n_i": (report.get("static") or {}).get("loads"),
        "t50_via": activity.get("t50_via"),
        "cost_s": dyn.get("solver_step_s"),
        "extract": "finish",
        "gold": False,
        "via": dyn.get("solver"),
    }
    if a_payload.get("static_ir_mv") is not None:
        ir = float(a_payload["static_ir_mv"])
        a_payload["static_ir_mv"] = ir * 1e3 if abs(ir) < 1.5 else ir
    rows = [normalize_solve(a_payload)]
    a_droop = rows[0].droop_mv
    mapping = (("solver_b", "amg"), ("solver_c", "krylov"), ("solver_d", "ras"))
    for key, kind in mapping:
        block = report.get(key)
        if not isinstance(block, dict) or not (block.get("ok") or block.get("status") == "ok"):
            continue
        blob = dict(block)
        blob.setdefault("solver_kind", kind)
        blob.setdefault("status", "ok")
        rows.append(normalize_solve(blob, reference_droop_mv=a_droop))
    return rows
