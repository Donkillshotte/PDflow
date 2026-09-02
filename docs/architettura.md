# Architettura del repository

Il tree è un **monorepo a tre superfici**. Non si riorganizza ORFS, non si
spostano i moduli in `learn/dse/*.py`, non si unificano prodotto e laboratorio.

## Directory

| Path | Superficie | Ruolo |
|---|---|---|
| `docs/` | tutte | Indice di lettura. Non contiene piani congelati. |
| `learn/dse/` | prodotto + lab | Package Python. Win = `win_rule.py`. Lab = controller F4. |
| `learn/scripts/` | prodotto + lab | Entry cook / TPE / test / IR / signoff |
| `learn/sim/dse/` | prodotto + lab | Registro jsonl, memorie, SDC campagna |
| `learn/designs/` | prodotto + corso | Overlay ORFS (gcd-tutorial, spi, aes, ibex, …) |
| `learn/lessons/` | corso | 00–07: README + LAB + `run.sh` |
| `learn/reference/` | corso + lab | Glossario, Tcl, IR, OSS, DSE lab |
| `learn/workbook/` | corso | Esercizi e quiz |
| `learn/flowlab/` | corso | RTL tutorial (variante `flowlab` locked) |
| `studio/` | corso | UI Next.js. Orchestra gli script, non li sostituisce |
| `engine/` | lab | `libdpn` (DirectLU / AMG / RAS / Krylov). Mai su AES 50–70k-R |
| `scripts/` | tutte | Install, finish prodotto, smoke corso, cloud |
| `tools/` | infra | ORFS + yosys + OpenSTA. **gitignored**, ricreabile |
| `PLAN.md` | lab | Fase 2 controller. Non è il prodotto |
| `AGENTS.md` | tutte | Refuse, un job, test, leftover |
| `CONTRIBUTING.md` | tutte | Come contribuire |

## Flusso prodotto (finish vero)

```
run_recipe_loop.py
  → cook.py / cook_recipe.py / run_tpe.py
    → scripts/run_design_finish.sh
      → ORFS make (FLOW_VARIANT=camp_*)
        → 6_report → win_rule.py → campaign_experiments.jsonl
```

Optuna vive **solo** in `learn/scripts/run_tpe.py`.
Niente `if design ==` in tuner, spazio, score, coordinatore, transfer.

## Flusso laboratorio (non win)

```
run_dse.py / controller
  → F1 synth → F2 place/GRT → F3 STA → F4 IR (engine/)
    → DesignMemory JSONL
```

Gold GCD Dynamic IR **45.298 mV** è `reference_run`. Finish FlowLab **6.075 mV**
è `current_run`. Non si confondono. AES riga `febe6804241c` è intatta.

## Cosa non si sposta

- `tools/OpenROAD-flow-scripts/` (checkout ORFS)
- `results/.../gcd/flowlab/` (baseline A)
- Moduli prodotto in `learn/dse/{win_rule,knob_catalog,tune_*,cook,floorplan}.py`
- Piani congelati elencati in [piani.md](piani.md)

## Slot ufficiali (prodotto)

Clock da `DESIGN_CATALOG` in `learn/dse/experiments.py`. Die da DEF ufficiale
(`floorplan.official_box`), non da `CORE_UTILIZATION`.

| id | top | clock | note |
|---|---|---|---|
| `gcd` | `gcd` | 0.46 ns | overlay `gcd-tutorial` |
| `spi` | `spi` | 1.0 ns | tune non ammissibile |
| `ibex` | `ibex_core` | 2.2 ns | Verilog overlay |
| `aes` | `aes_cipher_top` | 0.82 ns | `FLOORPLAN_DEF`; no DIE+DEF |
| `dynamic_node` | `dynamic_node_top_wrap` | 6.0 ns | |

Ordine cheap-first: gcd → spi → ibex → aes → dynamic_node.

## Varianti ORFS

| Nome | Chi la scrive | Locked |
|---|---|---|
| `learn` | corso | sì |
| `flowlab` | Studio / lab GCD A | sì |
| `base` | nome riservato | sì |
| `camp_{design}_base` | P0 prodotto | no (non si pulisce) |
| `camp_{design}_{recipe}` | OFAT | no |
| `camp_{design}_tpe_{12hex}` | TPE | no |

## Risorse VM

~15 GiB / 4 CPU / swap 0. Un job pesante. Wrapper con `prlimit --as`.
TPE è ask → `cook_one` → tell, seriale.
