# Operations

One heavy job at a time. The wrapper uses `prlimit --as`.
Never `FLOW_VARIANT` in `{flowlab, learn, base}`. Never Krylov on AES
(~50–70k-R). Never restamp gold GCD Dynamic IR **45.298 mV**.
Never touch `results/.../gcd/flowlab/` (baseline A).

## Environment

```bash
export PYTHONPATH=learn:learn/scripts
# tuner: pip install -r learn/requirements-tune.txt   # optuna>=3.4,<4
```

Cook entry: [`scripts/run_design_finish.sh`](../scripts/run_design_finish.sh)
via [`learn/dse/cook.py`](../learn/dse/cook.py) (`cook_one`).

## Product commands

```bash
# Review: cover / improve / tune
python3 learn/scripts/run_recipe_loop.py
python3 learn/scripts/run_recipe_loop.py --dry-run

# One recipe (title → id in knob_catalog.py)
python3 learn/scripts/cook_recipe.py --design gcd --recipes place_sparse_setup

# TPE, ≤8 finishes, serial
python3 -u learn/scripts/run_tpe.py --design ibex --max-cooks 8
python3 learn/scripts/run_tpe.py --design dynamic_node --dry-run

# Registry
# learn/sim/dse/campaign_experiments.jsonl
python3 learn/scripts/record_experiment.py --help
```

Cheap-first slots: gcd → spi → ibex → aes → dynamic_node.
spi is not admissible for tune.

## Tests

```bash
# Fast product suite (synthetic + gcd-scale + docs map). One at a time.
python3 learn/scripts/test_dse_next.py

# Lab DSE (controller / F4): do not mix with the suite above in one process
python3 learn/scripts/test_dse.py
```

Live finish only at gcd-scale in the fast suite. One `test_dse.py` at a time.
Live F4 last, and only when requested.

## Refuse (expected)

| Attempt | Outcome |
|---|---|
| `FLOW_VARIANT=flowlab` / `learn` / `base` | refused by wrapper |
| floorplan recipe (`core_*`, `aspect_wide`) | `cook_one` refuse |
| `cell_pad=2` (wall) | `cook_one` refuse |
| `synth_hier` (wall) | cover skips; cook refuse |
| `DIE_AREA` + `FLOORPLAN_DEF` (aes) | pin does not inject DIE |

## ORFS variants

Product name: `camp_{design}_{recipe}` or `camp_{design}_tpe_{12hex}`.
TPE registry phase T1. `extra.tuner=tpe`. Do not clean `camp_*_base`.

## Memory / leftovers

Do not commit `learn/sim/dse/memory_flowlab_nl.jsonl`,
`memory_camp_spi_dse.index.json`, `dse_camp_spi_dse.json`.
`learn/sim/dse/tpe_*.db` is already in `.gitignore`.
