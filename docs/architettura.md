# Repository architecture

The tree is a **three-surface monorepo**. Do not reorganize ORFS, do not
move modules in `learn/dse/*.py`, and do not merge product and lab.

## Directories

| Path | Surface | Role |
|---|---|---|
| `docs/` | all | Reading index. Does not hold frozen plans. |
| `learn/dse/` | product + lab | Python package. Win = `win_rule.py`. Lab = F4 controller. |
| `learn/scripts/` | product + lab | Cook / TPE / test / IR / signoff entry points |
| `learn/sim/dse/` | product + lab | jsonl registry, memories, campaign SDC |
| `learn/designs/` | product + course | ORFS overlays (gcd-tutorial, spi, aes, ibex, …) |
| `learn/lessons/` | course | 00–07: README + LAB + `run.sh` |
| `learn/reference/` | course + lab | Glossary, Tcl, IR, OSS, lab DSE |
| `learn/workbook/` | course | Exercises and quiz |
| `learn/flowlab/` | course | Tutorial RTL (locked `flowlab` variant) |
| `studio/` | course | Next.js UI. Orchestrates scripts, does not replace them |
| `engine/` | lab | `libdpn` (DirectLU / AMG / RAS / Krylov). Never on AES 50–70k-R |
| `scripts/` | all | Install, product finish, course smoke, cloud |
| `tools/` | infra | ORFS + yosys + OpenSTA. **gitignored**, reproducible |
| `PLAN.md` | lab | Phase 2 controller. Not the product |
| `AGENTS.md` | all | Refuse rules, one job, tests, leftovers |
| `CONTRIBUTING.md` | all | How to contribute |

## Product flow (real finish)

```
run_recipe_loop.py
  → cook.py / cook_recipe.py / run_tpe.py
    → scripts/run_design_finish.sh
      → ORFS make (FLOW_VARIANT=camp_*)
        → 6_report → win_rule.py → campaign_experiments.jsonl
```

Optuna lives **only** in `learn/scripts/run_tpe.py`.
No `if design ==` in tuner, space, score, coordinator, or transfer.

## Lab flow (not wins)

```
run_dse.py / controller
  → F1 synth → F2 place/GRT → F3 STA → F4 IR (engine/)
    → DesignMemory JSONL
```

Gold GCD Dynamic IR **45.298 mV** is `reference_run`. FlowLab finish **6.075 mV**
is `current_run`. Do not confuse them. AES row `febe6804241c` stays intact.

## Do not move

- `tools/OpenROAD-flow-scripts/` (ORFS checkout)
- `results/.../gcd/flowlab/` (baseline A)
- Product modules in `learn/dse/{win_rule,knob_catalog,tune_*,cook,floorplan}.py`
- Frozen plans listed in [piani.md](piani.md)

## Official slots (product)

Clock from `DESIGN_CATALOG` in `learn/dse/experiments.py`. Die from the official DEF
(`floorplan.official_box`), not from `CORE_UTILIZATION`.

| id | top | clock | note |
|---|---|---|---|
| `gcd` | `gcd` | 0.46 ns | `gcd-tutorial` overlay |
| `spi` | `spi` | 1.0 ns | tune not admissible |
| `ibex` | `ibex_core` | 2.2 ns | Verilog overlay |
| `aes` | `aes_cipher_top` | 0.82 ns | `FLOORPLAN_DEF`; no DIE+DEF |
| `dynamic_node` | `dynamic_node_top_wrap` | 6.0 ns | |

Cheap-first order: gcd → spi → ibex → aes → dynamic_node.

## ORFS variants

| Name | Writer | Locked |
|---|---|---|
| `learn` | course | yes |
| `flowlab` | Studio / lab GCD A | yes |
| `base` | reserved name | yes |
| `camp_{design}_base` | product P0 | no (do not delete) |
| `camp_{design}_{recipe}` | OFAT | no |
| `camp_{design}_tpe_{12hex}` | TPE | no |

## VM resources

~15 GiB / 4 CPU / swap 0. One heavy job. Wrapper with `prlimit --as`.
TPE is ask → `cook_one` → tell, serial.
