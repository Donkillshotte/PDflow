# Lesson 03 — Floorplanning

The floorplan is the chip's **building**: walls (die), rooms (core), floor (rows), electrical system (PDN). Logic cells are **not** yet placed: if you look for NAND gates in the GUI, you are in lesson 04.

On the GCD `learn` with `CORE_UTILIZATION=35` the log `2_1_floorplan.log` reports approximately:

| Metric | Typical course value |
|---|---|
| Die from utilization | 35%, aspect 1.0 |
| Core area | **1712.5 µm²** |
| Effective utilization | **0.367** |
| Design area (cells) | ~629 µm² (~37% of core) |
| Snapping origin | `(1.000, 1.000)` → `(1.140, 1.400)` (site grid) |

These numbers are your **yardstick**. If you double utilization, the core must shrink.

## Objectives

- Draw die vs core vs row vs site and explain *snapping*
- Use `CORE_UTILIZATION` knowing it is mutually exclusive with `DIE_AREA`
- Read `grid_strategy-M1-M4-M7.tcl` line by line
- Predict why high utilization kills CTS (bridge to lesson 05)

## Reading

- This README
- `walkthrough-floorplan.tcl.md` **in full**
- LAB 03
- `flow/designs/nangate45/gcd/grid_strategy-M1-M4-M7.tcl`
- Atlas: `gui-atlas.md` §5.2–5.4

## Four methods, only one

ORFS errors if you define two:

1. `FLOORPLAN_DEF` — import an already floorplanned DEF
2. `FOOTPRINT` (ICeWall) — chiplet / pad ring
3. `DIE_AREA` + `CORE_AREA` — explicit micrometers
4. `CORE_UTILIZATION` ← **course**

```tcl
initialize_floorplan -utilization 35 -aspect_ratio 1.0 \
  -core_space 1.0 -site FreePDK45_38x28_10R_NP_162NW_34O
```

**Mental formula:** with the same post-synth cell area,

```
area_core ≈ cell_area / (utilization/100)
```

High utilization = **small** core. Not “more visually full” in GUI at step 2_1: the cells are not there yet. You see fullness at CTS.

The **site** is the tile: library width/height. Snapping IFP-0028 is not a bug: it aligns the core to the grid.

## Sub-stages

| Step | Output | What you learn |
|---|---|---|
| 2_1 | die/core/rows/tracks | empty geometry (`win_floorplan.png`) |
| 2_2 | macro | GCD: no-op (no SRAM) |
| 2_3 | tapcell | well ties (`win_tapcell.png`) |
| 2_4 | PDN | VDD/VSS (`03_pdn_labeled.png`) |

## PDN — the grid you will use forever

Files: `grid_strategy-M1-M4-M7.tcl`

```tcl
set_voltage_domain -name {CORE} -power {VDD} -ground {VSS}
add_pdn_stripe -layer {metal1} -width {0.17} -pitch {2.4} -followpins
add_pdn_stripe -layer {metal4} -width {0.48} -pitch {28.0} -offset {2}
add_pdn_stripe -layer {metal7} -width {1.40} -pitch {15.0} -offset {2}
add_pdn_connect -layers {metal1 metal4}
add_pdn_connect -layers {metal4 metal7}
```

| Piece | Role | What you see in GUI 26Q2 |
|---|---|---|
| `followpins` M1 | rails on rows, touches every cell | tight blue lines |
| strap M4 | intermediate vertical/horizontal distribution | green bars (~3 on the GCD) |
| strap M7 | backbone | thick pink bars |
| `add_pdn_connect` | via stack between layers | visible when zooming crossings |

Without PDN the cells have no legal power. IR drop at finish (`orfs_final_ir_drop.png`, scale ~0–5 mV on the GCD) is blind if the grid does not exist.

`add_global_connection` connects instance `VDD`/`VSS` pins to power nets: that is why you do not hand-wire VDD on every NAND.

## GUI

- `gui_2_1_floorplan.odb`: two rectangles. Do **not** use `gui::set_display_controls "Rows"` → GUI-0013.
- `gui_2_4_floorplan_pdn.odb`: turn off metal2/3, keep M1+strap.

## Required experiment

`CORE_UTILIZATION=25` vs `50`, same `1_synth.odb` (do not rerun synth). Table core area from log `2_1_floorplan.log`.

Prediction: 50% → core ≈ half of 25% (not exact: snapping, margins, aspect).

## Common mistakes

- Util 55% + SDC 0.25 ns → DPL-0038 **later**, not at floorplan (a “green” floorplan misleads you)
- `DIE_AREA` together with `CORE_UTILIZATION` → exit 1 immediate
- PDN “invisible” = layers off
- Comparing core area between runs without `clean_floorplan`

## Power & SPICE chain

The floorplan generates the **PDN grid** (`2_4_floorplan_pdn.odb`); FlowLab verifies with [gridcheck](/flow?phase=pdn). The SPICE netlist is born post-finish — see [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-03-floorplan), [`spice-chip-mesh.md`](../../reference/spice-chip-mesh.md) and the pillar **power** in [`signoff-matrix.md`](../../reference/signoff-matrix.md).

| Link | Where |
|---|---|
| FlowLab | [floorplan](/flow?phase=floorplan) · [PDN](/flow?phase=pdn) |
| Script | `run_gridcheck.sh` |

## Duration

README+walkthrough 50–70 min, LAB 90–120 min, **total ~3 hours**.
