"""Design-agnostic multi-stage knob catalog.

Offsets are relative to whatever the design's config.mk already uses.
The same recipe id is valid on gcd, ibex, aes, … — no per-design branch.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_EXPORT = re.compile(r"^export\s+([A-Z0-9_]+)\s*(?:\?=|=)\s*(\S+)")

# One axis = one named change. Combine a few, never a full factorial.
# `env` values are absolute ORFS knobs. `offset` is added to the config default
# at cook time (the wrapper / driver resolves the default from config.mk).
RECIPES: list[dict[str, Any]] = [
    {
        "id": "synth_area",
        "stage": "synth",
        "title": "ABC area synthesis",
        "does": "Yosys + ABC area script. Does not rewrite project Verilog.",
        "payoff": "Fewer cells / lower power. With physical knobs, this method produced the §5 wins.",
        "env": {"ABC_AREA": "1", "ABC_SPEED": "0"},
    },
    {
        "id": "synth_delay",
        "stage": "synth",
        "title": "ABC delay synthesis",
        "does": "Yosys + ABC speed script. Same RTL, different mapping.",
        "payoff": "Chases slack in synthesis. In campaign: 0 §5 wins — keep as control, not default.",
        "env": {"ABC_SPEED": "1", "ABC_AREA": "0"},
    },
    {
        "id": "synth_hier",
        "stage": "synth",
        "title": "Hierarchical synthesis",
        "does": "SYNTH_HIERARCHICAL=1: do not flatten before ABC.",
        "payoff": "Less area blow-up on large designs; measure, do not assume.",
        "env": {"SYNTH_HIERARCHICAL": "1"},
    },
    {
        "id": "core_tighter",
        "stage": "floorplan",
        "title": "Tighter core",
        "does": "CORE_UTILIZATION += 10 vs config default.",
        "payoff": "Lab: moves the die. Not a product knob (fixed floorplan).",
        "offset": {"CORE_UTILIZATION": 10},
    },
    {
        "id": "core_looser",
        "stage": "floorplan",
        "title": "Looser core",
        "does": "CORE_UTILIZATION −= 10 vs config default.",
        "payoff": "Lab: moves the die. Not a product knob (fixed floorplan).",
        "offset": {"CORE_UTILIZATION": -10},
    },
    {
        "id": "aspect_wide",
        "stage": "floorplan",
        "title": "Wide floorplan aspect",
        "does": "CORE_ASPECT_RATIO=2 (ORFS default is 1).",
        "payoff": "Lab: changes shape. Not a product knob (fixed floorplan).",
        "env": {"CORE_ASPECT_RATIO": "2"},
    },
    {
        "id": "place_denser",
        "stage": "place",
        "title": "Denser placement",
        "does": "PLACE_DENSITY_LB_ADDON += 0.05 vs config default.",
        "payoff": "Fewer repair buffers, lower area/power (gcd win). Same die.",
        "offset": {"PLACE_DENSITY_LB_ADDON": 0.05},
    },
    {
        "id": "place_sparser",
        "stage": "place",
        "title": "Sparser placement",
        "does": "PLACE_DENSITY_LB_ADDON −= 0.05 vs config default.",
        "payoff": "More local space. Won slack on ibex; not on gcd.",
        "offset": {"PLACE_DENSITY_LB_ADDON": -0.05},
    },
    {
        "id": "cell_pad_plus",
        "stage": "place",
        "title": "Cell padding +1 site",
        "does": "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT and DETAIL += 1.",
        "payoff": "Less local congestion; area/WL may rise.",
        "env": {
            "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT": "1",
            "CELL_PAD_IN_SITES_DETAIL_PLACEMENT": "1",
        },
    },
    {
        "id": "repair_half_tns",
        "stage": "repair",
        "title": "Repair TNS at half",
        "does": "TNS_END_PERCENT 100→50: repair fewer violated paths.",
        "payoff": "Fewer buffers, lower area/power; worst slack may worsen.",
        "env": {"TNS_END_PERCENT": "50"},
    },
    {
        "id": "repair_setup_margin",
        "stage": "repair",
        "title": "Setup margin on repair",
        "does": "SETUP_SLACK_MARGIN=0.05 ns.",
        "payoff": "More buffers for slack. Useful when placement is already good.",
        "env": {"SETUP_SLACK_MARGIN": "0.05"},
    },
    {
        "id": "place_sparse_setup",
        "stage": "place",
        "title": "Sparser placement + setup margin",
        "does": "PLACE_DENSITY_LB_ADDON −= 0.05 and SETUP_SLACK_MARGIN=0.05 ns.",
        "payoff": "Winning combo on aes and ibex. Slack up; area/power/leakage under +10%; IR not worse by 10%.",
        "offset": {"PLACE_DENSITY_LB_ADDON": -0.05},
        "env": {"SETUP_SLACK_MARGIN": "0.05"},
    },
    {
        "id": "cts_closer_bufs",
        "stage": "cts",
        "title": "Tighter clock buffers",
        "does": "CTS_BUF_DISTANCE smaller than platform default.",
        "payoff": "Less skew, more clock buffers / power. Measure after place, not alone.",
        "env": {"CTS_BUF_DISTANCE": "80"},
    },
    {
        "id": "hold_margin",
        "stage": "repair",
        "title": "Hold margin on repair",
        "does": "HOLD_SLACK_MARGIN=0.05 ns.",
        "payoff": "Fewer hold violations, more buffers. On a closed die may cut IR/area.",
        "env": {"HOLD_SLACK_MARGIN": "0.05"},
    },
    {
        "id": "place_notiming",
        "stage": "place",
        "title": "Placement without timing-driven",
        "does": "GPL_TIMING_DRIVEN=0.",
        "payoff": "Place for density, not slack. Control of default timing-driven mode.",
        "env": {"GPL_TIMING_DRIVEN": "0"},
    },
    {
        "id": "cts_sparser",
        "stage": "cts",
        "title": "Sparser clock buffers",
        "does": "CTS_BUF_DISTANCE=200 (wider than default / 80 µm tight).",
        "payoff": "Fewer clock buffers, less power. Skew may rise.",
        "env": {"CTS_BUF_DISTANCE": "200"},
    },
    {
        "id": "repair_skip",
        "stage": "repair",
        "title": "No TNS repair",
        "does": "TNS_END_PERCENT=0: do not repair violated paths.",
        "payoff": "Fewer buffers. On a closed die may cut area/power.",
        "env": {"TNS_END_PERCENT": "0"},
    },
]


def by_id(recipe_id: str) -> dict[str, Any]:
    for r in RECIPES:
        if r["id"] == recipe_id:
            return r
    raise KeyError(recipe_id)


def stages() -> list[str]:
    out: list[str] = []
    for r in RECIPES:
        if r["stage"] not in out:
            out.append(r["stage"])
    return out


# Offsets can go out of range on a design whose default is already extreme
# (spi util=8; core_looser would be −2). Same recipe id stays valid everywhere.
_CLAMP = {
    "CORE_UTILIZATION": (5.0, 95.0),
    "PLACE_DENSITY_LB_ADDON": (0.0, 0.99),
}


def resolve(recipe_id: str, defaults: dict[str, float] | None = None) -> dict[str, str]:
    """Absolute env for make. `defaults` supplies config.mk values for offsets."""
    rec = by_id(recipe_id)
    env = {str(k): str(v) for k, v in (rec.get("env") or {}).items()}
    defaults = defaults or {}
    for key, delta in (rec.get("offset") or {}).items():
        if key not in defaults:
            raise KeyError(f"{recipe_id} needs default {key} from config.mk")
        raw = float(defaults[key]) + float(delta)
        lo, hi = _CLAMP.get(key, (None, None))
        if lo is not None:
            raw = max(lo, raw)
        if hi is not None:
            raw = min(hi, raw)
        env[key] = str(raw)
    return env


def resolve_many(recipe_ids: list[str], defaults: dict[str, float] | None = None) -> dict[str, str]:
    env: dict[str, str] = {}
    for rid in recipe_ids:
        env.update(resolve(rid, defaults))
    return env


def parse_config_defaults(config_mk: Path | str) -> dict[str, float]:
    """Numeric `export NAME = value` / `?=` lines from an ORFS config.mk."""
    out: dict[str, float] = {}
    for line in Path(config_mk).read_text().splitlines():
        m = _EXPORT.match(line.strip())
        if not m:
            continue
        try:
            out[m.group(1)] = float(m.group(2))
        except ValueError:
            continue
    return out


def config_mk_for(design: str) -> Path:
    from .experiments import DESIGN_CATALOG

    cat = DESIGN_CATALOG.get(design) or {}
    nick = cat.get("orfs_config") or design
    learn_cfg = _REPO / "learn" / "designs" / "nangate45" / nick / "config.mk"
    if learn_cfg.is_file():
        return learn_cfg
    orfs_cfg = _REPO / "tools/OpenROAD-flow-scripts/flow/designs/nangate45" / nick / "config.mk"
    if orfs_cfg.is_file():
        return orfs_cfg
    raise FileNotFoundError(f"no config.mk for design={design}")


def titles_of(recipe_ids: list[str]) -> str:
    return " + ".join(by_id(r)["title"] for r in recipe_ids)
