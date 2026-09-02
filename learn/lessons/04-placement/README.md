# Lesson 04 — Placement

Placement is the moment when the design **occupies space**. Before: cells in a pile. After: every gate has a coordinate, and timing starts to depend on wires.

## Objectives

- Distinguish **global placement** vs **detailed placement** without mixing them up
- Understand density, overflow, padding
- Read resizer report as *narrative* (what RSZ did and why)
- Inspect legalization in GUI (gp vs dp)
- Connect placement to CTS failure in lesson 05

## Required reading

1. This README
2. `walkthrough-global_place.tcl.md`
3. `golden-metrics.md` Place / CTS DPL section line by line
4. Atlas §5.5–5.6 (`win_place_gp.png` vs `win_place_dp.png`)
5. `LAB.md` lesson 04

## A reference `learn` run

| Stage | Area / util | Slack |
|---|---|---|
| Post-synth (in core) | ~629 µm² / 37% | (liberty) |
| Post-resizer `3_4` | **684 µm² / 40%** | worst slack **+0.01 ns**, 0 setup viol |
| `period_min` place | **0.45 ns** (~2240 MHz) | still **ideal clock** |
| CTS after (lesson 05) | 828 µm² / **48.3%** | −0.04 ns, clock **propagated** |

Resizer already ate ~55 µm² before CTS. The 45 buffers from lesson 05 start here, not from zero.

## The mathematical problem (intuition)

Global placement minimizes approximately:

```
wirelength + penalty_density + (optional) penalty_timing
```

subject to: cells in the core, not too crowded.

This is not NP-hard that *you* solve by hand: RePlAce (in OpenROAD) iterates. You choose **density target** and **padding**.

## Sub-stages placement ORFS

| Step | What it does | Why it exists |
|---|---|---|
| 3_1_place_gp_skip_io | GP without IO | internal estimate first |
| 3_2_place_iop | I/O placement | pins on the edge |
| 3_3_place_gp | full GP | wirelength + density |
| 3_4_place_resized | RSZ buffer/upsize/clone | timing pre-CTS |
| 3_5_place_dp | Detailed placement | site/row legalization |

The IO → GP order matters: fixed pins **pull** cells toward the edges.

## Global vs detailed — analogy

- **GP:** arrange furniture in the room “roughly” (may overlap a bit in the drawing)
- **DP:** aligns everything to tiles (sites). No overlap. May worsen wirelength a bit.

If in GUI `3_3` and `3_5` look identical, you are viewing the same file.

## Resizer (RSZ) — the real cost of a tight clock

After GP, OpenROAD estimates parasitics from placement and:

- inserts **buffers** on slow / high fanout nets
- **upsize** cells (X1 → X2 → X4) for slew
- **clone** gates to split loads
- swap pins

Every insertion **increases area**. This is the bridge to DPL-0038 in CTS.

Instance prefixes (GUI Find):

| Prefix | Role |
|---|---|
| `rebuffer*` | timing buffer |
| `fanout*` | split fanout |
| `hold*` | fix hold (rarer pre-CTS) |
| `max_cap*` / `max_length*` | capacitance/length constraints |

## Metrics to monitor

| Metric | Where | GCD mental threshold |
|---|---|---|
| Overflow | `3_global_place.rpt` / GP log | → 0 |
| Density | heatmap / log | below 1.0 after DP |
| WNS/TNS | `3_resizer.rpt` | may be negative |
| Buffer count | log `3_4_place_resized` | grows if SDC is tight |
| Instance utilization | DP log | << 100% if you want easy CTS |

## GUI — what to observe

Required sequence (15 min each):

1. `gui_3_2_place_iop.odb` — pins on the die edge
2. `gui_3_3_place_gp.odb` — blob, possible visual overlap
3. `gui_3_4_place_resized.odb` — search for new buffers
4. `gui_3_5_place_dp.odb` — aligned rows

**Placement Density** heatmap: red = full. If all red at util 55% + tight SDC, lesson 05 will fail.

Pixels and PNGs: `learn/reference/gui-atlas.md` §5.5–5.6. Menu: `gui-openroad.md`.

## Controlled experiment

One yardstick per run:

- Only `PLACE_DENSITY_LB_ADDON` 0.10 vs 0.20
- Only SDC relaxed vs default
- Not both

Table in notebook: density addon | overflow | buffer | WNS.

## Power & SPICE chain

Placement fixes **where** each cell feeds the mesh (`ITermNode_*` in `write_pg_spice`). See [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-04-placement).

| Link | Where |
|---|---|
| FlowLab | [place](/flow?phase=place) |
| Mesh (post L07) | `pdn/pg_vdd_bumps.sp` |

## Estimated duration

- README + walkthrough: 45 min
- LAB: 90 min
- GUI comparison: 45 min
- **Total: ~3 hours**
