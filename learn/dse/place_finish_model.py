"""Place → finish residual. Never a finish substitute.

Calibrated on the GCD bake-off A/B/C place-DP vs 6_report WNS:
A +12.3 ps → −37.2 ps (Δ −49.5 ps), B −313.6 → −338.3 (Δ −24.7),
C −116.7 → −186.9 (Δ −70.2). Default residual is conservative (−50 ps)
with uncertainty growing when place is already negative.
"""

from __future__ import annotations

from dataclasses import dataclass

from .feasibility import _wns_ns
from .memory import Candidate

DEFAULT_RESIDUAL_NS = -0.050
DEFAULT_SIGMA_NS = 0.040


@dataclass
class FinishWnsPred:
    mu_ns: float | None
    sigma_ns: float
    p_close: float
    information: float
    source: str

    def to_dict(self) -> dict:
        return {
            "mu_ns": self.mu_ns,
            "sigma_ns": self.sigma_ns,
            "p_close": self.p_close,
            "information": self.information,
            "source": self.source,
        }


def _phi(z: float) -> float:
    """Standard-normal CDF via tanh approximation (no scipy)."""
    return 0.5 * (1.0 + tanh_approx(z / 1.41421356237))


def tanh_approx(x: float) -> float:
    # rational tanh; good enough for ranking, not a paper CDF
    if x < -20:
        return -1.0
    if x > 20:
        return 1.0
    e = pow(2.718281828459045, 2.0 * x)
    return (e - 1.0) / (e + 1.0)


def predict_finish_wns(c: Candidate) -> FinishWnsPred:
    art = c.artifacts or {}
    place = art.get("place_wns_ns")
    src = "place"
    if place is None:
        wns, wsrc = _wns_ns(c)
        if wsrc in ("place", "floorplan", "route", "finish") and wns is not None:
            place, src = wns, wsrc
        else:
            return FinishWnsPred(None, 1.0, 0.0, 0.0, "none")
    place = float(place)
    residual = DEFAULT_RESIDUAL_NS
    sigma = DEFAULT_SIGMA_NS
    if place < 0:
        sigma = DEFAULT_SIGMA_NS + 0.08 * abs(place)
    mu = place + residual
    if src == "finish":
        mu, sigma, src = place, 0.005, "finish"
    # P(finish WNS >= 0) ≈ Φ(-mu/sigma) if mu is predicted WNS (positive is closed)
    p_close = float(_phi((mu - 0.0) / max(sigma, 1e-6)))
    info = 1.0 / max(sigma, 1e-6)
    return FinishWnsPred(mu_ns=mu, sigma_ns=sigma, p_close=p_close, information=info, source=src)
