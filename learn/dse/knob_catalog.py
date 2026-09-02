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
        "title": "Sintesi ABC area",
        "does": "Yosys + script ABC area. Non tocca il Verilog di progetto.",
        "payoff": "Meno celle / power. È il metodo che, con knob fisici, ha prodotto i win §5.",
        "env": {"ABC_AREA": "1", "ABC_SPEED": "0"},
    },
    {
        "id": "synth_delay",
        "stage": "synth",
        "title": "Sintesi ABC delay",
        "does": "Yosys + script ABC speed. Stesso RTL, altro mapping.",
        "payoff": "Insegue slack in sintesi. In campagna: 0 win §5 — tenere come controllo, non come default.",
        "env": {"ABC_SPEED": "1", "ABC_AREA": "0"},
    },
    {
        "id": "synth_hier",
        "stage": "synth",
        "title": "Sintesi gerarchica",
        "does": "SYNTH_HIERARCHICAL=1: non flatten prima di ABC.",
        "payoff": "Meno scoppio di area su design grandi; da misurare, non assunto.",
        "env": {"SYNTH_HIERARCHICAL": "1"},
    },
    {
        "id": "core_tighter",
        "stage": "floorplan",
        "title": "Core più stretto",
        "does": "CORE_UTILIZATION += 10 rispetto al default di config.",
        "payoff": "Die più piccolo, WL e IR spesso meglio (win ibex). Rischio congestion.",
        "offset": {"CORE_UTILIZATION": 10},
    },
    {
        "id": "core_looser",
        "stage": "floorplan",
        "title": "Core più largo",
        "does": "CORE_UTILIZATION −= 10 rispetto al default di config.",
        "payoff": "Più spazio al place/route. Su ibex ha perso slack e allungato i fili.",
        "offset": {"CORE_UTILIZATION": -10},
    },
    {
        "id": "aspect_wide",
        "stage": "floorplan",
        "title": "Floorplan più largo che alto",
        "does": "CORE_ASPECT_RATIO=2 (default ORFS è 1).",
        "payoff": "Cambia lunghezza dei path e forma della PDN. Stadio floorplan, non netlist.",
        "env": {"CORE_ASPECT_RATIO": "2"},
    },
    {
        "id": "place_denser",
        "stage": "place",
        "title": "Place più denso",
        "does": "PLACE_DENSITY_LB_ADDON += 0.05 rispetto al default di config.",
        "payoff": "Meno buffer di repair, area/power giù (win gcd). Stesso die.",
        "offset": {"PLACE_DENSITY_LB_ADDON": 0.05},
    },
    {
        "id": "place_sparser",
        "stage": "place",
        "title": "Place più sparso",
        "does": "PLACE_DENSITY_LB_ADDON −= 0.05 rispetto al default di config.",
        "payoff": "Più spazio locale. Su ibex ha comunque vinto slack; su gcd no.",
        "offset": {"PLACE_DENSITY_LB_ADDON": -0.05},
    },
    {
        "id": "cell_pad_plus",
        "stage": "place",
        "title": "Padding celle +1 site",
        "does": "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT e DETAIL += 1.",
        "payoff": "Meno congestion locale, area/WL possono salire.",
        "env": {
            "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT": "1",
            "CELL_PAD_IN_SITES_DETAIL_PLACEMENT": "1",
        },
    },
    {
        "id": "repair_half_tns",
        "stage": "repair",
        "title": "Repair TNS a metà",
        "does": "TNS_END_PERCENT 100→50: ripara meno path violati.",
        "payoff": "Meno buffer, area/power giù; slack worst può peggiorare.",
        "env": {"TNS_END_PERCENT": "50"},
    },
    {
        "id": "repair_setup_margin",
        "stage": "repair",
        "title": "Margine di setup sul repair",
        "does": "SETUP_SLACK_MARGIN=0.05 ns.",
        "payoff": "Più buffer in cambio di slack. Utile se il place è già buono.",
        "env": {"SETUP_SLACK_MARGIN": "0.05"},
    },
    {
        "id": "cts_closer_bufs",
        "stage": "cts",
        "title": "Buffer di clock più fitti",
        "does": "CTS_BUF_DISTANCE più piccolo del default di piattaforma.",
        "payoff": "Meno skew, più clock buffers / power. Misura after place, non da solo.",
        "env": {"CTS_BUF_DISTANCE": "80"},
    },
    {
        "id": "hold_margin",
        "stage": "repair",
        "title": "Margine di hold sul repair",
        "does": "HOLD_SLACK_MARGIN=0.05 ns.",
        "payoff": "Meno violazioni hold, più buffer. Su un die già chiuso può tagliare IR/area.",
        "env": {"HOLD_SLACK_MARGIN": "0.05"},
    },
    {
        "id": "place_notiming",
        "stage": "place",
        "title": "Place senza timing-driven",
        "does": "GPL_TIMING_DRIVEN=0.",
        "payoff": "Place per densità, non per slack. Controllo del default timing-driven.",
        "env": {"GPL_TIMING_DRIVEN": "0"},
    },
    {
        "id": "cts_sparser",
        "stage": "cts",
        "title": "Buffer di clock più radi",
        "does": "CTS_BUF_DISTANCE=200 (più largo del default / dei 80 µm fitti).",
        "payoff": "Meno clock buffers, meno power. Skew può salire.",
        "env": {"CTS_BUF_DISTANCE": "200"},
    },
    {
        "id": "repair_skip",
        "stage": "repair",
        "title": "Nessun repair TNS",
        "does": "TNS_END_PERCENT=0: non ripara i path violati.",
        "payoff": "Meno buffer. Su un die già chiuso può tagliare area/potenza.",
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
