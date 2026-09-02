# Product

Frozen choices live in [`learn/dse/product.md`](../learn/dse/product.md).
This page is the operational version.

## What we optimize

Physical knobs (and ABC area synthesis) on the **official Yosys netlist**.
Project Verilog is not rewritten. **Floorplan is fixed**
(official DEF area, size, and shape).

## Win rule

Same design, same clock, versus the P0 base.

- Timing not worse than 5 ps **and** at least one of area / power / leakage / IR
  better by ≥10%, with none of the four worse by ≥10%.
- Or timing better than 5 ps with none of the four worse by ≥10%.
- Or first to close (WNS≥0) when the base does not, without worsening the four by ≥10%.
- Moved die → `wrong_die` (lab, not a product win).
- Otherwise lose or tie.

Code: [`learn/dse/win_rule.py`](../learn/dse/win_rule.py).

## Cycle

`PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py`

1. **Cover** — catalog holes (human titles). Skips floorplan and `synth_area`.
   Skips inferred walls (today: hierarchical synthesis).
2. **Improve** — only slots with 0 wins.
3. **Tune** — TPE, one finish at a time, same die. Default after cover+improve.
4. **Stop** — catalog covered, improve exhausted, TPE budget spent, or slot
   not admissible (**spi @ 1 ns**).

`--deepen` is an override (2-axis grid). `--cover-all` / `--improve` remain.

## Catalog (titles)

One recipe = one axis, same id on every design.

| id | Title |
|---|---|
| `place_denser` | Denser placement |
| `place_sparser` | Sparser placement |
| `cell_pad_plus` | Cell padding +1 site |
| `repair_setup_margin` | Setup margin on repair |
| `repair_half_tns` | Repair TNS at half |
| `cts_closer_bufs` | Tighter clock buffers |
| `place_sparse_setup` | Sparser placement + setup margin |
| `synth_hier` | Hierarchical synthesis (wall: 0 wins on 5 designs) |
| `core_*` / `aspect_wide` | Lab (`wrong_die`) |

Definitions: [`learn/dse/knob_catalog.py`](../learn/dse/knob_catalog.py).

## Slots

Clock from `DESIGN_CATALOG`. Die from the official DEF (`floorplan.official_box`).

| id | clock | Tune |
|---|---|---|
| gcd | 0.46 ns | yes |
| spi | 1.0 ns | no (closed, 0 wins) |
| ibex | 2.2 ns | yes |
| aes | 0.82 ns | yes (`FLOORPLAN_DEF`, no DIE+DEF) |
| dynamic_node | 6.0 ns | yes |

Cheap-first: gcd → spi → ibex → aes → dynamic_node.

## Tuner

Space: 7 axes (density, pad 0–2, TNS, setup, hold, CTS, timing-driven).
Never util / aspect / die / ABC speed. Optuna only in
[`learn/scripts/run_tpe.py`](../learn/scripts/run_tpe.py).

Warm-start from the same die; then combo deepen; then up to 3 mechanisms
winning on ≥2 designs. Pad=2 is a wall (never finished on gcd and ibex).

Plans: [`tpe_plan.md`](../learn/dse/tpe_plan.md), [`arch_review.md`](../learn/dse/arch_review.md).
