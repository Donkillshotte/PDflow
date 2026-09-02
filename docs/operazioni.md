# Operazioni

Un job pesante alla volta. Il wrapper usa `prlimit --as`.
Mai `FLOW_VARIANT` in `{flowlab, learn, base}`. Mai Krylov su AES
(~50–70k-R). Mai restampare l’oro GCD Dynamic IR **45.298 mV**.
Mai toccare `results/.../gcd/flowlab/` (baseline A).

## Ambiente

```bash
export PYTHONPATH=learn:learn/scripts
# tuner: pip install -r learn/requirements-tune.txt   # optuna>=3.4,<4
```

Entry cook: [`scripts/run_design_finish.sh`](../scripts/run_design_finish.sh)
via [`learn/dse/cook.py`](../learn/dse/cook.py) (`cook_one`).

## Comandi prodotto

```bash
# Review: cover / improve / tune
python3 learn/scripts/run_recipe_loop.py
python3 learn/scripts/run_recipe_loop.py --dry-run

# Una ricetta (titolo → id in knob_catalog.py)
python3 learn/scripts/cook_recipe.py --design gcd --recipes place_sparse_setup

# TPE, ≤8 finish, seriale
python3 -u learn/scripts/run_tpe.py --design ibex --max-cooks 8
python3 learn/scripts/run_tpe.py --design dynamic_node --dry-run

# Registro
# learn/sim/dse/campaign_experiments.jsonl
python3 learn/scripts/record_experiment.py --help
```

Slot cheap-first: gcd → spi → ibex → aes → dynamic_node.
spi non è ammissibile al tune.

## Test

```bash
# Suite veloce prodotto (sintetico + gcd-scale + mappa docs). Una alla volta.
python3 learn/scripts/test_dse_next.py

# Lab DSE (controller / F4): non mescolare con la suite sopra nello stesso processo
python3 learn/scripts/test_dse.py
```

Live finish solo su gcd-scale nella suite veloce. Un `test_dse.py` alla volta.
Live F4 per ultimo, e solo se richiesto.

## Refuse (attesi)

| Tentativo | Esito |
|---|---|
| `FLOW_VARIANT=flowlab` / `learn` / `base` | rifiutato dal wrapper |
| ricetta floorplan (`core_*`, `aspect_wide`) | `cook_one` refuse |
| `cell_pad=2` (muro) | `cook_one` refuse |
| `synth_hier` (muro) | cover la salta; cook refuse |
| `DIE_AREA` + `FLOORPLAN_DEF` (aes) | pin non inietta DIE |

## Varianti ORFS

Nome prodotto: `camp_{design}_{recipe}` oppure `camp_{design}_tpe_{12hex}`.
Fase registro T1 per TPE. `extra.tuner=tpe`. Non si puliscono `camp_*_base`.

## Memoria / leftover

Non committare `learn/sim/dse/memory_flowlab_nl.jsonl`,
`memory_camp_spi_dse.index.json`, `dse_camp_spi_dse.json`.
`learn/sim/dse/tpe_*.db` è già in `.gitignore`.
