"""TPE search space on the pinned official die. No Optuna import.

CORE_UTILIZATION / CORE_ASPECT_RATIO / DIE_AREA are never sampled.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .floorplan import official_box
from .knob_catalog import config_mk_for, parse_config_defaults, resolve_many
from .recipe_labels import synth_method_from_exploration

FORBIDDEN = frozenset(
    {
        "CORE_UTILIZATION",
        "CORE_ASPECT_RATIO",
        "DIE_AREA",
        "CORE_AREA",
        "SYNTH_HIERARCHICAL",
        "ABC_SPEED",
        "ABC_AREA",
    }
)
PAD_KEYS = (
    "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT",
    "CELL_PAD_IN_SITES_DETAIL_PLACEMENT",
)
PARAM_ORDER = (
    "PLACE_DENSITY_LB_ADDON",
    "cell_pad",
    "TNS_END_PERCENT",
    "SETUP_SLACK_MARGIN",
    "HOLD_SLACK_MARGIN",
    "CTS_BUF_DISTANCE",
    "GPL_TIMING_DRIVEN",
)


def defaults_for(design: str) -> dict[str, float]:
    return parse_config_defaults(config_mk_for(design))


def _f(defaults: dict[str, float], key: str, fallback: float) -> float:
    v = defaults.get(key)
    if v is None:
        return float(fallback)
    return float(v)


def pad_default(defaults: dict[str, float]) -> int:
    g = defaults.get(PAD_KEYS[0])
    if g is None:
        return 0
    return int(round(float(g)))


def bounds(defaults: dict[str, float]) -> dict[str, tuple[Any, ...]]:
    """Optuna-free ranges. Values are (kind, lo, hi) or (kind, choices)."""
    lb0 = _f(defaults, "PLACE_DENSITY_LB_ADDON", 0.20)
    return {
        "PLACE_DENSITY_LB_ADDON": ("float", max(0.0, lb0 - 0.10), min(0.99, lb0 + 0.10)),
        "cell_pad": ("int", 0, 2),
        "TNS_END_PERCENT": ("int", 0, 100),
        "SETUP_SLACK_MARGIN": ("float", 0.0, 0.08),
        "HOLD_SLACK_MARGIN": ("float", 0.0, 0.05),
        "CTS_BUF_DISTANCE": ("float", 80.0, 200.0),
        "GPL_TIMING_DRIVEN": ("cat", (0, 1)),
    }


def clamp_params(raw: dict[str, Any], defaults: dict[str, float]) -> dict[str, Any]:
    b = bounds(defaults)
    out: dict[str, Any] = {}
    lo, hi = b["PLACE_DENSITY_LB_ADDON"][1], b["PLACE_DENSITY_LB_ADDON"][2]
    lb = raw.get("PLACE_DENSITY_LB_ADDON", _f(defaults, "PLACE_DENSITY_LB_ADDON", 0.20))
    out["PLACE_DENSITY_LB_ADDON"] = min(hi, max(lo, float(lb)))
    pad = raw.get("cell_pad", pad_default(defaults))
    out["cell_pad"] = min(2, max(0, int(round(float(pad)))))
    tns = raw.get("TNS_END_PERCENT", _f(defaults, "TNS_END_PERCENT", 100.0))
    out["TNS_END_PERCENT"] = min(100, max(0, int(round(float(tns)))))
    out["SETUP_SLACK_MARGIN"] = min(0.08, max(0.0, float(raw.get("SETUP_SLACK_MARGIN", 0.0))))
    out["HOLD_SLACK_MARGIN"] = min(0.05, max(0.0, float(raw.get("HOLD_SLACK_MARGIN", 0.0))))
    cts0 = defaults.get("CTS_BUF_DISTANCE")
    cts = raw.get("CTS_BUF_DISTANCE", 100.0 if cts0 is None else cts0)
    out["CTS_BUF_DISTANCE"] = min(200.0, max(80.0, float(cts)))
    gpl = raw.get("GPL_TIMING_DRIVEN", 1)
    out["GPL_TIMING_DRIVEN"] = 1 if float(gpl) >= 0.5 else 0
    return out


def to_env(params: dict[str, Any], defaults: dict[str, float]) -> dict[str, str]:
    """ORFS env. Omit keys that match config defaults (unset ≠ force 0)."""
    p = clamp_params(params, defaults)
    env: dict[str, str] = {}
    lb0 = _f(defaults, "PLACE_DENSITY_LB_ADDON", 0.20)
    if abs(p["PLACE_DENSITY_LB_ADDON"] - lb0) > 1e-9:
        env["PLACE_DENSITY_LB_ADDON"] = str(p["PLACE_DENSITY_LB_ADDON"])
    pad0 = pad_default(defaults)
    if int(p["cell_pad"]) != pad0:
        env[PAD_KEYS[0]] = str(int(p["cell_pad"]))
        env[PAD_KEYS[1]] = str(int(p["cell_pad"]))
    tns0 = _f(defaults, "TNS_END_PERCENT", 100.0)
    if int(p["TNS_END_PERCENT"]) != int(round(tns0)):
        env["TNS_END_PERCENT"] = str(int(p["TNS_END_PERCENT"]))
    if float(p["SETUP_SLACK_MARGIN"]) > 1e-12:
        env["SETUP_SLACK_MARGIN"] = str(p["SETUP_SLACK_MARGIN"])
    if float(p["HOLD_SLACK_MARGIN"]) > 1e-12:
        env["HOLD_SLACK_MARGIN"] = str(p["HOLD_SLACK_MARGIN"])
    cts0 = defaults.get("CTS_BUF_DISTANCE")
    if cts0 is None:
        if abs(float(p["CTS_BUF_DISTANCE"]) - 100.0) > 1e-6:
            env["CTS_BUF_DISTANCE"] = str(p["CTS_BUF_DISTANCE"])
    elif abs(float(p["CTS_BUF_DISTANCE"]) - float(cts0)) > 1e-6:
        env["CTS_BUF_DISTANCE"] = str(p["CTS_BUF_DISTANCE"])
    if int(p["GPL_TIMING_DRIVEN"]) != 1:
        env["GPL_TIMING_DRIVEN"] = "0"
    return env


def pin(design: str, env: dict[str, str]) -> dict[str, str]:
    """Inject official DIE/CORE and ABC area. Strip floorplan knobs."""
    out = {k: str(v) for k, v in env.items() if k not in FORBIDDEN}
    box = official_box(design)
    if box is None:
        raise FileNotFoundError(f"no official DEF box for {design}")
    out["DIE_AREA"] = box["DIE_AREA"]
    out["CORE_AREA"] = box["CORE_AREA"]
    synth = synth_method_from_exploration()
    out["ABC_AREA"] = str(synth["ABC_AREA"])
    out["ABC_SPEED"] = str(synth["ABC_SPEED"])
    return out


def fingerprint(params: dict[str, Any], defaults: dict[str, float]) -> str:
    p = clamp_params(params, defaults)
    canon = []
    for k in PARAM_ORDER:
        v = p[k]
        if isinstance(v, float):
            canon.append((k, round(v, 6)))
        else:
            canon.append((k, v))
    blob = json.dumps(canon, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def variant_name(design: str, params: dict[str, Any], defaults: dict[str, float]) -> str:
    return f"camp_{design}_tpe_{fingerprint(params, defaults)}"


def knobs_from_extra(extra: dict[str, Any] | None) -> dict[str, str]:
    extra = extra or {}
    knobs = {str(k): str(v) for k, v in (extra.get("knobs") or {}).items()}
    lb = extra.get("place_density_lb_addon")
    if "PLACE_DENSITY_LB_ADDON" not in knobs and lb is not None:
        knobs["PLACE_DENSITY_LB_ADDON"] = str(lb)
    return knobs


def project_knobs(knobs: dict[str, Any], defaults: dict[str, float]) -> dict[str, Any] | None:
    """Map a cook's extra.knobs onto the TPE space. None if it moved the die."""
    raw = {str(k): v for k, v in knobs.items()}
    ar = raw.get("CORE_ASPECT_RATIO")
    if ar is not None:
        try:
            if abs(float(ar) - 1.0) > 0.05:
                return None
        except (TypeError, ValueError):
            return None
    util = raw.get("CORE_UTILIZATION")
    if util is not None and "CORE_UTILIZATION" in defaults:
        try:
            if abs(float(util) - float(defaults["CORE_UTILIZATION"])) >= 1.0:
                return None
        except (TypeError, ValueError):
            return None
    pad = raw.get(PAD_KEYS[0], raw.get(PAD_KEYS[1], pad_default(defaults)))
    projected = {
        "PLACE_DENSITY_LB_ADDON": raw.get(
            "PLACE_DENSITY_LB_ADDON", _f(defaults, "PLACE_DENSITY_LB_ADDON", 0.20)
        ),
        "cell_pad": pad,
        "TNS_END_PERCENT": raw.get("TNS_END_PERCENT", _f(defaults, "TNS_END_PERCENT", 100.0)),
        "SETUP_SLACK_MARGIN": raw.get("SETUP_SLACK_MARGIN", 0.0),
        "HOLD_SLACK_MARGIN": raw.get("HOLD_SLACK_MARGIN", 0.0),
        "CTS_BUF_DISTANCE": raw.get("CTS_BUF_DISTANCE", defaults.get("CTS_BUF_DISTANCE", 100.0)),
        "GPL_TIMING_DRIVEN": raw.get("GPL_TIMING_DRIVEN", 1),
    }
    return clamp_params(projected, defaults)


def params_from_recipes(recipe_ids: list[str], defaults: dict[str, float]) -> dict[str, Any] | None:
    from .floorplan import FLOORPLAN_RECIPES

    if any(r in FLOORPLAN_RECIPES for r in recipe_ids):
        return None
    env = resolve_many(recipe_ids, defaults)
    return project_knobs(env, defaults)


def title_of_params(params: dict[str, Any]) -> str:
    bits = [f"{k}={params[k]}" for k in PARAM_ORDER if k in params]
    return "TPE " + ", ".join(bits)
