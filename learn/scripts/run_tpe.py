#!/usr/bin/env python3
"""TPE loop: ask one vector, cook_one, tell. Serial. Product tuner only.

Optuna lives here. Space and score stay import-free so the fast suite
does not need the extra pin.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "learn"), str(ROOT / "learn" / "scripts")]

from dse.cook import cook_one
from dse.experiments import DESIGN_CATALOG, ExperimentLog
from dse.knob_catalog import config_mk_for, parse_config_defaults
from dse.tune_score import TuneOutcome, evaluate
from dse.tune_space import (
    bounds,
    clamp_params,
    fingerprint,
    pin,
    title_of_params,
    to_env,
    variant_name,
)
from dse.tune_transfer import infer_walls, params_blocked
from dse.tune_warm import (
    already_combo_parts,
    base_of,
    collect_warm,
    enqueue_params,
    preview_tune,
    slot_rows,
    tune_admissible,
    win_ids_from_rows,
)
from dse.win_rule import verdict


def _optuna():
    try:
        import optuna
        from optuna.distributions import (
            CategoricalDistribution,
            FloatDistribution,
            IntDistribution,
        )
        from optuna.samplers import TPESampler
        from optuna.trial import TrialState
    except ImportError:
        print("optuna missing — pip install -r learn/requirements-tune.txt", file=sys.stderr)
        sys.exit(2)
    return optuna, TPESampler, FloatDistribution, IntDistribution, CategoricalDistribution, TrialState


def _constraints_func(trial):
    return trial.user_attrs.get("constraints", (1.0,))


def _dists(defaults, FloatDistribution, IntDistribution, CategoricalDistribution):
    out = {}
    for key, spec in bounds(defaults).items():
        kind = spec[0]
        if kind == "float":
            out[key] = FloatDistribution(float(spec[1]), float(spec[2]))
        elif kind == "int":
            out[key] = IntDistribution(int(spec[1]), int(spec[2]))
        elif kind == "cat":
            out[key] = CategoricalDistribution(list(spec[1]))
        else:
            raise ValueError(f"unknown bound kind {kind} for {key}")
    return out


def _db_path(design: str) -> Path:
    raw = os.environ.get("TPE_DB_DIR")
    base = Path(raw) if raw else (ROOT / "learn" / "sim" / "dse")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"tpe_{design}.db"


def _make_study(design: str, optuna, TPESampler, dists):
    try:
        sampler = TPESampler(
            constraints_func=_constraints_func,
            n_startup_trials=8,
            multivariate=True,
            seed=0,
        )
    except TypeError:
        sampler = TPESampler(
            constraints_func=_constraints_func,
            n_startup_trials=8,
            seed=0,
        )
    storage = f"sqlite:///{_db_path(design)}"
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    return optuna.create_study(
        study_name=f"tpe_{design}",
        direction="minimize",
        sampler=sampler,
        storage=storage,
        load_if_exists=True,
    )


def _frozen_params(params: dict[str, Any], dists) -> dict[str, Any]:
    frozen = {}
    for k in dists:
        v = params[k]
        dist = dists[k]
        name = type(dist).__name__
        if "Int" in name:
            frozen[k] = int(v)
        elif "Categorical" in name:
            frozen[k] = int(v) if not isinstance(v, bool) else v
        else:
            frozen[k] = float(v)
    return frozen


def _add_warm(study, optuna, dists, warm, defaults, base) -> int:
    n = 0
    existing = set()
    for t in study.trials:
        existing.add(tuple(sorted((k, t.params[k]) for k in t.params)))
    for params, exp in warm:
        p = clamp_params(params, defaults)
        frozen = _frozen_params(p, dists)
        key = tuple(sorted(frozen.items()))
        if key in existing:
            continue
        outcome = evaluate(exp, base)
        cons = tuple(float(c) for c in outcome.constraints)
        try:
            study.add_trial(
                optuna.trial.create_trial(
                    params=frozen,
                    distributions=dists,
                    value=float(outcome.score),
                    user_attrs={"constraints": cons},
                    system_attrs={"constraints": cons},
                )
            )
            existing.add(key)
            n += 1
        except Exception as err:
            print(json.dumps({"warm_skip": fingerprint(p, defaults), "error": str(err)}), file=sys.stderr)
    return n


def _fake_cand(params: dict[str, Any], base) -> Any:
    """Deterministic stand-in. Lose in the sparse/no-pad corner; win if pad+dense."""
    pad = int(params.get("cell_pad") or 0)
    dens = float(params.get("PLACE_DENSITY_LB_ADDON") or 0.0)
    lose_corner = pad == 0 and dens <= 0.12
    win_corner = pad >= 2 and dens >= 0.25
    dw = -0.020 if lose_corner else (0.008 if win_corner else 0.0)
    area_scale = 0.85 if win_corner else (1.02 if lose_corner else 1.0)
    return type(
        "E",
        (),
        {
            "status": "done",
            "role": "knob",
            "finish_wns_ns": float(base.finish_wns_ns) + dw,
            "stdcell_um2": float(base.stdcell_um2) * area_scale,
            "power_w": float(base.power_w) * (0.90 if win_corner else 1.0),
            "leakage_w": float(base.leakage_w) * (0.90 if win_corner else 1.0) if base.leakage_w else None,
            "ir_drop_v": float(base.ir_drop_v) * (0.90 if win_corner else 1.0) if base.ir_drop_v else None,
            "die_um2": getattr(base, "die_um2", None),
            "extra": {},
        },
    )()


def _best_win_score(warm, base) -> float:
    best = 0.0
    for _params, exp in warm:
        oc = evaluate(exp, base)
        if oc.verdict == "win":
            best = min(best, oc.score)
    return best


def _n_wins(rows, base) -> int:
    n = 0
    for e in rows:
        if getattr(e, "role", None) == "base":
            continue
        if getattr(e, "status", None) != "done" or getattr(e, "finish_wns_ns", None) is None:
            continue
        if verdict(e, base) == "win":
            n += 1
    return n


def _row_for_variant(log: ExperimentLog, variant: str):
    rows = log.by_variant(variant)
    if not rows:
        return None
    for e in reversed(rows):
        if e.finish_wns_ns is not None:
            return e
    return rows[-1]


def run_tpe(
    design: str,
    max_cooks: int = 8,
    fake: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    if design not in DESIGN_CATALOG:
        return {"ok": False, "error": f"unknown design {design}"}
    prev = preview_tune(design)
    if dry_run:
        return {**prev, "decision": "tune" if prev.get("admissible") else "skip", "dry_run": True}
    if not prev.get("admissible"):
        return {"ok": False, "error": "slot not admissible", "design": design, **prev}

    log = ExperimentLog()
    defaults = parse_config_defaults(config_mk_for(design))
    base = base_of(log, design)
    rows = slot_rows(log, design)
    if base is None:
        return {"ok": False, "error": "no usable base", "design": design}

    optuna, TPESampler, FloatD, IntD, CatD, TrialState = _optuna()
    dists = _dists(defaults, FloatD, IntD, CatD)
    study = _make_study(design, optuna, TPESampler, dists)

    warm = collect_warm(rows, defaults, base)
    n_warm = _add_warm(study, optuna, dists, warm, defaults, base)

    win_ids = win_ids_from_rows(rows, base, defaults)
    already = already_combo_parts(rows, defaults)
    walls = infer_walls(log.all())
    queue = enqueue_params(
        rows,
        defaults,
        win_ids,
        already,
        all_rows=log.all(),
        design=design,
        walls=walls,
    )
    for params in queue:
        frozen = _frozen_params(clamp_params(params, defaults), dists)
        try:
            study.enqueue_trial(frozen)
        except Exception as err:
            print(json.dumps({"enqueue_skip": fingerprint(params, defaults), "error": str(err)}), file=sys.stderr)

    seen = {fingerprint(p, defaults) for p, _ in warm}
    for e in rows:
        extra = e.extra or {}
        fp = extra.get("fingerprint")
        if fp and getattr(e, "status", None) in ("done", "stopped_by_policy"):
            seen.add(str(fp))

    plateau = 0
    cooked = 0
    asked = 0
    wins_before = _n_wins(rows, base)
    best_win = _best_win_score(warm, base)
    history: list[dict[str, Any]] = []
    max_asks = max(max_cooks * 4, max_cooks + 4)

    while cooked < max_cooks and asked < max_asks:
        trial = study.ask(fixed_distributions=dists)
        asked += 1
        params = clamp_params(dict(trial.params), defaults)
        fp = fingerprint(params, defaults)
        env = pin(design, to_env(params, defaults))
        title = title_of_params(params)
        var = variant_name(design, params, defaults)

        if fp in seen or params_blocked(params, walls) is not None:
            try:
                study.tell(trial, state=TrialState.PRUNED)
            except Exception:
                study.tell(trial, 1.0)
            continue
        seen.add(fp)

        extra = {
            "tuner": "tpe",
            "fingerprint": fp,
            "tpe_trial": cooked + 1,
            "title": title,
        }
        if fake:
            cand = _fake_cand(params, base)
            outcome = evaluate(cand, base)
            rec = {
                "ok": True,
                "fake": True,
                "variant": var,
                "verdict": outcome.verdict,
            }
        else:
            rec = cook_one(
                design,
                knobs=env,
                phase="T1",
                variant=var,
                extra=extra,
                skip_if_variant=True,
            )
            if rec.get("skipped"):
                try:
                    study.tell(trial, state=TrialState.PRUNED)
                except Exception:
                    study.tell(trial, 1.0)
                continue
            log = ExperimentLog()
            row = _row_for_variant(log, rec.get("variant") or var)
            if row is None:
                outcome = TuneOutcome(
                    score=1.0,
                    constraints=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                    verdict="incomplete",
                    notes="cook produced no row",
                )
            else:
                outcome = evaluate(row, base)

        try:
            trial.set_user_attr("constraints", tuple(float(c) for c in outcome.constraints))
            study.tell(trial, float(outcome.score))
        except Exception as err:
            try:
                study.add_trial(
                    optuna.trial.create_trial(
                        params=_frozen_params(params, dists),
                        distributions=dists,
                        value=float(outcome.score),
                        user_attrs={"constraints": tuple(float(c) for c in outcome.constraints)},
                        system_attrs={"constraints": tuple(float(c) for c in outcome.constraints)},
                    )
                )
            except Exception as err2:
                print(json.dumps({"tell_failed": str(err), "add_failed": str(err2)}), file=sys.stderr)

        cooked += 1
        history.append(
            {
                "fp": fp,
                "title": title,
                "score": outcome.score,
                "feasible": outcome.feasible,
                "verdict": outcome.verdict,
                "variant": rec.get("variant"),
            }
        )
        print(
            json.dumps(
                {
                    "n": cooked,
                    "fp": fp,
                    "title": title,
                    "score": outcome.score,
                    "feasible": outcome.feasible,
                    "verdict": outcome.verdict,
                    "variant": rec.get("variant"),
                }
            ),
            flush=True,
        )

        if outcome.feasible:
            better = outcome.verdict == "win" and outcome.score < best_win - 1e-15
            new_win = outcome.verdict == "win"
            if new_win or better:
                plateau = 0
                if better or (new_win and outcome.score < best_win):
                    best_win = outcome.score
            else:
                plateau += 1
        else:
            plateau = 0
        if plateau >= 3:
            break

    log = ExperimentLog()
    wins_after = _n_wins(slot_rows(log, design), base_of(log, design) or base)
    return {
        "ok": True,
        "design": design,
        "warm": n_warm,
        "cooked": cooked,
        "asked": asked,
        "history": history,
        "wins_before": wins_before,
        "wins_after": wins_after,
        "new_win": wins_after > wins_before,
        "fake": fake,
        "stopped_plateau": plateau >= 3,
    }


def _main() -> int:
    p = argparse.ArgumentParser(description="TPE tuner (product, serial ask/cook/tell)")
    p.add_argument("--design", required=True, choices=sorted(DESIGN_CATALOG))
    p.add_argument("--max-cooks", type=int, default=8)
    p.add_argument("--fake", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    out = run_tpe(args.design, max_cooks=args.max_cooks, fake=args.fake, dry_run=args.dry_run)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") or out.get("dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
