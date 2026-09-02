# Physical Design Glossary — OpenROAD / ORFS

Alphabetical reference. Return here during every lesson.

---

## A

**ABC** — Synthesis/logic optimization tool used internally by Yosys.

**Area (core)** — Rectangular area where standard cells are placed.

**Artifact** — File produced by a stage (`.odb`, `.def`, `.gds`, `.v`, `.sdc`, `.spef`).

---

## C

**Cell** — Instance of a library master cell (e.g. `AND2_X1`, `DFF_X1`).

**Clock domain** — Set of registers clocked by the same clock.

**Congestion** — Too much routing demand in a chip region.

**Constraints (SDC)** — Timing rules: clock, I/O delay, false path, multicycle.

**Core utilization** — Percentage of die occupied by logic core (floorplan knob).

**CTS (Clock Tree Synthesis)** — Build balanced clock tree toward all FFs.

---

## D

**DEF (Design Exchange Format)** — Text description of placement + routing + components.

**Detailed placement (DP)** — Legalization: every cell on a valid site, no overlap.

**Detailed routing (DRT)** — Final routing respecting width/spacing/via rules.

**DRC (Design Rule Check)** — Geometric verification (spacing, width, enclosure).

**DFF / Flip-flop** — Synchronous memory element; typical timing path endpoint.

**DPL-0038** — Detailed placement: utilization > 100% (cell area > core area). Legal failure, not “slightly negative timing”. LAB 05 part 4. This is not **RSZ-0062**.

---

## F

**False path** — Path STA must ignore (not temporally critical).

**Floorplan** — Definition of die, core, rows, power grid, IO pins.

**Flow variant** — ORFS results subdirectory (`base`, `learn`, …).

---

## G

**GUI** — OpenROAD Qt interface. This is not Preview HTTP. Atlas: `gui-atlas.md`.

**GUI-0013** — Nonexistent Display Control. In 26Q2 `gui::set_display_controls "Rows"` fails: no control named `Rows`.

**gcell** — Grid cell for **global routing**: capacity unit (how many wires fit in a region). Heatmap congestion = demand vs capacity per gcell. PNG `orfs_final_congestion.png`.

**Guide (GRT)** — 2D corridors per net, not wire mask-ready. Files `route.guide`.

**Global placement (GP)** — Approximate placement minimizing wirelength + density.

**Global routing (GRT)** — Routing guide assignment per region; not final wires.

**Gate-level netlist** — Verilog with library cells (post-synthesis).

---

## H

**Hold time** — Minimum time data must remain stable after clock edge.

**Heatmap (GUI)** — Color visualization of density, congestion, IR drop.

---

## I

**IFP-0028** — Init Floorplan message: origin/core **snapped** to site grid. This is not an error; aligns rectangle to LEF tiles. In log `2_1_floorplan.log` see `(1.000, 1.000)` → `(1.140, 1.400)` or similar.

**IO delay** — Timing budget between external pad/pin and registers.

**IR drop** — Voltage drop on power grid (finish stage).

**ideal clock** — STA pretends network latency = 0 (pre-CTS). After CTS the clock is **propagated** (delay of `CLKBUF*`).

---

## L

**LEF (Library Exchange Format)** — Physical geometry of tech + cells (layers, pins, sites).

**LIB (Liberty)** — Timing/power model of the cells (.lib).

**Legalization** — Move cells to valid sites without violating row alignment.

---

## M

**Master cell** — Cell definition in LEF (template).

**Multicycle path** — Path that can use multiple clock cycles.

---

## N

**NDR (Non-Default Rule)** — Routing rule wider/more spacing than default tech. On GCD post-CTS/route net `clk` in Inspector shows `CTS_NDR_0`: the clock is no longer one generic wire.

**ngspice** — Open-source SPICE simulator for System PDN in Studio (AC + TRAN). See [spice-ngspice-primer.md](./spice-ngspice-primer.md).

---

## O

**ODB (OpenDB)** — OpenROAD binary database; snapshot of every stage.

**OpenRCX** — OpenROAD parasitic extractor (`extract_parasitics` + `RCX_RULES`). Produces SPEF at finish. Without RCX, ORFS falls back to `estimate_parasitics -global_routing`.

**OpenSTA** — Static Timing Analyzer (part of OpenROAD and standalone).

---

## P

**PDK (Process Design Kit)** — Tech package: LEF, LIB, rules (Nangate45, sky130, …).

