"""I(t) scenario for F4. The solver does not know where current came from.

Triangle is the default shape. STA t50 / VCD / SAIF are named sources.
Missing waveforms stay ABSENT — never invented. CCS on Nangate45 is GAP
(NLDM has no current tables).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .fingerprint import sha256_text

ACTIVITY_ABSENT = "ABSENT"
ACTIVITY_REAL = "REAL"
ACTIVITY_SYNTHETIC = "SYNTHETIC"

SOURCES = ("ideal_triangle", "sta_t50", "vcd", "saif", "liberty_ccs")
CCS_GAP = "CCS on Nangate45 is GAP (NLDM) — not inventing current tables"


@dataclass
class CurrentScenario:
    source: str = "ideal_triangle"
    activity_status: str = ACTIVITY_SYNTHETIC
    scale: float = 1.0
    period_ns: float = 0.46
    sta: str | None = None
    waveform: str | None = None
    gap: str | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        src = str(self.source or "ideal_triangle")
        if src not in SOURCES:
            raise ValueError(f"unknown current source {src!r} — not inventing I(t)")
        self.source = src
        self.scale = float(self.scale)
        self.period_ns = float(self.period_ns)
        if not self.fingerprint:
            self.fingerprint = _fingerprint(self)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "CurrentScenario":
        d = d or {}
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _fingerprint(scen: CurrentScenario) -> str:
    blob = {
        "source": scen.source,
        "activity_status": scen.activity_status,
        "scale": scen.scale,
        "period_ns": scen.period_ns,
        "sta": scen.sta,
        "waveform": scen.waveform,
        "gap": scen.gap,
    }
    return sha256_text(json.dumps(blob, sort_keys=True, separators=(",", ":")))


def _is_file(p: Path | str | None) -> bool:
    return bool(p) and Path(str(p)).is_file()


def infer_scenario(
    *,
    source: str | None = None,
    period_ns: float = 0.46,
    scale: float = 1.0,
    sta: Path | str | None = None,
    waveform: Path | str | None = None,
) -> CurrentScenario:
    """Name the I(t) source. Missing VCD/SAIF/STA stay ABSENT — never invented.

    ``source=None`` keeps today's finish path: STA file → ``sta_t50``, else
    the triangle default. Explicit ``sta_t50`` is the GCD finish SPEF t50 path.
    """
    sta_s = str(sta) if sta else None
    wave_s = str(waveform) if waveform else None
    src = source
    if src == "liberty_ccs":
        return CurrentScenario(
            source="liberty_ccs",
            activity_status=ACTIVITY_ABSENT,
            scale=scale,
            period_ns=period_ns,
            gap=CCS_GAP,
        )
    if src in ("vcd", "saif"):
        if not _is_file(waveform):
            return CurrentScenario(
                source=src,
                activity_status=ACTIVITY_ABSENT,
                scale=scale,
                period_ns=period_ns,
                waveform=wave_s,
            )
        return CurrentScenario(
            source=src,
            activity_status=ACTIVITY_REAL,
            scale=scale,
            period_ns=period_ns,
            waveform=wave_s,
        )
    if src == "sta_t50":
        if not _is_file(sta):
            return CurrentScenario(
                source="sta_t50",
                activity_status=ACTIVITY_ABSENT,
                scale=scale,
                period_ns=period_ns,
                sta=sta_s,
            )
        return CurrentScenario(
            source="sta_t50",
            activity_status=ACTIVITY_REAL,
            scale=scale,
            period_ns=period_ns,
            sta=sta_s,
        )
    if src == "ideal_triangle":
        return CurrentScenario(
            source="ideal_triangle",
            activity_status=ACTIVITY_SYNTHETIC,
            scale=scale,
            period_ns=period_ns,
        )
    # Default: do not invent a waveform. STA on disk is today's GCD finish.
    if _is_file(waveform):
        suf = Path(str(waveform)).suffix.lower()
        kind = "saif" if suf == ".saif" else "vcd"
        return CurrentScenario(
            source=kind,
            activity_status=ACTIVITY_REAL,
            scale=scale,
            period_ns=period_ns,
            waveform=wave_s,
            sta=sta_s if _is_file(sta) else None,
        )
    if _is_file(sta):
        return CurrentScenario(
            source="sta_t50",
            activity_status=ACTIVITY_REAL,
            scale=scale,
            period_ns=period_ns,
            sta=sta_s,
        )
    return CurrentScenario(
        source="ideal_triangle",
        activity_status=ACTIVITY_SYNTHETIC,
        scale=scale,
        period_ns=period_ns,
    )


def i_t_inputs(source: str | None, activity_status: str | None) -> str:
    """Which I(t) files the worker may load. ``source`` wins over leftover flags.

    ``none`` — synthetic triangle (or ABSENT / CCS). ``sta`` / ``vcd`` / ``saif``
    — that named source only. ``argv`` — no scenario; honor ``--sta/--vcd/--saif``.
    """
    src = source or ""
    if src == "ideal_triangle" or src == "liberty_ccs":
        return "none"
    if src == "sta_t50":
        return "none" if activity_status == ACTIVITY_ABSENT else "sta"
    if src in ("vcd", "saif"):
        return "none" if activity_status == ACTIVITY_ABSENT else src
    return "argv"


def parse_scenario_json(blob: str | None) -> CurrentScenario | None:
    if not blob:
        return None
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return CurrentScenario.from_dict(data)


def attach_scenario_via(activity_via: dict | None, scenario: Any) -> dict:
    """Point ``SolveResult.activity_via`` at the scenario without dropping t50 counts."""
    out = dict(activity_via or {})
    if scenario is None:
        return out
    if isinstance(scenario, CurrentScenario):
        out["scenario"] = scenario.to_dict()
    elif isinstance(scenario, dict):
        out["scenario"] = dict(scenario)
    return out
