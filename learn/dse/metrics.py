"""Multi-objective QoR. Missing metrics do not dominate. Never a forced scalar.

``area_um2`` is mapped standard-cell instance area (Yosys ``stat -liberty`` /
OpenROAD instance area), not die/core area. ``power_w`` is OpenSTA Total.
Leakage is a first-class axis; internal/switching stay observation-only so
four correlated power columns do not explode the Pareto front.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Iterable


# Lower is better for every field. WNS/TNS are stored as -slack so a larger slack wins.
MINIMIZE = (
    "area_um2",  # stdcell / mapped instance area, µm²
    "n_cells",
    "wns_cost",  # -WNS_ns; 0 slack → 0
    "tns_cost",  # -TNS_ns; 0 total slack → 0
    "power_w",  # OpenSTA Total (internal+switching+leakage)
    "leakage_w",
    "congestion",
    "hpwl_um",  # OpenROAD HPWL in µm — not F2-fast grid units
    "static_ir_mv",
    "dynamic_ir_mv",
    "em_j_a_m2",
    "ttf_rel_inv",  # 1/ttf_rel so smaller TTF is worse
)


@dataclass
class QoR:
    area_um2: float | None = None
    n_cells: float | None = None
    wns_cost: float | None = None
    tns_cost: float | None = None
    power_w: float | None = None
    leakage_w: float | None = None
    internal_power_w: float | None = None  # observation; not MINIMIZE
    switching_power_w: float | None = None  # observation; not MINIMIZE
    congestion: float | None = None
    hpwl_um: float | None = None
    wirelength_um: float | None = None  # GRT total WL; observation
    core_util: float | None = None  # instance utilization 0–1 when measured
    static_ir_mv: float | None = None
    dynamic_ir_mv: float | None = None
    em_j_a_m2: float | None = None
    ttf_rel_inv: float | None = None
    fidelity: str = "F0"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "QoR":
        d = d or {}
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


def wns_cost_from_slack_ns(slack_ns: float | None) -> float | None:
    if slack_ns is None:
        return None
    return -float(slack_ns)


def tns_cost_from_tns_ns(tns_ns: float | None) -> float | None:
    """TNS is typically ≤ 0. Worse (more negative) TNS → higher cost."""
    if tns_ns is None:
        return None
    return -float(tns_ns)


def merge_sta_into_qor(q: QoR, blob: dict | None) -> QoR:
    """Stamp WNS/TNS/power split from an OpenSTA or GRT report dict.

    Missing keys stay None. Does not invent leakage from Total.
    """
    blob = blob or {}
    if blob.get("wns_ns") is not None:
        q.wns_cost = wns_cost_from_slack_ns(blob.get("wns_ns"))
    if blob.get("tns_ns") is not None:
        q.tns_cost = tns_cost_from_tns_ns(blob.get("tns_ns"))
    for name in (
        "power_w",
        "leakage_w",
        "internal_power_w",
        "switching_power_w",
        "hpwl_um",
        "wirelength_um",
        "core_util",
    ):
        if blob.get(name) is not None:
            setattr(q, name, float(blob[name]))
    if q.wirelength_um is None and blob.get("grt_wl") is not None:
        q.wirelength_um = float(blob["grt_wl"])
    return q


def enrich_parent_qor_from(parent: QoR, child: QoR) -> None:
    """Copy STA axes onto the F1/F2 parent after a successful F3/F5 child."""
    for name in (
        "wns_cost",
        "tns_cost",
        "power_w",
        "leakage_w",
        "internal_power_w",
        "switching_power_w",
    ):
        v = getattr(child, name)
        if v is not None:
            setattr(parent, name, v)


def inherit_parent_pd(q: QoR, parent: QoR) -> QoR:
    """Fill unset PD axes from the parent. Does not overwrite a measured child value."""
    for name in (
        "area_um2",
        "n_cells",
        "wns_cost",
        "tns_cost",
        "power_w",
        "leakage_w",
        "internal_power_w",
        "switching_power_w",
        "hpwl_um",
        "wirelength_um",
        "core_util",
    ):
        if getattr(q, name) is None:
            setattr(q, name, getattr(parent, name))
    return q


def core_util_from_report(raw: Any) -> float | None:
    """ORFS utilization is 0–1 or percent. Store 0–1. None if missing."""
    if raw is None:
        return None
    x = float(raw)
    if x > 1.5:
        x = x / 100.0
    if x < 0.0:
        return None
    return x


def qor_delta(child: QoR, parent: QoR | None) -> dict[str, float]:
    """Signed child − parent on axes both observed. Missing ≠ 0.

    Lower-is-better axes: a negative ``dynamic_ir_mv`` is an IR improvement.
    Axes where either side is None are omitted so a later reader cannot
    confuse “not measured” with “no change”.
    """
    if parent is None:
        return {}
    out: dict[str, float] = {}
    for name in MINIMIZE:
        vc, vp = getattr(child, name), getattr(parent, name)
        if vc is None or vp is None:
            continue
        out[name] = float(vc) - float(vp)
    return out


def baseline_delta_of(attr: dict | None) -> dict:
    """QoR vs liberty_default stored on ``Candidate.attr``.

    New rows use ``delta_vs_baseline``. Historical JSONL used ``delta``
    for the same payload. ``Candidate.delta`` is a different field (vs parent)
    and is never read here.
    """
    a = attr or {}
    payload = a.get("delta_vs_baseline")
    if payload is None:
        payload = a.get("delta")
    return dict(payload) if isinstance(payload, dict) else {}


FIDELITY_RANK = {"F0": 0, "F1": 1, "F2": 2, "F3": 3, "F4": 4, "F5": 5}
# Timing/power: a lower-fidelity point cannot dominate a higher-fidelity point.
# Area / congestion / IR / HPWL stay comparable as in ``dominates``.
TIMING_POWER = ("wns_cost", "tns_cost", "power_w", "leakage_w")


def _rank(q: QoR) -> int:
    return int(FIDELITY_RANK.get(str(q.fidelity or "F0"), 0))


def dominates_with_fidelity(a: QoR, b: QoR) -> bool:
    """Like ``dominates``, but timing/power from a cheaper model is untrusted.

    A lower-fidelity point cannot dominate a higher-fidelity point on
    ``wns_cost`` / ``tns_cost`` / ``power_w`` / ``leakage_w`` — those axes
    co-exist as ``uncertain``.
    Area and other non-timing axes stay comparable. At equal observed
    axes, the higher-fidelity point dominates (F5 at parity beats F1).
    ``pred`` is never consulted here.
    """
    ra, rb = _rank(a), _rank(b)
    better = False
    compared = 0
    equal = True
    for name in MINIMIZE:
        va, vb = getattr(a, name), getattr(b, name)
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        compared += 1
        if float(va) > float(vb) + 1e-15:
            return False
        if float(va) < float(vb) - 1e-15:
            if name in TIMING_POWER and ra < rb:
                # Untrusted improvement — co-exist, do not count as better.
                equal = False
                continue
            better = True
            equal = False
        elif abs(float(va) - float(vb)) > 1e-15:
            equal = False
    if better and compared > 0:
        return True
    if compared > 0 and equal and ra > rb:
        return True
    return False


def pareto_front_gated(
    items: Iterable[tuple[str, QoR]],
    pred: dict[str, float] | None = None,
) -> list[str]:
    """Non-dominated ids under ``dominates_with_fidelity``.

    ``pred`` (surrogate) is a tie-break only: lower predicted cost first
    among points that already co-exist. It never changes membership.
    """
    rows = [(i, q) for i, q in items if q is not None]
    keep: list[str] = []
    for i, qi in rows:
        if any(dominates_with_fidelity(qj, qi) for j, qj in rows if j != i):
            continue
        keep.append(i)
    if pred:
        keep.sort(key=lambda i: (pred.get(i) is None, float(pred[i]) if pred.get(i) is not None else 0.0))
    return keep


def dominates(a: QoR, b: QoR) -> bool:
    """a dominates b iff a is ≤ on all comparable axes and < on at least one.

    Axes where either value is None are skipped. Two points that share no
    comparable axis do not dominate each other.
    """
    better = False
    compared = 0
    for name in MINIMIZE:
        va, vb = getattr(a, name), getattr(b, name)
        if va is None and vb is None:
            continue
        # Incomplete observation: F4 IR-only must not dominate an F2 point
        # that also carries area/congestion. Missing ≠ better.
        if va is None or vb is None:
            return False
        compared += 1
        if float(va) > float(vb) + 1e-15:
            return False
        if float(va) < float(vb) - 1e-15:
            better = True
    return better and compared > 0


def pareto_front(items: Iterable[tuple[str, QoR]]) -> list[str]:
    """Return ids that are not dominated by any other id."""
    rows = [(i, q) for i, q in items if q is not None]
    keep: list[str] = []
    for i, qi in rows:
        if any(dominates(qj, qi) for j, qj in rows if j != i):
            continue
        keep.append(i)
    return keep