**PDN (Power Distribution Network)** — VDD/VSS mesh/straps in core. In Studio: gridcheck (L03) + post-finish mesh SPICE ([spice-chip-mesh.md](./spice-chip-mesh.md)).

**PDNSim** — OpenROAD `analyze_power_grid`: on-die static IR; exports `write_pg_spice`.

**Power chain** — Studio sequence: `activity_power` → `chip_pdn_ir` → `system_pdn` → export (`run_power_chain.sh`). Guide: [spice-power-chain.md](./spice-power-chain.md).

**period_min** — Minimum period (ns) for which STA, with *that* RC model, sees no negative WNS. fmax ≈ `1000 / period_min` MHz. At finish on the gold run is **0.50 ns** (~2011 MHz) vs SDC **0.46 ns** (~2174 MHz): target not closed.

**Placement** — Assign position (x,y) to every cell.

**Parasitics (SPEF)** — R/C extracted from layout for post-route STA.

---

## R

**Resizer (RSZ)** — OpenROAD tool that inserts buffers, upsizes, clones for timing.

**RSZ-0062** — Warning: resizer **did not** repair all setup. On GCD `learn` appears at CTS (`Inserted 45`) and the flow **continues**. This is not area overflow: that is **DPL-0038**.

**RTL** — Register Transfer Level; behavioral Verilog pre-synthesis.

**Row** — Row of sites where standard cells align.

---

## S

**SDC** — Synopsys Design Constraints (`.sdc` file).

**Setup time** — Required time for stable data before clock edge.

**SPICE** — Circuit simulation. In Studio: (1) chip resistive mesh from `write_pg_spice`; (2) System PDN ladder with **ngspice**.

**System PDN** — VRM → board → package → die chain (ngspice). Distinct from on-die chip PDN. FlowLab PKG phase.

**Site** — Minimum physical slot for a cell (e.g. `FreePDK45_38x28_...`).

**Skew** — Difference in clock arrival between different sinks.

**SPEF** — Standard Parasitic Exchange Format.

**STA** — Static Timing Analysis: verify setup/hold without simulation.

**STA-2204** — Typical error if ORFS **master** (26Q3) runs on OpenROAD **26Q2** (`get_property default` in save_images). The repo pins ORFS tag **26Q2**.

**Synthesis** — RTL → gate-level netlist mapped to library.

---

## T

**Tapcell** — Cells for well tie/substrate connection.

**Timing closure** — Achieve WNS ≥ 0 and TNS ≈ 0 on all corners.

**TNS (Total Negative Slack)** — Sum of all setup violations.

**Top module** — Verilog hierarchy root (`gcd` in our course).

---

## E

**EMSim** — Academic EM emission framework ([jinyier/EMSim](https://github.com/jinyier/EMSim), TIFS 2023). The *current analysis* step (PT-PX → PWL → HSpice) is the A/B split to copy. Prerequisites: VCS, Calibre xRC, PrimeTime PX, HSpice — not drop-in OSS.

## V

**vyges-em-ir** — Apache-2.0 engine ([vyges-tools/em-ir](https://github.com/vyges-tools/em-ir)): static IR CG + backward-Euler transient on a `.pdn`. Integrated on GCD via `run_vyges_em_ir.sh`. Bootstrap and simultaneous-switch check — **not** the platform core.

**Dynamic IR (I(t))** — Course engine (`pdn_dynamic.py`): I(t) per pin + **Solver A** (LU gold) + **Solver B** (SA-AMG) + scenario ranking on same A. This is not CCS nor VCD pin-accurate.

---

## W

**WNS (Worst Negative Slack)** — Worst setup violation (most critical).

**Wirelength** — Total interconnection length (placement/routing objective).

**write_pg_spice** — OpenROAD PDNSim export: R network + I currents per cell pin → input to `pdn_transient.py`, `spice_to_pdn.py` (vyges-em-ir) and `pdn_dynamic.py`.

---

## ORFS flow acronyms

```
RTL → yosys → 1_synth.odb
     → floorplan → 2_floorplan.odb
     → place → 3_place.odb
     → cts → 4_cts.odb
     → route → 5_route.odb
     → finish → 6_final.gds
```

---

## Questions to ask at every stage

| Stage | Question |
|---|---|
| Synth | How many cells? Any latches? |
| Floorplan | Core large enough for utilization target? |
| Place | Zero overflow? How many buffers did RSZ add? |
| CTS | Acceptable skew? Post-CTS area < 100%? |
| Route | DRC clean? Residual congestion? |
| Finish | WNS/TNS post-SPEF? `period_min` vs SDC? GDS opens in KLayout? |
