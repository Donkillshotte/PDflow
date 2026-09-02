"""Cross-design walls and order prior. No Optuna import.

A wall is inferred from the registry, not from a design name: pad=2 that
never finished on ≥2 designs, or synth_hier that never won on ≥2 designs.
Transfer enqueue copies the *order* of mechanisms that already won on
≥2 designs, not their scores.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tune_space import fingerprint, knobs_from_extra, project_knobs
from .win_rule import verdict

WALL_MIN_DESIGNS = 2
TRANSFER_MAX = 3
PAD_KEY = "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT"


@dataclass(frozen=True)
class Wall:
    kind: str
    value: Any
    designs: tuple[str, ...]
    reason: str


def _extra(exp: Any) -> dict[str, Any]:
    return getattr(exp, "extra", None) or {}


def _recipe_ids(exp: Any) -> list[str]:
    extra = _extra(exp)
    rids = list(extra.get("recipe_ids") or ([extra["recipe_id"]] if extra.get("recipe_id") else []))
    variant = str(getattr(exp, "variant", "") or "")
    if variant.endswith("_synth_hier") and "synth_hier" not in rids:
        rids.append("synth_hier")
    return rids


def _pad(knobs: dict[str, Any]) -> int | None:
    raw = knobs.get(PAD_KEY, knobs.get("cell_pad"))
    if raw is None:
        return None
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def _bases(rows: list[Any]) -> dict[str, Any]:
    """Official-slot bases only. Later clock-sweep role=base rows must not win."""
    from .experiments import DESIGN_CATALOG

    out: dict[str, Any] = {}
    for e in rows:
        if getattr(e, "role", None) != "base":
            continue
        if getattr(e, "finish_wns_ns", None) is None:
            continue
        design = str(getattr(e, "design", "") or "")
        if not design:
            continue
        clock = (DESIGN_CATALOG.get(design) or {}).get("clk_ns")
        if clock is not None and f"{float(e.clock_ns):.3f}" != f"{float(clock):.3f}":
            continue
        variant = str(getattr(e, "variant", "") or "")
        if design not in out or variant == f"camp_{design}_base":
            out[design] = e
    return out


def infer_walls(rows: list[Any]) -> list[Wall]:
    """Detect global walls from any list of experiment rows."""
    walls: list[Wall] = []
    fail_pad: set[str] = set()
    done_pad: set[str] = set()
    for e in rows:
        knobs = _extra(e).get("knobs") or {}
        if _pad(knobs) != 2:
            continue
        design = str(getattr(e, "design", "") or "")
        if not design:
            continue
        status = getattr(e, "status", None)
        if status == "failed":
            fail_pad.add(design)
        if status == "done" and getattr(e, "finish_wns_ns", None) is not None:
            done_pad.add(design)
    if len(fail_pad) >= WALL_MIN_DESIGNS and not done_pad:
        walls.append(
            Wall(
                kind="cell_pad",
                value=2,
                designs=tuple(sorted(fail_pad)),
                reason="pad=2 never finished on ≥2 designs",
            )
        )

    bases = _bases(rows)
    hier_designs: set[str] = set()
    hier_wins: set[str] = set()
    for e in rows:
        if "synth_hier" not in _recipe_ids(e):
            continue
        design = str(getattr(e, "design", "") or "")
        if not design:
            continue
        hier_designs.add(design)
        base = bases.get(design)
        if (
            base is not None
            and getattr(e, "status", None) == "done"
            and getattr(e, "finish_wns_ns", None) is not None
            and verdict(e, base) == "win"
        ):
            hier_wins.add(design)
    if len(hier_designs) >= WALL_MIN_DESIGNS and not hier_wins:
        walls.append(
            Wall(
                kind="recipe",
                value="synth_hier",
                designs=tuple(sorted(hier_designs)),
                reason="synth_hier never won on ≥2 designs",
            )
        )
    return walls


def params_blocked(params: dict[str, Any], walls: list[Wall]) -> Wall | None:
    pad = params.get("cell_pad")
    if pad is None:
        return None
    try:
        pad_i = int(round(float(pad)))
    except (TypeError, ValueError):
        return None
    for wall in walls:
        if wall.kind == "cell_pad" and int(wall.value) == pad_i:
            return wall
    return None


def recipes_blocked(recipe_ids: list[str], walls: list[Wall]) -> Wall | None:
    want = set(recipe_ids)
    for wall in walls:
        if wall.kind == "recipe" and wall.value in want:
            return wall
    return None


def mechanism_sig(params: dict[str, Any], defaults: dict[str, float]) -> str:
    """Coarse mechanism, stable across designs whose defaults differ."""
    bits: list[str] = []
    lb0 = float(defaults.get("PLACE_DENSITY_LB_ADDON", 0.20))
    lb = float(params.get("PLACE_DENSITY_LB_ADDON", lb0))
    if lb < lb0 - 0.02:
        bits.append("sparse")
    elif lb > lb0 + 0.02:
        bits.append("dense")
    pad = int(round(float(params.get("cell_pad", 0))))
    if pad >= 1:
        bits.append(f"pad{pad}")
    if float(params.get("SETUP_SLACK_MARGIN", 0.0)) > 0.005:
        bits.append("setup")
    if float(params.get("HOLD_SLACK_MARGIN", 0.0)) > 0.005:
        bits.append("hold")
    if float(params.get("CTS_BUF_DISTANCE", 100.0)) < 95.0:
        bits.append("cts_fitti")
    if int(round(float(params.get("TNS_END_PERCENT", 100)))) < 95:
        bits.append("tns")
    if int(round(float(params.get("GPL_TIMING_DRIVEN", 1)))) == 0:
        bits.append("no_td")
    return "+".join(bits) or "default"


def _win_params(exp: Any, defaults: dict[str, float], base: Any) -> dict[str, Any] | None:
    if getattr(exp, "status", None) != "done" or getattr(exp, "finish_wns_ns", None) is None:
        return None
    if getattr(exp, "role", None) == "base":
        return None
    if verdict(exp, base) != "win":
        return None
    return project_knobs(knobs_from_extra(_extra(exp)), defaults)


def transfer_enqueue(
    rows: list[Any],
    design: str,
    defaults: dict[str, float],
    *,
    already_fps: set[str] | None = None,
    walls: list[Wall] | None = None,
    max_n: int = TRANSFER_MAX,
) -> list[dict[str, Any]]:
    """Vectors of mechanisms that won on ≥2 designs, excluding this slot's loses."""
    walls = walls or []
    already_fps = already_fps or set()
    bases = _bases(rows)
    wins_by_sig: dict[str, set[str]] = {}
    loses_by_sig: dict[str, set[str]] = {}
    sample: dict[str, dict[str, Any]] = {}
    for e in rows:
        other = str(getattr(e, "design", "") or "")
        base = bases.get(other)
        if base is None:
            continue
        params = project_knobs(knobs_from_extra(_extra(e)), defaults)
        if params is None:
            continue
        sig = mechanism_sig(params, defaults)
        if getattr(e, "status", None) == "done" and getattr(e, "finish_wns_ns", None) is not None:
            v = verdict(e, base)
            if v == "win":
                wins_by_sig.setdefault(sig, set()).add(other)
                if other != design and sig not in sample and params_blocked(params, walls) is None:
                    sample[sig] = params
            elif v == "lose":
                loses_by_sig.setdefault(sig, set()).add(other)
    out: list[dict[str, Any]] = []
    for sig, params in sample.items():
        if len(wins_by_sig.get(sig, ())) < WALL_MIN_DESIGNS:
            continue
        if design in wins_by_sig.get(sig, ()):
            continue
        if design in loses_by_sig.get(sig, ()):
            continue
        fp = fingerprint(params, defaults)
        if fp in already_fps:
            continue
        already_fps.add(fp)
        out.append(params)
        if len(out) >= max_n:
            break
    return out
